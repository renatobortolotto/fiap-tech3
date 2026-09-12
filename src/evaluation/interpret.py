"""Interpretabilidade: importância de features, SHAP e efeitos marginais.

O edital pede explicitamente Feature Importance e SHAP Values. As três técnicas
aqui respondem a perguntas diferentes, e usar só uma delas engana:

* **Importância por ganho** (nativa das árvores) — quanto cada variável reduziu a
  impureza durante o treino. É rápida, mas ENVIESADA a favor de variáveis contínuas
  e de alta cardinalidade, que oferecem mais pontos de corte. Serve de triagem, não
  de conclusão.
* **Importância por permutação** — quanto a métrica PIORA ao embaralhar a coluna no
  conjunto de TESTE. Mede contribuição para a generalização, não para o ajuste, e é
  a medida honesta de "esta variável está puxando o resultado?". Com variáveis
  correlacionadas (e aqui elas são muito correlacionadas — IVS, renda e IDHM medem
  quase a mesma coisa) ela SUBESTIMA cada uma individualmente, porque o modelo se
  apoia nas gêmeas sobreviventes. Por isso é reportada junto da análise por bloco.
* **SHAP** — decompõe cada predição individual na contribuição aditiva de cada
  variável. É o único dos três que responde "por que ESTE aluno foi classificado
  como em risco?", que é a pergunta do gestor diante de uma lista de prioridades.

A análise por BLOCO (ablação) complementa as três: remove um bloco temático inteiro
e mede a perda de AUC. É imune ao problema da correlação entre variáveis gêmeas,
porque as gêmeas saem juntas.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.inspection import permutation_importance
from sklearn.metrics import roc_auc_score

from ..common.config import RANDOM_STATE
from ..common.log import get_logger
from ..preprocessing.features import ALVO, bloco_de, selecionar_features
from ..preprocessing.pipeline import montar_modelo

logger = get_logger("evaluation.interpret")


def importancia_nativa(pipeline, top: int | None = None) -> pd.DataFrame:
    """Importância por ganho do estimador final, com nomes já pós-transformação."""
    modelo = pipeline.named_steps["modelo"]
    nomes = list(pipeline.named_steps["preproc"].get_feature_names_out())
    if hasattr(modelo, "feature_importances_"):
        valores = modelo.feature_importances_
        medida = "ganho"
    elif hasattr(modelo, "coef_"):
        valores = np.abs(modelo.coef_.ravel())
        medida = "|coeficiente|"
    else:
        raise TypeError(f"{type(modelo).__name__} não expõe importância de features")
    df = (pd.DataFrame({"feature": nomes, "importancia": valores, "medida": medida})
            .assign(bloco=lambda d: d["feature"].map(bloco_de))
            .sort_values("importancia", ascending=False)
            .reset_index(drop=True))
    return df.head(top) if top else df


def importancia_permutacao(
    pipeline,
    X_teste: pd.DataFrame,
    y_teste,
    n_repeticoes: int = 5,
    max_amostra: int = 150_000,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Queda de ROC AUC ao embaralhar cada coluna do conjunto de teste.

    Subamostra o teste: com 1,85 milhão de linhas e ~120 colunas, uma passada
    completa exigiria ~600 reajustes de predição sobre a base inteira. Em 150 mil
    linhas o erro-padrão da AUC já é da ordem de 0,001 — muito menor que as
    diferenças que se quer ordenar.
    """
    rng = np.random.default_rng(random_state)
    if len(X_teste) > max_amostra:
        idx = rng.choice(len(X_teste), max_amostra, replace=False)
        X_teste, y_teste = X_teste.iloc[idx], np.asarray(y_teste)[idx]
    logger.info("Permutação sobre %d linhas x %d colunas (%d repetições)",
                len(X_teste), X_teste.shape[1], n_repeticoes)
    resultado = permutation_importance(
        pipeline, X_teste, y_teste,
        scoring="roc_auc", n_repeats=n_repeticoes,
        random_state=random_state, n_jobs=1,
    )
    return (pd.DataFrame({
                "feature": X_teste.columns,
                "queda_auc": resultado.importances_mean,
                "desvio": resultado.importances_std,
            })
            .assign(bloco=lambda d: d["feature"].map(bloco_de))
            .sort_values("queda_auc", ascending=False)
            .reset_index(drop=True))


