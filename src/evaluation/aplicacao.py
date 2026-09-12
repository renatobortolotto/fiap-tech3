"""Aplicação estratégica: das probabilidades individuais à decisão pública.

Um modelo que prevê a alfabetização de uma criança com AUC 0,65 não serve para
decidir sobre aquela criança — mas as mesmas probabilidades, AGREGADAS por
município, são muito mais precisas. É a diferença entre prever uma moeda e prever a
proporção de caras em mil lançamentos: o erro individual é irredutível, o erro da
média encolhe com a raiz de n.

Este módulo faz essa ponte e responde às perguntas de negócio do desafio:

1. Quais fatores mais impactam a alfabetização?      -> `interpret.ablacao_por_bloco`
2. Quais municípios apresentam maior risco?          -> `ranking_risco_municipal`
3. Quais regiões possuem padrões semelhantes?        -> `agrupar_municipios`
4. Como prever quem não atingirá as metas?           -> `risco_de_nao_atingir_meta`
5. Quais variáveis mais influenciam os modelos?      -> `interpret.importancia_*`
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..common.config import RANDOM_STATE
from ..common.log import get_logger
from ..preprocessing.features import ALVO

logger = get_logger("evaluation.aplicacao")


# =============================================================================
# 2. Risco educacional municipal
# =============================================================================
def ranking_risco_municipal(
    teste: pd.DataFrame,
    probabilidades: np.ndarray,
    min_alunos: int = 30,
) -> pd.DataFrame:
    """Agrega as probabilidades individuais em um retrato de risco por município.

    Três leituras, deliberadamente distintas:

    * `taxa_prevista` — média das probabilidades. É o que o modelo espera do
      município dado o seu contexto.
    * `taxa_observada` — o que de fato ocorreu.
    * `residuo` — observado menos previsto.
    * `residuo_ajustado` — o resíduo menos a mediana do resíduo da própria UF. **É a
      coluna mais útil para política pública**, e não o risco absoluto nem o resíduo
      bruto: ela desconta a deriva estadual, que não é atribuível à gestão municipal. Um município pobre com taxa baixa é
      esperado; um município que vai MUITO PIOR do que seu contexto prevê tem um
      problema de gestão, não de pobreza — e esse é acionável. O resíduo positivo
      identifica o caminho inverso: redes que superam o próprio contexto e cujas
      práticas merecem ser estudadas.

    O erro-padrão da média vem da variância de Bernoulli das probabilidades
    previstas, e serve para não tratar como diferente um município de 30 alunos
    cuja oscilação é puro acaso.
    """
    dados = teste[["id_municipio", "nome_municipio", "sigla_uf", "ter_regiao", ALVO]].copy()
    # A ABT é carregada com colunas de texto em dtype `category` (economia de memória).
    # Categóricas não suportam concatenação nem agregação textual a jusante, e o grão
    # aqui é o município — a economia deixou de importar. Convertidas de volta a texto.
    for col in ("id_municipio", "nome_municipio", "sigla_uf", "ter_regiao"):
        if str(dados[col].dtype) == "category":
            dados[col] = dados[col].astype(str)
    dados["prob"] = np.asarray(probabilidades, dtype=float)

    agrupado = dados.groupby("id_municipio", observed=True).agg(
        municipio=("nome_municipio", "first"),
        uf=("sigla_uf", "first"),
        regiao=("ter_regiao", "first"),
        n_alunos=("prob", "size"),
        taxa_prevista=("prob", "mean"),
        taxa_observada=(ALVO, "mean"),
        variancia=("prob", lambda p: float(np.sum(p * (1 - p)))),
    )
    agrupado = agrupado[agrupado["n_alunos"] >= min_alunos].copy()
    agrupado["erro_padrao"] = np.sqrt(agrupado["variancia"]) / agrupado["n_alunos"]
    agrupado["residuo"] = agrupado["taxa_observada"] - agrupado["taxa_prevista"]
    # Resíduo padronizado: quantos erros-padrão o município está do esperado
    agrupado["residuo_z"] = agrupado["residuo"] / agrupado["erro_padrao"].replace(0, np.nan)
    agrupado["risco"] = 1 - agrupado["taxa_prevista"]

    # Resíduo LÍQUIDO DA DERIVA ESTADUAL. O resíduo bruto confunde duas coisas: o
    # desempenho do município frente ao próprio contexto, e o deslocamento de toda a
    # UF entre os anos. O caso é real: o Rio Grande do Sul caiu 18,9 p.p. entre 2023 e
    # 2024, e por isso municípios gaúchos dominam a lista dos piores resíduos brutos —
    # o que diz respeito ao estado, não à gestão de cada rede. Subtraindo a mediana do
    # resíduo da própria UF, o que sobra é o desvio do município em relação aos seus
    # pares estaduais. É esta a coluna com leitura de gestão.
    mediana_uf = agrupado.groupby("uf", observed=True)["residuo"].transform("median")
    agrupado["residuo_uf"] = mediana_uf
    agrupado["residuo_ajustado"] = agrupado["residuo"] - mediana_uf

    logger.info("Ranking municipal: %d municípios com >= %d alunos avaliados",
                len(agrupado), min_alunos)
    return (agrupado.drop(columns="variancia")
                    .sort_values("risco", ascending=False)
                    .reset_index())


def calibracao_agregada(ranking: pd.DataFrame) -> dict:
    """Quão bem a previsão agregada acerta a taxa municipal observada.

    Esta é a métrica que justifica o uso do modelo para decisão pública: mesmo
    quando a predição individual é modesta, a predição da TAXA municipal costuma
    ser boa, porque o erro individual em grande parte se cancela.
    """
    erro = ranking["taxa_prevista"] - ranking["taxa_observada"]
    return {
        "n_municipios": int(len(ranking)),
        "correlacao": float(ranking["taxa_prevista"].corr(ranking["taxa_observada"])),
        "erro_medio_absoluto_pp": float(erro.abs().mean() * 100),
        "erro_mediano_pp": float(erro.abs().median() * 100),
        "vies_pp": float(erro.mean() * 100),
        "r2": float(1 - (erro ** 2).sum()
                    / ((ranking["taxa_observada"] - ranking["taxa_observada"].mean()) ** 2).sum()),
    }


# =============================================================================
# 3. Agrupamento de municípios com padrões semelhantes
# =============================================================================
VARIAVEIS_PERFIL = [
    "ses_ivs", "ses_log_renda_per_capita", "ses_idhm_educacao",
    "ses_idade_mediana", "ses_share_pop_5a9", "ses_taxa_alfab_adultos_25a44",
    "ses_taxa_pbf", "inse_medio", "edu_tdi_anos_iniciais",
    "edu_docentes_superior_ai", "inf_pct_internet_aprendizagem",
    "inf_alunos_por_turma_ai", "fin_invest_aluno_ens_fund",
]


def agrupar_municipios(
    mun: pd.DataFrame,
    k: int = 5,
    variaveis: list[str] | None = None,
    random_state: int = RANDOM_STATE,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Agrupa municípios por PERFIL DE CONTEXTO, não por desempenho.

    O alvo fica deliberadamente fora do agrupamento: se entrasse, os grupos
    reproduziriam a taxa de alfabetização e não haveria o que descobrir. Excluído,
    a taxa observada de cada grupo vira um RESULTADO da análise — e a comparação
    entre grupos de contexto parecido revela quanto do desempenho não é explicado
    pelo contexto.

    Devolve (municípios com rótulo de grupo, perfil médio de cada grupo).
    """
    variaveis = [v for v in (variaveis or VARIAVEIS_PERFIL) if v in mun.columns]
    dados = mun.dropna(subset=["id_municipio"]).copy()

    modelo = make_pipeline(
        SimpleImputer(strategy="median"),
        StandardScaler(),
        KMeans(n_clusters=k, n_init=10, random_state=random_state),
    )
    dados["grupo"] = modelo.fit_predict(dados[variaveis])

    perfil = (dados.groupby("grupo")
                   .agg(n_municipios=("id_municipio", "size"),
                        taxa_observada=(ALVO, "mean"),
                        **{v: (v, "mean") for v in variaveis})
                   .sort_values("taxa_observada"))
    # Renumera os grupos do mais frágil ao mais favorável, para leitura direta
    ordem = {antigo: novo for novo, antigo in enumerate(perfil.index, start=1)}
    dados["grupo"] = dados["grupo"].map(ordem)
    perfil.index = [ordem[i] for i in perfil.index]
    perfil = perfil.sort_index()
    perfil.index.name = "grupo"

    logger.info("Agrupamento em %d perfis sobre %d variáveis de contexto", k, len(variaveis))
    return dados, perfil


