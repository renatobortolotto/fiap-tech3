-- features.ext_ideb_saeb — contexto de aprendizagem do município (IDEB e SAEB 5º ano)
-- Fontes: `basedosdados.br_inep_ideb.municipio` / `.uf` e `basedosdados.br_inep_saeb.municipio`.
--
-- REGRA DE DEFASAGEM: a última edição DIVULGADA antes da aplicação da prova do ano-alvo.
--     alvo 2023 -> edição 2021 (divulgada em set/2022)
--     alvo 2024 -> edição 2023 (divulgada em ago/2024)
--
-- POR QUE NÃO USAR O IDEB DO PRÓPRIO ANO. Não é vazamento direto do alvo — são alunos
-- diferentes (5º ano x 2º ano), prova e construto diferentes. Mas é vazamento temporal,
-- e ele foi MEDIDO: a correlação ponto-bisserial, no grão do aluno, entre
-- `alfabetizado`(2023) e o IDEB municipal sobe de 0,190 (edição 2021) para 0,221
-- (edição 2023) — uma inflação de 16%. Ela vem do choque município-ano compartilhado:
-- o SAEB do 5º ano de 2023 foi aplicado na MESMA onda de novembro que a prova de
-- alfabetização. Além disso, o IDEB 2023 só foi publicado em ago/2024 — depois da prova
-- de 2023. Usá-lo quebraria a causalidade temporal e seria irreprodutível em produção.
--
-- O sinal é estável ao longo das edições (r = 0,179 em 2017; 0,189 em 2019; 0,190 em
-- 2021), de modo que recuar uma edição custa muito pouco em poder preditivo.
--
-- Fallback explícito: onde não há IDEB municipal, usa-se o da UF, com a flag
-- `edu_ideb_imputado_uf` marcando a substituição — imputação nunca silenciosa.
CREATE OR REPLACE TABLE `{features}.ext_ideb_saeb` AS
WITH mapa_defasagem AS (
    SELECT 2023 AS ano_alvo, 2021 AS ano_ref, 2019 AS ano_ref_anterior
    UNION ALL
    SELECT 2024 AS ano_alvo, 2023 AS ano_ref, 2021 AS ano_ref_anterior
),
ideb AS (
    SELECT ano, id_municipio, sigla_uf, rede, ideb, taxa_aprovacao,
           indicador_rendimento, nota_saeb_matematica,
           nota_saeb_lingua_portuguesa, nota_saeb_media_padronizada
    FROM `{basedosdados_ideb}.municipio`
    WHERE anos_escolares = 'iniciais (1-5)' AND ensino = 'fundamental'
      AND ano IN (2019, 2021, 2023)
),
ideb_uf AS (
    SELECT ano, sigla_uf, ideb
    FROM `{basedosdados_ideb}.uf`
    WHERE anos_escolares = 'iniciais (1-5)' AND ensino = 'fundamental'
      AND rede = 'publica' AND ano IN (2019, 2021, 2023)
),
saeb AS (
    -- Atenção à fonte: em Língua Portuguesa os níveis vão até 9 (nivel_10 é NULL);
    -- em Matemática vão até 10. Somar 11 níveis em LP produziria NULL silencioso.
    SELECT ano, id_municipio,
        MAX(IF(disciplina = 'LP' AND localizacao = 'total',  media, NULL)) AS media_lp,
        MAX(IF(disciplina = 'MT' AND localizacao = 'total',  media, NULL)) AS media_mt,
        MAX(IF(disciplina = 'LP' AND localizacao = 'total',
               nivel_0 + nivel_1 + nivel_2, NULL))                        AS lp_baixos,
        MAX(IF(disciplina = 'LP' AND localizacao = 'total',
               nivel_6 + nivel_7 + nivel_8 + nivel_9, NULL))              AS lp_altos,
        MAX(IF(disciplina = 'LP' AND localizacao = 'urbana', media, NULL)) AS lp_urbana,
        MAX(IF(disciplina = 'LP' AND localizacao = 'rural',  media, NULL)) AS lp_rural
    FROM `{basedosdados_saeb}.municipio`
    WHERE serie = 5 AND rede = 'total - estadual e municipal'
      AND localizacao IN ('total', 'urbana', 'rural')
      AND ano IN (2019, 2021, 2023)
    GROUP BY ano, id_municipio
),
municipios AS (
    SELECT DISTINCT id_municipio, sigla_uf FROM ideb WHERE rede = 'publica'
),
grade AS (
    SELECT d.ano_alvo, d.ano_ref, d.ano_ref_anterior,
           m.id_municipio, m.sigla_uf, r AS rede_ideb
    FROM mapa_defasagem d
    CROSS JOIN municipios m
    CROSS JOIN UNNEST(['municipal', 'estadual', 'privada']) AS r
)
SELECT
    g.ano_alvo AS ano,
    g.id_municipio,
    INITCAP(g.rede_ideb) AS rede,
    g.ano_ref AS edu_ideb_ano_referencia,
    -- IDEB da rede pública do município (referência principal)
    pub.ideb                        AS edu_ideb_ai_publica,
    own.ideb                        AS edu_ideb_ai_rede_do_aluno,
    ant.ideb                        AS edu_ideb_ai_publica_anterior,
    pub.ideb - ant.ideb             AS edu_ideb_variacao,
    pub.taxa_aprovacao              AS edu_ideb_taxa_aprovacao,
    pub.indicador_rendimento        AS edu_ideb_indicador_rendimento,
    pub.nota_saeb_lingua_portuguesa AS edu_saeb_nota_lp,
    pub.nota_saeb_matematica        AS edu_saeb_nota_mat,
    pub.nota_saeb_media_padronizada AS edu_saeb_nota_padronizada,
    -- SAEB do 5º ano: distribuição de níveis de leitura
    sb.media_lp                     AS edu_saeb5_media_lp,
    sb.media_mt                     AS edu_saeb5_media_mt,
    sb.lp_baixos                    AS edu_saeb5_pct_lp_baixos,
    sb.lp_altos                     AS edu_saeb5_pct_lp_altos,
    sb.lp_urbana - sb.lp_rural      AS edu_saeb5_gap_urbano_rural_lp,
    -- Contexto da UF e imputação explícita
    uf.ideb                         AS edu_ideb_ai_uf,
    COALESCE(pub.ideb, uf.ideb)     AS edu_ideb_ai_publica_imputado,
    pub.ideb IS NULL AND uf.ideb IS NOT NULL AS edu_ideb_imputado_uf
FROM grade g
LEFT JOIN ideb pub
    ON pub.id_municipio = g.id_municipio AND pub.ano = g.ano_ref AND pub.rede = 'publica'
LEFT JOIN ideb own
    ON own.id_municipio = g.id_municipio AND own.ano = g.ano_ref AND own.rede = g.rede_ideb
LEFT JOIN ideb ant
    ON ant.id_municipio = g.id_municipio AND ant.ano = g.ano_ref_anterior AND ant.rede = 'publica'
LEFT JOIN saeb sb
    ON sb.id_municipio = g.id_municipio AND sb.ano = g.ano_ref
LEFT JOIN ideb_uf uf
    ON uf.sigla_uf = g.sigla_uf AND uf.ano = g.ano_ref
