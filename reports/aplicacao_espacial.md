# Aplicação estratégica — desenho `espacial`

## Por que agregar por município muda tudo

A predição individual de alfabetização tem teto baixo: o desfecho de uma criança depende de fatores que nenhum dado público municipal captura. Mas o erro individual em grande parte se **cancela na média** — e é a média municipal que orienta a decisão pública.

| métrica da previsão agregada por município | valor |
|---|---:|
| municípios avaliados (≥30 alunos) | 1.253 |
| correlação prevista × observada | **0,797** |
| erro absoluto médio | **10,3 p.p.** |
| erro mediano | 9,2 p.p. |
| viés | -0,93 p.p. |
| R² | 0,536 |

![calibração municipal](../images/20_calibracao_municipal.png)

## Quais municípios apresentam maior risco educacional

Risco = 1 − taxa prevista. Municípios com ao menos 100 alunos avaliados.

| município | UF | alunos | risco previsto | taxa observada |
|---|---|---:|---:|---:|
| Muquém de São Francisco | BA | 118 | 67,2% | 22,0% |
| Coaraci | BA | 115 | 62,6% | 39,1% |
| Pacatuba | SE | 106 | 62,0% | 30,2% |
| Coronel João Sá | BA | 111 | 61,4% | 36,0% |
| Pilão Arcado | BA | 391 | 61,2% | 22,5% |
| Porto da Folha | SE | 228 | 60,5% | 17,5% |
| Ibititá | BA | 100 | 60,2% | 28,0% |
| São Francisco do Conde | BA | 342 | 59,6% | 25,7% |
| Buerarema | BA | 140 | 59,4% | 28,6% |
| Aporá | BA | 230 | 59,4% | 16,5% |
| Itarantim | BA | 112 | 59,3% | 41,1% |
| Campo Alegre de Lourdes | BA | 189 | 59,3% | 28,0% |
| Aurelino Leal | BA | 122 | 59,2% | 33,6% |
| Cachoeira | BA | 242 | 59,1% | 33,1% |
| Paratinga | BA | 233 | 58,9% | 24,5% |

## Quem foge do próprio contexto — a leitura acionável

O risco absoluto em geral apenas reflete a pobreza do território. O **resíduo** (observado − previsto) isola o que o contexto NÃO explica: resíduo muito negativo aponta problema de gestão; muito positivo aponta prática que merece ser estudada e replicada.

![resíduos](../images/21_residuos_municipais.png)

### Abaixo do esperado

| município | UF | alunos | observado | previsto | resíduo |
|---|---|---:|---:|---:|---:|
| Anapurus | MA | 109 | 33,9% | 66,2% | **-32,3 p.p.** |
| Taquari | RS | 226 | 26,5% | 55,7% | **-29,2 p.p.** |
| Matias Cardoso | MG | 112 | 31,2% | 58,7% | **-27,5 p.p.** |
| Oiapoque | AP | 384 | 21,4% | 48,4% | **-27,0 p.p.** |
| Miguelópolis | SP | 155 | 31,0% | 57,6% | **-26,7 p.p.** |
| Escada | PE | 406 | 30,8% | 56,5% | **-25,7 p.p.** |
| Jacareacanga | PA | 187 | 26,2% | 51,7% | **-25,5 p.p.** |
| Buriti | MA | 251 | 29,1% | 53,6% | **-24,5 p.p.** |
| Matões | MA | 269 | 34,2% | 58,6% | **-24,4 p.p.** |
| Ouricuri | PE | 510 | 31,4% | 55,6% | **-24,2 p.p.** |

### Acima do esperado

| município | UF | alunos | observado | previsto | resíduo |
|---|---|---:|---:|---:|---:|
| Atalaia do Norte | AM | 164 | 84,1% | 46,1% | **+38,1 p.p.** |
| Lagoa Grande do Maranhão | MA | 106 | 97,2% | 62,6% | **+34,6 p.p.** |
| Taperoá | PB | 123 | 91,1% | 63,2% | **+27,9 p.p.** |
| Maracaí | SP | 110 | 90,9% | 63,1% | **+27,8 p.p.** |
| Uruana | GO | 132 | 97,7% | 71,7% | **+26,1 p.p.** |
| Buenos Aires | PE | 124 | 85,5% | 60,2% | **+25,3 p.p.** |
| Magalhães de Almeida | MA | 144 | 81,9% | 57,2% | **+24,7 p.p.** |
| Panelas | PE | 237 | 94,5% | 70,0% | **+24,5 p.p.** |
| Água Branca | PI | 187 | 92,0% | 67,9% | **+24,1 p.p.** |
| Santana do Cariri | CE | 172 | 96,5% | 72,7% | **+23,8 p.p.** |

## Quais regiões possuem padrões semelhantes

Agrupamento em 5 perfis por **contexto** (vulnerabilidade, demografia, INSE, docência, infraestrutura, financiamento). O alvo ficou deliberadamente de fora: assim a taxa de alfabetização de cada grupo é um resultado da análise, não o critério que a produziu.

![grupos](../images/22_grupos_municipais.png)

| grupo | municípios | % alfabetizados |
|---|---:|---:|
| 1 | 191 | 51,7% |
| 2 | 367 | 58,8% |
| 3 | 1 | 59,6% |
| 4 | 321 | 65,3% |
| 5 | 373 | 69,4% |

## Quais municípios podem não atingir a meta

A taxa municipal prevista é a média de indicadores de Bernoulli; sua distribuição amostral é aproximadamente normal, e a probabilidade de ficar abaixo da meta é Φ((meta − previsto) / erro-padrão).

| classificação | municípios |
|---|---:|
| provável cumprimento | 229 |
| atenção | 69 |
| risco alto | 69 |
| risco crítico | 263 |

| município | UF | meta | taxa prevista | prob. de não atingir |
|---|---|---:|---:|---:|
| Lajeado | RS | 75,5% | 56,5% | **100,0%** |
| Apucarana | PR | 80,0% | 67,8% | **100,0%** |
| Cambé | PR | 79,2% | 64,9% | **100,0%** |
| Caxias do Sul | RS | 70,9% | 53,8% | **100,0%** |
| Viamão | RS | 62,4% | 53,2% | **100,0%** |
| Venâncio Aires | RS | 78,4% | 59,7% | **100,0%** |
| Londrina | PR | 74,8% | 63,9% | **100,0%** |
| Rio de Janeiro | RJ | 60,1% | 55,5% | **100,0%** |
| Sapiranga | RS | 73,9% | 57,6% | **100,0%** |
| Vila Velha | ES | 70,0% | 62,1% | **100,0%** |
| Fazenda Rio Grande | PR | 70,7% | 61,6% | **100,0%** |
| Francisco Beltrão | PR | 79,7% | 67,7% | **100,0%** |
| Panambi | RS | 76,0% | 59,5% | **100,0%** |
| Barbalha | CE | 80,0% | 66,5% | **100,0%** |
| Brusque | SC | 70,5% | 61,1% | **100,0%** |

> **Ressalva estatística.** O cálculo supõe independência condicional entre alunos. Como colegas de escola compartilham choques não observados, o erro-padrão real é maior e estas probabilidades são mais extremas do que deveriam. A **ordenação** é confiável; a magnitude, não.