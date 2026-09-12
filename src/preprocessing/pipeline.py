"""Construção do pré-processamento INTEGRADO ao modelo (scikit-learn Pipeline).

Requisito do edital: "Integração do pré-processamento diretamente ao modelo".
Aqui isso não é um detalhe de estilo — é a garantia mecânica contra vazamento.
Imputação, escalonamento e encoding são ESTIMADORES, com parâmetros aprendidos.
Se fossem aplicados ao dataframe inteiro antes do split, a mediana de imputação e
as médias do target encoding teriam visto o conjunto de teste. Dentro de um
``Pipeline``, cada `fit` acontece apenas sobre a dobra de treino — e o mesmo vale
dentro de cada dobra da validação cruzada.

Três famílias de tratamento, escolhidas pelo tipo da coluna:

1. **Numéricas** — `SimpleImputer(strategy="median", add_indicator=True)`.
   A mediana resiste à assimetria das variáveis socioeconômicas (PIB per capita,
   população) muito melhor que a média. O `add_indicator` cria uma coluna binária
   "estava faltando": essencial aqui, porque ausência de histórico municipal NÃO
   é aleatória — marca municípios que entraram na avaliação em 2024, um grupo com
   perfil próprio. Ver docs/decisoes-analiticas.md §4.
2. **Categóricas de baixa cardinalidade** — `OneHotEncoder`, com
   `handle_unknown="infrequent_if_exist"` para que categorias vistas só no teste
   caiam no balde "infrequente" em vez de quebrar a predição.
3. **Categóricas de alta cardinalidade** — `TargetEncoder`. O `fit_transform` do
   scikit-learn faz o encoding fora-da-dobra por validação cruzada interna, o que
   neutraliza o vazamento clássico da técnica.

O escalonamento é condicional: modelos lineares precisam (`escalonar=True`),
modelos de árvore são invariantes a transformações monotônicas e dispensam.
"""
from __future__ import annotations

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler, TargetEncoder

from .features import CATEGORICAS_ALTA_CARDINALIDADE

LIMITE_CARDINALIDADE = 15


def classificar_colunas(
    X: pd.DataFrame,
    limite_cardinalidade: int = LIMITE_CARDINALIDADE,
) -> dict[str, list[str]]:
    """Separa as colunas em numéricas, categóricas de baixa e de alta cardinalidade.

    Booleanas são tratadas como numéricas (0/1): já são a sua própria codificação.
    Uma categórica é "de alta cardinalidade" se estiver na lista declarada em
    ``features.py`` ou se ultrapassar ``limite_cardinalidade`` níveis distintos.
    """
    numericas, cat_baixa, cat_alta = [], [], []
    for col in X.columns:
        serie = X[col]
        if pd.api.types.is_bool_dtype(serie) or pd.api.types.is_numeric_dtype(serie):
            numericas.append(col)
        elif col in CATEGORICAS_ALTA_CARDINALIDADE or serie.nunique(dropna=True) > limite_cardinalidade:
            cat_alta.append(col)
        else:
            cat_baixa.append(col)
    return {"numericas": numericas, "cat_baixa": cat_baixa, "cat_alta": cat_alta}


def construir_preprocessador(
    X: pd.DataFrame,
    escalonar: bool = False,
    random_state: int = 42,
) -> ColumnTransformer:
    """Monta o ``ColumnTransformer`` a partir dos tipos observados em ``X``.

    ``escalonar=True`` acrescenta `StandardScaler` ao ramo numérico — necessário
    para regressão logística, dispensável para modelos baseados em árvores.
    """
    grupos = classificar_colunas(X)

    passos_num: list = [("imputar", SimpleImputer(strategy="median", add_indicator=True))]
    if escalonar:
        passos_num.append(("escalonar", StandardScaler()))
    ramo_numerico = Pipeline(passos_num)

    ramo_cat_baixa = Pipeline([
        ("imputar", SimpleImputer(strategy="most_frequent")),
        ("codificar", OneHotEncoder(
            handle_unknown="infrequent_if_exist",
            min_frequency=0.01,        # categorias com <1% viram "infrequente"
            sparse_output=False,
        )),
    ])

    ramo_cat_alta = Pipeline([
        ("imputar", SimpleImputer(strategy="constant", fill_value="__ausente__")),
        ("codificar", TargetEncoder(
            target_type="binary",
            cv=5,                       # encoding fora-da-dobra: antivazamento
            smooth="auto",              # encolhe categorias raras para a média global
            random_state=random_state,
        )),
    ])

    transformadores = []
    if grupos["numericas"]:
        transformadores.append(("num", ramo_numerico, grupos["numericas"]))
    if grupos["cat_baixa"]:
        transformadores.append(("cat", ramo_cat_baixa, grupos["cat_baixa"]))
    if grupos["cat_alta"]:
        transformadores.append(("alvo", ramo_cat_alta, grupos["cat_alta"]))

    return ColumnTransformer(
        transformadores,
        remainder="drop",
        verbose_feature_names_out=False,
    ).set_output(transform="pandas")


def montar_modelo(
    X: pd.DataFrame,
    estimador,
    escalonar: bool = False,
    random_state: int = 42,
) -> Pipeline:
    """Pipeline completa: pré-processamento + estimador, em um único objeto.

    O objeto retornado é o que se treina, valida, serializa e coloca em produção —
    nunca um dataframe já transformado à parte. É essa unidade que garante que a
    mesma transformação aprendida no treino seja aplicada, idêntica, na inferência.
    """
    return Pipeline([
        ("preproc", construir_preprocessador(X, escalonar=escalonar,
                                             random_state=random_state)),
        ("modelo", estimador),
    ])


def resumo_preprocessamento(X: pd.DataFrame) -> pd.DataFrame:
    """Tabela legível de como cada coluna será tratada (para o relatório)."""
    grupos = classificar_colunas(X)
    tratamento = {
        **{c: "numérica — imputação por mediana (+ indicador de ausência)"
           for c in grupos["numericas"]},
        **{c: "categórica — one-hot (categorias <1% agrupadas)"
           for c in grupos["cat_baixa"]},
        **{c: "categórica de alta cardinalidade — target encoding fora-da-dobra"
           for c in grupos["cat_alta"]},
    }
    return pd.DataFrame({
        "coluna": list(X.columns),
        "tipo": [str(X[c].dtype) for c in X.columns],
        "n_distintos": [int(X[c].nunique(dropna=True)) for c in X.columns],
        "pct_ausente": [round(float(X[c].isna().mean()) * 100, 2) for c in X.columns],
        "tratamento": [tratamento.get(c, "-") for c in X.columns],
    })