# =============================================================================
# 4. Risco de não atingir a meta pactuada
# =============================================================================
def risco_de_nao_atingir_meta(
    ranking: pd.DataFrame,
    metas: pd.DataFrame,
    coluna_meta: str = "mun_lag_meta_ano_alvo",
) -> pd.DataFrame:
    """Probabilidade de o município ficar abaixo da meta pactuada.

    A taxa municipal prevista é a média de n indicadores de Bernoulli
    independentes condicionalmente às features; pelo Teorema Central do Limite sua
    distribuição amostral é aproximadamente normal com desvio `erro_padrao`. A
    probabilidade de ficar abaixo da meta é, então, Φ((meta − previsto) / erro).

    O pressuposto de independência condicional é otimista: alunos da mesma escola
    compartilham choques não observados, o que torna o erro-padrão real MAIOR que o
    calculado. Na prática, as probabilidades aqui são mais extremas (próximas de 0
    ou 1) do que deveriam — a ordenação é confiável, a magnitude deve ser lida com
    reserva. Está registrado nas limitações do README.
    """
    from scipy import stats

    df = ranking.merge(metas, on="id_municipio", how="left")
    meta = df[coluna_meta] / 100.0                   # metas vêm em pontos percentuais
    erro = df["erro_padrao"].replace(0, np.nan)
    df["meta"] = meta
    df["distancia_ate_meta_pp"] = (df["taxa_prevista"] - meta) * 100
    df["prob_nao_atingir"] = stats.norm.cdf((meta - df["taxa_prevista"]) / erro)
    df["classificacao"] = pd.cut(
        df["prob_nao_atingir"],
        bins=[-0.01, 0.20, 0.50, 0.80, 1.01],
        labels=["provável cumprimento", "atenção", "risco alto", "risco crítico"],
    )
    return df.sort_values("prob_nao_atingir", ascending=False)


