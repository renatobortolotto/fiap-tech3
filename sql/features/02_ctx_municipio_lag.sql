-- features.ctx_municipio_lag — contexto EDUCACIONAL do município, defasado em 1 ano
--
-- DECISÃO ANALÍTICA (data leakage, parte 3 de 3):
-- Indicadores de alfabetização do PRÓPRIO ano são, por construção, a média do
-- próprio alvo dentro do município — vazamento massivo. Aqui TODA métrica de
-- desempenho é deslocada para t-1: as features do ano N descrevem o resultado
-- observado em N-1, que é exatamente a informação disponível a um gestor público
-- ao planejar o ano N. A chave da tabela é `ano_alvo` (= ano dos alunos), e o
-- conteúdo vem de `ano_alvo - 1`.
--
-- Justificativa empírica do desenho: a taxa de alfabetização municipal é ALTAMENTE
-- persistente entre anos (correlação 2023 x 2024 = 0,81 em municípios com >= 200
-- alunos avaliados), enquanto a taxa da ESCOLA quase não persiste (r = 0,22 com
-- >= 50 alunos/ano). O componente previsível do fenômeno é sobretudo municipal —
-- ver docs/decisoes-analiticas.md.
CREATE OR REPLACE TABLE `{features}.ctx_municipio_lag` AS
WITH desempenho_municipio AS (
    -- Taxa observada por município e ano, medida na própria população de modelagem
    SELECT
        ano,
        id_municipio,
        COUNT(*) AS n_avaliados,
        COUNT(DISTINCT id_escola) AS n_escolas,
        AVG(IF(alvo_alfabetizado, 1.0, 0.0)) AS taxa_observada
    FROM `{features}.populacao_avaliada`
    GROUP BY ano, id_municipio
),
indicador_oficial AS (
    -- Indicador oficial INEP (2º ano, rede Municipal) + distribuição por nível de leitura.
    -- Níveis 0-2 = não alfabetizado / leitura incipiente; 6-8 = leitura consolidada.
    SELECT
        ano,
        id_municipio,
        taxa_alfabetizacao,
        media_portugues,
        proporcao_aluno_nivel_0 + proporcao_aluno_nivel_1 + proporcao_aluno_nivel_2
            AS prop_niveis_baixos,
        proporcao_aluno_nivel_6 + proporcao_aluno_nivel_7 + proporcao_aluno_nivel_8
            AS prop_niveis_altos
    FROM `{silver}.indicador_municipio`
    WHERE serie = 2 AND rede = 'Municipal'
    QUALIFY ROW_NUMBER() OVER (PARTITION BY ano, id_municipio ORDER BY ano) = 1
),
metas AS (
    -- Metas pactuadas no Compromisso Nacional Criança Alfabetizada.
    -- `nivel_alfabetizacao` é a faixa em que o MEC classificou o município.
    -- A meta do ano-alvo NÃO é vazamento: é um compromisso definido a priori,
    -- conhecido antes do resultado.
    SELECT
        ano,
        id_municipio,
        meta_alfabetizacao_2024,
        meta_alfabetizacao_2025,
        meta_alfabetizacao_2026,
        meta_alfabetizacao_2030,
        nivel_alfabetizacao,
        percentual_participacao
    FROM `{silver}.metas_municipio`
)
SELECT
    d.ano + 1 AS ano_alvo,
    d.id_municipio,

    -- Bloco A: desempenho municipal observado em t-1
    d.taxa_observada        AS mun_lag_taxa_observada,
    d.n_avaliados           AS mun_lag_n_avaliados,
    d.n_escolas             AS mun_lag_n_escolas,
    io.taxa_alfabetizacao   AS mun_lag_taxa_oficial,
    io.media_portugues      AS mun_lag_media_portugues,
    io.prop_niveis_baixos   AS mun_lag_prop_niveis_baixos,
    io.prop_niveis_altos    AS mun_lag_prop_niveis_altos,

    -- Bloco B: metas e política pública (definidas a priori, sem vazamento)
    CASE d.ano + 1
        WHEN 2024 THEN m.meta_alfabetizacao_2024
        WHEN 2025 THEN m.meta_alfabetizacao_2025
        WHEN 2026 THEN m.meta_alfabetizacao_2026
    END                       AS mun_meta_ano_alvo,
    m.meta_alfabetizacao_2030 AS mun_meta_2030,
    m.nivel_alfabetizacao     AS mun_nivel_alfabetizacao,
    m.percentual_participacao AS mun_lag_pct_participacao,

    -- Bloco C: distância até a meta, medida com o resultado de t-1
    io.taxa_alfabetizacao - CASE d.ano + 1
        WHEN 2024 THEN m.meta_alfabetizacao_2024
        WHEN 2025 THEN m.meta_alfabetizacao_2025
        WHEN 2026 THEN m.meta_alfabetizacao_2026
    END                       AS mun_lag_gap_meta_ano,
    io.taxa_alfabetizacao - m.meta_alfabetizacao_2030
                              AS mun_lag_gap_meta_2030
FROM desempenho_municipio d
LEFT JOIN indicador_oficial io
    ON io.ano = d.ano AND io.id_municipio = d.id_municipio
LEFT JOIN metas m
    ON m.ano = d.ano AND m.id_municipio = d.id_municipio
