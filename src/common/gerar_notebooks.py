"""Gera os notebooks a partir dos módulos de `src/`.

Os notebooks são DELIBERADAMENTE finos: eles narram a análise e chamam funções que
vivem em `src/`. A lógica não mora na célula.

O motivo é prático, não estético. Um notebook com a lógica embutida não é testável,
não é reutilizável entre as etapas e — o problema mais sério num projeto de ML —
permite que células rodem fora de ordem, produzindo resultados que não se
reproduzem. Mantendo a lógica em módulos versionados, o notebook vira o que deve
ser: o relato executável da análise, e `make tudo` continua sendo a fonte da verdade.

Uso:
    ./venv/bin/python -m src.common.gerar_notebooks
"""
from __future__ import annotations

import sys

import nbformat as nbf

from .config import REPO_ROOT
from .log import get_logger

logger = get_logger("common.gerar_notebooks")
NOTEBOOKS = REPO_ROOT / "notebooks"

PREAMBULO = """import sys, warnings
from pathlib import Path
sys.path.insert(0, str(Path.cwd().parent))
warnings.filterwarnings("ignore", category=FutureWarning)

# O acesso ao BigQuery exige o token de curta duração:
#   export GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)
"""


def _md(texto: str) -> nbf.NotebookNode:
    return nbf.v4.new_markdown_cell(texto)


def _code(codigo: str) -> nbf.NotebookNode:
    return nbf.v4.new_code_cell(codigo.strip())


def _salvar(nb: nbf.NotebookNode, nome: str) -> str:
    nb.metadata["kernelspec"] = {"display_name": "Python 3", "language": "python",
                                 "name": "python3"}
    nb.metadata["language_info"] = {"name": "python", "version": "3.10"}
    destino = NOTEBOOKS / nome
    destino.parent.mkdir(parents=True, exist_ok=True)
    nbf.write(nb, destino)
    logger.info("Notebook gerado: %s", destino)
    return str(destino)


# =============================================================================
def notebook_eda() -> str:
    nb = nbf.v4.new_notebook(cells=[
        _md("""# 1 · Análise exploratória

**Tech Challenge Fase 3 — Predição e inteligência analítica para alfabetização**

Este notebook percorre a análise exploratória que sustenta as decisões de modelagem.
As funções vêm de `src/visualization/eda.py`; aqui está a narrativa.

Pergunta de fundo: *onde está a variação da alfabetização, e qual parte dela é
previsível a partir de dados públicos?*"""),
        _code(PREAMBULO + """
from src.modeling.dataset import carregar_abt
from src.preprocessing.features import ALVO, blocos, selecionar_features
from src.visualization import eda

df = carregar_abt()
features = selecionar_features(list(df.columns))
df.shape, len(features)"""),
        _md("""## A base

`features.abt_aluno` tem um registro por aluno **efetivamente avaliado** — quem faltou
à prova foi excluído, porque para esses o rótulo é determinístico (ver
`docs/decisoes-analiticas.md` §1) e o modelo aprenderia apenas a detectar ausência."""),
        _code("""for bloco, cols in sorted(blocos(features).items(), key=lambda kv: -len(kv[1])):
    print(f"{bloco:32} {len(cols):3d} features")

df.groupby("ano")[ALVO].agg(alunos="size", taxa="mean")"""),
        _md("## Distribuições: por ano, rede e região"),
        _code("""eda.fig_distribuicao_alvo(df)"""),
        _md("""## Onde está a dispersão

A variação entre escolas é maior que entre municípios — mas, como a próxima seção
mostra, quase toda ela é transitória."""),
        _code("""eda.fig_dispersao_unidades(df)"""),
        _md("""## O que persiste de um ano para o outro

Este é o achado que determina o desenho do projeto: **a taxa municipal é altamente
persistente (r ≈ 0,81)**.

O valor calculado para "escola" (r ≈ 0,22) **não** mede persistência escolar:
`id_escola` é renumerado a cada ano — só 2,4% dos identificadores presentes em 2023 e
2024 apontam para o mesmo município. Unir os anos por essa chave liga escolas
diferentes. Por isso nenhuma feature longitudinal de escola entra no projeto."""),
        _code("""caminho, persistencia = eda.fig_persistencia(df)
persistencia"""),
        _md("""## Correlações

Medidas no grão do **município**. No grão do aluno, uma variável municipal é constante
dentro do município e sua correlação é diluída pelo ruído individual. A leitura
municipal é uma correlação **ecológica**: descreve diferenças entre redes de ensino,
e não pode ser lida como efeito sobre um indivíduo."""),
        _code("""mun = eda.agregar_municipio(df)
corr = eda.correlacoes_municipais(mun, features)
corr.head(20)"""),
        _code("""eda.fig_top_correlacoes(corr)"""),
        _md("""## Formato da relação

Decis das variáveis mais associadas ao alvo. Curvas monotônicas indicam relação
estável; curvas em U revelam não linearidade, que só um modelo flexível captura."""),
        _code("""principais = [c for c in corr.head(6)["feature"] if c in df.columns][:4]
eda.fig_decis(df, principais)"""),
        _md("## Geografia"),
        _code("""eda.fig_mapa(mun)"""),
        _md("""## Dados ausentes

A ausência se concentra nas features defasadas e **não é aleatória**: marca municípios
que entraram na avaliação em 2024. Por isso a imputação vem acompanhada de um
indicador binário de ausência — "sem histórico" é informação, não ruído."""),
        _code("""eda.fig_ausencias(df, features)"""),
        _md("""## Hipóteses que a exploração sustenta

1. **O componente previsível é municipal.** A persistência entre anos existe no
   município (r = 0,81) e não há como medi-la na escola.
2. **Contexto socioeconômico e demográfico pesa mais que infraestrutura escolar.**
   As correlações mais fortes são demográficas e de vulnerabilidade, não de
   equipamento.
3. **A predição individual terá teto baixo e a agregada será boa.** A variação
   dentro de um mesmo município é grande e não observável com dados públicos; a
   média municipal, ao contrário, é bem determinada.
4. **O teste de 2024 mistura duas capacidades**: generalizar no tempo e extrapolar
   para UFs novas (AC, DF, SP). As métricas precisam ser estratificadas."""),
    ])
    return _salvar(nb, "01_analise_exploratoria.ipynb")


