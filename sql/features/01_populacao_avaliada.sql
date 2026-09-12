-- features.populacao_avaliada — população de modelagem no grão ALUNO
--
-- DECISÃO ANALÍTICA (data leakage, parte 1 de 3):
-- Restringimos a população a alunos EFETIVAMENTE AVALIADOS
-- (presenca = TRUE AND preenchimento_caderno = TRUE). Verificação empírica na
-- silver.alunos (3.868.499 linhas):
--   presenca=FALSE                      -> 512.216 linhas, alfabetizado=TRUE em 0
--   presenca=TRUE, preenchimento=FALSE  ->   1.185 linhas, alfabetizado=TRUE em 0
--   ambos TRUE                          -> 3.355.098 linhas, alfabetizado=TRUE em 59,16%
-- Ou seja, fora da população avaliada o rótulo é DETERMINÍSTICO. Mantê-la
-- transformaria o modelo num detector de ausência (acurácia inflada, zero valor
-- pedagógico) e `presenca` seria uma feature de vazamento perfeito.
--
-- DECISÃO ANALÍTICA (data leakage, parte 2 de 3):
-- `proficiencia` NÃO é exportada. O alvo é exatamente `proficiencia >= 743`
-- (corte Saeb): 0 registros discordantes em 3,35 milhões. Usá-la daria AUC = 1,0
-- sem qualquer aprendizado.
--
-- Fonte de streaming (500 eventos sintéticos da Fase 2) é excluída: são dados
-- simulados, que contaminariam a avaliação de um modelo preditivo real.
CREATE OR REPLACE TABLE `{features}.populacao_avaliada`
PARTITION BY RANGE_BUCKET(ano, GENERATE_ARRAY(2023, 2031, 1))
CLUSTER BY id_municipio, id_escola
AS
SELECT
    a.ano,
    a.id_aluno,
    a.id_escola,
    a.id_municipio,
    a.sigla_uf,
    a.caderno,
    a.rede,
    a.peso_aluno,
    a.alfabetizado AS alvo_alfabetizado
FROM `{silver}.alunos` a
WHERE a.presenca
  AND a.preenchimento_caderno
  AND a.fonte = 'batch'
  AND a.alfabetizado IS NOT NULL
