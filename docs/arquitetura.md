# Arquitetura

## Visão geral

A Fase 3 não reimplementa a engenharia de dados: ela **consome** a camada Gold
construída na Fase 2 e acrescenta uma camada de *feature store* e uma camada de
modelagem.

```
                      ┌──────────────────────────────────────┐
  FASE 2 (existente)  │  bronze  →  silver  →  gold  │ ops   │
                      └──────────────┬───────────────────────┘
                                     │  BigQuery (US)
                      ┌──────────────▼───────────────────────┐
  FASE 3 · dados      │  features.*   (11 tabelas)           │
                      │  ├ populacao_avaliada  (grão aluno)  │
                      │  ├ ctx_municipio_lag   (t-1)         │
                      │  ├ ctx_territorio                    │
                      │  ├ ext_censo_escolar                 │
                      │  ├ ext_indicadores_educacionais      │
                      │  ├ ext_inse                          │
                      │  ├ ext_ideb_saeb                     │
                      │  ├ ext_ibge                          │
                      │  ├ ext_vulnerabilidade               │
                      │  ├ ext_financas                      │
                      │  └ abt_aluno   (3.354.661 × 145)     │
                      └──────────────┬───────────────────────┘
                                     │  EXPORT DATA → GCS → Parquet
                      ┌──────────────▼───────────────────────┐
  FASE 3 · modelagem  │  data/processed/abt_aluno.parquet    │
                      │         ↓                            │
                      │  sklearn Pipeline                    │
                      │   ├ ColumnTransformer                │
                      │   │   ├ numéricas → imputação +      │
                      │   │   │   indicador de ausência      │
                      │   │   ├ categóricas → one-hot        │
                      │   │   └ alta cardinalidade →         │
                      │   │       TargetEncoder (CV interna) │
                      │   └ estimador                        │
                      └──────────────┬───────────────────────┘
                                     │
                      ┌──────────────▼───────────────────────┐
  FASE 3 · saídas     │  models/  reports/  images/          │
                      └──────────────────────────────────────┘
```

## Por que o pesado fica no BigQuery

Toda a junção e agregação — 3,3 milhões de alunos contra dez tabelas de contexto,
algumas com bilhões de linhas — roda no BigQuery, não em pandas. Três razões:

1. **Volume.** `br_inep_censo_escolar.escola` tem 4 milhões de linhas e 455 colunas
   (6,2 GiB). Baixá-la para agregar localmente seria absurdo; agregada no BigQuery ao
   grão município × rede, ela vira 20 mil linhas.
2. **Custo controlado.** O BigQuery é colunar: selecionar 25 das 455 colunas custa
   proporcionalmente. Cada consulta roda com `maximum_bytes_billed = 10 GiB` como
   trava, e `make features-dry` estima antes de gastar.
3. **Reprodutibilidade.** Cada tabela é um `CREATE OR REPLACE TABLE` versionado em
   `sql/features/`. Rodar `make features` do zero reconstrói tudo de forma idêntica.

O Parquet local existe só para a modelagem: 3,35 milhões de linhas por 145 colunas
cabem em 37 MiB comprimidos e são lidas em segundos, o que permite dezenas de
experimentos sem custo de consulta.

## O caminho BigQuery → disco

`EXPORT DATA` para o GCS em Parquet, seguido de download — e não a API REST de
resultados, que pagina e consome memória. A exportação inteira leva ~20 segundos.

Duas travas obrigatórias, ambas aprendidas na prática:

- **O prefixo do GCS é limpo antes de cada exportação.** `overwrite = true` só
  sobrescreve os arquivos que a exportação atual escreve; partes remanescentes de uma
  exportação anterior sobrevivem e entram no `glob` do download. Isso ocorreu: uma
  parte de esquema antigo somou 46.482 linhas à ABT local e ressuscitou quatro
  colunas já removidas.
- **A contagem de linhas do Parquet é conferida contra a tabela de origem**, e a
  extração falha se divergir.

## Convenção de prefixos

O nome da coluna carrega o bloco temático, o que torna trivial ligar e desligar
blocos inteiros nos experimentos de ablação e identificar de relance a origem de
qualquer feature:

| prefixo | bloco | defasagem |
|---|---|---|
| `alu_` | atributos do aluno | — |
| `inf_` | infraestrutura e porte da rede escolar | mesmo ano (Censo de maio) |
| `inse_` | nível socioeconômico das escolas | última edição publicada |
| `edu_` | indicadores educacionais, IDEB e SAEB | mista (ver `fontes-de-dados.md`) |
| `mun_lag_` | contexto educacional do município | t-1, obrigatória |
| `ses_` | socioeconômico do município | estática ou t-1 |
| `fin_` | financiamento da educação | exercício fiscal t-1 |
| `ter_` | território | estática |
| `uf_lag_` | contexto da UF | t-1, obrigatória |

Os prefixos `mun_lag_` e `uf_lag_` não são decorativos: `selecionar_features()` os
usa para **remover automaticamente** todo o histórico no desenho out-of-time, onde
ele não existe. A convenção é o mecanismo de segurança, não só documentação.

## Camadas de código

```
src/
├── common/          configuração, cliente BigQuery, logging, geração de notebooks
├── preprocessing/   metadados de features, pipeline sklearn, construção da feature store
├── modeling/        dataset e partições, catálogo de candidatos, treino, Optuna
├── evaluation/      métricas e bootstrap, interpretabilidade, aplicação estratégica
└── visualization/   estilo, EDA e gráficos de avaliação
```

Os notebooks em `notebooks/` são gerados por `make notebooks` a partir de
`src/common/gerar_notebooks.py` e apenas **chamam** esses módulos. A lógica não mora
na célula: assim ela é testável, reutilizável entre etapas e imune ao problema de
células executadas fora de ordem.

## Reprodutibilidade

```bash
make setup                                        # venv + dependências
export GCP_ACCESS_TOKEN=$(gcloud auth print-access-token)
make features-dry                                 # valida os SQLs e estima o custo
make tudo                                         # feature store → ABT → EDA → modelos → relatórios
make testes                                       # 13 testes, incluindo os de antivazamento
```

A semente aleatória (`random_state = 42`) está centralizada em `config/config.yaml` e
é propagada a todo estimador, partição e reamostragem de bootstrap.
