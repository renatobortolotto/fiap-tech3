-- features.ext_censo_escolar — infraestrutura e porte da rede escolar do município
-- Fonte: `basedosdados.br_inep_censo_escolar.escola` (INEP).
--
-- GRÃO DE JOIN (ano, id_municipio, rede) — e não a escola. Motivo em
-- docs/decisoes-analiticas.md §6: o `id_escola` dos microdados de alfabetização é
-- uma chave anonimizada, sem correspondência com o código INEP (0 de 42.811 casam).
-- Agregamos, então, o retrato da rede municipal que atende os anos iniciais.
--
-- SEM VAZAMENTO TEMPORAL, mesmo usando o MESMO ano: a data de referência do Censo
-- Escolar é a última quarta-feira de maio, enquanto a prova de alfabetização é
-- aplicada em novembro. A informação existe antes do desfecho.
--
-- Agregações ponderadas pelas MATRÍCULAS dos anos iniciais, não pela contagem de
-- escolas: uma escola de 800 alunos não pode pesar o mesmo que uma de 20 ao
-- descrever a realidade que a criança média encontra.
--
-- Universo: escolas em atividade (`tipo_situacao_funcionamento = '1'`) que ofertam
-- anos iniciais. As situações 2 e 3 (paralisada/extinta) têm 100% de nulos nos campos
-- de infraestrutura e contaminariam as médias.
CREATE OR REPLACE TABLE `{features}.ext_censo_escolar` AS
WITH base AS (
    SELECT
        ano,
        id_municipio,
        CASE rede
            WHEN '1' THEN 'Federal' WHEN '2' THEN 'Estadual'
            WHEN '3' THEN 'Municipal' WHEN '4' THEN 'Privada'
        END AS rede,
        COALESCE(quantidade_matricula_fundamental_anos_iniciais, 0) AS mat_ai,
        COALESCE(quantidade_turma_fundamental_anos_iniciais, 0)     AS tur_ai,
        COALESCE(quantidade_docente_fundamental_anos_iniciais, 0)   AS doc_ai,
        COALESCE(quantidade_matricula_fundamental_anos_iniciais_integral, 0) AS mat_ai_int,
        COALESCE(quantidade_desktop_aluno, 0)
            + COALESCE(quantidade_computador_portatil_aluno, 0)
            + COALESCE(quantidade_tablet_aluno, 0)                  AS disp_aluno,
        IF(tipo_localizacao = '1', 1, 0)                            AS f_urbana,
        IF(tipo_localizacao_diferenciada IN ('2','3','4'), 1, 0)    AS f_loc_dif,
        agua_potavel               AS f_agua_potavel,
        esgoto_rede_publica        AS f_esgoto_publico,
        energia_rede_publica       AS f_energia_publica,
        lixo_servico_coleta        AS f_lixo_coleta,
        internet_aprendizagem      AS f_internet_aprend,
        COALESCE(banda_larga, 0)   AS f_banda_larga,
        biblioteca_sala_leitura    AS f_biblioteca,
        laboratorio_informatica    AS f_lab_info,
        quadra_esportes            AS f_quadra,
        parque_infantil            AS f_parque,
        refeitorio                 AS f_refeitorio,
        alimentacao                AS f_alimentacao,
        material_pedagogico_jogo   AS f_mat_jogo,
        profissional_pedagogia     AS f_prof_pedagogia,
        orgao_conselho_escolar     AS f_conselho_escolar
    FROM `{basedosdados_censo_escolar}.escola`
    WHERE ano IN (2023, 2024)
      AND tipo_situacao_funcionamento = '1'
      AND etapa_ensino_fundamental_anos_iniciais = 1
)
SELECT
    ano,
    id_municipio,
    rede,
    -- Porte da rede
    COUNT(*)                                            AS inf_n_escolas_ai,
    SUM(mat_ai)                                         AS inf_matriculas_ai,
    SAFE_DIVIDE(SUM(mat_ai), NULLIF(SUM(tur_ai), 0))    AS inf_alunos_por_turma_ai,
    SAFE_DIVIDE(SUM(mat_ai), NULLIF(SUM(doc_ai), 0))    AS inf_alunos_por_docente_ai,
    SAFE_DIVIDE(SUM(mat_ai_int), NULLIF(SUM(mat_ai), 0)) AS inf_pct_tempo_integral_ai,
    SAFE_DIVIDE(SUM(disp_aluno), NULLIF(SUM(mat_ai), 0)) AS inf_dispositivos_por_aluno,
    -- Localização
    SAFE_DIVIDE(SUM(f_urbana * mat_ai),  NULLIF(SUM(mat_ai), 0)) AS inf_pct_urbana,
    SAFE_DIVIDE(SUM(f_loc_dif * mat_ai), NULLIF(SUM(mat_ai), 0)) AS inf_pct_loc_diferenciada,
    -- Saneamento e utilidades básicas
    SAFE_DIVIDE(SUM(f_agua_potavel * mat_ai),   NULLIF(SUM(mat_ai), 0)) AS inf_pct_agua_potavel,
    SAFE_DIVIDE(SUM(f_esgoto_publico * mat_ai), NULLIF(SUM(mat_ai), 0)) AS inf_pct_esgoto_publico,
    SAFE_DIVIDE(SUM(f_energia_publica * mat_ai),NULLIF(SUM(mat_ai), 0)) AS inf_pct_energia_publica,
    SAFE_DIVIDE(SUM(f_lixo_coleta * mat_ai),    NULLIF(SUM(mat_ai), 0)) AS inf_pct_lixo_coleta,
    -- Conectividade
    SAFE_DIVIDE(SUM(f_internet_aprend * mat_ai),NULLIF(SUM(mat_ai), 0)) AS inf_pct_internet_aprendizagem,
    SAFE_DIVIDE(SUM(f_banda_larga * mat_ai),    NULLIF(SUM(mat_ai), 0)) AS inf_pct_banda_larga,
    -- Espaços pedagógicos
    SAFE_DIVIDE(SUM(f_biblioteca * mat_ai),     NULLIF(SUM(mat_ai), 0)) AS inf_pct_biblioteca_leitura,
    SAFE_DIVIDE(SUM(f_lab_info * mat_ai),       NULLIF(SUM(mat_ai), 0)) AS inf_pct_lab_informatica,
    SAFE_DIVIDE(SUM(f_quadra * mat_ai),         NULLIF(SUM(mat_ai), 0)) AS inf_pct_quadra,
    SAFE_DIVIDE(SUM(f_parque * mat_ai),         NULLIF(SUM(mat_ai), 0)) AS inf_pct_parque_infantil,
    SAFE_DIVIDE(SUM(f_mat_jogo * mat_ai),       NULLIF(SUM(mat_ai), 0)) AS inf_pct_material_jogo,
    -- Assistência e gestão
    SAFE_DIVIDE(SUM(f_refeitorio * mat_ai),     NULLIF(SUM(mat_ai), 0)) AS inf_pct_refeitorio,
    SAFE_DIVIDE(SUM(f_alimentacao * mat_ai),    NULLIF(SUM(mat_ai), 0)) AS inf_pct_alimentacao,
    SAFE_DIVIDE(SUM(f_prof_pedagogia * mat_ai), NULLIF(SUM(mat_ai), 0)) AS inf_pct_prof_pedagogia,
    SAFE_DIVIDE(SUM(f_conselho_escolar * mat_ai),NULLIF(SUM(mat_ai), 0)) AS inf_pct_conselho_escolar
FROM base
WHERE rede IS NOT NULL
GROUP BY ano, id_municipio, rede
