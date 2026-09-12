"""Identidade visual dos gráficos do projeto.

A paleta não foi escolhida por gosto: é uma paleta categórica validada para
daltonismo (separação CVD ΔE >= 8 em OKLab entre pares adjacentes) e para contraste
mínimo contra a superfície clara. As cores são atribuídas SEMPRE na mesma ordem de
slot — nunca cicladas — de modo que a mesma entidade tenha a mesma cor em todos os
gráficos do relatório.

Três papéis distintos de cor, que nunca se misturam:

* **Categórica** — identidade (rede, região, modelo). Ordem fixa de slots.
* **Sequencial** — magnitude (taxa de alfabetização num mapa). Um único matiz,
  claro -> escuro.
* **Divergente** — polaridade (acima/abaixo da meta). Dois matizes opostos com
  cinza neutro no meio; nunca um matiz no ponto neutro.

Três slots categóricos (aqua, amarelo, magenta) ficam abaixo de 3:1 de contraste
contra o fundo claro; por isso os gráficos que os usam trazem rótulo direto ou
legenda explícita — identidade nunca depende só da cor.
"""
from __future__ import annotations

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

# --- Superfície e tinta ------------------------------------------------------
SUPERFICIE = "#fcfcfb"
TINTA_PRIMARIA = "#0b0b0b"
TINTA_SECUNDARIA = "#52514e"
TINTA_SUAVE = "#8a8985"
GRADE = "#e8e7e3"

# --- Categórica (ordem fixa de slots) ----------------------------------------
CATEGORICA = [
    "#2a78d6",  # 1 azul
    "#eb6834",  # 2 laranja
    "#1baf7a",  # 3 aqua
    "#eda100",  # 4 amarelo
    "#e87ba4",  # 5 magenta
    "#008300",  # 6 verde
    "#4a3aa7",  # 7 violeta
    "#e34948",  # 8 vermelho
]

# --- Sequencial (azul, claro -> escuro) --------------------------------------
SEQUENCIAL_STEPS = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5",
                    "#256abf", "#184f95", "#0d366b"]
SEQUENCIAL = LinearSegmentedColormap.from_list("azul_seq", SEQUENCIAL_STEPS)

# --- Divergente (azul <-> vermelho, cinza neutro) ----------------------------
DIVERGENTE = LinearSegmentedColormap.from_list(
    "azul_vermelho", ["#0d366b", "#3987e5", "#cde2fb", "#f0efec",
                      "#f6c9c8", "#e34948", "#8f2120"]
)

# --- Status (reservadas; nunca usadas como "série 4") ------------------------
STATUS = {"bom": "#008300", "atencao": "#eda100",
          "grave": "#eb6834", "critico": "#e34948"}


def aplicar_estilo() -> None:
    """Aplica o estilo global do projeto ao matplotlib."""
    mpl.rcParams.update({
        "figure.facecolor": SUPERFICIE,
        "axes.facecolor": SUPERFICIE,
        "savefig.facecolor": SUPERFICIE,
        "savefig.bbox": "tight",
        "savefig.dpi": 150,
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "text.color": TINTA_PRIMARIA,
        "axes.labelcolor": TINTA_SECUNDARIA,
        "axes.edgecolor": GRADE,
        "axes.linewidth": 1.0,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.titlecolor": TINTA_PRIMARIA,
        "axes.titlepad": 12,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": GRADE,
        "grid.linewidth": 0.8,
        "xtick.color": TINTA_SECUNDARIA,
        "ytick.color": TINTA_SECUNDARIA,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "lines.linewidth": 2.0,
        "lines.markersize": 8,
        "patch.linewidth": 0,
    })


def num(valor: float, casas: int = 1, sinal: bool = False) -> str:
    """Formata um número no padrão brasileiro (vírgula decimal).

    Existe porque a forma ingênua — `f"{x:.1f} p.p.".replace(".", ",")` — também
    troca os pontos da abreviatura, produzindo "10,6 p,p,". O erro apareceu três
    vezes em gráficos diferentes antes de virar esta função.
    """
    formato = f"{{:+.{casas}f}}" if sinal else f"{{:.{casas}f}}"
    return formato.format(valor).replace(".", ",")


def limpar_eixos(ax, manter=("left", "bottom")) -> None:
    """Remove as bordas supérfluas: a grade já dá a referência de leitura."""
    for lado, spine in ax.spines.items():
        spine.set_visible(lado in manter)


def rotular_barras(ax, formato="{:.0f}", deslocamento=3, horizontal=False) -> None:
    """Rótulo direto no fim de cada barra, com vírgula decimal (pt-BR).

    Obrigatório nos gráficos que usam os slots de menor contraste: a identidade
    do dado não pode depender só da cor.
    """
    def _fmt(v):
        return formato.format(v).replace(".", ",")

    for barra in ax.patches:
        if horizontal:
            valor = barra.get_width()
            ax.annotate(_fmt(valor),
                        (valor, barra.get_y() + barra.get_height() / 2),
                        xytext=(deslocamento, 0), textcoords="offset points",
                        va="center", ha="left", fontsize=8, color=TINTA_SECUNDARIA)
        else:
            valor = barra.get_height()
            ax.annotate(_fmt(valor),
                        (barra.get_x() + barra.get_width() / 2, valor),
                        xytext=(0, deslocamento), textcoords="offset points",
                        ha="center", va="bottom", fontsize=8, color=TINTA_SECUNDARIA)


def titular(ax, titulo: str, subtitulo: str | None = None) -> None:
    """Título em negrito com subtítulo explicativo em tinta secundária.

    O espaçamento acompanha o número de linhas do subtítulo: com `pad` fixo, um
    subtítulo de duas linhas invade o título.
    """
    if not subtitulo:
        ax.set_title(titulo, loc="left")
        return
    n_linhas = subtitulo.count("\n") + 1
    ax.set_title(titulo, loc="left", pad=12 + 13 * n_linhas)
    ax.text(0, 1.015, subtitulo, transform=ax.transAxes, fontsize=9,
            color=TINTA_SECUNDARIA, va="bottom", ha="left", linespacing=1.35)


def salvar(fig, nome: str, pasta=None) -> str:
    """Salva a figura em images/ e devolve o caminho."""
    from ..common.config import IMAGES_DIR
    destino = (pasta or IMAGES_DIR) / f"{nome}.png"
    fig.savefig(destino)
    plt.close(fig)
    return str(destino)
