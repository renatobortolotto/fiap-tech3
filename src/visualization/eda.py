"""Análise exploratória: distribuições, padrões, correlações e hipóteses.

Gera as figuras de `images/` e o relatório `reports/eda.md`. Toda a lógica vive
aqui e não nos notebooks — os notebooks apenas chamam estas funções, de modo que a
análise seja versionável, testável e reexecutável sem depender de estado de kernel.

Uma escolha metodológica atravessa o arquivo: **as correlações são medidas no grão
do MUNICÍPIO, não no do aluno**. No grão do aluno, uma variável municipal é
constante dentro do município, e a correlação ponto-bisserial resultante é diluída
pelo ruído individual — ela mede o quanto o contexto explica um desfecho individual,
que é sempre pouco. No grão do município, mede-se o que a variável realmente
descreve: a diferença entre redes de ensino. As duas leituras aparecem no relatório,
com a advertência de que a segunda é uma correlação ECOLÓGICA e não pode ser lida
como efeito individual.
"""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from ..common.config import IMAGES_DIR, REPORTS_DIR
from ..common.log import get_logger
from ..preprocessing.features import ALVO, bloco_de, selecionar_features
from .estilo import (
    CATEGORICA,
    DIVERGENTE,
    GRADE,
    SEQUENCIAL,
    TINTA_SECUNDARIA,
    aplicar_estilo,
    limpar_eixos,
    rotular_barras,
    salvar,
    titular,
)

logger = get_logger("visualization.eda")
MIN_ALUNOS_MUNICIPIO = 30   # abaixo disso a taxa municipal é ruído amostral


# =============================================================================
# Agregações de apoio
# =============================================================================
def agregar_municipio(df: pd.DataFrame, min_alunos: int = MIN_ALUNOS_MUNICIPIO):
    """Taxa observada por (ano, município), com as features municipais anexadas.

    As features de contexto são constantes dentro do município, então `first`
    recupera o valor sem distorção.
    """
    chaves = ["ano", "id_municipio"]
    numericas = [c for c in df.select_dtypes("number").columns
                 if c != ALVO and c not in chaves]
    especificacao = {"n_alunos": ("id_aluno", "size"), ALVO: (ALVO, "mean")}
    # As features de contexto são constantes dentro do município: `first` recupera
    # o valor sem distorção. As chaves do agrupamento ficam de fora da agregação —
    # `reset_index` as reinsere, e duplicá-las causaria colisão de nomes.
    especificacao.update({c: (c, "first") for c in numericas})
    # `ter_regiao` é categórica mas é necessária para as leituras regionais
    for col in ("ter_regiao", "nome_municipio", "sigla_uf", "ter_latitude",
                "ter_longitude"):
        if col in df.columns and col not in especificacao:
            especificacao[col] = (col, "first")

    mun = (df.groupby(chaves, observed=True)
             .agg(**especificacao)
             .reset_index())
    return mun[mun["n_alunos"] >= min_alunos]


# =============================================================================
# 1. Distribuições
# =============================================================================
def fig_distribuicao_alvo(df: pd.DataFrame) -> str:
    """Taxa de alfabetização por ano, rede e região — o retrato de partida."""
    aplicar_estilo()
    fig, eixos = plt.subplots(1, 3, figsize=(13, 4.2))

    por_ano = df.groupby("ano")[ALVO].mean().mul(100)
    eixos[0].bar(por_ano.index.astype(str), por_ano.values,
                 color=CATEGORICA[0], width=0.55)
    rotular_barras(eixos[0], "{:.1f}%")
    titular(eixos[0], "Por ano", "% de alunos avaliados alfabetizados")
    eixos[0].set_ylim(0, 100)

    por_rede = (df.groupby("alu_rede")[ALVO].agg(["mean", "size"])
                  .query("size >= 1000").sort_values("mean"))
    eixos[1].barh(por_rede.index, por_rede["mean"].mul(100),
                  color=CATEGORICA[1], height=0.55)
    rotular_barras(eixos[1], "{:.1f}%", horizontal=True)
    titular(eixos[1], "Por rede", "redes com ao menos 1.000 alunos")
    eixos[1].set_xlim(0, 100)

    por_regiao = df.groupby("ter_regiao")[ALVO].mean().mul(100).sort_values()
    eixos[2].barh(por_regiao.index, por_regiao.values,
                  color=CATEGORICA[2], height=0.6)
    rotular_barras(eixos[2], "{:.1f}%", horizontal=True)
    titular(eixos[2], "Por região", "desigualdade regional é a maior fonte de variação")
    eixos[2].set_xlim(0, 100)

    for ax in eixos:
        limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "01_distribuicao_alvo")


