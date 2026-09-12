"""Catálogo de algoritmos candidatos, com a justificativa de cada escolha.

A comparação cobre três famílias, para que a escolha final seja defendida por
evidência e não por moda:

1. **Referência trivial** (`DummyClassifier`) — prediz sempre a taxa-base. Define
   o piso: qualquer modelo que não o supere com folga não aprendeu nada.
2. **Linear** (`LogisticRegression`) — interpretável por construção, coeficientes
   lidos como razão de chances. Serve de contraprova: se o ganho dos modelos
   complexos sobre ela for pequeno, o fenômeno é essencialmente aditivo e o
   modelo simples deve ser preferido por transparência — atributo que importa
   quando a saída embasa política pública.
3. **Ensembles de árvores por boosting** (`HistGradientBoosting`, `LightGBM`,
   `XGBoost`) — estado da arte em dados tabulares, capturam interações e efeitos
   não lineares (ex.: o efeito da infraestrutura escolar depender da região) sem
   especificação manual.

`RandomForest` fica de fora deliberadamente: em 3,3 milhões de linhas o custo de
treino é uma ordem de grandeza maior que o do boosting histogramado, sem vantagem
esperada de acurácia em dados tabulares densos.
"""
from __future__ import annotations

from lightgbm import LGBMClassifier
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from xgboost import XGBClassifier

from ..common.config import RANDOM_STATE

# Cada entrada: (estimador, precisa_escalonar, descrição)
CANDIDATOS: dict[str, tuple] = {
    "referencia": (
        DummyClassifier(strategy="prior"),
        False,
        "Prediz sempre a taxa-base. Piso de comparação.",
    ),
    "logistica": (
        LogisticRegression(
            # `max_iter` e `tol` calibrados para o volume: com 1,5 milhão de linhas
            # por ~180 colunas, cada iteração do lbfgs percorre ~2 GiB duas vezes
            # (~0,4 s). O padrão (1000 iterações, tol=1e-4) leva ~7 minutos para
            # ganhar, nas últimas centenas de passos, menos de 0,001 de AUC — o
            # erro-padrão da própria métrica é uma ordem de grandeza maior.
            max_iter=300,
            tol=1e-3,
            solver="lbfgs",
            C=1.0,
            random_state=RANDOM_STATE,
        ),
        True,   # exige escalonamento
        "Linear e interpretável; contraprova de que a complexidade se paga.",
    ),
    "hist_gb": (
        HistGradientBoostingClassifier(
            max_iter=400,
            learning_rate=0.06,
            max_leaf_nodes=63,
            min_samples_leaf=200,
            l2_regularization=1.0,
            early_stopping=True,
            validation_fraction=0.1,
            n_iter_no_change=30,
            random_state=RANDOM_STATE,
        ),
        False,
        "Boosting histogramado do scikit-learn; sem dependência externa.",
    ),
    "lightgbm": (
        LGBMClassifier(
            n_estimators=800,
            learning_rate=0.05,
            num_leaves=63,
            min_child_samples=200,
            subsample=0.8,
            subsample_freq=1,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            random_state=RANDOM_STATE,
            n_jobs=-1,
            verbose=-1,
        ),
        False,
        "Boosting leaf-wise; referência em dados tabulares de grande volume.",
    ),
    "xgboost": (
        XGBClassifier(
            n_estimators=800,
            learning_rate=0.05,
            max_depth=7,
            min_child_weight=50,
            subsample=0.8,
            colsample_bytree=0.8,
            reg_lambda=1.0,
            tree_method="hist",
            eval_metric="logloss",
            random_state=RANDOM_STATE,
            n_jobs=-1,
        ),
        False,
        "Boosting depth-wise com regularização explícita; controle de overfitting.",
    ),
}


def obter(nome: str):
    """Devolve (estimador clonável, precisa_escalonar, descrição)."""
    if nome not in CANDIDATOS:
        raise KeyError(f"candidato desconhecido: {nome}. "
                       f"Disponíveis: {sorted(CANDIDATOS)}")
    return CANDIDATOS[nome]
