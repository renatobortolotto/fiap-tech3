# Decisões analíticas

Registro das decisões de dados e modelagem do Tech Challenge Fase 3, cada uma com a
evidência empírica que a sustenta. Todos os números foram medidos sobre as tabelas do
projeto no BigQuery (`fiap-data-engineering`), não estimados.

---

## 1. A população de modelagem exclui alunos não avaliados

**Decisão.** O modelo é treinado apenas sobre alunos com `presenca = TRUE` e
`preenchimento_caderno = TRUE` — 3.354.661 dos 3.868.499 registros de `silver.alunos`.

**Evidência.** O rótulo `alfabetizado` é determinístico fora dessa população:

| `presenca` | `preenchimento_caderno` | registros | % alfabetizado |
|---|---|---:|---:|
| FALSE | FALSE | 512.216 | **0,00 %** |
| TRUE  | FALSE | 1.185 | **0,00 %** |
| TRUE  | TRUE  | 3.355.098 | 59,16 % |

**Por quê.** Quem não faz a prova não é classificado como alfabetizado. Se mantivéssemos
esses registros, `presenca` seria um preditor perfeito da classe negativa: o modelo
alcançaria acurácia alta aprendendo "faltou ⇒ não alfabetizado", que é uma tautologia
administrativa, não um achado pedagógico. A pergunta de negócio — *quais crianças correm
risco de não se alfabetizar* — só faz sentido entre as crianças efetivamente avaliadas.

**Consequência.** A taxa-base do problema passa de 51,3 % para 59,2 %, e o problema fica
aproximadamente balanceado — não é necessário reamostrar nem reponderar classes.

> **Ressalva registrada.** A ausência à prova é, ela própria, um sinal de risco
> educacional relevante. Ela não é ignorada no projeto: entra como *contexto agregado*
> (taxa de ausência do município em t-1), nunca como atributo do próprio aluno que está
> sendo classificado.

---

## 2. `proficiencia` é o alvo disfarçado e foi removida

**Decisão.** A coluna `proficiencia` não entra em nenhuma feature, em nenhum modelo.

**Evidência.** O alvo é *exatamente* `proficiencia >= 743` (corte Saeb de alfabetização).
Em 3.355.098 alunos avaliados:

- alunos com `alfabetizado = TRUE` e `proficiencia < 743`: **0**
- alunos com `alfabetizado = FALSE` e `proficiencia >= 743`: **0**

**Por quê.** Não há relação estatística a aprender — há uma identidade. Qualquer modelo
com essa variável atinge AUC = 1,0 e não generaliza para nada, porque em produção a
proficiência só existe *depois* da prova, que é o momento em que o alvo também já é
conhecido. É o caso-escola de *target leakage*.

**Também removidas pela mesma lógica:** `presenca` e `preenchimento_caderno`
(determinam a classe negativa, ver §1) e `id_aluno` (identificador sem poder
preditivo generalizável).

---

## 3. Todo contexto de desempenho é defasado em um ano

**Decisão.** Features derivadas de desempenho — taxa de alfabetização do município, da
escola, da UF — descrevem o ano **anterior** ao ano do aluno. A tabela
`features.ctx_municipio_lag` é chaveada por `ano_alvo`, e seu conteúdo vem de
`ano_alvo - 1`.

**Por quê.** A taxa de alfabetização do município no *mesmo* ano é literalmente a média
do alvo dos colegas daquele aluno: vazamento massivo. A defasagem também reproduz a
realidade operacional — um gestor que planeja 2024 conhece o resultado de 2023, não o de
2024.

**Evidência de que a defasagem preserva sinal.** A taxa municipal é fortemente
persistente entre anos:

| Unidade | Filtro | n | corr(2023, 2024) |
|---|---|---:|---:|
| Município | ≥ 200 avaliados/ano | 1.404 | **0,810** |
| Município | ≥ 50 avaliados/ano | 3.591 | 0,740 |

**Correção de rumo registrada.** A primeira medição também calculou a persistência
no grão da ESCOLA e encontrou r = 0,22 — que foi inicialmente interpretado como
"o desempenho escolar é instável porque as coortes do 2º ano são pequenas e a taxa
observada é dominada por ruído amostral". **Essa interpretação estava errada**, e a
verificação da chave mostrou por quê: `id_escola` é **renumerado a cada ano**. Dos
36.051 identificadores presentes em 2023 e 2024, apenas **864 (2,4%)** apontam para
o mesmo município; 80,6% apenas permanecem na mesma UF, porque a numeração é
reatribuída anualmente em blocos por unidade da federação.

Ou seja, unir os dois anos por `id_escola` conecta escolas **diferentes** que por
acaso receberam o mesmo número. O r = 0,22 não media persistência escolar: media um
efeito de UF disfarçado. O arquivo SQL da hipótese refutada foi preservado em
`docs/descartado/` com o registro completo.

**Conclusão que fica.** Os dados **não permitem nenhuma feature longitudinal no grão
da escola**. O único nível com histórico confiável é o município, cuja chave é o
código IBGE genuíno e estável. Isso reforça — agora por um caminho diferente — que a
unidade de análise deste projeto é o município.