# =============================================================================
def notebook_modelagem() -> str:
    nb = nbf.v4.new_notebook(cells=[
        _md("""# 2 · Modelagem supervisionada

Pipeline completa de Machine Learning: tratamento, engenharia de atributos,
transformação, tratamento de vazamento, integração do pré-processamento ao modelo,
treinamento e validação.

**Dois desenhos**, porque são duas perguntas de generalização diferentes:

| | Modelo A — temporal | Modelo B — espacial |
|---|---|---|
| treino | 2023 | 75% dos municípios de 2024 |
| teste | 2024 | 25% dos municípios restantes |
| histórico t-1 | indisponível (não há 2022) | disponível |
| pergunta | sobrevive à passagem do tempo? | vale para municípios nunca vistos? |"""),
        _code(PREAMBULO + """
from src.modeling.dataset import carregar_abt, split_temporal, split_espacial
from src.preprocessing.features import ALVO, descartar_degeneradas, selecionar_features
from src.preprocessing.pipeline import resumo_preprocessamento
from src.modeling import candidatos, train

df = carregar_abt()
treino, teste = split_temporal(df)
len(treino), len(teste)"""),
        _md("""## Tratamento de data leakage

Três exclusões, todas medidas e não presumidas:

1. `proficiencia` — o alvo é **exatamente** `proficiencia >= 743`: 0 discordâncias em
   3,35 milhões de alunos.
2. `presenca` e `preenchimento_caderno` — determinam a classe negativa (513.401
   registros, 0% alfabetizados).
3. Todo contexto de desempenho é **defasado em um ano**. E as metas do Compromisso
   Nacional entram nessa regra: elas correlacionam **0,968** com o resultado de 2023,
   porque foram calculadas a partir dele."""),
        _code("""features = selecionar_features(list(df.columns), permitir_defasadas=False)
features, descartadas = descartar_degeneradas(treino, features)
print(f"{len(features)} features")
descartadas"""),
        _md("""## Pré-processamento integrado ao modelo

Imputação, escalonamento e encoding são **estimadores**: têm parâmetros aprendidos.
Aplicá-los ao dataframe inteiro antes do split faria a mediana de imputação e as
médias do target encoding enxergarem o teste. Dentro de um `Pipeline`, cada `fit`
acontece só na dobra de treino."""),
        _code("""resumo_preprocessamento(treino[features]).head(25)"""),
        _md("""## Os candidatos

Três famílias, para que a escolha final seja defendida por evidência: uma referência
trivial (piso), um modelo linear interpretável (contraprova) e ensembles de árvores
por boosting (estado da arte em dados tabulares)."""),
        _code("""for nome, (est, escalonar, desc) in candidatos.CANDIDATOS.items():
    print(f"{nome:12} {type(est).__name__:32} {desc}")"""),
        _md("## Modelo A — validação out-of-time"),
        _code("""resultado_a = train.executar("temporal")
resultado_a["metricas"].round(4)"""),
        _md("""### Por estrato de cobertura territorial

Três UFs (AC, DF, SP) aparecem só em 2024 — 23,1% do conjunto de teste. Um número
único misturaria *generalização temporal* com *extrapolação geográfica*."""),
        _code("""resultado_a["por_estrato"].round(4)"""),
        _md("## Modelo B — validação espacial (municípios nunca vistos)"),
        _code("""resultado_b = train.executar("espacial")
resultado_b["metricas"].round(4)"""),
        _md("""## Comparação estatística

Duas AUCs diferentes não bastam: é preciso saber se a diferença excede a incerteza
amostral. O bootstrap **pareado** usa as mesmas reamostragens nos dois modelos,
eliminando a variância comum."""),
        _code("""from src.evaluation.metrics import comparar_bootstrap, ic_bootstrap

y = resultado_a["teste"][ALVO].astype(int).to_numpy()
probs = resultado_a["probabilidades"]
reais = [m for m in resultado_a["metricas"].index if m != "referencia"]
vencedor = reais[0]

for m in reais:
    v, lo, hi = ic_bootstrap(y, probs[m])
    print(f"{m:12} ROC AUC = {v:.4f}  IC 95% [{lo:.4f}, {hi:.4f}]")

print()
for m in reais[1:]:
    r = comparar_bootstrap(y, probs[m], probs[vencedor])
    print(f"{vencedor} - {m:12} = {r['diferenca']:+.4f}  p = {r['p_valor']:.3f}")"""),
        _md("""O resultado é um **empate estatístico**: a vantagem do LightGBM sobre a
regressão logística não é distinguível da incerteza amostral (p ≈ 0,09). O teto é
imposto pelos dados, não pelo algoritmo — ver §5 e §8.1 do README."""),
        _md("""## Otimização de hiperparâmetros

A busca roda sob **validação cruzada agrupada por município**. Sem o agrupamento, o
hiperparâmetro vencedor seria o que melhor MEMORIZA a média municipal — o oposto do
objetivo. O espaço de busca é de regularização, não de capacidade."""),
        _code("""# Demora alguns minutos; descomente para executar.
# from src.modeling import tune
# melhor_config = tune.executar("temporal", n_tentativas=40)
# melhor_config"""),
    ])
    return _salvar(nb, "02_modelagem.ipynb")


