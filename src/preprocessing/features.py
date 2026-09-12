"""Metadados das features: blocos, papéis e política de vazamento.

As colunas da ABT seguem uma convenção de prefixo que identifica o BLOCO de origem.
Isso mantém a engenharia de atributos legível e torna trivial ligar/desligar blocos
inteiros nos experimentos de ablação.

    alu_*    atributos do próprio aluno (poucos: a base de microdados é enxuta)
    inf_*    infraestrutura e porte da escola (Censo Escolar)
    inse_*   nível socioeconômico da escola (INSE/INEP)
    edu_*    indicadores educacionais da escola/município (INEP)
    mun_*    contexto do município — `mun_lag_*` exige defasagem temporal
    ses_*    socioeconômico do município (IBGE, IPEA)
    fin_*    financiamento educacional do município (FNDE/FUNDEB, SICONFI)
    ter_*    território (região, coordenadas, capital, Amazônia Legal)
    uf_*     contexto da unidade da federação — `uf_lag_*` exige defasagem
"""
from __future__ import annotations

# --- Alvo --------------------------------------------------------------------
ALVO = "alvo_alfabetizado"

# --- Identificadores: nunca são features -------------------------------------
# `id_aluno` e `id_escola` são identificadores sem poder generalizável; usá-los
# como categoria faria o modelo memorizar indivíduos e escolas do próprio ano.
# `ano` é constante dentro de cada desenho de treino. `nome_municipio` é rótulo
# de exibição (redundante com `id_municipio`).
IDENTIFICADORES = ["ano", "id_aluno", "id_escola", "nome_municipio"]

# --- Colunas proibidas (data leakage) ----------------------------------------
# Ver docs/decisoes-analiticas.md §2. Nunca entram em nenhum modelo.
VAZADAS = [
    "proficiencia",            # o alvo é exatamente proficiencia >= 743
    "presenca",                # presenca = FALSE => alfabetizado = FALSE sempre
    "preenchimento_caderno",   # idem
]

# --- Artefatos do desenho amostral -------------------------------------------
# `alu_peso_amostral` é o peso do desenho amostral do INEP, não um atributo da
# criança. Dois motivos para deixá-lo fora, o segundo decisivo:
#
# 1. Semântico — descreve como a amostra foi construída, não a aluna ou o aluno.
#    Serve para ponderar estatísticas descritivas, não para prever um desfecho.
# 2. Empírico — a metodologia de ponderação MUDOU entre os dois anos: 2023 tem
#    13.185 valores distintos com mínimo 0,095; 2024 tem 540 valores distintos com
#    mínimo 1,0. No desenho out-of-time isso é deriva de covariável pura: o modelo
#    aprenderia em 2023 uma relação que não existe em 2024.
#
# Verificado que NÃO é vazamento (correlação com o alvo de -0,045 em 2023 e -0,066
# em 2024) — a exclusão é por rigor metodológico, não por contaminação.
ARTEFATOS_AMOSTRAIS = ["alu_peso_amostral"]

# --- Categóricas de alta cardinalidade ---------------------------------------
# Recebem TargetEncoder, cujo `fit_transform` do scikit-learn faz o encoding
# FORA-DA-DOBRA (validação cruzada interna) — o antídoto para o vazamento
# clássico dessa técnica.
#
# `id_municipio` merece uma observação: no Modelo A (treino 2023 -> teste 2024),
# codificá-lo pelo alvo equivale a injetar a taxa municipal de 2023 nas linhas de
# 2024. Como treino e teste são disjuntos NO TEMPO, isso é uma defasagem legítima,
# e é justamente assim que o Modelo A captura o efeito municipal sem usar as
# colunas `mun_lag_*` (que não existem para 2023). Ver docs/decisoes-analiticas.md §4.
CATEGORICAS_ALTA_CARDINALIDADE = ["id_municipio", "sigla_uf", "ter_mesorregiao"]