**A dispersão entre escolas continua válida** e é grande (p10 = 26% e p90 = 90% de
alfabetização em 2023): dentro de um mesmo ano, `id_escola` agrupa corretamente os
alunos da mesma escola. O que não existe é a ponte entre os anos.

---

## 4. Dois desenhos de validação, porque 2023 não tem passado

**Restrição descoberta nos dados.** A cobertura das features defasadas é assimétrica:

| Ano dos alunos | alunos | contexto municipal t-1 | contexto escolar t-1 | meta pactuada | território |
|---|---:|---:|---:|---:|---:|
| 2023 | 1.502.809 | **0 %** | **0 %** | 0 % | 100 % |
| 2024 | 1.851.852 | 76,9 % | 79,0 % | 74,2 % | 100 % |

Não existe 2022 na base: nenhum aluno de 2023 pode ter histórico. Um único modelo com
histórico defasado descartaria 45 % dos dados e ficaria sem validação temporal.

**Decisão.** Dois modelos complementares, reportados lado a lado:

- **Modelo A — prospectivo (*out-of-time*).** Treino em 2023, teste em 2024. Usa apenas
  features disponíveis nos dois anos: território, infraestrutura escolar, nível
  socioeconômico, indicadores educacionais e socioeconômicos municipais. Responde
  *"o modelo sobrevive à passagem do tempo?"* — é a prova de generalização.
- **Modelo B — operacional.** Apenas 2024, acrescentando o histórico de t-1, com
  validação agrupada por município (*GroupKFold*) para medir generalização a municípios
  nunca vistos. Responde *"qual o teto de acerto quando o gestor tem o histórico em
  mãos?"*.

A diferença entre A e B quantifica exatamente **quanto vale ter memória histórica** na
predição — um resultado de interesse direto para política pública.

**O teste out-of-time não é só "um ano depois" — a geografia muda.** Três unidades da
federação aparecem apenas em 2024: **AC, DF e SP**. São 676 municípios novos e
**428.119 alunos, ou 23,1% do conjunto de teste**, sem qualquer presença em 2023. Há
também deriva real de nível nas UFs presentes nos dois anos: o Rio Grande do Sul cai
18,9 p.p. (64,7% -> 45,8%) e Minas Gerais sobe 11,7 p.p. (60,9% -> 72,6%).

Consequência para a avaliação: a métrica do teste de 2024 mistura duas coisas
diferentes — *generalização temporal* (UFs já vistas, um ano depois) e *extrapolação
geográfica* (UFs nunca vistas). Por isso as métricas são reportadas **estratificadas**
nos dois grupos, além do total. Um número único aqui esconderia qual das duas
capacidades o modelo realmente tem.

**Os 23 % de alunos de 2024 sem histórico municipal** não são descartados: são municípios
que entraram na avaliação em 2024. Recebem imputação explícita mais um indicador binário
de ausência, para que o modelo trate "sem histórico" como uma categoria informativa e não
como um valor plausível.

---

## 5. Dados de streaming da Fase 2 ficam fora do treino

**Decisão.** `fonte = 'streaming'` é excluída da população de modelagem (500 registros).

**Por quê.** São eventos *sintéticos*, gerados pelo produtor Pub/Sub da Fase 2 para
demonstrar a ingestão near-real-time. Incluí-los contaminaria a avaliação com dados
artificiais. A camada de streaming continua válida como demonstração de arquitetura; não
é fonte de verdade para um modelo preditivo.

---

---

## 6. O identificador de escola é anônimo: todo enriquecimento externo é municipal

**Descoberta.** `silver.alunos.id_escola` **não é o código INEP da escola**. É uma
chave substituta densa, de `60000001` a `60042811` (42.811 escolas), com prefixo único
`"60"` — enquanto códigos INEP reais começam pelo código IBGE da UF (11 = RO, 31 = MG…).
O `id_municipio`, em contraste, é IBGE genuíno de 7 dígitos (26 prefixos de UF distintos).

**Verificação.** Cruzando os 42.811 identificadores contra
`basedosdados.br_inep_censo_escolar.escola` (2023): **0 correspondências**. O INEP
anonimizou a escola nos microdados de alfabetização.

**Consequências.**

1. Fontes externas com grão escolar — INSE por escola, infraestrutura do Censo Escolar,
   indicadores educacionais por escola, IDEB por escola — **não podem ser ligadas ao
   aluno**. O INSE por escola seria provavelmente a feature socioeconômica mais forte
   do projeto, e foi perdido por essa limitação da fonte.
2. O contorno adotado: **agregar as fontes escolares ao grão (ano, município, rede)**,
   que é ligável com cobertura de 100 %. Perde-se a variação entre escolas de um mesmo
   município; preserva-se a variação entre municípios — que, como mostra §3, é justamente
   a parcela estruturalmente previsível do fenômeno.
3. O histórico da própria escola (`esc_lag_*`) continua disponível, porque é calculado
   *dentro* da base, onde a chave substituta é consistente entre 2023 e 2024.

Esta é uma limitação da fonte, não uma escolha de projeto, e está registrada como tal na
seção de limitações do README.

*(Seções seguintes — features externas, escolha de algoritmo e interpretação — são
acrescentadas conforme as etapas são concluídas.)*
