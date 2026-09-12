-- features.ctx_territorio — atributos TERRITORIAIS do município (estáticos)
--
-- Fonte: `silver.dim_municipio` (diretório oficial de municípios do IBGE, carregado
-- na Fase 2) e `gold.panorama_uf` (contexto da UF, defasado em 1 ano).
-- São atributos estruturais — região, coordenadas, condição de capital, Amazônia
-- Legal — que não dependem do ano nem do desempenho: risco de vazamento nulo.
--
-- Latitude e longitude entram como features numéricas contínuas: permitem ao
-- modelo baseado em árvores capturar gradientes geográficos (Norte/Nordeste x
-- Sul/Sudeste) sem que precisemos codificar a região manualmente.
CREATE OR REPLACE TABLE `{features}.ctx_territorio` AS
WITH uf_lag AS (
    -- Panorama da UF no ano anterior (rede pública), da camada Gold da Fase 2
    SELECT
        ano + 1 AS ano_alvo,
        sigla_uf,
        taxa AS uf_lag_taxa,
        ranking_taxa AS uf_lag_ranking
        -- `gap` e `pct_municipios_atingiram_meta` NÃO entram: são 100% NULL em 2023
        -- (70 de 70 linhas), porque a trajetória de metas só começa em 2024 — e 2023
        -- é o único ano disponível como defasagem. Verificado.
    FROM `{gold}.panorama_uf`
    WHERE rede = 'Pública (Estadual e Municipal)'
),
anos AS (
    SELECT DISTINCT ano AS ano_alvo FROM `{features}.populacao_avaliada`
)
SELECT
    a.ano_alvo,
    d.id_municipio,
    d.nome_municipio,
    d.sigla_uf,
    d.nome_regiao        AS ter_regiao,
    d.nome_mesorregiao   AS ter_mesorregiao,
    d.latitude           AS ter_latitude,
    d.longitude          AS ter_longitude,
    d.capital_uf         AS ter_capital_uf,
    d.amazonia_legal     AS ter_amazonia_legal,
    u.uf_lag_taxa,
    u.uf_lag_ranking
FROM anos a
CROSS JOIN `{silver}.dim_municipio` d
LEFT JOIN uf_lag u
    ON u.ano_alvo = a.ano_alvo AND u.sigla_uf = d.sigla_uf
