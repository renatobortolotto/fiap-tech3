-- features.ctx_escola_lag — contexto da ESCOLA, defasado em 1 ano
--
-- Mesmo princípio de defasagem da tabela municipal: o conteúdo vem de
-- `ano_alvo - 1`. A taxa escolar é um preditor FRACO (persistência r = 0,22 entre
-- 2023 e 2024) porque as coortes do 2º ano são pequenas — a taxa observada é
-- dominada por ruído amostral. Mantemos a feature acompanhada de `esc_lag_n_avaliados`
-- para que o modelo possa aprender a descontar taxas medidas em coortes pequenas,
-- e de uma versão encolhida para a média municipal (shrinkage empírico-bayesiano).
CREATE OR REPLACE TABLE `{features}.ctx_escola_lag` AS
WITH escola AS (
    SELECT
        ano,
        id_escola,
        ANY_VALUE(id_municipio) AS id_municipio,
        COUNT(*) AS n_avaliados,
        SUM(IF(alvo_alfabetizado, 1, 0)) AS n_alfabetizados,
        AVG(IF(alvo_alfabetizado, 1.0, 0.0)) AS taxa_observada
    FROM `{features}.populacao_avaliada`
    GROUP BY ano, id_escola
),
municipio AS (
    SELECT ano, id_municipio, AVG(IF(alvo_alfabetizado, 1.0, 0.0)) AS taxa_mun
    FROM `{features}.populacao_avaliada`
    GROUP BY ano, id_municipio
)
SELECT
    e.ano + 1 AS ano_alvo,
    e.id_escola,
    e.taxa_observada AS esc_lag_taxa_observada,
    e.n_avaliados    AS esc_lag_n_avaliados,
    -- Shrinkage empírico-bayesiano em direção à média do município:
    -- (alfabetizados + k*taxa_mun) / (n + k), com k = 30 (ordem de grandeza de uma
    -- coorte típica do 2º ano). Com n pequeno a estimativa tende à média municipal;
    -- com n grande, à taxa da própria escola.
    SAFE_DIVIDE(
        e.n_alfabetizados + 30 * m.taxa_mun,
        e.n_avaliados + 30
    ) AS esc_lag_taxa_suavizada,
    -- Quanto a escola se descola do próprio município (após suavização)
    SAFE_DIVIDE(
        e.n_alfabetizados + 30 * m.taxa_mun,
        e.n_avaliados + 30
    ) - m.taxa_mun AS esc_lag_desvio_vs_municipio
FROM escola e
LEFT JOIN municipio m
    ON m.ano = e.ano AND m.id_municipio = e.id_municipio
