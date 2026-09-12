"""Executa a análise de interpretabilidade do modelo escolhido.

Produz importância nativa, importância por permutação, valores SHAP e ablação por
bloco — quatro leituras complementares — e escreve `reports/interpretabilidade.md`.

Uso:
    ./venv/bin/python -m src.evaluation.executar_interpretacao
    ./venv/bin/python -m src.evaluation.executar_interpretacao --desenho espacial
"""
from __future__ import annotations

import argparse
import sys

import joblib
import pandas as pd

from ..common.config import MODELS_DIR, RANDOM_STATE, REPORTS_DIR
from ..common.log import get_logger
from ..modeling.dataset import carregar_abt
from ..modeling.train import DESENHOS, amostrar
from ..preprocessing.features import ALVO, descartar_degeneradas, selecionar_features
from ..visualization import plots
from . import interpret

logger = get_logger("evaluation.executar_interpretacao")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Interpretabilidade do modelo.")
    parser.add_argument("--desenho", default="temporal", choices=sorted(DESENHOS))
    parser.add_argument("--amostra-ablacao", type=int, default=400_000,
                        help="subamostra para a ablação (são ~11 reajustes do modelo)")
    args = parser.parse_args(argv)

    caminho_modelo = MODELS_DIR / f"modelo_{args.desenho}.joblib"
    if not caminho_modelo.exists():
        logger.error("Modelo não encontrado: %s. Rode `make modelo-a` antes.",
                     caminho_modelo)
        return 1

    split, permitir_defasadas = DESENHOS[args.desenho]
    df = carregar_abt()
    if args.desenho == "espacial":
        df = df[df["ano"] == 2024].copy()
    colunas = list(df.columns)
    treino, teste = split(df)
    del df

    features = selecionar_features(colunas, permitir_defasadas=permitir_defasadas)
    features, _ = descartar_degeneradas(treino, features)

    pipeline = joblib.load(caminho_modelo)
    nome_modelo = type(pipeline.named_steps["modelo"]).__name__
    logger.info("Modelo carregado: %s (%d features)", nome_modelo, len(features))

    figuras: dict[str, str] = {}

    # --- 1. Importância nativa ----------------------------------------------
    logger.info("1/4 importância nativa")
    nativa = interpret.importancia_nativa(pipeline)
    nativa.to_csv(REPORTS_DIR / f"importancia_nativa_{args.desenho}.csv", index=False)
    figuras["nativa"] = plots.fig_importancia(
        nativa, "importancia",
        "Importância nativa (ganho na construção das árvores)",
        "enviesada a favor de variáveis contínuas e de alta cardinalidade — "
        "leia como triagem, não como conclusão",
        f"12a_importancia_nativa_{args.desenho}")

    # --- 2. Importância por permutação --------------------------------------
    logger.info("2/4 importância por permutação (no conjunto de teste)")
    permut = interpret.importancia_permutacao(
        pipeline, teste[features], teste[ALVO].astype(int).to_numpy())
    permut.to_csv(REPORTS_DIR / f"importancia_permutacao_{args.desenho}.csv", index=False)
    figuras["permutacao"] = plots.fig_importancia(
        permut, "queda_auc",
        "Importância por permutação (queda de AUC no teste)",
        "mede contribuição para a GENERALIZAÇÃO; subestima variáveis "
        "correlacionadas entre si",
        f"12b_importancia_permutacao_{args.desenho}")

    # --- 3. SHAP -------------------------------------------------------------
    logger.info("3/4 valores SHAP")
    try:
        valores, X_t, esperado = interpret.valores_shap(pipeline, teste[features])
        figuras["shap"] = plots.fig_shap_resumo(valores, X_t,
                                                f"14_shap_{args.desenho}")
        shap_medio = (pd.DataFrame({"feature": X_t.columns,
                                    "shap_medio_abs": abs(valores).mean(axis=0)})
                        .sort_values("shap_medio_abs", ascending=False))
        shap_medio.to_csv(REPORTS_DIR / f"shap_medio_{args.desenho}.csv", index=False)
    except Exception as exc:                       # modelo linear não tem TreeExplainer
        logger.warning("SHAP indisponível para %s: %s", nome_modelo, exc)
        shap_medio = pd.DataFrame()

    # --- 4. Ablação por bloco ------------------------------------------------
    logger.info("4/4 ablação por bloco")
    from ..modeling import candidatos as cat
    nome_candidato = {"LGBMClassifier": "lightgbm", "XGBClassifier": "xgboost",
                      "HistGradientBoostingClassifier": "hist_gb",
                      "LogisticRegression": "logistica"}.get(nome_modelo, "lightgbm")
    estimador, escalonar, _ = cat.obter(nome_candidato)
    ablacao = interpret.ablacao_por_bloco(
        amostrar(treino, args.amostra_ablacao), teste, features,
        estimador, escalonar=escalonar, random_state=RANDOM_STATE)
    ablacao.to_csv(REPORTS_DIR / f"ablacao_{args.desenho}.csv", index=False)
    figuras["ablacao"] = plots.fig_ablacao(ablacao)

    # --- Relatório -----------------------------------------------------------
    def tabela(df: pd.DataFrame, cols: list[str], n: int = 15) -> list[str]:
        linhas = ["| " + " | ".join(cols) + " |",
                  "|" + "|".join(["---"] * len(cols)) + "|"]
        for _, r in df.head(n).iterrows():
            linhas.append("| " + " | ".join(
                f"`{r[c]}`" if c == "feature" else
                (f"{r[c]:.5f}".replace(".", ",") if isinstance(r[c], float) else str(r[c]))
                for c in cols) + " |")
        return linhas

    md = [
        f"# Interpretabilidade — desenho `{args.desenho}`",
        "",
        f"Modelo: **{nome_modelo}** · {len(features)} features.",
        "",
        "Quatro leituras, propositalmente diferentes. Quando elas discordam, a "
        "discordância é informação: importância nativa alta com permutação baixa "
        "indica variável que o modelo usou para ajustar ruído.",
        "",
        "## 1. Importância nativa (ganho)",
        "",
        *tabela(nativa, ["feature", "bloco", "importancia"]),
        "",
        f"![nativa](../images/{figuras['nativa'].split('/')[-1]})",
        "",
        "## 2. Importância por permutação (queda de AUC no teste)",
        "",
        "A medida honesta: quanto a generalização piora ao embaralhar a coluna.",
        "",
        *tabela(permut, ["feature", "bloco", "queda_auc", "desvio"]),
        "",
        f"![permutação](../images/{figuras['permutacao'].split('/')[-1]})",
        "",
    ]
    if not shap_medio.empty:
        md += [
            "## 3. SHAP",
            "",
            "Decomposição aditiva de cada predição individual.",
            "",
            *tabela(shap_medio, ["feature", "shap_medio_abs"]),
            "",
            f"![shap](../images/{figuras['shap'].split('/')[-1]})",
            "",
        ]
    md += [
        "## 4. Ablação por bloco",
        "",
        "Remove um bloco temático inteiro e mede a perda. É a leitura que sobrevive "
        "à multicolinearidade.",
        "",
        *tabela(ablacao, ["bloco", "n_features", "roc_auc", "queda_auc"], n=20),
        "",
        f"![ablação](../images/{figuras['ablacao'].split('/')[-1]})",
        "",
    ]
    destino = REPORTS_DIR / f"interpretabilidade_{args.desenho}.md"
    destino.write_text("\n".join(md), encoding="utf-8")
    logger.info("Relatório salvo em %s", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
