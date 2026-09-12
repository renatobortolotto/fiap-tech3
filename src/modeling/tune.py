"""Otimização de hiperparâmetros com Optuna, sob validação agrupada.

O edital pede "estratégias de otimização e validação dos modelos, com o objetivo de
aumentar a capacidade de generalização e reduzir problemas de overfitting". Três
decisões concretizam isso aqui:

1. **A validação cruzada é AGRUPADA POR MUNICÍPIO** (`StratifiedGroupKFold`). É o
   ponto mais importante: como praticamente toda feature é constante dentro de um
   município, uma CV comum colocaria alunos do mesmo município nos dois lados e o
   modelo seria premiado por MEMORIZAR a média municipal. O hiperparâmetro escolhido
   sob essa CV enganosa seria o que mais memoriza — exatamente o oposto do objetivo.
2. **O espaço de busca é de regularização**, não de capacidade bruta: profundidade,
   folhas, mínimo por folha, subamostragem de linhas e colunas, L1/L2. Com 1,5 milhão
   de linhas e um sinal fraco, o risco real não é falta de capacidade — é sobreajuste
   ao ruído municipal.
3. **O conjunto de teste nunca participa.** A busca roda apenas sobre o treino; o
   teste é aberto uma única vez, ao final, para a métrica reportada.

Uso:
    ./venv/bin/python -m src.modeling.tune --tentativas 40
    ./venv/bin/python -m src.modeling.tune --desenho espacial --amostra 400000
"""
from __future__ import annotations

import argparse
import json
import sys

import numpy as np
import optuna
from lightgbm import LGBMClassifier
from sklearn.model_selection import cross_val_score

from ..common.config import MODELS_DIR, N_FOLDS, RANDOM_STATE, REPORTS_DIR
from ..common.log import get_logger
from ..preprocessing.features import ALVO, descartar_degeneradas, selecionar_features
from ..preprocessing.pipeline import montar_modelo
from .dataset import carregar_abt, cv_agrupada, split_espacial, split_temporal
from .train import DESENHOS, amostrar

logger = get_logger("modeling.tune")
optuna.logging.set_verbosity(optuna.logging.WARNING)


def espaco_busca(trial: optuna.Trial) -> dict:
    """Espaço de busca do LightGBM, centrado em REGULARIZAÇÃO."""
    return {
        "n_estimators": trial.suggest_int("n_estimators", 200, 1200, step=100),
        "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.15, log=True),
        "num_leaves": trial.suggest_int("num_leaves", 15, 127, log=True),
        "min_child_samples": trial.suggest_int("min_child_samples", 50, 2000, log=True),
        "subsample": trial.suggest_float("subsample", 0.6, 1.0),
        "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
        "reg_alpha": trial.suggest_float("reg_alpha", 1e-3, 10.0, log=True),
        "reg_lambda": trial.suggest_float("reg_lambda", 1e-3, 10.0, log=True),
        "max_depth": trial.suggest_int("max_depth", 3, 12),
    }


def executar(
    desenho: str = "temporal",
    n_tentativas: int = 40,
    n_amostra: int | None = 400_000,
    n_folds: int = 3,
) -> dict:
    """Roda a busca e devolve os melhores hiperparâmetros.

    A busca usa uma subamostra estratificada e 3 dobras por padrão: com 40 tentativas
    sobre 1,5 milhão de linhas e 5 dobras seriam ~200 ajustes de LightGBM. A ordenação
    relativa entre configurações é estável em amostra grande o bastante, e o modelo
    final é reajustado na base completa com os parâmetros vencedores.
    """
    split, permitir_defasadas = DESENHOS[desenho]
    df = carregar_abt()
    if desenho == "espacial":
        df = df[df["ano"] == 2024].copy()
    colunas = list(df.columns)
    treino, _ = split(df)
    del df

    treino_busca = amostrar(treino, n_amostra)
    features = selecionar_features(colunas, permitir_defasadas=permitir_defasadas)
    features, _ = descartar_degeneradas(treino_busca, features)

    X = treino_busca[features]
    y = treino_busca[ALVO].astype(int)
    grupos = treino_busca["id_municipio"]
    cv = cv_agrupada(n_splits=n_folds)
    logger.info("Busca em %d linhas, %d features, %d dobras agrupadas por município",
                len(X), len(features), n_folds)

    def objetivo(trial: optuna.Trial) -> float:
        params = espaco_busca(trial)
        modelo = montar_modelo(
            X,
            LGBMClassifier(**params, random_state=RANDOM_STATE, n_jobs=-1, verbose=-1),
            escalonar=False,
            random_state=RANDOM_STATE,
        )
        notas = cross_val_score(modelo, X, y, groups=grupos, cv=cv,
                                scoring="roc_auc", n_jobs=1)
        trial.set_user_attr("desvio", float(np.std(notas)))
        return float(np.mean(notas))

    estudo = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE),
        study_name=f"lightgbm_{desenho}",
    )
    estudo.optimize(objetivo, n_trials=n_tentativas, show_progress_bar=False,
                    callbacks=[_registrar])

    melhor = {"desenho": desenho, "roc_auc_cv": estudo.best_value,
              "desvio_cv": estudo.best_trial.user_attrs.get("desvio"),
              "n_tentativas": n_tentativas, "n_amostra": len(X),
              "params": estudo.best_params}
    destino = REPORTS_DIR / f"melhores_params_{desenho}.json"
    destino.write_text(json.dumps(melhor, indent=2, ensure_ascii=False), encoding="utf-8")

    historico = estudo.trials_dataframe()
    historico.to_csv(REPORTS_DIR / f"optuna_historico_{desenho}.csv", index=False)

    logger.info("Melhor ROC AUC (CV agrupada): %.4f ± %.4f",
                estudo.best_value, melhor["desvio_cv"] or 0.0)
    logger.info("Parâmetros: %s", json.dumps(estudo.best_params, indent=2))
    return melhor


def _registrar(estudo: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
    if trial.value is not None:
        logger.info("tentativa %2d: ROC AUC = %.4f (melhor até aqui %.4f)",
                    trial.number + 1, trial.value, estudo.best_value)


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Otimização de hiperparâmetros do LightGBM com Optuna."
    )
    parser.add_argument("--desenho", default="temporal", choices=sorted(DESENHOS))
    parser.add_argument("--tentativas", type=int, default=40)
    parser.add_argument("--amostra", type=int, default=400_000)
    parser.add_argument("--folds", type=int, default=3)
    args = parser.parse_args(argv)
    executar(args.desenho, args.tentativas, args.amostra, args.folds)
    return 0


if __name__ == "__main__":
    sys.exit(main())
