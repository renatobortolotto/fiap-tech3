# Análise exploratória

Gerado por `make eda`. Todos os números vêm da ABT (`features.abt_aluno`), não de amostras.

## 1. A base

- **3.354.661** alunos avaliados, em **5.547** municípios
- **139** features candidatas em **10** blocos temáticos (antes do descarte de colunas degeneradas, que o treino aplica: o Modelo A usa 125 e o Modelo B, 137)

| ano | alunos | % alfabetizados |
|---|---:|---:|
| 2023 | 1.502.809 | 58,4% |
| 2024 | 1.851.852 | 59,8% |

| bloco | nº de features |
|---|---:|
| município (socioeconômico) | 38 |
| educacional | 31 |
| escola (infraestrutura) | 23 |
| município (financiamento) | 16 |
| escola (socioeconômico) | 10 |
| município (educacional) | 9 |
| território | 6 |
| identificação geográfica | 2 |
| aluno | 2 |
| UF | 2 |

## 2. Onde está a variação

![distribuição do alvo](images/01_distribuicao_alvo.png)

![dispersão](images/02_dispersao_escolas_municipios.png)

## 3. O que persiste entre os anos

Correlação entre a taxa de 2023 e a de 2024 da mesma unidade:

| unidade | n | r |
|---|---:|---:|
| município | 4.277 | **0,705** |
| "escola" (chave renumerada) | 18.756 | 0,249 |

O valor da escola **não** mede persistência escolar: `id_escola` é renumerado a cada ano (só 2,4% dos identificadores presentes nos dois anos apontam para o mesmo município). Ver `docs/decisoes-analiticas.md` §3.

![persistência](images/03_persistencia_ano_a_ano.png)

## 4. Correlações

Medidas no grão do **município** (correlação ecológica — não pode ser lida como efeito individual).

| feature | bloco | r | n |
|---|---|---:|---:|
| `mun_lag_media_portugues` | município (educacional) | +0,701 | 4.342 |
| `mun_lag_taxa_observada` | município (educacional) | +0,700 | 4.368 |
| `mun_lag_taxa_oficial` | município (educacional) | +0,693 | 4.342 |
| `mun_lag_meta_ano_alvo` | município (educacional) | +0,682 | 4.201 |
| `mun_lag_nivel_alfabetizacao` | município (educacional) | +0,673 | 4.201 |
| `uf_lag_taxa` | UF | +0,622 | 4.950 |
| `uf_lag_ranking` | UF | -0,612 | 4.950 |
| `edu_ideb_ai_publica` | educacional | +0,602 | 9.013 |
| `edu_ideb_ai_publica_imputado` | educacional | +0,600 | 9.434 |
| `edu_ideb_ai_rede_do_aluno` | educacional | +0,590 | 8.918 |
| `edu_saeb5_media_lp` | educacional | +0,590 | 9.219 |
| `mun_lag_gap_meta_ano` | município (educacional) | +0,581 | 4.201 |

![correlações](images/04_top_correlacoes.png)

![decis](images/05_perfil_por_decil.png)

## 5. Geografia

![mapa](images/06_mapa_municipios.png)

## 6. Dados ausentes

![ausentes](images/07_dados_ausentes.png)
