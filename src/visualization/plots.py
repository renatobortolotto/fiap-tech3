"""Gráficos de avaliação, interpretabilidade e aplicação estratégica."""
from __future__ import annotations

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.calibration import calibration_curve
from sklearn.metrics import precision_recall_curve, roc_curve

from .estilo import (
    CATEGORICA,
    DIVERGENTE,
    STATUS,
    TINTA_SECUNDARIA,
    TINTA_SUAVE,
    aplicar_estilo,
    limpar_eixos,
    rotular_barras,
    salvar,
    titular,
)


# =============================================================================
# Avaliação
# =============================================================================
def fig_curvas(y, probabilidades: dict[str, np.ndarray], nome: str) -> str:
    """ROC, precisão-revocação e calibração, lado a lado.

    A terceira é a que costuma faltar e a que mais importa aqui: um modelo bem
    ordenado mas descalibrado leva o gestor a dimensionar errado o programa de apoio.
    """
    aplicar_estilo()
    fig, eixos = plt.subplots(1, 3, figsize=(14, 4.6))
    y = np.asarray(y).astype(int)

    limites_calibracao = [1.0, 0.0]
    for i, (modelo, p) in enumerate(probabilidades.items()):
        cor = CATEGORICA[i % len(CATEGORICA)]
        fpr, tpr, _ = roc_curve(y, p)
        eixos[0].plot(fpr, tpr, color=cor, label=modelo)
        prec, rev, _ = precision_recall_curve(y, p)
        eixos[1].plot(rev, prec, color=cor, label=modelo)
        obs, prev = calibration_curve(y, p, n_bins=20, strategy="quantile")
        eixos[2].plot(prev, obs, marker="o", ms=4, color=cor, label=modelo)
        limites_calibracao[0] = min(limites_calibracao[0], prev.min(), obs.min())
        limites_calibracao[1] = max(limites_calibracao[1], prev.max(), obs.max())

    eixos[0].plot([0, 1], [0, 1], ls="--", color=TINTA_SUAVE, lw=1.2)
    eixos[0].set_xlabel("Falsos positivos")
    eixos[0].set_ylabel("Verdadeiros positivos")
    titular(eixos[0], "Curva ROC", "capacidade de ordenação, independente do limiar")

    eixos[1].axhline(y.mean(), ls="--", color=TINTA_SUAVE, lw=1.2)
    eixos[1].set_xlabel("Revocação")
    eixos[1].set_ylabel("Precisão")
    titular(eixos[1], "Precisão x revocação", f"linha de base = taxa positiva ({y.mean():.1%})")

    eixos[2].plot([0, 1], [0, 1], ls="--", color=TINTA_SUAVE, lw=1.2)
    # Com o eixo em 0-1 o desvio é invisível: todas as probabilidades vivem numa
    # faixa estreita em torno da taxa-base. A janela é ajustada aos dados, com folga.
    folga = 0.04
    eixos[2].set_xlim(limites_calibracao[0] - folga, limites_calibracao[1] + folga)
    eixos[2].set_ylim(limites_calibracao[0] - folga, limites_calibracao[1] + folga)
    eixos[2].set_aspect("equal", adjustable="box")
    eixos[2].set_xlabel("Probabilidade prevista")
    eixos[2].set_ylabel("Frequência observada")
    titular(eixos[2], "Calibração",
            "sobre a diagonal = probabilidade confiável · eixo ajustado à faixa "
            "efetiva das previsões")

    for ax in eixos:
        ax.legend(loc="lower right" if ax is not eixos[1] else "upper right")
        limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, f"10_curvas_{nome}")


def fig_metricas_por_estrato(por_estrato: pd.DataFrame, nome: str) -> str:
    """ROC AUC por estrato de cobertura territorial.

    Devolve string vazia quando há um único estrato — caso do desenho espacial, em
    que a partição por município garante, por construção, que todo o teste caia em
    "município novo". Um gráfico de barra única não informa nada.
    """
    dados = por_estrato.drop(index="(total)", errors="ignore").copy()
    if len(dados) < 2:
        return ""
    aplicar_estilo()
    total = por_estrato.loc["(total)", "roc_auc"] if "(total)" in por_estrato.index else None

    fig, ax = plt.subplots(figsize=(8.5, 3.6))
    ax.barh(dados.index, dados["roc_auc"], color=CATEGORICA[0], height=0.55)
    for y, (auc, n) in enumerate(zip(dados["roc_auc"], dados["n"])):
        ax.annotate(f"{auc:.3f}".replace(".", ",")
                    + f"   ({int(n):,} alunos)".replace(",", "."),
                    (auc, y), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=9, color=TINTA_SECUNDARIA)
    if total is not None:
        ax.axvline(total, color=CATEGORICA[1], ls="--", lw=1.5)
        ax.annotate(f"total {total:.3f}".replace(".", ","),
                    (total, len(dados) - 0.4), xytext=(4, 0),
                    textcoords="offset points", fontsize=9, color=CATEGORICA[1])
    ax.set_xlim(0.5, max(0.75, dados["roc_auc"].max() * 1.25))
    ax.set_xlabel("ROC AUC")
    titular(ax, "Generalização não é uma coisa só",
            "desempenho separado por quanto o treino já conhecia o território")
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, f"11_estratos_{nome}")


