-- features.abt_aluno — Analytical Base Table, grão ALUNO
--
-- Junta a população de modelagem a todos os blocos de contexto. Todos os joins são
-- LEFT: nenhum aluno é descartado por ausência de feature — a ausência é tratada
-- explicitamente no pipeline (imputação + indicador binário de ausência), porque
-- "sem dado" é, aqui, uma informação sobre o município e não um acidente.
--
-- Convenção de prefixos (ver src/preprocessing/features.py):
--   alu_  aluno | esc_lag_ escola (histórico) | inf_ escola (infraestrutura)
--   inse_ escola (socioeconômico) | edu_ educacional | mun_ município (educacional)
--   ses_  município (socioeconômico) | fin_ município (financiamento)
--   ter_  território | uf_lag_ UF
--
-- Chave de junção dos blocos externos: (ano, id_municipio, rede). O grão escolar é
-- inalcançável porque o id_escola dos microdados é anonimizado (docs §6).
CREATE OR REPLACE TABLE `{features}.abt_aluno`
PARTITION BY RANGE_BUCKET(ano, GENERATE_ARRAY(2023, 2031, 1))
CLUSTER BY id_municipio
AS
SELECT
    -- Identificadores (nunca são features)
    p.ano,
    p.id_aluno,
    p.id_escola,
    p.id_municipio,
    p.sigla_uf,
    t.nome_municipio,

    -- Alvo
    p.alvo_alfabetizado,

    -- Bloco: aluno
    p.caderno     AS alu_caderno,
    p.rede        AS alu_rede,
    p.peso_aluno  AS alu_peso_amostral,

    -- Bloco: escola (histórico próprio, t-1)
    e.esc_lag_taxa_observada,
    e.esc_lag_taxa_suavizada,
    e.esc_lag_desvio_vs_municipio,
    e.esc_lag_n_avaliados,

    -- Bloco: município (educacional, t-1) e metas
    m.mun_lag_taxa_observada,
    m.mun_lag_n_avaliados,
    m.mun_lag_n_escolas,
    m.mun_lag_taxa_oficial,
    m.mun_lag_media_portugues,
    m.mun_lag_meta_ano_alvo,
    m.mun_lag_nivel_alfabetizacao,
    m.mun_lag_pct_participacao,
    m.mun_lag_gap_meta_ano,

    -- Bloco: escola (infraestrutura da rede municipal — Censo Escolar)
    c.inf_n_escolas_ai,
    c.inf_matriculas_ai,
    c.inf_alunos_por_turma_ai,
    c.inf_alunos_por_docente_ai,
    c.inf_pct_tempo_integral_ai,
    c.inf_dispositivos_por_aluno,
    c.inf_pct_urbana,
    c.inf_pct_loc_diferenciada,
    c.inf_pct_agua_potavel,
    c.inf_pct_esgoto_publico,
    c.inf_pct_energia_publica,
    c.inf_pct_lixo_coleta,
    c.inf_pct_internet_aprendizagem,
    c.inf_pct_banda_larga,
    c.inf_pct_biblioteca_leitura,
    c.inf_pct_lab_informatica,
    c.inf_pct_quadra,
    c.inf_pct_parque_infantil,
    c.inf_pct_material_jogo,
    c.inf_pct_refeitorio,
    c.inf_pct_alimentacao,
    c.inf_pct_prof_pedagogia,
    c.inf_pct_conselho_escolar,

    -- Bloco: escola (socioeconômico — INSE agregado)
    n.inse_medio,
    n.inse_medio_uf,
    n.inse_desvio_vs_uf,
    n.inse_desvio_escolas,
    n.inse_min_escola,
    n.inse_pct_niveis_baixos,
    n.inse_pct_niveis_altos,
    n.inse_pct_escolas_rurais,
    n.inse_tamanho_medio_escola,
    n.inse_n_escolas,

    -- Bloco: educacional (indicadores INEP, mesmo ano e rendimento defasado)
    i.edu_tdi_anos_iniciais,
    i.edu_tdi_2ano,
    i.edu_alunos_por_turma_ai,
    i.edu_horas_aula_ai,
    i.edu_afd_grupo1_ai,
    i.edu_afd_grupo5_ai,
    i.edu_docentes_superior_ai,
    i.edu_esforco_docente_n1,
    i.edu_esforco_docente_n6,
    i.edu_complexidade_gestao_n1,
    i.edu_regularidade_docente_alta,
    i.edu_regularidade_docente_baixa,
    i.edu_gap_tdi_rural_urbana,
    i.edu_alunos_por_turma_rural,
    i.edu_aprovacao_ai_lag1,
    i.edu_reprovacao_ai_lag1,
    i.edu_abandono_ai_lag1,

    -- Bloco: educacional (IDEB/SAEB defasados)
    d.edu_ideb_ai_publica,
    d.edu_ideb_ai_rede_do_aluno,
    d.edu_ideb_variacao,
    d.edu_ideb_taxa_aprovacao,
    d.edu_ideb_indicador_rendimento,
    d.edu_saeb_nota_lp,
    d.edu_saeb_nota_mat,
    d.edu_saeb5_media_lp,
    d.edu_saeb5_pct_lp_baixos,
    d.edu_saeb5_pct_lp_altos,
    d.edu_saeb5_gap_urbano_rural_lp,
    d.edu_ideb_ai_uf,
    d.edu_ideb_ai_publica_imputado,
    d.edu_ideb_imputado_uf,

    -- Bloco: município (socioeconômico — IBGE: demografia, economia, Censo 2022)
    b.ses_pib_per_capita,
    b.ses_log_populacao,
    b.ses_idade_mediana,
    b.ses_indice_envelhecimento,
    b.ses_share_pop_5a9,
    b.ses_share_pop_0a14,
    b.ses_moradores_por_domicilio,
    b.ses_densidade_demografica,
    b.ses_share_indigena_quilombola,
    b.ses_taxa_alfabetizacao_15mais,
    b.ses_taxa_alfab_adultos_25a44,
    b.ses_share_esgoto_inadequado,
    b.ses_share_domicilio_precario,

    -- Bloco: município (socioeconômico — vulnerabilidade social e transferência de renda)
    v.ses_ivs,
    v.ses_ivs_capital_humano,
    v.ses_ivs_renda_trabalho,
    v.ses_ivs_infra_urbana,
    v.ses_idhm_educacao,
    v.ses_log_renda_per_capita,
    v.ses_gini,
    v.ses_prop_vulneravel,
    v.ses_prop_domicilio_denso,
    v.ses_prop_resp_sem_fundamental,
    v.ses_prop_mae_sem_fundamental,
    v.ses_fecundidade_total,
    v.ses_mortalidade_infantil,
    v.ses_prop_crianca_fora_escola,
    v.ses_expectativa_anos_estudo,
    v.ses_taxa_atraso_2anos_fund,
    v.ses_taxa_desocupacao,
    v.ses_prop_pobreza_criancas,
    v.ses_taxa_freq_escola_5_6,
    v.ses_taxa_cadunico,
    v.ses_taxa_pbf,
    v.ses_razao_pbf_cadunico,
    v.ses_valor_medio_familia_pbf,
    v.ses_cobertura_pbf_atual,
    v.ses_valor_pbf_per_capita_atual,

    -- Bloco: município (financiamento da educação — FUNDEB/SIOPE e SICONFI)
    fi.fin_fonte_estadual,
    fi.fin_invest_aluno_ens_fund,
    fi.fin_invest_aluno_educ_basica,
    fi.fin_desp_professor_por_aluno,
    fi.fin_pct_mde_sobre_impostos,
    fi.fin_pct_fundeb_remuneracao,
    fi.fin_pct_fundeb_nao_aplicado,
    fi.fin_pct_fundeb_ens_fund,
    fi.fin_pct_fundeb_educ_infantil,
    fi.fin_pct_desp_ens_fund_sobre_educ,
    fi.fin_log_desp_educacao,
    fi.fin_log_receita_fundeb,
    fi.fin_pct_educacao_sobre_desp_total,
    fi.fin_pct_ens_fund_sobre_educacao,
    fi.fin_pct_fundeb_sobre_desp_total,
    fi.fin_pct_complementacao_uniao,

    -- Bloco: território e UF
    t.ter_regiao,
    t.ter_mesorregiao,
    t.ter_latitude,
    t.ter_longitude,
    t.ter_capital_uf,
    t.ter_amazonia_legal,
    t.uf_lag_taxa,
    t.uf_lag_ranking