def fig_dispersao_unidades(df: pd.DataFrame) -> str:
    """Dispersão da taxa entre escolas e entre municípios, lado a lado."""
    aplicar_estilo()
    fig, ax = plt.subplots(figsize=(9, 4.6))

    escolas = (df.groupby(["ano", "id_escola"], observed=True)[ALVO]
                 .agg(["mean", "size"]).query("size >= 20")["mean"].mul(100))
    municipios = (df.groupby(["ano", "id_municipio"], observed=True)[ALVO]
                    .agg(["mean", "size"]).query("size >= 30")["mean"].mul(100))

    bins = np.linspace(0, 100, 41)
    ax.hist(escolas, bins=bins, density=True, color=CATEGORICA[0], alpha=0.55,
            label=f"Escolas (n = {len(escolas):,})".replace(",", "."))
    ax.hist(municipios, bins=bins, density=True, color=CATEGORICA[1], alpha=0.55,
            label=f"Municípios (n = {len(municipios):,})".replace(",", "."))
    ax.axvline(df[ALVO].mean() * 100, color=TINTA_SECUNDARIA, ls="--", lw=1.5)
    ax.annotate(f"média nacional {df[ALVO].mean()*100:.1f}%",
                (df[ALVO].mean() * 100, ax.get_ylim()[1] * 0.92),
                xytext=(6, 0), textcoords="offset points",
                fontsize=9, color=TINTA_SECUNDARIA)
    ax.set_xlabel("Taxa de alfabetização da unidade (%)")
    ax.set_ylabel("Densidade")
    ax.legend(loc="upper left")
    titular(ax, "A variação entre escolas é maior — mas quase toda transitória",
            "distribuição das taxas observadas; escolas com ≥20 e municípios com ≥30 alunos")
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "02_dispersao_escolas_municipios")


# =============================================================================
# 2. Persistência do sinal — o achado central
# =============================================================================
def fig_persistencia(df: pd.DataFrame) -> tuple[str, dict]:
    """Correlação entre 2023 e 2024 da mesma unidade: escola x município."""
    aplicar_estilo()

    def pares(chave: str, minimo: int):
        g = (df.groupby(["ano", chave], observed=True)[ALVO]
               .agg(["mean", "size"]).reset_index())
        g = g[g["size"] >= minimo]
        largo = g.pivot(index=chave, columns="ano", values="mean").dropna()
        return largo

    escolas = pares("id_escola", 20)
    municipios = pares("id_municipio", 30)
    r_esc = stats.pearsonr(escolas[2023], escolas[2024])[0]
    r_mun = stats.pearsonr(municipios[2023], municipios[2024])[0]

    fig, eixos = plt.subplots(1, 2, figsize=(11, 5), sharex=True, sharey=True)
    for ax, dados, r, titulo, cor, n in [
        (eixos[0], escolas, r_esc, "Escola", CATEGORICA[0], len(escolas)),
        (eixos[1], municipios, r_mun, "Município", CATEGORICA[1], len(municipios)),
    ]:
        ax.scatter(dados[2023] * 100, dados[2024] * 100, s=6, alpha=0.18,
                   color=cor, edgecolors="none")
        ax.plot([0, 100], [0, 100], color=TINTA_SECUNDARIA, ls="--", lw=1.2)
        ax.set_xlabel("Taxa em 2023 (%)")
        titular(ax, f"{titulo} — r = {r:.2f}".replace(".", ","),
                f"n = {n:,}".replace(",", ".") + " unidades presentes nos dois anos")
        limpar_eixos(ax)
    eixos[0].set_ylabel("Taxa em 2024 (%)")
    eixos[0].set_xlim(0, 100)
    eixos[0].set_ylim(0, 100)
    fig.suptitle("O sinal municipal persiste; o escolar, não",
                 x=0.01, ha="left", fontsize=13, fontweight="bold")
    fig.tight_layout()
    caminho = salvar(fig, "03_persistencia_ano_a_ano")
    return caminho, {"r_escola": r_esc, "r_municipio": r_mun,
                     "n_escolas": len(escolas), "n_municipios": len(municipios)}


