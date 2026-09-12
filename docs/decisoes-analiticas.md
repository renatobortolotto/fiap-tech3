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
persistente entre anos; a escolar, quase não é:

| Unidade | Filtro | n | corr(2023, 2024) |
|---|---|---:|---:|
| Município | ≥ 200 avaliados/ano | 1.404 | **0,810** |
| Município | ≥ 50 avaliados/ano | 3.591 | 0,740 |
| Escola | ≥ 50 avaliados/ano | 3.486 | **0,215** |
| Escola | ≥ 20 avaliados/ano | 18.756 | 0,250 |

**Interpretação — o achado analítico central do projeto.** A dispersão bruta entre
escolas é grande (p10 = 26 % e p90 = 90 % de alfabetização em 2023), mas quase nada dela
sobrevive ao ano seguinte. A coorte do 2º ano de uma escola típica tem poucas dezenas de
alunos, e a taxa observada é dominada por ruído amostral. **O componente estruturalmente
previsível da alfabetização é municipal, não escolar.** Isso alinha o modelo à unidade em
que a política pública de fato opera — o município é quem gere a rede dos anos iniciais.

**Consequência de engenharia.** A taxa da escola em t-1 entra suavizada por *shrinkage*
empírico-bayesiano em direção à média do município
(`(alfabetizados + 30 · taxa_município) / (n + 30)`), acompanhada do tamanho da coorte,
para que o modelo possa descontar taxas medidas em coortes pequenas.

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

*(Seções seguintes — features externas, escolha de algoritmo e interpretação — são
acrescentadas conforme as etapas são concluídas.)*
