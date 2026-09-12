-- features.ext_financas — financiamento municipal da educação (FUNDEB e SICONFI)
-- Fontes: `br_fnde_fundeb.indicador_municipal` / `.indicador_estadual` (SIOPE/FNDE)
-- e `br_me_siconfi.municipio_despesas_funcao` / `.municipio_receitas_orcamentarias`
-- (Declaração de Contas Anuais, Tesouro Nacional).
--
-- DEFASAGEM DE 1 EXERCÍCIO: `ano_fiscal = ano_do_aluno - 1`. Alunos de 2023 recebem o
-- exercício de 2022; alunos de 2024, o de 2023. As duas safras existem completas, o
-- que elimina vazamento temporal e ainda dá ao modelo duas observações fiscais
-- distintas em vez de uma constante replicada. O bimestre 6 é o acumulado de
-- fechamento do exercício.
--
-- DISTRITO FEDERAL: `id_municipio = '5300108'` não existe nas tabelas municipais de
-- nenhuma das duas fontes — são 27.701 alunos em 2024 (1,3% do ano). Resolvido pelas
-- tabelas estaduais, com os códigos de indicador próprios do nível estadual (que são
-- DIFERENTES dos municipais). A flag `fin_fonte_estadual` marca essas linhas, para
-- que o modelo possa distinguir: a semântica difere, o DF é rede distrital.
--
-- INDICADORES SIOPE DESCARTADOS: 39, 43, 46-49, 61, 62 têm de 80% a 100% de zeros
-- (o 61 é 100% zero) e o 92 cobre apenas 2 a 3 mil municípios. Os indicadores 65 e 66
-- são literalmente o IDEB — além de virtualmente vazios, seriam risco de vazamento
-- contextual e ficam fora por princípio.
--
-- EXPECTATIVA HONESTA: as correlações desta fonte (|r| entre 0,09 e 0,28) são
-- ECOLÓGICAS, medidas no nível do município. No grão do aluno o incremento tende a
-- ser modesto — é contexto fiscal do município, não um atributo da criança.
CREATE OR REPLACE TABLE `{features}.ext_financas` AS
WITH fundeb_municipal AS (
    SELECT
        id_municipio,
        ano AS ano_fiscal,
        FALSE AS fonte_estadual,
        MAX(IF(id_indicador = '45', valor_real, NULL))       AS invest_aluno_ens_fund,
        MAX(IF(id_indicador = '56', valor_real, NULL))       AS invest_aluno_educ_basica,
        MAX(IF(id_indicador = '58', valor_real, NULL))       AS desp_professor_por_aluno,
        MAX(IF(id_indicador = '24', valor_percentual, NULL)) AS pct_mde_sobre_impostos,
        MAX(IF(id_indicador = '67', valor_percentual, NULL)) AS pct_fundeb_remuneracao,
        MAX(IF(id_indicador = '27', valor_percentual, NULL)) AS pct_fundeb_nao_aplicado,
        MAX(IF(id_indicador = '29', valor_percentual, NULL)) AS pct_fundeb_ens_fund,
        MAX(IF(id_indicador = '28', valor_percentual, NULL)) AS pct_fundeb_educ_infantil,
        MAX(IF(id_indicador = '32', valor_percentual, NULL)) AS pct_desp_ens_fund_sobre_educ
    FROM `{basedosdados_fundeb}.indicador_municipal`
    WHERE ano IN (2022, 2023) AND bimestre = 6
      AND id_indicador IN ('24','27','28','29','32','45','56','58')
    GROUP BY id_municipio, ano
),
fundeb_df AS (
    -- Os códigos de indicador do nível estadual NÃO coincidem com os municipais.
    SELECT
        '5300108' AS id_municipio,
        ano AS ano_fiscal,
        TRUE AS fonte_estadual,
        MAX(IF(id_indicador = '66', valor_real, NULL))       AS invest_aluno_ens_fund,
        MAX(IF(id_indicador = '72', valor_real, NULL))       AS invest_aluno_educ_basica,
        MAX(IF(id_indicador = '74', valor_real, NULL))       AS desp_professor_por_aluno,
        MAX(IF(id_indicador = '40', valor_percentual, NULL)) AS pct_mde_sobre_impostos,
        MAX(IF(id_indicador = '42', valor_percentual, NULL)) AS pct_fundeb_remuneracao,
        MAX(IF(id_indicador = '44', valor_percentual, NULL)) AS pct_fundeb_nao_aplicado,
        MAX(IF(id_indicador = '46', valor_percentual, NULL)) AS pct_fundeb_ens_fund,
        MAX(IF(id_indicador = '45', valor_percentual, NULL)) AS pct_fundeb_educ_infantil,
        MAX(IF(id_indicador = '49', valor_percentual, NULL)) AS pct_desp_ens_fund_sobre_educ
    FROM `{basedosdados_fundeb}.indicador_estadual`
    WHERE ano IN (2022, 2023) AND bimestre = 6 AND sigla_uf = 'DF'
    GROUP BY ano
),
fundeb AS (
    SELECT * FROM fundeb_municipal UNION ALL SELECT * FROM fundeb_df
),
despesa AS (
    -- 3.12.000 = função Educação; 3.00.000 = despesa total (exceto intraorçamentária)
    SELECT
        id_municipio, ano AS ano_fiscal,
        MAX(IF(id_conta_bd = '3.00.000', valor, NULL)) AS desp_total,
        MAX(IF(id_conta_bd = '3.12.000', valor, NULL)) AS desp_educacao,
        MAX(IF(id_conta_bd = '3.12.361', valor, NULL)) AS desp_ens_fundamental
    FROM `{basedosdados_siconfi}.municipio_despesas_funcao`
    WHERE ano IN (2022, 2023) AND estagio_bd = 'Despesas Empenhadas'
      AND id_conta_bd IN ('3.00.000', '3.12.000', '3.12.361')
    GROUP BY id_municipio, ano
    UNION ALL
    SELECT '5300108', ano,
        MAX(IF(id_conta_bd = '3.00.000', valor, NULL)),
        MAX(IF(id_conta_bd = '3.12.000', valor, NULL)),
        MAX(IF(id_conta_bd = '3.12.361', valor, NULL))
    FROM `{basedosdados_siconfi}.uf_despesas_funcao`
    WHERE ano IN (2022, 2023) AND sigla_uf = 'DF' AND estagio_bd = 'Despesas Empenhadas'
      AND id_conta_bd IN ('3.00.000', '3.12.000', '3.12.361')
    GROUP BY ano
),
receita AS (
    -- `id_conta_bd` é NULL nestas linhas: o filtro tem de ser pelo texto de `conta_bd`.
    SELECT
        id_municipio, ano AS ano_fiscal,
        SUM(IF(conta_bd LIKE 'Transferências de Recursos do Fundo%', valor, 0))
            AS receita_fundeb,
        SUM(IF(conta_bd LIKE 'Transferências de Recursos de Complementação da União%', valor, 0))
            AS receita_complementacao_uniao
    FROM `{basedosdados_siconfi}.municipio_receitas_orcamentarias`
    WHERE ano IN (2022, 2023) AND estagio_bd = 'Receitas Brutas Realizadas'
      AND LOWER(conta_bd) LIKE '%fundeb%'
    GROUP BY id_municipio, ano
    UNION ALL
    SELECT '5300108', ano,
        SUM(IF(conta_bd LIKE 'Transferências de Recursos do Fundo%', valor, 0)),
        SUM(IF(conta_bd LIKE 'Transferências de Recursos de Complementação da União%', valor, 0))
    FROM `{basedosdados_siconfi}.uf_receitas_orcamentarias`
    WHERE ano IN (2022, 2023) AND sigla_uf = 'DF' AND estagio_bd = 'Receitas Brutas Realizadas'
      AND LOWER(conta_bd) LIKE '%fundeb%'
    GROUP BY ano
),
base AS (
    SELECT
        COALESCE(f.id_municipio, d.id_municipio, r.id_municipio) AS id_municipio,
        COALESCE(f.ano_fiscal, d.ano_fiscal, r.ano_fiscal)       AS ano_fiscal,
        f.* EXCEPT (id_municipio, ano_fiscal),
        d.* EXCEPT (id_municipio, ano_fiscal),
        r.* EXCEPT (id_municipio, ano_fiscal)
    FROM fundeb f
    FULL JOIN despesa d USING (id_municipio, ano_fiscal)
    FULL JOIN receita r USING (id_municipio, ano_fiscal)
)
SELECT
    ano_fiscal + 1 AS ano,
    id_municipio,
    COALESCE(fonte_estadual, FALSE)   AS fin_fonte_estadual,
    -- Investimento por aluno (já normalizado pelo FNDE via matrículas do Censo)
    invest_aluno_ens_fund             AS fin_invest_aluno_ens_fund,
    invest_aluno_educ_basica          AS fin_invest_aluno_educ_basica,
    desp_professor_por_aluno          AS fin_desp_professor_por_aluno,
    -- Esforço e alocação
    pct_mde_sobre_impostos            AS fin_pct_mde_sobre_impostos,
    pct_fundeb_remuneracao            AS fin_pct_fundeb_remuneracao,
    pct_fundeb_nao_aplicado           AS fin_pct_fundeb_nao_aplicado,
    pct_fundeb_ens_fund               AS fin_pct_fundeb_ens_fund,
    pct_fundeb_educ_infantil          AS fin_pct_fundeb_educ_infantil,
    pct_desp_ens_fund_sobre_educ      AS fin_pct_desp_ens_fund_sobre_educ,
    -- Escala orçamentária (log: a distribuição é fortemente assimétrica)
    LOG(NULLIF(desp_educacao, 0))     AS fin_log_desp_educacao,
    LOG(NULLIF(receita_fundeb, 0))    AS fin_log_receita_fundeb,
    -- Razões derivadas — as features de maior |r| segundo o reconhecimento
    SAFE_DIVIDE(desp_educacao, desp_total) * 100
        AS fin_pct_educacao_sobre_desp_total,
    SAFE_DIVIDE(desp_ens_fundamental, desp_educacao) * 100
        AS fin_pct_ens_fund_sobre_educacao,
    SAFE_DIVIDE(receita_fundeb, desp_total) * 100
        AS fin_pct_fundeb_sobre_desp_total,
    -- Complementação da União (VAAT): NULL não é dado faltante — significa que o
    -- município não recebe complementação. Convertido em 0 explicitamente.
    COALESCE(SAFE_DIVIDE(receita_complementacao_uniao,
                         NULLIF(receita_fundeb, 0)) * 100, 0)
        AS fin_pct_complementacao_uniao
FROM base
WHERE ano_fiscal IN (2022, 2023)
