"""Materializa a feature store analítica no BigQuery (`features.*`).

Executa, em ordem lexicográfica, os arquivos `sql/features/*.sql`. O prefixo `NN_`
define a ordem de dependência. Cada arquivo é um `CREATE OR REPLACE TABLE`,
tornando a construção idempotente e reprodutível.

Uso (da raiz do repo):
    export GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)
    ./venv/bin/python -m src.preprocessing.build_features            # executa
    ./venv/bin/python -m src.preprocessing.build_features --dry-run  # só valida e estima custo
    ./venv/bin/python -m src.preprocessing.build_features --only 04  # um arquivo
"""
import argparse
import sys

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

from ..common.config import SQL_DIR, sql_names
from ..common.gcp import bq_client
from ..common.log import get_logger

logger = get_logger("preprocessing.build_features")

FEATURES_DIR = SQL_DIR / "features"


def arquivos_sql(only: list[str] | None = None) -> list:
    """Arquivos .sql da feature store, em ordem de execução."""
    files = sorted(FEATURES_DIR.glob("*.sql"))
    if not files:
        raise FileNotFoundError(f"Nenhum .sql em {FEATURES_DIR}")
    if only:
        files = [f for f in files if any(f.name.startswith(p) for p in only)]
        if not files:
            raise FileNotFoundError(f"Nenhum .sql casa com o filtro {only}")
    return files


def render(path) -> str:
    """Resolve os placeholders {features}, {silver}, {gold}, ... no SQL."""
    return path.read_text(encoding="utf-8").format(**sql_names())


def dry_run(client: bigquery.Client, files: list) -> int:
    """Valida a sintaxe e soma o custo estimado, sem executar nada.

    Os arquivos formam uma cadeia de dependências: o 02 lê a tabela criada pelo 01.
    Num ambiente ainda não materializado, o dry-run dos arquivos seguintes falha com
    404 — isso é esperado e reportado como PENDENTE, não como erro.
    """
    total = 0
    for path in files:
        try:
            job = client.query(render(path),
                               job_config=bigquery.QueryJobConfig(dry_run=True))
        except NotFound as exc:
            faltante = str(exc).split("Not found: ")[-1].split(" was not found")[0]
            logger.warning("[dry-run] %-38s PENDENTE — depende de %s (ainda não "
                           "materializada)", path.name, faltante)
            continue
        total += job.total_bytes_processed or 0
        logger.info("[dry-run] %-38s OK — %s", path.name,
                    _fmt_bytes(job.total_bytes_processed))
    logger.info("Custo estimado total (arquivos validáveis): %s", _fmt_bytes(total))
    return total


def executar(client: bigquery.Client, files: list) -> None:
    """Executa os SQLs em ordem, registrando linhas e bytes de cada etapa."""
    total_bytes = 0
    for path in files:
        job = client.query(render(path))
        job.result()
        total_bytes += job.total_bytes_processed or 0
        alvo = job.ddl_target_table
        linhas = client.get_table(alvo).num_rows if alvo else None
        logger.info("%-38s -> %-28s %10s linhas | %s",
                    path.name,
                    alvo.table_id if alvo else "-",
                    f"{linhas:,}" if linhas is not None else "-",
                    _fmt_bytes(job.total_bytes_processed))
    logger.info("Feature store materializada. Total processado: %s",
                _fmt_bytes(total_bytes))


def _fmt_bytes(n: int | None) -> str:
    if not n:
        return "0 B"
    for unidade in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unidade == "TiB":
            return f"{n:.1f} {unidade}"
        n /= 1024


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Materializa a feature store analítica (features.*) no BigQuery."
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="apenas valida os SQLs e estima o custo")
    parser.add_argument("--only", action="append",
                        help="executa apenas arquivos cujo nome começa com o prefixo "
                             "(ex.: --only 04); pode repetir")
    args = parser.parse_args(argv)

    files = arquivos_sql(args.only)
    client = bq_client()
    logger.info("Feature store: %d arquivo(s) SQL", len(files))

    if args.dry_run:
        dry_run(client, files)
    else:
        executar(client, files)
    return 0


if __name__ == "__main__":
    sys.exit(main())