# =============================================================================
# 3. Correlações
# =============================================================================
def correlacoes_municipais(mun: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    """Correlação de Pearson de cada feature com a taxa municipal (ecológica)."""
    linhas = []
    for col in features:
        serie = mun[col]
        if not pd.api.types.is_numeric_dtype(serie) or serie.notna().sum() < 100:
            continue
        valido = serie.notna()
        if serie[valido].nunique() < 3:
            continue
        r, p = stats.pearsonr(serie[valido], mun.loc[valido, ALVO])
        linhas.append({"feature": col, "bloco": bloco_de(col), "r": r,
                       "p_valor": p, "n": int(valido.sum())})
    return (pd.DataFrame(linhas)
              .assign(abs_r=lambda d: d["r"].abs())
              .sort_values("abs_r", ascending=False)
              .drop(columns="abs_r")
              .reset_index(drop=True))


def fig_top_correlacoes(corr: pd.DataFrame, n: int = 18) -> str:
    """As features mais associadas à taxa municipal, coloridas pelo sinal."""
    aplicar_estilo()
    topo = corr.head(n).iloc[::-1]
    cores = [CATEGORICA[0] if r > 0 else CATEGORICA[7] for r in topo["r"]]

    fig, ax = plt.subplots(figsize=(9.5, 0.42 * n + 1.8))
    ax.barh(topo["feature"], topo["r"], color=cores, height=0.62)
    ax.axvline(0, color=TINTA_SECUNDARIA, lw=1)
    for y, (r, bloco) in enumerate(zip(topo["r"], topo["bloco"])):
        desloc = 4 if r > 0 else -4
        ax.annotate(f"{r:+.2f}".replace(".", ",") + f"  · {bloco}", (r, y),
                    xytext=(desloc, 0), textcoords="offset points",
                    va="center", ha="left" if r > 0 else "right",
                    fontsize=8, color=TINTA_SECUNDARIA)
    ax.set_xlim(-1.0, 1.0)
    ax.set_xlabel("Correlação de Pearson com a taxa municipal de alfabetização")
    titular(ax, f"As {n} variáveis mais associadas à alfabetização",
            "correlação ECOLÓGICA (grão do município) — azul positiva, vermelha negativa")
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "04_top_correlacoes")


def fig_decis(df: pd.DataFrame, features: list[str]) -> str:
    """Taxa de alfabetização por decil das principais variáveis contextuais.

    Curvas monotônicas indicam relação estável e aproveitável por qualquer modelo;
    curvas em U revelam não linearidade, que só um modelo flexível captura.
    """
    aplicar_estilo()
    features = [f for f in features if f in df.columns][:4]
    fig, eixos = plt.subplots(1, len(features), figsize=(3.4 * len(features), 4),
                              sharey=True)
    eixos = np.atleast_1d(eixos)

    for ax, col, cor in zip(eixos, features, CATEGORICA):
        sub = df[[col, ALVO]].dropna()
        if len(sub) < 1000:
            continue
        sub = sub.assign(decil=pd.qcut(sub[col], 10, labels=False, duplicates="drop"))
        perfil = sub.groupby("decil")[ALVO].mean().mul(100)
        ax.plot(perfil.index + 1, perfil.values, marker="o", color=cor)
        ax.set_xlabel("Decil")
        ax.set_xticks(range(1, 11, 3))
        titular(ax, col.replace("_", " "),
                f"amplitude {perfil.max() - perfil.min():.1f} p.p.".replace(".", ","))
        limpar_eixos(ax)
    eixos[0].set_ylabel("% alfabetizados")
    fig.tight_layout()
    return salvar(fig, "05_perfil_por_decil")


def fig_mapa(mun: pd.DataFrame) -> str:
    """Dispersão geográfica dos municípios, colorida pela taxa de alfabetização."""
    aplicar_estilo()
    dados = mun[(mun["ano"] == mun["ano"].max())
                & mun["ter_latitude"].notna()].copy()
    fig, ax = plt.subplots(figsize=(7.5, 7.5))
    pontos = ax.scatter(dados["ter_longitude"], dados["ter_latitude"],
                        c=dados[ALVO] * 100, s=7, cmap=SEQUENCIAL,
                        vmin=20, vmax=95, edgecolors="none")
    barra = fig.colorbar(pontos, ax=ax, shrink=0.6, pad=0.02)
    barra.set_label("% alfabetizados", color=TINTA_SECUNDARIA, fontsize=9)
    barra.outline.set_visible(False)
    ax.set_xlabel("Longitude")
    ax.set_ylabel("Latitude")
    ax.set_aspect("equal")
    ax.grid(color=GRADE, lw=0.5)
    titular(ax, f"Geografia da alfabetização — {int(dados['ano'].max())}",
            f"{len(dados):,}".replace(",", ".") +
            " municípios com ≥30 alunos avaliados; escala sequencial de um único matiz")
    limpar_eixos(ax, manter=())
    fig.tight_layout()
    return salvar(fig, "06_mapa_municipios")


def fig_ausencias(df: pd.DataFrame, features: list[str], n: int = 20) -> str:
    """Perfil de dados faltantes — a justificativa para a estratégia de imputação."""
    aplicar_estilo()
    faltantes = (df[features].isna().mean().mul(100)
                   .sort_values(ascending=False).head(n))
    faltantes = faltantes[faltantes > 0].iloc[::-1]
    if faltantes.empty:
        return ""
    fig, ax = plt.subplots(figsize=(9, 0.4 * len(faltantes) + 1.8))
    ax.barh(faltantes.index, faltantes.values, color=CATEGORICA[3], height=0.62)
    rotular_barras(ax, "{:.1f}%", horizontal=True)
    ax.set_xlabel("% de registros ausentes")
    ax.set_xlim(0, max(faltantes.max() * 1.18, 5))
    titular(ax, "Onde faltam dados",
            "ausência concentrada nas features defasadas: municípios que entraram "
            "na avaliação em 2024")
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "07_dados_ausentes")