def valores_shap(
    pipeline,
    X: pd.DataFrame,
    max_amostra: int = 30_000,
    random_state: int = RANDOM_STATE,
):
    """Valores SHAP do modelo de árvore, no espaço JÁ TRANSFORMADO.

    Aplicar o `TreeExplainer` ao espaço transformado é o que permite ler a
    contribuição de cada coluna que o modelo realmente viu — inclusive as colunas
    criadas pelo pré-processamento, como os indicadores de ausência, cuja
    importância é em si um achado (o modelo aprende que "sem histórico" informa).

    Devolve (valores_shap, X_transformado, valor_esperado).
    """
    import shap

    rng = np.random.default_rng(random_state)
    if len(X) > max_amostra:
        X = X.iloc[rng.choice(len(X), max_amostra, replace=False)]
    X_t = pipeline.named_steps["preproc"].transform(X)
    modelo = pipeline.named_steps["modelo"]

    explicador = shap.TreeExplainer(modelo)
    valores = explicador.shap_values(X_t)
    if isinstance(valores, list):            # alguns modelos devolvem por classe
        valores = valores[1]
    elif valores.ndim == 3:
        valores = valores[:, :, 1]
    esperado = explicador.expected_value
    if isinstance(esperado, (list, np.ndarray)):
        esperado = np.ravel(esperado)[-1]
    return valores, X_t, float(esperado)


def ablacao_por_bloco(
    treino: pd.DataFrame,
    teste: pd.DataFrame,
    features: list[str],
    estimador,
    escalonar: bool = False,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Perda de ROC AUC ao remover cada bloco temático inteiro.

    É a leitura que sobrevive à multicolinearidade: variáveis que medem a mesma
    coisa saem juntas, então a queda observada é a contribuição real e não
    redundante daquele bloco de informação.
    """
    prefixos = {
        "aluno": ("alu_",),
        "escola (histórico)": ("esc_lag_",),
        "escola (infraestrutura)": ("inf_",),
        "escola (socioeconômico)": ("inse_",),
        "educacional": ("edu_",),
        "município (educacional)": ("mun_",),
        "município (socioeconômico)": ("ses_",),
        "município (financiamento)": ("fin_",),
        "território": ("ter_",),
        "UF": ("uf_",),
        "identificação geográfica": ("id_municipio", "sigla_uf"),
    }
    X_tr, y_tr = treino[features], treino[ALVO].astype(int)
    X_te, y_te = teste[features], teste[ALVO].astype(int)

    base = montar_modelo(X_tr, clone(estimador), escalonar=escalonar,
                         random_state=random_state).fit(X_tr, y_tr)
    auc_completo = roc_auc_score(y_te, base.predict_proba(X_te)[:, 1])
    logger.info("AUC com todas as %d features: %.4f", len(features), auc_completo)

    linhas = [{"bloco": "(modelo completo)", "n_features": len(features),
               "roc_auc": auc_completo, "queda_auc": 0.0}]
    for bloco, pref in prefixos.items():
        restantes = [f for f in features if not f.startswith(pref)]
        removidas = len(features) - len(restantes)
        if removidas == 0 or not restantes:
            continue
        pipe = montar_modelo(treino[restantes], clone(estimador),
                             escalonar=escalonar, random_state=random_state)
        pipe.fit(treino[restantes], y_tr)
        auc = roc_auc_score(y_te, pipe.predict_proba(teste[restantes])[:, 1])
        linhas.append({"bloco": f"sem {bloco}", "n_features": len(restantes),
                       "roc_auc": auc, "queda_auc": auc_completo - auc})
        logger.info("sem %-28s AUC=%.4f (queda %+.4f, -%d features)",
                    bloco, auc, auc_completo - auc, removidas)
    return (pd.DataFrame(linhas)
              .sort_values("queda_auc", ascending=False)
              .reset_index(drop=True))
