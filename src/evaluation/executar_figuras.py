"""Regenera as figuras de avaliação a partir dos artefatos já salvos.

Curvas ROC / precisão-revocação / calibração e o painel por estrato territorial são
deriváveis das probabilidades previstas — que `src.modeling.train` persiste em
`reports/probabilidades_<desenho>.npy`. Este módulo existe para redesenhar os
gráficos sem repetir o treino, que leva minutos.

Uso:
    ./venv/bin/python -m src.evaluation.executar_figuras --desenho temporal
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from ..common.config import REPORTS_DIR
from ..common.log import get_logger
from ..modeling.dataset import carregar_abt
from ..modeling.train import DESENHOS
from ..preprocessing.features import ALVO
from ..visualization import plots
from .metrics import avaliar_por_estrato, estratos_de_cobertura

logger = get_logger("evaluation.executar_figuras")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Regenera as figuras de avaliação sem retreinar."
    )
    parser.add_argument("--desenho", default="temporal", choices=sorted(DESENHOS))
    args = parser.parse_args(argv)

    caminho_probs = REPORTS_DIR / f"probabilidades_{args.desenho}.npy"
    caminho_metricas = REPORTS_DIR / f"metricas_{args.desenho}.csv"
    if not caminho_probs.exists() or not caminho_metricas.exists():
        logger.error("Artefatos ausentes — rode `make modelo-%s` antes.",
                     "a" if args.desenho == "temporal" else "b")
        return 1

    # As colunas do .npy seguem a ordem do índice do quadro de métricas.
    quadro = pd.read_csv(caminho_metricas, index_col=0)
    probabilidades = np.load(caminho_probs)
    nomes = list(quadro.index)
    if probabilidades.shape[1] != len(nomes):
        logger.error("Incompatibilidade: %d colunas de probabilidade para %d modelos",
                     probabilidades.shape[1], len(nomes))
        return 1

    split, _ = DESENHOS[args.desenho]
    df = carregar_abt()
    if args.desenho == "espacial":
        df = df[df["ano"] == 2024].copy()
    treino, teste = split(df)
    del df

    if len(teste) != len(probabilidades):
        logger.error("Conjunto de teste com %d linhas, mas %d probabilidades salvas",
                     len(teste), len(probabilidades))
        return 1

    y = teste[ALVO].astype(int).to_numpy()
    por_modelo = {nome: probabilidades[:, i] for i, nome in enumerate(nomes)}

    caminho_curvas = plots.fig_curvas(
        y, {n: p for n, p in por_modelo.items() if n != "referencia"}, args.desenho)

    estratos = estratos_de_cobertura(treino, teste)
    por_estrato = avaliar_por_estrato(y, por_modelo[nomes[0]], estratos)
    por_estrato.to_csv(REPORTS_DIR / f"metricas_{args.desenho}_por_estrato.csv")
    caminho_estratos = plots.fig_metricas_por_estrato(por_estrato, args.desenho)

    print(f"\nMelhor modelo ('{nomes[0]}') por estrato de cobertura territorial:")
    print(por_estrato.round(4).to_string())
    logger.info("Figuras: %s | %s",
                caminho_curvas.split("/")[-1], caminho_estratos.split("/")[-1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
