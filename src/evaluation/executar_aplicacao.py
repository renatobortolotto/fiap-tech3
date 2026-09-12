"""Traduz o modelo em inteligência aplicada: risco municipal, perfis e metas.

Responde às perguntas de negócio do desafio e escreve `reports/aplicacao.md`.

Uso:
    ./venv/bin/python -m src.evaluation.executar_aplicacao
"""
from __future__ import annotations

import argparse
import sys

import joblib
import pandas as pd

from ..common.config import MODELS_DIR, REPORTS_DIR
from ..common.log import get_logger
from ..modeling.dataset import carregar_abt
from ..modeling.train import DESENHOS
from ..preprocessing.features import ALVO, descartar_degeneradas, selecionar_features
from ..visualization import eda, plots
from . import aplicacao

logger = get_logger("evaluation.executar_aplicacao")


def _mil(n) -> str:
    return f"{int(n):,}".replace(",", ".")


def _v(x, casas=3) -> str:
    return f"{x:.{casas}f}".replace(".", ",")


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(description="Aplicação estratégica do modelo.")
    parser.add_argument("--desenho", default="temporal", choices=sorted(DESENHOS))
    parser.add_argument("--grupos", type=int, default=5)
    args = parser.parse_args(argv)

    caminho_modelo = MODELS_DIR / f"modelo_{args.desenho}.joblib"
    if not caminho_modelo.exists():
        logger.error("Modelo não encontrado: %s", caminho_modelo)
        return 1

    split, permitir_defasadas = DESENHOS[args.desenho]
    df_completo = carregar_abt()
    df = df_completo[df_completo["ano"] == 2024].copy() if args.desenho == "espacial" \
        else df_completo
    colunas = list(df.columns)
    treino, teste = split(df)

    features = selecionar_features(colunas, permitir_defasadas=permitir_defasadas)
    features, _ = descartar_degeneradas(treino, features)
    pipeline = joblib.load(caminho_modelo)

    logger.info("Prevendo %s alunos do conjunto de teste", _mil(len(teste)))
    prob = pipeline.predict_proba(teste[features])[:, 1]

    # --- 2. Ranking de risco municipal --------------------------------------
    logger.info("Risco municipal")
    ranking = aplicacao.ranking_risco_municipal(teste, prob)
    calib = aplicacao.calibracao_agregada(ranking)
    ranking.to_csv(REPORTS_DIR / f"risco_municipal_{args.desenho}.csv", index=False)
    f_calib = plots.fig_calibracao_municipal(ranking, calib)
    f_resid = plots.fig_residuos(ranking)

    # --- 3. Agrupamento por perfil de contexto -------------------------------
    logger.info("Agrupamento de municípios em %d perfis", args.grupos)
    mun = eda.agregar_municipio(teste)
    municipios, perfil = aplicacao.agrupar_municipios(mun, k=args.grupos)
    perfil.to_csv(REPORTS_DIR / f"perfis_municipais_{args.desenho}.csv")
    municipios[["id_municipio", "grupo", ALVO]].to_csv(
        REPORTS_DIR / f"municipios_por_grupo_{args.desenho}.csv", index=False)
    f_grupos = plots.fig_grupos(perfil, municipios)

    # --- 4. Risco de não atingir a meta --------------------------------------
    metas_disponiveis = "mun_lag_meta_ano_alvo" in teste.columns and \
        teste["mun_lag_meta_ano_alvo"].notna().any()
    risco_meta = pd.DataFrame()
    if metas_disponiveis:
        logger.info("Risco de não atingir a meta pactuada")
        metas = (teste[["id_municipio", "mun_lag_meta_ano_alvo"]]
                 .dropna().drop_duplicates("id_municipio"))
        risco_meta = aplicacao.risco_de_nao_atingir_meta(ranking, metas)
        risco_meta.to_csv(REPORTS_DIR / f"risco_meta_{args.desenho}.csv", index=False)
    else:
        logger.warning("Metas indisponíveis no desenho '%s' (são features defasadas, "
                       "ausentes no treino de 2023) — seção omitida", args.desenho)

    # --- Relatório -----------------------------------------------------------
    top_risco = ranking[ranking["n_alunos"] >= 100].head(15)
    piores_residuos = ranking[ranking["n_alunos"] >= 100].nsmallest(10, "residuo")
    melhores_residuos = ranking[ranking["n_alunos"] >= 100].nlargest(10, "residuo")

    md = [
        f"# Aplicação estratégica — desenho `{args.desenho}`",
        "",
        "## Por que agregar por município muda tudo",
        "",
        "A predição individual de alfabetização tem teto baixo: o desfecho de uma "
        "criança depende de fatores que nenhum dado público municipal captura. Mas o "
        "erro individual em grande parte se **cancela na média** — e é a média "
        "municipal que orienta a decisão pública.",
        "",
        "| métrica da previsão agregada por município | valor |",
        "|---|---:|",
        f"| municípios avaliados (≥30 alunos) | {_mil(calib['n_municipios'])} |",
        f"| correlação prevista × observada | **{_v(calib['correlacao'])}** |",
        f"| erro absoluto médio | **{_v(calib['erro_medio_absoluto_pp'], 1)} p.p.** |",
        f"| erro mediano | {_v(calib['erro_mediano_pp'], 1)} p.p. |",
        f"| viés | {_v(calib['vies_pp'], 2)} p.p. |",
        f"| R² | {_v(calib['r2'])} |",
        "",
        f"![calibração municipal](../images/{f_calib.split('/')[-1]})",
        "",
        "## Quais municípios apresentam maior risco educacional",
        "",
        "Risco = 1 − taxa prevista. Municípios com ao menos 100 alunos avaliados.",
        "",
        "| município | UF | alunos | risco previsto | taxa observada |",
        "|---|---|---:|---:|---:|",
    ]
    for _, r in top_risco.iterrows():
        md.append(f"| {r['municipio']} | {r['uf']} | {_mil(r['n_alunos'])} | "
                  f"{_v(r['risco']*100, 1)}% | {_v(r['taxa_observada']*100, 1)}% |")

    md += [
        "",
        "## Quem foge do próprio contexto — a leitura acionável",
        "",
        "O risco absoluto em geral apenas reflete a pobreza do território. O **resíduo** "
        "(observado − previsto) isola o que o contexto NÃO explica: resíduo muito "
        "negativo aponta problema de gestão; muito positivo aponta prática que merece "
        "ser estudada e replicada.",
        "",
        f"![resíduos](../images/{f_resid.split('/')[-1]})",
        "",
        "### Abaixo do esperado",
        "",
        "| município | UF | alunos | observado | previsto | resíduo |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for _, r in piores_residuos.iterrows():
        md.append(f"| {r['municipio']} | {r['uf']} | {_mil(r['n_alunos'])} | "
                  f"{_v(r['taxa_observada']*100, 1)}% | {_v(r['taxa_prevista']*100, 1)}% | "
                  f"**{_v(r['residuo']*100, 1)} p.p.** |")

    md += ["", "### Acima do esperado", "",
           "| município | UF | alunos | observado | previsto | resíduo |",
           "|---|---|---:|---:|---:|---:|"]
    for _, r in melhores_residuos.iterrows():
        md.append(f"| {r['municipio']} | {r['uf']} | {_mil(r['n_alunos'])} | "
                  f"{_v(r['taxa_observada']*100, 1)}% | {_v(r['taxa_prevista']*100, 1)}% | "
                  f"**+{_v(r['residuo']*100, 1)} p.p.** |")

    md += [
        "",
        "## Quais regiões possuem padrões semelhantes",
        "",
        f"Agrupamento em {args.grupos} perfis por **contexto** (vulnerabilidade, "
        "demografia, INSE, docência, infraestrutura, financiamento). O alvo ficou "
        "deliberadamente de fora: assim a taxa de alfabetização de cada grupo é um "
        "resultado da análise, não o critério que a produziu.",
        "",
        f"![grupos](../images/{f_grupos.split('/')[-1]})",
        "",
        "| grupo | municípios | % alfabetizados |",
        "|---|---:|---:|",
    ]
    for g, r in perfil.iterrows():
        md.append(f"| {g} | {_mil(r['n_municipios'])} | "
                  f"{_v(r['taxa_observada']*100, 1)}% |")

    if not risco_meta.empty:
        criticos = risco_meta[risco_meta["n_alunos"] >= 100].head(15)
        resumo = (risco_meta[risco_meta["n_alunos"] >= 100]["classificacao"]
                  .value_counts().sort_index())
        md += [
            "",
            "## Quais municípios podem não atingir a meta",
            "",
            "A taxa municipal prevista é a média de indicadores de Bernoulli; sua "
            "distribuição amostral é aproximadamente normal, e a probabilidade de "
            "ficar abaixo da meta é Φ((meta − previsto) / erro-padrão).",
            "",
            "| classificação | municípios |",
            "|---|---:|",
        ]
        for classe, n in resumo.items():
            md.append(f"| {classe} | {_mil(n)} |")
        md += [
            "",
            "| município | UF | meta | taxa prevista | prob. de não atingir |",
            "|---|---|---:|---:|---:|",
        ]
        for _, r in criticos.iterrows():
            md.append(f"| {r['municipio']} | {r['uf']} | "
                      f"{_v(r['mun_lag_meta_ano_alvo'], 1)}% | "
                      f"{_v(r['taxa_prevista']*100, 1)}% | "
                      f"**{_v(r['prob_nao_atingir']*100, 1)}%** |")
        md += [
            "",
            "> **Ressalva estatística.** O cálculo supõe independência condicional "
            "entre alunos. Como colegas de escola compartilham choques não observados, "
            "o erro-padrão real é maior e estas probabilidades são mais extremas do que "
            "deveriam. A **ordenação** é confiável; a magnitude, não.",
        ]

    destino = REPORTS_DIR / f"aplicacao_{args.desenho}.md"
    destino.write_text("\n".join(md), encoding="utf-8")
    logger.info("Relatório salvo em %s", destino)
    return 0


if __name__ == "__main__":
    sys.exit(main())