FROM `{features}.populacao_avaliada` p
LEFT JOIN `{features}.ctx_escola_lag` e
    ON e.ano_alvo = p.ano AND e.id_escola = p.id_escola
LEFT JOIN `{features}.ctx_municipio_lag` m
    ON m.ano_alvo = p.ano AND m.id_municipio = p.id_municipio
LEFT JOIN `{features}.ctx_territorio` t
    ON t.ano_alvo = p.ano AND t.id_municipio = p.id_municipio
LEFT JOIN `{features}.ext_censo_escolar` c
    ON c.ano = p.ano AND c.id_municipio = p.id_municipio AND c.rede = p.rede
LEFT JOIN `{features}.ext_inse` n
    ON n.ano = p.ano AND n.id_municipio = p.id_municipio AND n.rede = p.rede
LEFT JOIN `{features}.ext_indicadores_educacionais` i
    ON i.ano = p.ano AND i.id_municipio = p.id_municipio AND i.rede = p.rede
LEFT JOIN `{features}.ext_ideb_saeb` d
    ON d.ano = p.ano AND d.id_municipio = p.id_municipio AND d.rede = p.rede
LEFT JOIN `{features}.ext_ibge` b
    ON b.ano = p.ano AND b.id_municipio = p.id_municipio
LEFT JOIN `{features}.ext_vulnerabilidade` v
    ON v.ano = p.ano AND v.id_municipio = p.id_municipio
LEFT JOIN `{features}.ext_financas` fi
    ON fi.ano = p.ano AND fi.id_municipio = p.id_municipio
