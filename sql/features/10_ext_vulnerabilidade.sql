-- features.ext_vulnerabilidade — vulnerabilidade social e transferência de renda
-- Fontes: `br_ipea_avs.municipio` (Atlas de Vulnerabilidade Social, Censo 2010),
-- `mundo_onu_adh.municipio` (Atlas do Desenvolvimento Humano, Censo 2010),
-- `br_mc_indicadores.transferencias_municipio` (Cadastro Único / Bolsa Família, 2020)
-- e `br_cgu_beneficios_cidadao.novo_bolsa_familia` (Portal da Transparência, 2023-2024).
--
-- TRÊS CAMADAS TEMPORAIS, deliberadamente distintas:
--
-- * AVS e ADH — Censo 2010, defasagem fixa de 13-14 anos. Parecem velhos demais, e
--   em parte são: não informam mudança recente. Mas a estrutura socioeconômica
--   municipal brasileira é fortemente persistente, e essas são as únicas fontes de
--   vulnerabilidade com cobertura nacional completa e 0% de nulos. Entram como
--   covariáveis ESTRUTURAIS, não conjunturais.
-- * Cadastro Único / Bolsa Família (2020) — defasagem de 3-4 anos. A razão
--   PBF/CadÚnico é a segunda feature socioeconômica mais forte do conjunto
--   (r = -0,309 contra a taxa municipal de 2023).
-- * Novo Bolsa Família (2023 e 2024) — CONTEMPORÂNEO ao ano-alvo. É o único sinal
--   socioeconômico dos próprios anos avaliados. Não é vazamento: a cobertura do
--   programa em junho é uma condição socioeconômica preexistente, medida meses
--   antes da prova de novembro, e não um desfecho de alfabetização.
--
-- ARMADILHAS DA FONTE, ambas obrigatórias:
-- 1. Em `br_ipea_avs.municipio`, os filtros raca_cor / sexo / localizacao = 'total' e
--    `nome_udh IS NULL` são indispensáveis: sem eles a tabela devolve recortes
--    demográficos e Unidades de Desenvolvimento Humano intramunicipais sob o mesmo
--    id_municipio, e o join sofre fan-out de até 27x (recortes) vezes centenas (UDHs).
-- 2. Em `novo_bolsa_familia`, o filtro `mes_competencia = 6` usa a chave de cluster e
--    derruba o custo de 21,5 GiB para ~1,85 GiB. Junho é o mês de referência escolhido
--    por ser o meio do ano letivo, bem antes da prova.
CREATE OR REPLACE TABLE `{features}.ext_vulnerabilidade` AS
WITH avs AS (
    SELECT
        id_municipio,
        ivs                                                           AS ivs,
        ivs_capital_humano                                            AS ivs_capital_humano,
        ivs_renda_trabalho                                            AS ivs_renda_trabalho,
        ivs_infraestrutura_urbana                                     AS ivs_infra_urbana,
        idhm_e                                                        AS idhm_educacao,
        LOG(NULLIF(renda_per_capita, 0))                              AS log_renda_per_capita,
        indice_gini                                                   AS gini,
        proporcao_vulneravel                                          AS prop_vulneravel,
        proporcao_domicilio_densidade                                 AS prop_domicilio_denso,
        proporcao_responsavel_fundamental_incompleto                  AS prop_resp_sem_fundamental,
        proporcao_maternidade_fundamental_incompleto_crianca_15_menos AS prop_mae_sem_fundamental,
        fecundidade_total                                             AS fecundidade_total,
        mortalidade_1_menos                                           AS mortalidade_infantil,
        proporcao_crianca_fora_escola_6_14                            AS prop_crianca_fora_escola
    FROM `{basedosdados_ipea_avs}.municipio`
    WHERE ano = 2010
      AND raca_cor = 'total' AND sexo = 'total' AND localizacao = 'total'
      AND nome_udh IS NULL
),
adh AS (
    -- Apenas indicadores NÃO redundantes com o AVS.
    SELECT
        id_municipio,
        expectativa_anos_estudo   AS expectativa_anos_estudo,
        taxa_atraso_2_fundamental AS taxa_atraso_2anos_fundamental,
        taxa_desocupacao_18_mais  AS taxa_desocupacao,
        prop_pobreza_criancas     AS prop_pobreza_criancas,
        taxa_freq_5_6             AS taxa_freq_escola_5_6
    FROM `{basedosdados_onu_adh}.municipio`
    WHERE ano = 2010
),
cadunico AS (
    SELECT
        id_municipio,
        AVG(pessoas_cadastradas_cu)    AS pessoas_cadastradas,
        AVG(pessoas_beneficiarias_pbf) AS pessoas_pbf,
        SAFE_DIVIDE(AVG(pessoas_beneficiarias_pbf),
                    NULLIF(AVG(pessoas_cadastradas_cu), 0)) AS razao_pbf_cadunico,
        SAFE_DIVIDE(AVG(valor_pago_pbf),
                    NULLIF(AVG(familias_beneficiarias_pbf), 0)) AS valor_medio_familia
    FROM `{basedosdados_mc_indicadores}.transferencias_municipio`
    WHERE ano = 2020
    GROUP BY id_municipio
),
novo_bolsa_familia AS (
    -- COUNT(*) conta PARCELAS, não famílias: COUNT(DISTINCT nis) custaria 29,9 GiB.
    SELECT
        ano_competencia AS ano,
        id_municipio,
        COUNT(*)           AS parcelas_junho,
        SUM(valor_parcela) AS valor_junho
    FROM `{basedosdados_cgu_beneficios}.novo_bolsa_familia`
    WHERE mes_competencia = 6 AND ano_competencia IN (2023, 2024)
    GROUP BY ano_competencia, id_municipio
),
populacao AS (
    SELECT ano, id_municipio, populacao
    FROM `{basedosdados_ibge_populacao}.municipio`
    WHERE ano IN (2023, 2024) AND id_municipio IS NOT NULL
)
SELECT
    p.ano,
    p.id_municipio,
    -- Bloco estrutural: vulnerabilidade social (Censo 2010)
    a.ivs                        AS ses_ivs,
    a.ivs_capital_humano         AS ses_ivs_capital_humano,
    a.ivs_renda_trabalho         AS ses_ivs_renda_trabalho,
    a.ivs_infra_urbana           AS ses_ivs_infra_urbana,
    a.idhm_educacao              AS ses_idhm_educacao,
    a.log_renda_per_capita       AS ses_log_renda_per_capita,
    a.gini                       AS ses_gini,
    a.prop_vulneravel            AS ses_prop_vulneravel,
    a.prop_domicilio_denso       AS ses_prop_domicilio_denso,
    a.prop_resp_sem_fundamental  AS ses_prop_resp_sem_fundamental,
    a.prop_mae_sem_fundamental   AS ses_prop_mae_sem_fundamental,
    a.fecundidade_total          AS ses_fecundidade_total,
    a.mortalidade_infantil       AS ses_mortalidade_infantil,
    a.prop_crianca_fora_escola   AS ses_prop_crianca_fora_escola,
    -- Bloco estrutural: desenvolvimento humano (Censo 2010)
    h.expectativa_anos_estudo        AS ses_expectativa_anos_estudo,
    h.taxa_atraso_2anos_fundamental  AS ses_taxa_atraso_2anos_fund,
    h.taxa_desocupacao               AS ses_taxa_desocupacao,
    h.prop_pobreza_criancas          AS ses_prop_pobreza_criancas,
    h.taxa_freq_escola_5_6           AS ses_taxa_freq_escola_5_6,
    -- Bloco de transferência de renda (2020 e contemporâneo)
    SAFE_DIVIDE(c.pessoas_cadastradas, p.populacao) AS ses_taxa_cadunico,
    SAFE_DIVIDE(c.pessoas_pbf, p.populacao)         AS ses_taxa_pbf,
    c.razao_pbf_cadunico                            AS ses_razao_pbf_cadunico,
    c.valor_medio_familia                           AS ses_valor_medio_familia_pbf,
    SAFE_DIVIDE(n.parcelas_junho, p.populacao)      AS ses_cobertura_pbf_atual,
    SAFE_DIVIDE(n.valor_junho, p.populacao)         AS ses_valor_pbf_per_capita_atual
FROM populacao p
LEFT JOIN avs a                ON a.id_municipio = p.id_municipio
LEFT JOIN adh h                ON h.id_municipio = p.id_municipio
LEFT JOIN cadunico c           ON c.id_municipio = p.id_municipio
LEFT JOIN novo_bolsa_familia n ON n.id_municipio = p.id_municipio AND n.ano = p.ano
