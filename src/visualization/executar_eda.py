"""Executa a análise exploratória completa: figuras em images/ e relatório em reports/.

Uso:
    export GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)
    ./venv/bin/python -m src.visualization.executar_eda
"""
from __future__ import annotations

import sys

from ..common.config import REPORTS_DIR
from ..common.log import get_logger
from ..modeling.dataset import carregar_abt
from ..preprocessing.features import ALVO, blocos, selecionar_features
from . import eda

logger = get_logger("visualization.executar_eda")


def _pct(x: float) -> str:
    return f"{x*100:.1f}%".replace(".", ",")


def main() -> int:
    df = carregar_abt()
    features = selecionar_features(list(df.columns))
    logger.info("EDA sobre %d alunos e %d features", len(df), len(features))

    logger.info("1/7 distribuição do alvo")
    f1 = eda.fig_distribuicao_alvo(df)
    logger.info("2/7 dispersão entre escolas e municípios")
    f2 = eda.fig_dispersao_unidades(df)
    logger.info("3/7 persistência ano a ano")
    f3, persistencia = eda.fig_persistencia(df)

    logger.info("4/7 agregação municipal e correlações")
    mun = eda.agregar_municipio(df)
    corr = eda.correlacoes_municipais(mun, features)
    corr.to_csv(REPORTS_DIR / "correlacoes_municipais.csv", index=False)
    f4 = eda.fig_top_correlacoes(corr)

    logger.info("5/7 perfil por decil")
    principais = [c for c in corr.head(6)["feature"] if c in df.columns][:4]
    f5 = eda.fig_decis(df, principais)

    logger.info("6/7 mapa")
    f6 = eda.fig_mapa(mun)
    logger.info("7/7 dados ausentes")
    f7 = eda.fig_ausencias(df, features)

    # --- Relatório -----------------------------------------------------------
    por_ano = df.groupby("ano")[ALVO].agg(["size", "mean"])
    blocos_features = blocos(features)
    topo = corr.head(12)

    linhas = [
        "# Análise exploratória",
        "",
        "Gerado por `make eda`. Todos os números vêm da ABT "
        "(`features.abt_aluno`), não de amostras.",
        "",
        "## 1. A base",
        "",
        f"- **{len(df):,}** alunos avaliados".replace(",", ".")
        + f", em **{df['id_municipio'].nunique():,}** municípios".replace(",", "."),
        f"- **{len(features)}** features candidatas em **{len(blocos_features)}** "
        "blocos temáticos (antes do descarte de colunas degeneradas, que o treino "
        "aplica: o Modelo A usa 125 e o Modelo B, 137)",
        "",
        "| ano | alunos | % alfabetizados |",
        "|---|---:|---:|",
    ]
    for ano, linha in por_ano.iterrows():
        linhas.append(f"| {ano} | {int(linha['size']):,}".replace(",", ".")
                      + f" | {_pct(linha['mean'])} |")

    linhas += [
        "",
        "| bloco | nº de features |",
        "|---|---:|",
    ]
    for bloco, cols in sorted(blocos_features.items(), key=lambda kv: -len(kv[1])):
        linhas.append(f"| {bloco} | {len(cols)} |")

    linhas += [
        "",
        "## 2. Onde está a variação",
        "",
        f"![distribuição do alvo]({f1.split('/')[-2]}/{f1.split('/')[-1]})",
        "",
        f"![dispersão]({f2.split('/')[-2]}/{f2.split('/')[-1]})",
        "",
        "## 3. O que persiste entre os anos",
        "",
        f"Correlação entre a taxa de 2023 e a de 2024 da mesma unidade:",
        "",
        "| unidade | n | r |",
        "|---|---:|---:|",
        f"| município | {persistencia['n_municipios']:,}".replace(",", ".")
        + f" | **{persistencia['r_municipio']:.3f}** |".replace(".", ","),
        f"| \"escola\" (chave renumerada) | {persistencia['n_escolas']:,}".replace(",", ".")
        + f" | {persistencia['r_escola']:.3f} |".replace(".", ","),
        "",
        "O valor da escola **não** mede persistência escolar: `id_escola` é renumerado "
        "a cada ano (só 2,4% dos identificadores presentes nos dois anos apontam para o "
        "mesmo município). Ver `docs/decisoes-analiticas.md` §3.",
        "",
        f"![persistência]({f3.split('/')[-2]}/{f3.split('/')[-1]})",
        "",
        "## 4. Correlações",
        "",
        "Medidas no grão do **município** (correlação ecológica — não pode ser lida "
        "como efeito individual).",
        "",
        "| feature | bloco | r | n |",
        "|---|---|---:|---:|",
    ]
    for _, r in topo.iterrows():
        linhas.append(f"| `{r['feature']}` | {r['bloco']} | "
                      f"{r['r']:+.3f}".replace(".", ",") + f" | {int(r['n']):,}".replace(",", ".") + " |")

    linhas += [
        "",
        f"![correlações]({f4.split('/')[-2]}/{f4.split('/')[-1]})",
        "",
        f"![decis]({f5.split('/')[-2]}/{f5.split('/')[-1]})",
        "",
        "## 5. Geografia",
        "",
        f"![mapa]({f6.split('/')[-2]}/{f6.split('/')[-1]})",
        "",
        "## 6. Dados ausentes",
        "",
        f"![ausentes]({f7.split('/')[-2]}/{f7.split('/')[-1]})" if f7 else
        "Nenhuma feature com ausência relevante.",
        "",
    ]

    destino = REPORTS_DIR / "eda.md"
    destino.write_text("\n".join(linhas), encoding="utf-8")
    logger.info("Relatório salvo em %s", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