# --- Prefixos que dependem de histórico defasado -----------------------------
# Só existem para alunos de 2024 (não há 2022 na base). O Modelo A NÃO pode
# usá-los; o Modelo B (operacional, 2024) usa.
#
# Não há prefixo de escola aqui: `id_escola` é renumerado a cada ano (só 2,4% dos
# identificadores presentes nos dois anos apontam para o mesmo município), o que
# torna impossível qualquer feature longitudinal escolar. Ver docs §3.
PREFIXOS_DEFASADOS = ("mun_lag_", "uf_lag_")

_MAPA_BLOCOS = {
    "alu_": "aluno",
    "inf_": "escola (infraestrutura)",
    "inse_": "escola (socioeconômico)",
    "edu_": "educacional",
    "mun_": "município (educacional)",
    "ses_": "município (socioeconômico)",
    "fin_": "município (financiamento)",
    "ter_": "território",
    "uf_": "UF",
}


def bloco_de(coluna: str) -> str:
    """Bloco temático de uma coluna, a partir do prefixo."""
    for prefixo, bloco in _MAPA_BLOCOS.items():
        if coluna.startswith(prefixo):
            return bloco
    if coluna in CATEGORICAS_ALTA_CARDINALIDADE:
        return "identificação geográfica"
    return "outros"


def blocos(colunas: list[str]) -> dict[str, list[str]]:
    """Agrupa as colunas por bloco temático (ordem estável, blocos vazios omitidos)."""
    saida: dict[str, list[str]] = {}
    for col in colunas:
        saida.setdefault(bloco_de(col), []).append(col)
    return saida


def selecionar_features(
    colunas: list[str],
    permitir_defasadas: bool = True,
    blocos_excluidos: tuple[str, ...] = (),
) -> list[str]:
    """Colunas utilizáveis como feature.

    Remove alvo, identificadores, colunas vazadas e artefatos do desenho amostral. Quando ``permitir_defasadas``
    é False (Modelo A, out-of-time), remove também tudo que depende de histórico
    t-1 — inexistente para os alunos de 2023. ``blocos_excluidos`` recebe prefixos
    e serve aos experimentos de ablação por bloco.
    """
    descartar = (set(IDENTIFICADORES) | {ALVO} | set(VAZADAS)
                 | set(ARTEFATOS_AMOSTRAIS))
    feats = [c for c in colunas if c not in descartar]
    if not permitir_defasadas:
        feats = [c for c in feats if not c.startswith(PREFIXOS_DEFASADOS)]
    if blocos_excluidos:
        feats = [c for c in feats if not c.startswith(blocos_excluidos)]
    return feats


def descartar_degeneradas(
    X_treino,
    features: list[str],
) -> tuple[list[str], dict[str, str]]:
    """Remove features sem informação NO CONJUNTO DE TREINO.

    Duas patologias, ambas encontradas de fato neste projeto:

    * **100% ausente** — `proporcao_aluno_nivel_0..8` do INEP é NULL em todo o ano
      de 2023, e as colunas de valor adicionado do PIB municipal ainda não foram
      publicadas para 2022/2023. Uma coluna assim não só não informa nada: quebra
      o `SimpleImputer`, que não tem valor algum de onde calcular a mediana.
    * **Constante** — `meta_alfabetizacao_2030` vale 80,0 para os 5.352 municípios.
      Variância zero, contribuição zero, e ainda ocupa espaço na interpretação.

    A decisão é tomada OLHANDO SÓ O TREINO e depois aplicada ao teste — descartar
    com base na base inteira seria uma forma sutil de vazamento.
    """
    descartadas: dict[str, str] = {}
    mantidas: list[str] = []
    for col in features:
        serie = X_treino[col]
        if serie.isna().all():
            descartadas[col] = "100% ausente no treino"
        elif serie.nunique(dropna=True) <= 1:
            descartadas[col] = "constante no treino (variância zero)"
        else:
            mantidas.append(col)
    return mantidas, descartadas
