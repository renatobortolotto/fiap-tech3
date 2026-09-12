# Fontes de dados

Todas as fontes externas são públicas e foram acessadas via
[Base dos Dados](https://basedosdados.org) no BigQuery. Cada bloco de features tem
uma **política temporal explícita** — a coluna mais importante desta tabela, porque é
ela que separa contexto legítimo de vazamento.

## Base do projeto (Fase 2)

| Tabela | Grão | Papel |
|---|---|---|
| `silver.alunos` | aluno × ano | microdados do Indicador Criança Alfabetizada; origem do alvo |
| `silver.indicador_municipio` | município × ano × série × rede | indicador oficial INEP |
| `silver.metas_municipio` | município × ano | metas do Compromisso Nacional |
| `silver.dim_municipio` | município | dimensão territorial (IBGE) |
| `gold.panorama_uf` | UF × ano × rede | panorama estadual |

## Fontes externas

| Bloco | Fonte | Grão de junção | Política temporal | Cobertura medida |
|---|---|---|---|---|
| `inf_*` | `br_inep_censo_escolar.escola` | ano + município + rede | **mesmo ano** — a referência do Censo é a última quarta de maio; a prova é em novembro | 100,00% |
| `edu_*` (INEP) | `br_inep_indicadores_educacionais.municipio` | ano + município + rede | estruturais no mesmo ano; **rendimento defasado 1 ano** (só é apurado depois da prova) | 99,94% / 99,98% |
| `edu_*` (IDEB/SAEB) | `br_inep_ideb.municipio`, `.uf`, `br_inep_saeb.municipio` | ano + município + rede | **última edição divulgada antes da prova**: alvo 2023 → edição 2021; alvo 2024 → edição 2023 | 96,9% / 99,7% |
| `inse_*` | `br_inep_indicador_nivel_socioeconomico.escola` | ano + município + rede | mesma regra do IDEB: alvo 2023 → INSE 2021; alvo 2024 → INSE 2023 | 99,5% / 99,9% |
| `ses_*` (demografia) | `br_ibge_censo_2022.*` | município | estático, referência 31/07/2022 (anterior aos dois anos-alvo) | 100% |
| `ses_*` (economia) | `br_ibge_pib.municipio`, `br_ibge_populacao.municipio` | ano + município | **defasado 1 ano** — e obrigatoriamente: não existe PIB municipal de 2024 | 100% |
| `ses_*` (vulnerabilidade) | `br_ipea_avs.municipio`, `mundo_onu_adh.municipio` | município | Censo 2010, defasagem fixa de 13-14 anos | 99,91% |
| `ses_*` (transferências) | `br_mc_indicadores.transferencias_municipio` | município | exercício de 2020 | 100% |
| `ses_*` (PBF atual) | `br_cgu_beneficios_cidadao.novo_bolsa_familia` | ano + município | **contemporâneo**, competência de junho — condição socioeconômica preexistente, medida meses antes da prova | 100% |
| `fin_*` | `br_fnde_fundeb.indicador_*`, `br_me_siconfi.*` | ano + município | **exercício fiscal fechado anterior** (t-1) | 99,7% |
| `ter_*` | `silver.dim_municipio` | município | estático | 100% |

## Fontes avaliadas e descartadas

| Fonte | Motivo (verificado, não presumido) |
|---|---|
| `br_inep_censo_escolar.escola` **no grão da escola** | `id_escola` dos microdados não é código INEP: 0 de 42.811 casam |
| `br_inep_indicador_nivel_socioeconomico.escola` no grão da escola | idem — seria provavelmente a feature mais forte do projeto |
| `br_inep_saeb.aluno_ef_5ano` | tem INSE individual e escolaridade da mãe, mas a geografia está mascarada (prefixos inexistentes no IBGE) |
| `br_inep_censo_escolar.turma` / `.docente` / `.matricula` | views sobre *staging*; um único `GROUP BY` estoura o teto de 10 GiB |
| `br_ibge_censo_2022` — abastecimento de água | ~780 MiB (44% do custo do bloco) para correlação de 0,058 |
| `br_ipea_acesso_oportunidades` | cobre 20 municípios (0,36%) |
| `gold.desempenho_alunos` (Fase 2) | é um `GROUP BY` de `silver.alunos`; `pct_acima_corte_743` é a definição literal do alvo |
| `br_ibge_pib` — valor adicionado setorial | 100% NULL nas safras 2022 e 2023 |
| Indicadores SIOPE 39, 43, 46-49, 61, 62 | de 80% a 100% de zeros (o 61 é 100% zero) |
| `br_inep_ideb` no grão da escola | mesma limitação de chave |

## Custo

A materialização completa da feature store custa **cerca de 3,5 GiB** de dados
processados no BigQuery — bem dentro da franquia mensal gratuita de 1 TiB.

O `make features-dry` reporta **1,5 GiB**, e a diferença é instrutiva: duas fontes são
*views sobre armazenamento externo* (`br_cgu_beneficios_cidadao.novo_bolsa_familia` e
`br_fnde_fundeb.indicador_municipal`, esta última com segurança em nível de linha). O
dry run devolve **0 bytes** para elas — não porque sejam gratuitas, mas porque o
BigQuery não consegue estimá-las. O custo real, medido na execução, é de cerca de
1,9 GiB.

**A lição operacional:** um dry run que reporta 0 B numa view externa não é um sinal
verde. Nessas fontes, o controle de custo tem de vir do `maximum_bytes_billed`, que
aqui é de 10 GiB por consulta — foi ele que impediu a extração de
`br_inep_censo_escolar.docente` (13 GiB) de rodar por engano.
