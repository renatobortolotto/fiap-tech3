-- features.ext_ibge — contexto demográfico e econômico do município (IBGE)
-- Fontes: `br_ibge_censo_2022` (vários blocos), `br_ibge_pib.municipio`,
-- `br_ibge_populacao.municipio`.
--
-- DEFASAGEM. PIB e população entram sempre de t-1 — aqui a defasagem não é só
-- prudência: não existe PIB municipal de 2024, então lag 1 é obrigatório. O Censo
-- 2022 é estático (data de referência 31/07/2022), anterior aos dois anos-alvo:
-- legítimo, mas sem variação temporal.
--
-- PRIORIDADE DEMOGRÁFICA, não sanitária. As correlações medidas contra a taxa de
-- alfabetização municipal (n = 5.548) mostram uma hierarquia contraintuitiva:
--     idade mediana          +0,320
--     % da população de 5-9   -0,307
--     índice de envelhecimento +0,306
--     moradores por domicílio  -0,249
--     PIB per capita           +0,109
--     saneamento          0,06 a 0,09
-- Municípios demograficamente jovens — com muitas crianças por adulto e domicílios
-- numerosos — alfabetizam menos. O sinal é de PRESSÃO DEMOGRÁFICA sobre a rede, e
-- é mais forte que o de renda ou de infraestrutura sanitária.
--
-- DECISÃO DE FINOPS. O bloco de abastecimento de água foi descartado: custava
-- ~780 MiB (44% do custo total desta consulta) para uma correlação de 0,058 com o
-- alvo. Esgoto e coleta de lixo cobrem a mesma dimensão por uma fração do custo.
CREATE OR REPLACE TABLE `{features}.ext_ibge` AS
WITH anos AS (
    SELECT ano FROM UNNEST([2023, 2024]) AS ano
),
pib AS (
    -- Apenas `pib`: nas safras 2022 e 2023 as colunas de valor adicionado
    -- (va, va_agropecuaria, va_industria, va_servicos) estão 100% NULL na fonte
    -- (0 de 5.570 municípios em 2022) — o IBGE ainda não publicou a abertura
    -- setorial desses anos. Extraí-las produziria três features 100% ausentes.
    SELECT id_municipio, ano, pib
    FROM `{basedosdados_ibge_pib}.municipio`
    WHERE ano IN (2022, 2023)
),
populacao AS (
    SELECT id_municipio, ano, populacao
    FROM `{basedosdados_ibge_populacao}.municipio`
    WHERE ano IN (2022, 2023) AND id_municipio IS NOT NULL
),
censo AS (
    SELECT
        id_municipio,
        taxa_alfabetizacao                            AS taxa_alfabetizacao_15mais,
        SAFE_DIVIDE(populacao, NULLIF(area, 0))       AS densidade_demografica,
        SAFE_DIVIDE(populacao, NULLIF(domicilios, 0)) AS moradores_por_domicilio,
        idade_mediana,
        indice_envelhecimento,
        SAFE_DIVIDE(populacao_indigena + populacao_quilombola, NULLIF(populacao, 0))
            AS share_indigena_quilombola
    FROM `{basedosdados_ibge_censo2022}.municipio`
),
faixa_etaria AS (
    -- O filtro ano = 2022 é obrigatório: a tabela também contém o Censo 2010.
    SELECT
        id_municipio,
        SAFE_DIVIDE(SUM(IF(grupo_idade = '5 a 9 anos', populacao, 0)),
                    NULLIF(SUM(populacao), 0)) AS share_pop_5a9,
        SAFE_DIVIDE(SUM(IF(grupo_idade IN ('0 a 4 anos', '5 a 9 anos', '10 a 14 anos'),
                           populacao, 0)),
                    NULLIF(SUM(populacao), 0)) AS share_pop_0a14
    FROM `{basedosdados_ibge_censo2022}.populacao_grupo_idade_sexo_raca`
    WHERE ano = 2022
    GROUP BY id_municipio
),
alfabetizacao_adultos AS (
    -- Capital educacional da geração dos pais: a variável que mais se aproxima,
    -- em dado público municipal, da escolaridade familiar da criança.
    SELECT
        id_municipio,
        SAFE_DIVIDE(
            SUM(IF(grupo_idade IN ('25 a 34 anos', '35 a 44 anos')
                   AND alfabetizacao = 'Alfabetizadas', populacao, 0)),
            NULLIF(SUM(IF(grupo_idade IN ('25 a 34 anos', '35 a 44 anos'),
                          populacao, 0)), 0)
        ) AS taxa_alfab_adultos_25a44
    FROM `{basedosdados_ibge_censo2022}.alfabetizacao_grupo_idade_sexo_raca`
    GROUP BY id_municipio
),
esgoto AS (
    -- Exclui a categoria AGREGADA para não duplicar o denominador.
    SELECT
        id_municipio,
        SAFE_DIVIDE(SUM(IF(tipo_esgotamento_sanitario IN (
                'Não tinham banheiro nem sanitário', 'Vala',
                'Rio, lago, córrego ou mar', 'Fossa rudimentar ou buraco'),
                populacao, 0)), NULLIF(SUM(populacao), 0)) AS share_esgoto_inadequado
    FROM `{basedosdados_ibge_censo2022}.caracteristica_domicilio_grupo_idade_raca_esgotamento_sanitario`
    WHERE ano = 2022
      AND tipo_esgotamento_sanitario <> 'Rede geral, rede pluvial ou fossa ligada à rede'
    GROUP BY id_municipio
),
domicilio AS (
    SELECT
        id_municipio,
        SAFE_DIVIDE(SUM(IF(tipo_domicilio IN (
                'Estrutura residencial permanente degradada ou inacabada',
                'Habitação em casa de cômodos ou cortiço',
                'Habitação indígena sem paredes ou maloca'),
                populacao, 0)), NULLIF(SUM(populacao), 0)) AS share_domicilio_precario
    FROM `{basedosdados_ibge_censo2022}.caracteristica_domicilio_grupo_idade_raca_tipo_domicilio`
    WHERE ano = 2022
    GROUP BY id_municipio
)
SELECT
    a.ano,
    c.id_municipio,
    -- Bloco econômico (t-1)
    SAFE_DIVIDE(p.pib, NULLIF(q.populacao, 0))      AS ses_pib_per_capita,
    LOG(NULLIF(q.populacao, 0))                     AS ses_log_populacao,
    -- Bloco demográfico (Censo 2022) — o mais forte, ver cabeçalho
    c.idade_mediana                 AS ses_idade_mediana,
    c.indice_envelhecimento         AS ses_indice_envelhecimento,
    f.share_pop_5a9                 AS ses_share_pop_5a9,
    f.share_pop_0a14                AS ses_share_pop_0a14,
    c.moradores_por_domicilio       AS ses_moradores_por_domicilio,
    c.densidade_demografica         AS ses_densidade_demografica,
    c.share_indigena_quilombola     AS ses_share_indigena_quilombola,
    -- Bloco de capital educacional e habitação
    c.taxa_alfabetizacao_15mais     AS ses_taxa_alfabetizacao_15mais,
    al.taxa_alfab_adultos_25a44     AS ses_taxa_alfab_adultos_25a44,
    e.share_esgoto_inadequado       AS ses_share_esgoto_inadequado,
    d.share_domicilio_precario      AS ses_share_domicilio_precario
FROM censo c
CROSS JOIN anos a
LEFT JOIN pib p                    ON p.id_municipio = c.id_municipio AND p.ano = a.ano - 1
LEFT JOIN populacao q              ON q.id_municipio = c.id_municipio AND q.ano = a.ano - 1
LEFT JOIN faixa_etaria f           ON f.id_municipio = c.id_municipio
LEFT JOIN alfabetizacao_adultos al ON al.id_municipio = c.id_municipio
LEFT JOIN esgoto e                 ON e.id_municipio = c.id_municipio
LEFT JOIN domicilio d              ON d.id_municipio = c.id_municipio