# =============================================================================
# Interpretabilidade
# =============================================================================
def fig_importancia(imp: pd.DataFrame, coluna: str, titulo: str,
                    subtitulo: str, nome: str, n: int = 20) -> str:
    """Barras horizontais de importância, com o bloco temático como rótulo direto."""
    aplicar_estilo()
    topo = imp.head(n).iloc[::-1]
    fig, ax = plt.subplots(figsize=(9.5, 0.42 * n + 1.8))
    ax.barh(topo["feature"], topo[coluna], color=CATEGORICA[0], height=0.62)
    for y, (valor, bloco) in enumerate(zip(topo[coluna], topo["bloco"])):
        ax.annotate(f"{valor:.4f}".replace(".", ",") + f"  · {bloco}", (valor, y),
                    xytext=(5, 0), textcoords="offset points", va="center",
                    fontsize=8, color=TINTA_SECUNDARIA)
    ax.set_xlim(0, topo[coluna].max() * 1.55)
    titular(ax, titulo, subtitulo)
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, nome)


def fig_ablacao(ablacao: pd.DataFrame, margem_total: float | None = None) -> str:
    """Perda de AUC ao remover cada bloco temático inteiro.

    ``margem_total`` é a vantagem do modelo completo sobre o acaso (AUC − 0,5). Serve
    para calibrar a leitura: sem essa referência, o eixo auto-escalado faz diferenças
    de 0,001 parecerem grandes. Com ela, fica claro que nenhum bloco isolado responde
    por mais de ~1% do que o modelo sabe.
    """
    aplicar_estilo()
    completo = ablacao[ablacao["bloco"] == "(modelo completo)"]
    if margem_total is None and not completo.empty:
        margem_total = float(completo["roc_auc"].iloc[0]) - 0.5

    dados = ablacao[ablacao["bloco"] != "(modelo completo)"].copy()
    dados = dados.sort_values("queda_auc").tail(12)
    rotulos = dados["bloco"].str.replace("sem ", "", regex=False)
    cores = [CATEGORICA[0] if q > 0 else CATEGORICA[7] for q in dados["queda_auc"]]

    fig, ax = plt.subplots(figsize=(10, 0.46 * len(dados) + 2.2))
    ax.barh(rotulos, dados["queda_auc"], color=cores, height=0.58)
    ax.axvline(0, color=TINTA_SECUNDARIA, lw=1)

    limite = max(abs(dados["queda_auc"]).max(), 1e-6)
    for y, q in enumerate(dados["queda_auc"]):
        # Barras negativas recebem o rótulo à DIREITA do zero, onde a linha está
        # vazia — à esquerda ele colidiria com o nome do bloco no eixo.
        x, ha, desloc = (q, "left", 6) if q > 0 else (0.0, "left", 6)
        ax.annotate(f"{q:+.4f}".replace(".", ","), (x, y),
                    xytext=(desloc, 0), textcoords="offset points",
                    va="center", ha=ha, fontsize=8.5, color=TINTA_SECUNDARIA)
    ax.set_xlim(-limite * 1.25, limite * 1.45)
    ax.set_xlabel("Queda de ROC AUC ao remover o bloco e retreinar")

    subtitulo = ("ablação por bloco — imune à multicolinearidade, porque variáveis "
                 "redundantes saem juntas")
    if margem_total:
        subtitulo += (f"\nreferência de escala: a vantagem total do modelo sobre o "
                      f"acaso é {margem_total:.3f}".replace(".", ",")
                      + " — nenhum bloco isolado vale 1% disso")
    titular(ax, "Nenhum bloco de informação é insubstituível", subtitulo)
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "13_ablacao_por_bloco")


def fig_shap_resumo(valores, X_t, nome: str = "14_shap_resumo", n: int = 18) -> str:
    """Resumo SHAP (beeswarm): magnitude e direção do efeito de cada variável."""
    import shap

    aplicar_estilo()
    fig = plt.figure(figsize=(9.5, 0.42 * n + 2.2))
    shap.summary_plot(valores, X_t, max_display=n, show=False, plot_size=None,
                      cmap=DIVERGENTE)
    ax = plt.gca()
    ax.set_xlabel("Valor SHAP — contribuição para o log-odds de estar alfabetizado")
    titular(ax, "Como cada variável empurra a predição",
            "cada ponto é um aluno; a cor é o valor da variável (azul baixo, "
            "vermelho alto)")
    # A biblioteca rotula a barra de cor em inglês ("Feature value", "High", "Low");
    # traduzimos para manter o relatório inteiro em português.
    for eixo in fig.axes:
        if eixo is ax:
            continue
        if eixo.get_ylabel() == "Feature value":
            eixo.set_ylabel("Valor da variável", color=TINTA_SECUNDARIA, fontsize=9)
        eixo.set_yticks(eixo.get_ylim())
        eixo.set_yticklabels(["baixo", "alto"], fontsize=8, color=TINTA_SECUNDARIA)
    fig.tight_layout()
    return salvar(fig, nome)