def caracterizar_grupos(perfil: pd.DataFrame, n_variaveis: int = 4) -> pd.DataFrame:
    """Descreve cada grupo pelas variáveis em que ele mais se afasta da média geral.

    Um agrupamento sem caracterização é um rótulo sem conteúdo: saber que "o grupo 1
    alfabetiza 52,6%" não diz a um gestor o que esse grupo É. Aqui cada perfil é
    padronizado contra a média de todos os grupos, e reportamos as variáveis de maior
    desvio absoluto — as que efetivamente separam aquele grupo dos demais.
    """
    variaveis = [c for c in perfil.columns
                 if c not in ("n_municipios", "taxa_observada")]
    z = ((perfil[variaveis] - perfil[variaveis].mean()) /
         perfil[variaveis].std(ddof=0).replace(0, np.nan))

    linhas = []
    for grupo in perfil.index:
        desvios = z.loc[grupo].dropna().sort_values(key=abs, ascending=False)
        marcas = [f"{'↑' if desvios[v] > 0 else '↓'} {v}"
                  for v in desvios.index[:n_variaveis]]
        linhas.append({
            "grupo": grupo,
            "n_municipios": int(perfil.loc[grupo, "n_municipios"]),
            "taxa_observada": float(perfil.loc[grupo, "taxa_observada"]),
            "caracteristicas": " · ".join(marcas),
        })
    return pd.DataFrame(linhas).set_index("grupo")
