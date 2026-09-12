-- features.ext_indicadores_educacionais — indicadores educacionais do INEP
-- Fonte: `basedosdados.br_inep_indicadores_educacionais.municipio`.
-- Grão de join: (ano, id_municipio, rede) — cobertura verificada de 100%.
--
-- DUAS POLÍTICAS TEMPORAIS DISTINTAS, conforme o momento em que cada indicador é apurado:
--
-- * ESTRUTURAIS (mesmo ano) — distorção idade-série, alunos por turma, horas-aula,
--   formação/esforço docente, complexidade de gestão. Todos derivam do Censo Escolar,
--   cuja referência é maio; a prova é em novembro. A informação antecede o desfecho.
-- * RENDIMENTO (defasados em 1 ano) — aprovação, reprovação e abandono. A taxa do ano X
--   só é apurada DEPOIS do encerramento do ano letivo, ou seja, depois da prova. Usá-la
--   contemporaneamente seria vazamento temporal sobre a mesma coorte.
--
-- Nota de qualidade da fonte: formação docente (afd), docentes com superior (dsu),
-- esforço docente (ied), complexidade de gestão (icg) e regularidade docente (ird) são
-- publicados SOMENTE na linha agregada rede='Total' — na linha 'Municipal' são ~98,6%
-- nulos. Por isso vêm de um CTE separado, no grão do município.
CREATE OR REPLACE TABLE `{features}.ext_indicadores_educacionais` AS
WITH base AS (
    SELECT
        ano,
        id_municipio,
        LOWER(localizacao) AS loc,
        REPLACE(LOWER(rede), 'ú', 'u') AS rede_n,   -- normaliza 'Pública'/'publica'
        tdi_ef_anos_iniciais, tdi_ef_2_ano,
        atu_ef_anos_iniciais, had_ef_anos_iniciais,
        taxa_aprovacao_ef_anos_iniciais,
        taxa_reprovacao_ef_anos_iniciais,
        taxa_abandono_ef_anos_iniciais,
        afd_ef_anos_iniciais_grupo_1, afd_ef_anos_iniciais_grupo_5,
        dsu_ef_anos_iniciais,
        ied_ef_anos_iniciais_nivel_1, ied_ef_anos_iniciais_nivel_6,
        icg_nivel_1, ird_alta, ird_baixa_regularidade
    FROM `{basedosdados_indicadores_edu}.municipio`
    WHERE ano BETWEEN 2022 AND 2024      -- 2022 entra apenas como fonte da defasagem
),
por_rede AS (
    SELECT ano, id_municipio, rede_n,
           tdi_ef_anos_iniciais, tdi_ef_2_ano,
           atu_ef_anos_iniciais, had_ef_anos_iniciais,
           taxa_aprovacao_ef_anos_iniciais,
           taxa_reprovacao_ef_anos_iniciais,
           taxa_abandono_ef_anos_iniciais
    FROM base
    WHERE loc = 'total' AND rede_n IN ('municipal', 'estadual', 'privada')
),
municipio_total AS (
    SELECT ano, id_municipio,
           afd_ef_anos_iniciais_grupo_1, afd_ef_anos_iniciais_grupo_5,
           dsu_ef_anos_iniciais,
           ied_ef_anos_iniciais_nivel_1, ied_ef_anos_iniciais_nivel_6,
           icg_nivel_1, ird_alta, ird_baixa_regularidade
    FROM base
    WHERE loc = 'total' AND rede_n = 'total'
),
gap_rural_urbano AS (
    -- Desigualdade INTRAmunicipal: onde o campo está muito atrás da cidade,
    -- a média municipal esconde bolsões de risco.
    SELECT ano, id_municipio,
           MAX(IF(loc = 'rural',  tdi_ef_anos_iniciais, NULL)) AS tdi_rural,
           MAX(IF(loc = 'urbana', tdi_ef_anos_iniciais, NULL)) AS tdi_urbana,
           MAX(IF(loc = 'rural',  atu_ef_anos_iniciais, NULL)) AS atu_rural
    FROM base
    WHERE rede_n = 'total' AND loc IN ('rural', 'urbana')
    GROUP BY ano, id_municipio
)
SELECT
    r.ano,
    r.id_municipio,
    INITCAP(r.rede_n) AS rede,
    -- Estruturais (mesmo ano, referência de maio)
    r.tdi_ef_anos_iniciais      AS edu_tdi_anos_iniciais,
    r.tdi_ef_2_ano              AS edu_tdi_2ano,
    r.atu_ef_anos_iniciais      AS edu_alunos_por_turma_ai,
    r.had_ef_anos_iniciais      AS edu_horas_aula_ai,
    t.afd_ef_anos_iniciais_grupo_1 AS edu_afd_grupo1_ai,
    t.afd_ef_anos_iniciais_grupo_5 AS edu_afd_grupo5_ai,
    t.dsu_ef_anos_iniciais      AS edu_docentes_superior_ai,
    t.ied_ef_anos_iniciais_nivel_1 AS edu_esforco_docente_n1,
    t.ied_ef_anos_iniciais_nivel_6 AS edu_esforco_docente_n6,
    t.icg_nivel_1               AS edu_complexidade_gestao_n1,
    t.ird_alta                  AS edu_regularidade_docente_alta,
    t.ird_baixa_regularidade    AS edu_regularidade_docente_baixa,
    g.tdi_rural - g.tdi_urbana  AS edu_gap_tdi_rural_urbana,
    g.atu_rural                 AS edu_alunos_por_turma_rural,
    -- Rendimento (defasado em 1 ano)
    l.taxa_aprovacao_ef_anos_iniciais  AS edu_aprovacao_ai_lag1,
    l.taxa_reprovacao_ef_anos_iniciais AS edu_reprovacao_ai_lag1,
    l.taxa_abandono_ef_anos_iniciais   AS edu_abandono_ai_lag1
FROM por_rede r
LEFT JOIN municipio_total t
    ON t.ano = r.ano AND t.id_municipio = r.id_municipio
LEFT JOIN gap_rural_urbano g
    ON g.ano = r.ano AND g.id_municipio = r.id_municipio
LEFT JOIN por_rede l
    ON l.ano = r.ano - 1 AND l.id_municipio = r.id_municipio AND l.rede_n = r.rede_n
WHERE r.ano IN (2023, 2024)
