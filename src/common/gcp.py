"""Cliente BigQuery com autenticação flexível (mesmo padrão da Fase 2).

Ordem de autenticação:
1. ``GCP_ACCESS_TOKEN`` no ambiente — ``export GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)``.
   Necessário nesta máquina porque o Application Default Credentials local
   pertence a outra conta, sem acesso ao projeto.
2. Application Default Credentials.
"""
import os

from google.cloud import bigquery

from .config import LOCATION, MAX_BYTES_BILLED, PROJECT_ID


def _credentials():
    token = os.environ.get("GCP_ACCESS_TOKEN")
    if token:
        from google.oauth2.credentials import Credentials

        return Credentials(token=token)
    return None  # Application Default Credentials


def bq_client() -> bigquery.Client:
    """Cliente BigQuery com teto de bytes faturados por consulta (FinOps)."""
    return bigquery.Client(
        project=PROJECT_ID,
        credentials=_credentials(),
        location=LOCATION,
        default_query_job_config=bigquery.QueryJobConfig(
            maximum_bytes_billed=MAX_BYTES_BILLED
        ),
    )