# =============================================================================
# Aplicação estratégica
# =============================================================================
def fig_calibracao_municipal(ranking: pd.DataFrame, metricas: dict) -> str:
    """Taxa prevista x observada por município — a precisão que interessa ao gestor."""
    aplicar_estilo()
    fig, ax = plt.subplots(figsize=(6.8, 6.4))
    ax.scatter(ranking["taxa_prevista"] * 100, ranking["taxa_observada"] * 100,
               s=np.clip(ranking["n_alunos"] / 25, 4, 90),
               alpha=0.3, color=CATEGORICA[0], edgecolors="none")
    ax.plot([0, 100], [0, 100], ls="--", color=TINTA_SECUNDARIA, lw=1.3)
    ax.set_xlabel("Taxa municipal prevista (%)")
    ax.set_ylabel("Taxa municipal observada (%)")
    ax.set_xlim(10, 100)
    ax.set_ylim(0, 100)
    titular(ax, "No grão do município, a previsão é precisa",
            f"r = {metricas['correlacao']:.3f}".replace(".", ",")
            + f" · erro absoluto médio {metricas['erro_medio_absoluto_pp']:.1f} p.p."
              .replace(".", ",")
            + f" · {metricas['n_municipios']:,} municípios".replace(",", "."))
    ax.annotate("tamanho do ponto = nº de alunos avaliados", (0.03, 0.95),
                xycoords="axes fraction", fontsize=8, color=TINTA_SECUNDARIA)
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "20_calibracao_municipal")


def fig_residuos(ranking: pd.DataFrame, n: int = 12, coluna: str = "residuo_ajustado") -> str:
    """Municípios que mais superam e mais ficam abaixo dos seus pares estaduais.

    Usa por padrão o resíduo **ajustado pela UF**: o resíduo bruto confunde gestão
    municipal com deriva do estado inteiro entre os anos, e o Rio Grande do Sul — que
    caiu 18,9 p.p. — dominaria a lista por um motivo que nada tem a ver com as redes
    municipais gaúchas.
    """
    aplicar_estilo()
    if coluna not in ranking.columns:
        coluna = "residuo"
    validos = ranking[ranking["n_alunos"] >= 100].copy()
    piores = validos.nsmallest(n, coluna)
    melhores = validos.nlargest(n, coluna)
    dados = pd.concat([piores, melhores]).sort_values(coluna)
    rotulos = (dados["municipio"].astype(str).str.slice(0, 22)
               + " / " + dados["uf"].astype(str))
    cores = [STATUS["critico"] if r < 0 else STATUS["bom"] for r in dados[coluna]]

    fig, ax = plt.subplots(figsize=(9.5, 0.38 * len(dados) + 2))
    ax.barh(rotulos, dados[coluna] * 100, color=cores, height=0.6)
    ax.axvline(0, color=TINTA_SECUNDARIA, lw=1)
    for y, r in enumerate(dados[coluna] * 100):
        ax.annotate(f"{r:+.1f} p.p.".replace(".", ","), (r, y),
                    xytext=(5 if r > 0 else -5, 0), textcoords="offset points",
                    va="center", ha="left" if r > 0 else "right",
                    fontsize=8, color=TINTA_SECUNDARIA)
    ax.set_xlabel("Resíduo ajustado pela UF (pontos percentuais)")
    titular(ax, "Quem foge dos próprios pares estaduais",
            "observado menos previsto, descontada a mediana do resíduo da UF\n"
            "à esquerda, redes muito abaixo do que o contexto e o estado explicam; "
            "à direita, as que superam")
    limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "21_residuos_municipais")


def fig_grupos(perfil: pd.DataFrame, municipios: pd.DataFrame) -> str:
    """Perfis de município encontrados por agrupamento, e o desempenho de cada um."""
    aplicar_estilo()
    fig, eixos = plt.subplots(1, 2, figsize=(12.5, 4.4))

    taxas = perfil["taxa_observada"] * 100
    eixos[0].bar([f"Grupo {i}" for i in perfil.index], taxas,
                 color=[CATEGORICA[(i - 1) % len(CATEGORICA)] for i in perfil.index],
                 width=0.6)
    rotular_barras(eixos[0], "{:.1f}%")
    eixos[0].set_ylim(0, 100)
    eixos[0].set_ylabel("% alfabetizados")
    titular(eixos[0], "Desempenho por perfil de contexto",
            "o alvo ficou FORA do agrupamento — a taxa é resultado, não critério")

    tamanhos = perfil["n_municipios"]
    eixos[1].bar([f"Grupo {i}" for i in perfil.index], tamanhos,
                 color=[CATEGORICA[(i - 1) % len(CATEGORICA)] for i in perfil.index],
                 width=0.6)
    rotular_barras(eixos[1], "{:.0f}")
    eixos[1].set_ylabel("Municípios")
    titular(eixos[1], "Tamanho de cada grupo", "municípios com ≥30 alunos avaliados")

    for ax in eixos:
        limpar_eixos(ax)
    fig.tight_layout()
    return salvar(fig, "22_grupos_municipais")
