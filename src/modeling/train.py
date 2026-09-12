"""Execução dos experimentos de modelagem.

Um "experimento" é a combinação de (desenho de validação, conjunto de features,
lista de algoritmos). O runner treina cada candidato na partição de treino, avalia
na de teste e devolve o quadro comparativo — sempre com o mesmo pré-processamento
embutido no pipeline, para que a comparação entre algoritmos seja justa.

Uso:
    export GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)
    ./venv/bin/python -m src.modeling.train --desenho temporal
    ./venv/bin/python -m src.modeling.train --desenho espacial --amostra 300000
"""
from __future__ import annotations

import argparse
import gc
import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.base import clone

from ..common.config import MODELS_DIR, RANDOM_STATE, REPORTS_DIR
from ..common.log import get_logger
from ..evaluation.metrics import (
    avaliar,
    avaliar_por_estrato,
    estratos_de_cobertura,
    tabela_metricas,
)
from ..preprocessing.features import (
    ALVO,
    blocos,
    descartar_degeneradas,
    selecionar_features,
)
from ..preprocessing.pipeline import montar_modelo
from . import candidatos as cat
from .dataset import carregar_abt, split_espacial, split_temporal

logger = get_logger("modeling.train")

DESENHOS = {
    # nome -> (função de split, permite features defasadas)
    # O desenho temporal treina em 2023, ano sem histórico: features defasadas
    # não existem e precisam ser desligadas.
    "temporal": (split_temporal, False),
    "espacial": (split_espacial, True),
}


def amostrar(df: pd.DataFrame, n: int | None, random_state: int = RANDOM_STATE):
    """Subamostra estratificada pelo alvo (para iteração rápida durante o ajuste)."""
    if n is None or n >= len(df):
        return df
    return (df.groupby(ALVO, group_keys=False)
              .apply(lambda g: g.sample(int(round(n * len(g) / len(df))),
                                        random_state=random_state))
              .reset_index(drop=True))


def treinar_e_avaliar(
    treino: pd.DataFrame,
    teste: pd.DataFrame,
    features: list[str],
    nomes: list[str],
) -> tuple[dict, dict, dict]:
    """Treina cada candidato e avalia no conjunto de teste.

    Devolve (métricas, probabilidades previstas, pipelines treinados).
    """
    X_tr, y_tr = treino[features], treino[ALVO].astype(int)
    X_te, y_te = teste[features], teste[ALVO].astype(int)

    metricas, probabilidades, modelos = {}, {}, {}
    for nome in nomes:
        estimador, escalonar, _ = cat.obter(nome)
        pipe = montar_modelo(X_tr, clone(estimador), escalonar=escalonar,
                             random_state=RANDOM_STATE)
        inicio = time.perf_counter()
        pipe.fit(X_tr, y_tr)
        duracao = time.perf_counter() - inicio

        p = pipe.predict_proba(X_te)[:, 1].astype("float32")
        m = avaliar(y_te.to_numpy(), p)
        m["segundos_treino"] = round(duracao, 1)
        metricas[nome], probabilidades[nome], modelos[nome] = m, p, pipe
        gc.collect()
        logger.info("%-12s ROC AUC=%.4f  PR AUC=%.4f  KS=%.4f  Brier=%.4f  (%.0fs)",
                    nome, m["roc_auc"], m["pr_auc"], m["ks"], m["brier"], duracao)
    return metricas, probabilidades, modelos


def executar(
    desenho: str = "temporal",
    n_amostra: int | None = None,
    nomes: list[str] | None = None,
    salvar: bool = True,
) -> dict:
    """Roda um experimento completo e persiste métricas e modelos."""
    split, permitir_defasadas = DESENHOS[desenho]
    df = carregar_abt()

    if desenho == "espacial":
        # O desenho espacial só faz sentido no ano que tem histórico disponível.
        df = df[df["ano"] == 2024].copy()
        logger.info("Desenho espacial restrito a 2024 (%d alunos)", len(df))

    colunas = list(df.columns)
    treino, teste = split(df)
    del df
    gc.collect()
    if n_amostra:
        treino, teste = amostrar(treino, n_amostra), amostrar(teste, n_amostra)
        logger.info("Subamostrado para %d/%d (treino/teste)", len(treino), len(teste))

    features = selecionar_features(colunas, permitir_defasadas=permitir_defasadas)
    features, descartadas = descartar_degeneradas(treino, features)
    for col, motivo in descartadas.items():
        logger.warning("Feature descartada: %-36s (%s)", col, motivo)
    logger.info("Desenho '%s': %d features em %d blocos",
                desenho, len(features), len(blocos(features)))
    for bloco, cols in blocos(features).items():
        logger.info("   %-28s %2d features", bloco, len(cols))

    nomes = nomes or list(cat.CANDIDATOS)
    metricas, probabilidades, modelos = treinar_e_avaliar(treino, teste, features, nomes)

    quadro = tabela_metricas(metricas)
    print("\n" + quadro.round(4).to_string())

    # Métricas do melhor modelo, separadas por quanto o treino já conhecia o território
    melhor = quadro.index[0]
    estratos = estratos_de_cobertura(treino, teste)
    por_estrato = avaliar_por_estrato(teste[ALVO].astype(int).to_numpy(),
                                      probabilidades[melhor], estratos)
    print(f"\nModelo '{melhor}' por estrato de cobertura territorial:")
    print(por_estrato.round(4).to_string())

    if salvar:
        destino = REPORTS_DIR / f"metricas_{desenho}.csv"
        quadro.to_csv(destino)
        with open(REPORTS_DIR / f"features_{desenho}.json", "w", encoding="utf-8") as f:
            json.dump({"desenho": desenho, "n_features": len(features),
                       "features": features, "blocos": blocos(features)},
                      f, ensure_ascii=False, indent=2)
        por_estrato.to_csv(REPORTS_DIR / f"metricas_{desenho}_por_estrato.csv")
        joblib.dump(modelos[melhor], MODELS_DIR / f"modelo_{desenho}.joblib")
        np.save(REPORTS_DIR / f"probabilidades_{desenho}.npy",
                np.column_stack([probabilidades[n] for n in quadro.index]))
        logger.info("Salvos: %s | melhor = %s", destino.name, melhor)

    return {"metricas": quadro, "por_estrato": por_estrato,
            "probabilidades": probabilidades,
            "modelos": modelos, "features": features,
            "treino": treino, "teste": teste}


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Experimentos de modelagem.")
    parser.add_argument("--desenho", default="temporal", choices=sorted(DESENHOS))
    parser.add_argument("--amostra", type=int, default=None,
                        help="subamostra para iteração rápida (padrão: base completa)")
    parser.add_argument("--modelos", action="append",
                        help="restringe aos candidatos indicados; pode repetir")
    args = parser.parse_args(argv)
    executar(args.desenho, args.amostra, args.modelos)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
