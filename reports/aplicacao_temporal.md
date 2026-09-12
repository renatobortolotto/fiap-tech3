# Aplicação estratégica — desenho `temporal`

## Por que agregar por município muda tudo

A predição individual de alfabetização tem teto baixo: o desfecho de uma criança depende de fatores que nenhum dado público municipal captura. Mas o erro individual em grande parte se **cancela na média** — e é a média municipal que orienta a decisão pública.

| métrica da previsão agregada por município | valor |
|---|---:|
| municípios avaliados (≥30 alunos) | 4.973 |
| correlação prevista × observada | **0,713** |
| erro absoluto médio | **10,6 p.p.** |
| erro mediano | 8,3 p.p. |
| viés | -3,28 p.p. |
| R² | 0,447 |

![calibração municipal](../images/20_calibracao_municipal.png)

## Quais municípios apresentam maior risco educacional

Risco = 1 − taxa prevista. Municípios com ao menos 100 alunos avaliados.

| município | UF | alunos | risco previsto | taxa observada |
|---|---|---:|---:|---:|
| Casa Nova | BA | 430 | 81,4% | 20,9% |
| Poço Redondo | SE | 345 | 80,4% | 26,7% |
| Goiatins | TO | 127 | 78,4% | 38,6% |
| Aporá | BA | 230 | 78,1% | 16,5% |
| Entre Rios | BA | 255 | 77,6% | 32,5% |
| Esplanada | BA | 359 | 76,0% | 24,0% |
| Ourolândia | BA | 141 | 76,0% | 34,0% |
| Araci | BA | 331 | 75,4% | 24,5% |
| Porto da Folha | SE | 228 | 75,4% | 17,5% |
| Jussara | BA | 122 | 75,3% | 43,4% |
| Rodelas | BA | 162 | 75,2% | 28,4% |
| Campos Lindos | TO | 148 | 75,2% | 38,5% |
| Pacatuba | SE | 106 | 75,0% | 30,2% |
| Canindé de São Francisco | SE | 460 | 74,9% | 27,0% |
| Canudos | BA | 156 | 74,8% | 30,1% |

## Quem foge do próprio contexto — a leitura acionável

O risco absoluto em geral apenas reflete a pobreza do território. O **resíduo** (observado − previsto) isola o que o contexto NÃO explica: resíduo muito negativo aponta problema de gestão; muito positivo aponta prática que merece ser estudada e replicada.

![resíduos](../images/21_residuos_municipais.png)

### Abaixo do esperado

| município | UF | alunos | observado | previsto | resíduo |
|---|---|---:|---:|---:|---:|
| Anapurus | MA | 109 | 33,9% | 82,8% | **-48,8 p.p.** |
| Uiraúna | PB | 124 | 45,2% | 89,6% | **-44,4 p.p.** |
| Pantano Grande | RS | 103 | 31,1% | 74,3% | **-43,2 p.p.** |
| São Marcos | RS | 152 | 44,7% | 84,0% | **-39,2 p.p.** |
| Pirapemas | MA | 103 | 41,7% | 79,2% | **-37,4 p.p.** |
| Taquari | RS | 226 | 26,5% | 63,8% | **-37,3 p.p.** |
| Constantina | RS | 105 | 49,5% | 83,8% | **-34,2 p.p.** |
| Marcação | PB | 129 | 21,7% | 55,8% | **-34,1 p.p.** |
| Parnarama | MA | 322 | 55,3% | 88,6% | **-33,4 p.p.** |
| Guaporé | RS | 240 | 49,6% | 81,8% | **-32,2 p.p.** |

### Acima do esperado

| município | UF | alunos | observado | previsto | resíduo |
|---|---|---:|---:|---:|---:|
| Tartarugalzinho | AP | 284 | 90,5% | 28,9% | **+61,5 p.p.** |
| Carlinda | MT | 121 | 99,2% | 45,9% | **+53,3 p.p.** |
| Capinzal do Norte | MA | 101 | 91,1% | 39,4% | **+51,6 p.p.** |
| Alagoa Nova | PB | 235 | 89,4% | 38,0% | **+51,3 p.p.** |
| São João do Arraial | PI | 115 | 87,8% | 39,3% | **+48,6 p.p.** |
| Corinto | MG | 231 | 85,7% | 45,9% | **+39,8 p.p.** |
| Jequiá da Praia | AL | 115 | 95,7% | 56,4% | **+39,3 p.p.** |
| Varjão de Minas | MG | 105 | 93,3% | 54,6% | **+38,8 p.p.** |
| Papagaios | MG | 134 | 89,6% | 51,3% | **+38,2 p.p.** |
| Fortaleza dos Nogueiras | MA | 194 | 78,9% | 42,7% | **+36,2 p.p.** |

## Quais regiões possuem padrões semelhantes

Agrupamento em 5 perfis por **contexto** (vulnerabilidade, demografia, INSE, docência, infraestrutura, financiamento). O alvo ficou deliberadamente de fora: assim a taxa de alfabetização de cada grupo é um resultado da análise, não o critério que a produziu.

![grupos](../images/22_grupos_municipais.png)

| grupo | municípios | % alfabetizados |
|---|---:|---:|
| 1 | 622 | 52,6% |
| 2 | 1.138 | 57,9% |
| 3 | 763 | 60,5% |
| 4 | 1.370 | 67,6% |
| 5 | 1.080 | 69,9% |

## Quais municípios podem não atingir a meta

A taxa municipal prevista é a média de indicadores de Bernoulli; sua distribuição amostral é aproximadamente normal, e a probabilidade de ficar abaixo da meta é Φ((meta − previsto) / erro-padrão).

| classificação | municípios |
|---|---:|
| provável cumprimento | 351 |
| atenção | 199 |
| risco alto | 418 |
| risco crítico | 1.502 |

| município | UF | meta | taxa prevista | prob. de não atingir |
|---|---|---:|---:|---:|
| Rio de Janeiro | RJ | 60,1% | 55,6% | **100,0%** |
| Ji-Paraná | RO | 80,0% | 64,8% | **100,0%** |
| Aparecida de Goiânia | GO | 63,9% | 55,8% | **100,0%** |
| Niterói | RJ | 56,6% | 47,3% | **100,0%** |
| Recife | PE | 65,3% | 59,2% | **100,0%** |
| Viamão | RS | 62,4% | 53,3% | **100,0%** |
| Porto Velho | RO | 67,5% | 61,5% | **100,0%** |
| Macapá | AP | 49,2% | 41,4% | **100,0%** |
| Salvador | BA | 45,5% | 40,6% | **100,0%** |
| Ponta Porã | MS | 61,5% | 50,6% | **100,0%** |
| Duque de Caxias | RJ | 52,5% | 45,5% | **100,0%** |
| Jaboatão dos Guararapes | PE | 61,0% | 53,8% | **100,0%** |
| Curitiba | PR | 71,9% | 66,2% | **100,0%** |
| Campo Grande | MS | 47,7% | 41,5% | **100,0%** |
| Várzea Grande | MT | 53,2% | 46,6% | **100,0%** |

> **Ressalva estatística.** O cálculo supõe independência condicional entre alunos. Como colegas de escola compartilham choques não observados, o erro-padrão real é maior e estas probabilidades são mais extremas do que deveriam. A **ordenação** é confiável; a magnitude, não.