# =============================================================================
def notebook_aplicacao() -> str:
    nb = nbf.v4.new_notebook(cells=[
        _md("""# 3 · Interpretabilidade e aplicação estratégica

Duas perguntas: **por que** o modelo decide o que decide, e **o que fazer** com isso."""),
        _code(PREAMBULO + """
import joblib
from src.common.config import MODELS_DIR
from src.modeling.dataset import carregar_abt, split_temporal
from src.preprocessing.features import ALVO, descartar_degeneradas, selecionar_features
from src.evaluation import interpret, aplicacao
from src.visualization import eda, plots

df = carregar_abt()
treino, teste = split_temporal(df)
features = selecionar_features(list(df.columns), permitir_defasadas=False)
features, _ = descartar_degeneradas(treino, features)
pipeline = joblib.load(MODELS_DIR / "modelo_temporal.joblib")
type(pipeline.named_steps["modelo"]).__name__"""),
        _md("""## Quatro leituras de importância

Elas têm vieses diferentes de propósito. Quando discordam, a discordância informa:
importância nativa alta com permutação baixa indica variável usada para ajustar ruído."""),
        _code("""interpret.importancia_nativa(pipeline, top=20)"""),
        _code("""permut = interpret.importancia_permutacao(pipeline, teste[features],
                                          teste[ALVO].astype(int).to_numpy())
permut.head(20)"""),
        _md("""### SHAP

O único método que responde *"por que ESTE aluno foi classificado como em risco?"* —
a pergunta do gestor diante de uma lista de prioridades."""),
        _code("""valores, X_t, esperado = interpret.valores_shap(pipeline, teste[features])
plots.fig_shap_resumo(valores, X_t)"""),
        _md("""### Ablação por bloco

A leitura que sobrevive à multicolinearidade: variáveis que medem a mesma coisa
(IVS, renda, IDHM) saem juntas, então a queda observada é contribuição real."""),
        _code("""from src.modeling.candidatos import obter
from src.modeling.train import amostrar
est, escalonar, _ = obter("lightgbm")
ablacao = interpret.ablacao_por_bloco(amostrar(treino, 400_000), teste, features,
                                      est, escalonar=escalonar)
ablacao"""),
        _md("""## Da probabilidade individual à decisão pública

A predição individual tem teto baixo — o desfecho de uma criança depende de fatores
que nenhum dado público municipal captura. Mas o erro individual se cancela na média,
e é a média municipal que orienta a política."""),
        _code("""prob = pipeline.predict_proba(teste[features])[:, 1]
ranking = aplicacao.ranking_risco_municipal(teste, prob)
calib = aplicacao.calibracao_agregada(ranking)
calib"""),
        _code("""plots.fig_calibracao_municipal(ranking, calib)"""),
        _md("""### A coluna acionável: o resíduo ajustado pela UF

O risco absoluto em geral só reflete a pobreza do território. O **resíduo**
(observado − previsto) isola o que o contexto não explica.

Mas o resíduo bruto tem um defeito que apareceu na prática: **confunde gestão
municipal com deriva do estado inteiro**. Como o Rio Grande do Sul caiu 18,9 p.p.
entre 2023 e 2024, municípios gaúchos ocupavam 4 das 10 piores posições — por um
motivo que nada tem a ver com as redes municipais. A coluna usada é o
`residuo_ajustado`: o resíduo menos a mediana do resíduo da própria UF."""),
        _code("""plots.fig_residuos(ranking)"""),
        _code("""ranking[ranking["n_alunos"] >= 100].nsmallest(10, "residuo_ajustado")[
    ["municipio", "uf", "n_alunos", "taxa_observada", "taxa_prevista",
     "residuo", "residuo_ajustado"]]"""),
        _md("""## Regiões com padrões semelhantes

Agrupamento por **contexto**, com o alvo deliberadamente de fora — assim a taxa de
alfabetização de cada grupo é um resultado da análise, não o critério que a produziu."""),
        _code("""mun = eda.agregar_municipio(teste)
municipios, perfil = aplicacao.agrupar_municipios(mun, k=5)
perfil[["n_municipios", "taxa_observada"]]"""),
        _code("""plots.fig_grupos(perfil, municipios)"""),
        _md("""## Municípios em risco de não atingir a meta

A taxa municipal prevista é a média de indicadores de Bernoulli; sua distribuição
amostral é aproximadamente normal, e a probabilidade de ficar abaixo da meta é
Φ((meta − previsto) / erro-padrão).

**Ressalva:** o cálculo supõe independência condicional entre alunos. Como colegas de
escola compartilham choques não observados, o erro-padrão real é maior — a ordenação é
confiável, a magnitude não."""),
        _code("""# Requer o desenho espacial (as metas são features defasadas, ausentes em 2023).
# Ver reports/aplicacao_espacial.md"""),
    ])
    return _salvar(nb, "03_interpretabilidade_e_aplicacao.ipynb")


def main() -> int:
    notebook_eda()
    notebook_modelagem()
    notebook_aplicacao()
    return 0


if __name__ == "__main__":
    sys.exit(main())
