"""Extração da ABT do BigQuery e desenhos de validação.

A ABT (`features.abt_aluno`) fica no BigQuery; aqui ela é materializada em Parquet
local uma única vez (`data/processed/abt_aluno.parquet`) para que os experimentos
de modelagem rodem sem custo de consulta e de forma reprodutível.

DOIS DESENHOS DE VALIDAÇÃO, porque são DUAS perguntas de generalização diferentes:

* **Temporal (out-of-time)** — treino em 2023, teste em 2024. Mede se o modelo
  sobrevive à passagem do tempo em municípios já conhecidos. É o Modelo A.
* **Espacial (out-of-space)** — partição agrupada por MUNICÍPIO, de modo que
  nenhum município apareça ao mesmo tempo no treino e no teste. Mede se o modelo
  vale para municípios nunca vistos — a pergunta relevante quando se quer aplicar
  o modelo a uma rede que ainda não foi avaliada.

Agrupar por município não é preciosismo: sem isso, o `TargetEncoder` de
`id_municipio` e as features `mun_*` permitiriam ao modelo reconhecer o município
do aluno de teste, inflando a métrica.
"""
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

import pandas as pd
from sklearn.model_selection import GroupShuffleSplit, StratifiedGroupKFold

from ..common.config import (
    ANO_TESTE,
    ANO_TREINO,
    BUCKET,
    N_FOLDS,
    PROCESSED_DIR,
    RANDOM_STATE,
    table_id,
)
from ..common.gcp import bq_client
from ..common.log import get_logger
from ..preprocessing.features import ALVO

logger = get_logger("modeling.dataset")

CAMINHO_ABT = PROCESSED_DIR / "abt_aluno.parquet"


def extrair_abt(destino: Path = CAMINHO_ABT, forcar: bool = False) -> Path:
    """Materializa `features.abt_aluno` em Parquet local.

    O caminho é BigQuery -> GCS -> disco, e não a API REST de resultados: para 3,35
    milhões de linhas por ~100 colunas a paginação REST leva dezenas de minutos e
    consome memória desnecessária, enquanto o `EXPORT DATA` roda dentro do BigQuery
    e o download vem em Parquet já comprimido.
    """
    if destino.exists() and not forcar:
        logger.info("ABT já existe em %s (use forcar=True para rebaixar)", destino)
        return destino

    tabela = table_id("features", "abt_aluno")
    prefixo = f"gs://{BUCKET}/fase3/abt_aluno"
    logger.info("Exportando %s -> %s", tabela, prefixo)

    client = bq_client()
    client.query(f"""
        EXPORT DATA OPTIONS(
            uri = '{prefixo}/parte-*.parquet',
            format = 'PARQUET',
            compression = 'SNAPPY',
            overwrite = true
        ) AS SELECT * FROM `{tabela}`
    """).result()

    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        subprocess.run(["gsutil", "-q", "-m", "cp", f"{prefixo}/parte-*.parquet", tmp],
                       check=True)
        partes = sorted(Path(tmp).glob("parte-*.parquet"))
        logger.info("Baixadas %d partes; consolidando", len(partes))
        df = pd.concat([pd.read_parquet(p) for p in partes], ignore_index=True)
    df.to_parquet(destino, index=False)

    logger.info("ABT salva: %d linhas x %d colunas (%.1f MiB)",
                len(df), df.shape[1], destino.stat().st_size / 1024**2)
    return destino


def carregar_abt(caminho: Path = CAMINHO_ABT) -> pd.DataFrame:
    """Carrega a ABT local; extrai do BigQuery se ainda não existir."""
    if not caminho.exists():
        extrair_abt(caminho)
    df = pd.read_parquet(caminho)
    logger.info("ABT carregada: %d linhas x %d colunas", len(df), df.shape[1])
    return df


# --- Desenho A: temporal (out-of-time) ---------------------------------------
def split_temporal(
    df: pd.DataFrame,
    ano_treino: int = ANO_TREINO,
    ano_teste: int = ANO_TESTE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Treino no ano anterior, teste no ano seguinte. Sem interseção temporal."""
    treino = df[df["ano"] == ano_treino].copy()
    teste = df[df["ano"] == ano_teste].copy()
    logger.info("Split temporal: treino %d (%d) | teste %d (%d)",
                ano_treino, len(treino), ano_teste, len(teste))
    return treino, teste


# --- Desenho B: espacial (out-of-space) --------------------------------------
def split_espacial(
    df: pd.DataFrame,
    frac_teste: float = 0.25,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Partição agrupada por município: nenhum município nos dois lados."""
    gss = GroupShuffleSplit(n_splits=1, test_size=frac_teste,
                            random_state=random_state)
    idx_treino, idx_teste = next(gss.split(df, groups=df["id_municipio"]))
    treino, teste = df.iloc[idx_treino].copy(), df.iloc[idx_teste].copy()
    logger.info("Split espacial: treino %d alunos / %d municípios | "
                "teste %d alunos / %d municípios",
                len(treino), treino["id_municipio"].nunique(),
                len(teste), teste["id_municipio"].nunique())
    assert not set(treino["id_municipio"]) & set(teste["id_municipio"]), \
        "vazamento: município presente no treino e no teste"
    return treino, teste


def cv_agrupada(n_splits: int = N_FOLDS, random_state: int = RANDOM_STATE):
    """Validação cruzada estratificada pelo alvo e AGRUPADA por município.

    Estratificar mantém a taxa-base estável entre dobras; agrupar impede que o
    mesmo município caia em treino e validação, o que inflaria a métrica através
    do target encoding e das features municipais.
    """
    return StratifiedGroupKFold(n_splits=n_splits, shuffle=True,
                                random_state=random_state)


def X_y_grupos(df: pd.DataFrame, features: list[str]):
    """Separa matriz de features, alvo binário e vetor de grupos (município)."""
    X = df[features]
    y = df[ALVO].astype(int)
    grupos = df["id_municipio"]
    return X, y, grupos
