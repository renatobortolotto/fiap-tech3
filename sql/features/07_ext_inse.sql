-- features.ext_inse — Nível Socioeconômico das escolas (INSE/INEP), agregado ao município
-- Fonte: `basedosdados.br_inep_indicador_nivel_socioeconomico.escola`.
--
-- O INSE é a medida socioeconômica mais direta disponível: é construído a partir dos
-- questionários respondidos pelas famílias (escolaridade dos pais, renda, bens no
-- domicílio). No grão da ESCOLA seria, muito provavelmente, a feature mais forte do
-- projeto — mas o join escolar é impossível (§6). Agregamos ao município × rede,
-- ponderando pelo número de alunos que compõem o indicador de cada escola.
--
-- DEFASAGEM. O INSE só existe em 2013, 2015, 2019, 2021 e 2023 (não há 2024).
-- Aplicamos a mesma regra do IDEB — "a última edição divulgada antes da prova do
-- ano-alvo":
--     alvo 2023 -> INSE 2021
--     alvo 2024 -> INSE 2023
-- Isso evita usar, para 2023, um indicador medido na mesma onda do desfecho.
--
-- Nota da fonte: em 2023 os percentuais por nível trazem NULL onde o valor é 0%
-- (verificado: com IFNULL a soma fecha em 100,000). O IFNULL é obrigatório.
CREATE OR REPLACE TABLE `{features}.ext_inse` AS
WITH mapa_defasagem AS (
    SELECT 2023 AS ano_alvo, 2021 AS ano_inse
    UNION ALL
    SELECT 2024 AS ano_alvo, 2023 AS ano_inse
),
base AS (
    SELECT
        ano,
        id_municipio,
        sigla_uf,
        CAST(rede AS INT64) AS rede_codigo,
        inse,
        quantidade_alunos_inse AS q,
        IFNULL(percentual_nivel_1, 0) + IFNULL(percentual_nivel_2, 0) AS p_baixos,
        IFNULL(percentual_nivel_6, 0) + IFNULL(percentual_nivel_7, 0)
            + IFNULL(percentual_nivel_8, 0) AS p_altos,
        tipo_localizacao,
        area
    FROM `{basedosdados_inse}.escola`
    WHERE ano IN (2021, 2023)
      AND CAST(rede AS INT64) IN (2, 3)     -- Estadual e Municipal
      AND quantidade_alunos_inse > 0
),
por_municipio AS (
    SELECT
        ano,
        id_municipio,
        ANY_VALUE(sigla_uf) AS sigla_uf,
        CASE rede_codigo WHEN 2 THEN 'Estadual' WHEN 3 THEN 'Municipal' END AS rede,
        COUNT(*)                                  AS n_escolas,
        SAFE_DIVIDE(SUM(inse * q), SUM(q))        AS inse_medio,
        STDDEV_SAMP(inse)                         AS inse_desvio_escolas,
        MIN(inse)                                 AS inse_min_escola,
        SAFE_DIVIDE(SUM(p_baixos * q), SUM(q))    AS pct_niveis_baixos,
        SAFE_DIVIDE(SUM(p_altos * q), SUM(q))     AS pct_niveis_altos,
        SAFE_DIVIDE(COUNTIF(tipo_localizacao = '2'), COUNT(*)) * 100 AS pct_escolas_rurais,
        SAFE_DIVIDE(SUM(q), COUNT(*))             AS tamanho_medio_escola
    FROM base
    GROUP BY ano, id_municipio, rede_codigo
),
por_uf AS (
    SELECT ano, sigla_uf,
           CASE rede_codigo WHEN 2 THEN 'Estadual' WHEN 3 THEN 'Municipal' END AS rede,
           SAFE_DIVIDE(SUM(inse * q), SUM(q)) AS inse_medio_uf
    FROM base
    GROUP BY ano, sigla_uf, rede_codigo
)
SELECT
    d.ano_alvo AS ano,
    m.id_municipio,
    m.rede,
    d.ano_inse                         AS inse_ano_referencia,
    m.inse_medio,
    u.inse_medio_uf                    AS inse_medio_uf,
    m.inse_medio - u.inse_medio_uf     AS inse_desvio_vs_uf,
    m.inse_desvio_escolas,
    m.inse_min_escola,
    m.pct_niveis_baixos                AS inse_pct_niveis_baixos,
    m.pct_niveis_altos                 AS inse_pct_niveis_altos,
    m.pct_escolas_rurais               AS inse_pct_escolas_rurais,
    m.tamanho_medio_escola             AS inse_tamanho_medio_escola,
    m.n_escolas                        AS inse_n_escolas
FROM mapa_defasagem d
JOIN por_municipio m ON m.ano = d.ano_inse
LEFT JOIN por_uf u   ON u.ano = d.ano_inse AND u.sigla_uf = m.sigla_uf AND u.rede = m.rede
WHERE m.rede IS NOT NULL
