"""Métricas de avaliação e validação estatística.

O edital pede "validação estatística dos modelos" e "validação garantindo
replicabilidade e generalização". Um número de acurácia isolado não atende a isso:
é preciso saber se a diferença entre dois modelos é maior que a incerteza amostral.
Por isso toda métrica principal vem com intervalo de confiança por bootstrap, e a
comparação entre modelos é feita por bootstrap PAREADO (mesmas reamostragens para
os dois modelos, o que remove a variância comum e é bem mais sensível que comparar
dois intervalos de confiança independentes).

Por que estas métricas, neste problema:

* **ROC AUC** — mede ordenação, independe do limiar e é insensível à taxa-base.
  É a métrica de referência para comparar modelos aqui.
* **PR AUC (average precision)** — foca na classe positiva; útil porque o uso real
  é priorizar quem precisa de apoio, e não classificar todo mundo.
* **Brier score e log loss** — medem CALIBRAÇÃO. Para política pública a
  probabilidade precisa significar o que diz: se o modelo aponta 30 % de risco para
  mil crianças, cerca de 300 devem de fato não se alfabetizar. Um modelo bem
  ordenado mas descalibrado induz a dimensionar mal o programa de apoio.
* **KS** — separação máxima entre as distribuições acumuladas das duas classes;
  leitura consagrada em modelos de risco.
* **Acurácia balanceada e MCC** — resumos de classificação robustos a desbalanceamento.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    confusion_matrix,
    f1_score,
    log_loss,
    matthews_corrcoef,
    precision_score,
    recall_score,
    roc_auc_score,
    roc_curve,
)

from ..common.config import RANDOM_STATE


def ks(y: np.ndarray, p: np.ndarray) -> float:
    """Estatística KS: separação máxima entre as acumuladas das duas classes."""
    fpr, tpr, _ = roc_curve(y, p)
    return float(np.max(tpr - fpr))


def limiar_otimo(y: np.ndarray, p: np.ndarray) -> float:
    """Limiar que maximiza o índice de Youden (sensibilidade + especificidade - 1).

    Preferido ao 0,5 fixo porque 0,5 só é ótimo quando as classes são simétricas
    em frequência E em custo — o que aqui não se sustenta: deixar de identificar
    uma criança em risco custa muito mais que um alerta falso.
    """
    fpr, tpr, limiares = roc_curve(y, p)
    return float(limiares[int(np.argmax(tpr - fpr))])


def avaliar(
    y: np.ndarray,
    p: np.ndarray,
    limiar: float | None = None,
) -> dict[str, float]:
    """Painel completo de métricas para um vetor de probabilidades previstas."""
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    lim = limiar_otimo(y, p) if limiar is None else limiar
    pred = (p >= lim).astype(int)
    tn, fp, fn, tp = confusion_matrix(y, pred, labels=[0, 1]).ravel()
    return {
        "roc_auc": roc_auc_score(y, p),
        "pr_auc": average_precision_score(y, p),
        "ks": ks(y, p),
        "brier": brier_score_loss(y, p),
        "log_loss": log_loss(y, np.clip(p, 1e-6, 1 - 1e-6)),
        "acuracia": accuracy_score(y, pred),
        "acuracia_balanceada": balanced_accuracy_score(y, pred),
        "precisao": precision_score(y, pred, zero_division=0),
        "recall": recall_score(y, pred, zero_division=0),
        "f1": f1_score(y, pred, zero_division=0),
        "mcc": matthews_corrcoef(y, pred),
        "limiar": lim,
        "vn": int(tn), "fp": int(fp), "fn": int(fn), "vp": int(tp),
        "n": int(len(y)),
        "taxa_base": float(y.mean()),
    }


def ic_bootstrap(
    y: np.ndarray,
    p: np.ndarray,
    metrica=roc_auc_score,
    n_reamostras: int = 200,
    alfa: float = 0.05,
    random_state: int = RANDOM_STATE,
    max_amostra: int = 200_000,
) -> tuple[float, float, float]:
    """Intervalo de confiança percentil por bootstrap: (valor, inferior, superior).

    Em bases de milhões de linhas, reamostrar tudo 200 vezes é caro e desnecessário:
    o IC já é estreitíssimo. Subamostramos para ``max_amostra`` — o IC resultante é
    conservador (mais largo que o verdadeiro), o que é o lado seguro do erro.
    """
    rng = np.random.default_rng(random_state)
    y = np.asarray(y).astype(int)
    p = np.asarray(p, dtype=float)
    if len(y) > max_amostra:
        idx = rng.choice(len(y), max_amostra, replace=False)
        y, p = y[idx], p[idx]
    valores = []
    for _ in range(n_reamostras):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:       # reamostra degenerada
            continue
        valores.append(metrica(y[idx], p[idx]))
    return (
        float(metrica(y, p)),
        float(np.percentile(valores, 100 * alfa / 2)),
        float(np.percentile(valores, 100 * (1 - alfa / 2))),
    )


def comparar_bootstrap(
    y: np.ndarray,
    p_a: np.ndarray,
    p_b: np.ndarray,
    metrica=roc_auc_score,
    n_reamostras: int = 200,
    random_state: int = RANDOM_STATE,
    max_amostra: int = 200_000,
) -> dict[str, float]:
    """Bootstrap PAREADO da diferença métrica(B) - métrica(A).

    As mesmas reamostragens alimentam os dois modelos, eliminando a variância comum.
    ``p_valor`` é bicaudal, obtido da fração de reamostras em que a diferença troca
    de sinal — a leitura direta de "a vantagem observada poderia ser acaso?".
    """
    rng = np.random.default_rng(random_state)
    y = np.asarray(y).astype(int)
    p_a, p_b = np.asarray(p_a, dtype=float), np.asarray(p_b, dtype=float)
    if len(y) > max_amostra:
        idx = rng.choice(len(y), max_amostra, replace=False)
        y, p_a, p_b = y[idx], p_a[idx], p_b[idx]
    difs = []
    for _ in range(n_reamostras):
        idx = rng.integers(0, len(y), len(y))
        if len(np.unique(y[idx])) < 2:
            continue
        difs.append(metrica(y[idx], p_b[idx]) - metrica(y[idx], p_a[idx]))
    difs = np.asarray(difs)
    observada = float(metrica(y, p_b) - metrica(y, p_a))
    p_valor = 2 * min((difs <= 0).mean(), (difs >= 0).mean())
    return {
        "diferenca": observada,
        "ic_inferior": float(np.percentile(difs, 2.5)),
        "ic_superior": float(np.percentile(difs, 97.5)),
        "p_valor": float(min(p_valor, 1.0)),
    }


def tabela_metricas(resultados: dict[str, dict]) -> pd.DataFrame:
    """Monta o quadro comparativo {nome_do_modelo: métricas} -> DataFrame ordenado."""
    df = pd.DataFrame(resultados).T
    ordem = ["roc_auc", "pr_auc", "ks", "acuracia_balanceada", "f1", "recall",
             "precisao", "mcc", "brier", "log_loss", "limiar", "n", "taxa_base"]
    cols = [c for c in ordem if c in df.columns]
    return df[cols].sort_values("roc_auc", ascending=False)
