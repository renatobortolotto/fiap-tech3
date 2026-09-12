"""Configuração central do projeto (config/config.yaml).

Espelha o módulo equivalente da Fase 2 para manter a experiência de uso
consistente entre as duas entregas.
"""
import os
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
_CONFIG_PATH = REPO_ROOT / "config" / "config.yaml"

with open(_CONFIG_PATH, encoding="utf-8") as _f:
    CFG = yaml.safe_load(_f)

# --- GCP ---------------------------------------------------------------------
PROJECT_ID = os.environ.get("GCP_PROJECT_ID", CFG["gcp"]["project_id"])
LOCATION = CFG["gcp"]["location"]
BUCKET = CFG["gcp"]["bucket"]
DATASETS = CFG["gcp"]["datasets"]
MAX_BYTES_BILLED = int(CFG["finops"]["maximum_bytes_billed"])

# --- Modelagem ---------------------------------------------------------------
MODELAGEM = CFG["modelagem"]
ALVO = MODELAGEM["alvo"]
ANO_TREINO = int(MODELAGEM["ano_treino"])
ANO_TESTE = int(MODELAGEM["ano_teste"])
RANDOM_STATE = int(MODELAGEM["random_state"])
N_FOLDS = int(MODELAGEM["n_folds"])
COLUNAS_VAZADAS = list(MODELAGEM["colunas_vazadas"])

# --- Caminhos locais ---------------------------------------------------------
DATA_DIR = REPO_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = REPO_ROOT / "models"
IMAGES_DIR = REPO_ROOT / "images"
REPORTS_DIR = REPO_ROOT / "reports"
SQL_DIR = REPO_ROOT / "sql"

for _d in (RAW_DIR, INTERIM_DIR, PROCESSED_DIR, MODELS_DIR, IMAGES_DIR, REPORTS_DIR):
    _d.mkdir(parents=True, exist_ok=True)


def table_id(layer: str, table: str) -> str:
    """Nome completo `projeto.dataset.tabela` de uma tabela em uma camada."""
    return f"{PROJECT_ID}.{DATASETS[layer]}.{table}"


def sql_names() -> dict:
    """Placeholders usados nos arquivos .sql ({project}, {silver}, {gold}, ...)."""
    names = {"project": PROJECT_ID}
    names.update({k: f"{PROJECT_ID}.{v}" for k, v in DATASETS.items()})
    names.update(CFG["fontes_externas"])
    return names
