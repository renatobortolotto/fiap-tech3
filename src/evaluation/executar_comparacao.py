"""Comparação estatística entre os modelos, por bootstrap pareado.

Responde à pergunta que a tabela de métricas não responde: **a diferença entre dois
modelos excede a incerteza amostral?** Comparar dois intervalos de confiança
independentes é um teste fraco; o bootstrap PAREADO usa as mesmas reamostragens nos
dois modelos, elimina a variância comum e detecta diferenças muito menores.

Uso:
    ./venv/bin/python -m src.evaluation.executar_comparacao --desenho temporal
"""
from __future__ import annotations

import argparse
import sys

import numpy as np
import pandas as pd

from ..common.config import REPORTS_DIR
from ..common.log import get_logger
from ..modeling.dataset import CAMINHO_ABT
from ..modeling.train import DESENHOS
from ..preprocessing.features import ALVO
from .metrics import comparar_bootstrap, ic_bootstrap

logger = get_logger("evaluation.executar_comparacao")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap pareado entre os modelos de um desenho."
    )
    parser.add_argument("--desenho", default="temporal", choices=sorted(DESENHOS))
    parser.add_argument("--reamostras", type=int, default=300)
    args = parser.parse_args(argv)

    quadro = pd.read_csv(REPORTS_DIR / f"metricas_{args.desenho}.csv", index_col=0)
    probs = np.load(REPORTS_DIR / f"probabilidades_{args.desenho}.npy")
    nomes = list(quadro.index)

    # Só as colunas necessárias: carregar a ABT inteira aqui seria desperdício.
    df = pd.read_parquet(CAMINHO_ABT, columns=["ano", ALVO])
    if args.desenho == "temporal":
        y = df.loc[df["ano"] == 2024, ALVO].astype(int).to_numpy()
    else:
        # O desenho espacial particiona por município: é preciso refazer o split.
        from .executar_figuras import DESENHOS as _D  # mesma fonte de verdade
        from ..modeling.dataset import carregar_abt
        completo = carregar_abt()
        completo = completo[completo["ano"] == 2024]
        _, teste = _D[args.desenho][0](completo)
        y = teste[ALVO].astype(int).to_numpy()
    if len(y) != len(probs):
        logger.error("Teste com %d linhas, %d probabilidades salvas", len(y), len(probs))
        return 1

    p = {n: probs[:, i] for i, n in enumerate(nomes)}
    reais = [n for n in nomes if n != "referencia"]
    vencedor = reais[0]

    linhas_ic = []
    for n in reais:
        v, lo, hi = ic_bootstrap(y, p[n], n_reamostras=args.reamostras)
        linhas_ic.append({"modelo": n, "roc_auc": v, "ic_inferior": lo,
                          "ic_superior": hi, "largura_ic": hi - lo})
    ic = pd.DataFrame(linhas_ic)

    linhas_cmp = []
    for n in reais:
        if n == vencedor:
            continue
        r = comparar_bootstrap(y, p[n], p[vencedor], n_reamostras=args.reamostras)
        linhas_cmp.append({"comparacao": f"{vencedor} − {n}", **r,
                           "significativo_5pct": r["p_valor"] < 0.05})
    cmp = pd.DataFrame(linhas_cmp)

    ic.to_csv(REPORTS_DIR / f"ic_bootstrap_{args.desenho}.csv", index=False)
    cmp.to_csv(REPORTS_DIR / f"comparacao_pareada_{args.desenho}.csv", index=False)

    print(f"\nIntervalos de confiança (bootstrap, {args.reamostras} reamostras):")
    print(ic.round(4).to_string(index=False))
    print(f"\nComparações pareadas contra o vencedor ({vencedor}):")
    print(cmp.round(4).to_string(index=False))
    logger.info("Salvos em reports/ic_bootstrap_%s.csv e comparacao_pareada_%s.csv",
                args.desenho, args.desenho)
    return 0


if __name__ == "__main__":
    sys.exit(main())
