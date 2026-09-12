"""Testes de antivazamento.

Vazamento de dados não aparece como erro: aparece como uma métrica boa demais.
Por isso ele precisa de teste automatizado — é a única classe de defeito de
modelagem que se disfarça de sucesso.
"""
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

from src.preprocessing.features import (
    ALVO,
    IDENTIFICADORES,
    PREFIXOS_DEFASADOS,
    VAZADAS,
    descartar_degeneradas,
    selecionar_features,
)
from src.preprocessing.pipeline import montar_modelo

COLUNAS_EXEMPLO = [
    "ano", "id_aluno", "id_escola", "id_municipio", "sigla_uf", "nome_municipio",
    ALVO, "proficiencia", "presenca", "preenchimento_caderno",
    "alu_caderno", "alu_rede", "mun_lag_taxa_observada", "uf_lag_taxa",
    "ter_latitude", "inf_pct_biblioteca_leitura", "ses_ivs", "edu_ideb_ai_publica",
]


def test_colunas_vazadas_nunca_viram_feature():
    """`proficiencia`, `presenca` e `preenchimento_caderno` jamais entram."""
    feats = selecionar_features(COLUNAS_EXEMPLO)
    for col in VAZADAS:
        assert col not in feats, f"{col} vazou para a lista de features"


def test_identificadores_nunca_viram_feature():
    """Identificadores sem poder generalizável ficam de fora."""
    feats = selecionar_features(COLUNAS_EXEMPLO)
    for col in IDENTIFICADORES:
        assert col not in feats
    assert ALVO not in feats


def test_desenho_temporal_remove_features_defasadas():
    """O Modelo A (treino 2023) não pode usar histórico: 2022 não existe."""
    feats = selecionar_features(COLUNAS_EXEMPLO, permitir_defasadas=False)
    assert not [f for f in feats if f.startswith(PREFIXOS_DEFASADOS)]
    # e no desenho que as permite, elas aparecem
    assert "mun_lag_taxa_observada" in selecionar_features(COLUNAS_EXEMPLO, True)


def test_abt_nao_traz_features_longitudinais_de_escola():
    """`id_escola` é renumerado a cada ano — nenhuma feature `esc_lag_*` é legítima.

    Só 864 dos 36.051 identificadores presentes em 2023 e 2024 (2,4%) apontam para o
    mesmo município: unir os anos por essa chave liga escolas diferentes. O teste
    trava contra a reintrodução acidental dessas colunas na ABT, lendo o SQL que a
    define — a garantia tem de estar na origem, não só na seleção de features.
    """
    sql = (Path(__file__).resolve().parents[1]
           / "sql" / "features" / "20_abt_aluno.sql").read_text(encoding="utf-8")
    linhas_de_codigo = [l for l in sql.splitlines() if not l.strip().startswith("--")]
    assert not any("esc_lag_" in l for l in linhas_de_codigo), (
        "coluna esc_lag_* reintroduzida na ABT — ver docs/decisoes-analiticas.md §3"
    )


def test_target_encoder_nao_vaza_para_dados_novos():
    """O TargetEncoder deve usar encoding fora-da-dobra.

    Construímos o pior caso: uma coluna categórica de altíssima cardinalidade em que
    cada categoria tem UMA linha só. Um target encoder ingênuo memorizaria o alvo de
    cada linha e atingiria AUC ~1,0 no treino. Com validação cruzada interna, a
    categoria nunca vê o próprio alvo, e o desempenho em dados novos fica no acaso —
    que é o correto, já que a coluna não carrega informação generalizável.
    """
    rng = np.random.default_rng(0)
    n = 4000
    X = pd.DataFrame({"id_municipio": [f"m{i}" for i in range(n)],
                      "ruido": rng.normal(size=n)})
    y = pd.Series(rng.integers(0, 2, n))

    modelo = montar_modelo(X, LogisticRegression(max_iter=500), escalonar=True)
    modelo.fit(X, y)

    X_novo = pd.DataFrame({"id_municipio": [f"m{i}" for i in range(n, 2 * n)],
                           "ruido": rng.normal(size=n)})
    y_novo = pd.Series(rng.integers(0, 2, n))
    auc = roc_auc_score(y_novo, modelo.predict_proba(X_novo)[:, 1])
    assert 0.40 < auc < 0.60, (
        f"AUC {auc:.3f} em dados sem sinal — indício de vazamento pelo encoding"
    )


def test_imputacao_aprende_so_no_treino():
    """A mediana de imputação vem do treino; o teste não participa do ajuste."""
    treino = pd.DataFrame({"x": [1.0, 2.0, 3.0, np.nan], "c": list("aabb")})
    teste = pd.DataFrame({"x": [np.nan], "c": ["a"]})
    y = pd.Series([0, 1, 0, 1])

    modelo = montar_modelo(treino, LogisticRegression(max_iter=200), escalonar=False)
    modelo.fit(treino, y)
    imputador = modelo.named_steps["preproc"].named_transformers_["num"].named_steps["imputar"]
    assert imputador.statistics_[0] == pytest.approx(2.0), (
        "a mediana deveria vir apenas das linhas de treino (1, 2, 3)"
    )
    assert np.isfinite(modelo.predict_proba(teste)[:, 1]).all()


def test_descartar_degeneradas_pega_nulos_e_constantes():
    """Colunas 100% ausentes ou constantes no treino são removidas com motivo."""
    treino = pd.DataFrame({
        "boa": [1.0, 2.0, 3.0],
        "toda_nula": [np.nan] * 3,
        "constante": [7.0] * 3,
    })
    mantidas, descartadas = descartar_degeneradas(treino, list(treino.columns))
    assert mantidas == ["boa"]
    assert "100% ausente" in descartadas["toda_nula"]
    assert "constante" in descartadas["constante"]


def test_peso_amostral_nao_e_feature():
    """O peso do desenho amostral do INEP não entra como preditor.

    Não é vazamento (r = -0,045 em 2023 e -0,066 em 2024), mas sua metodologia mudou
    entre os anos — 13.185 valores distintos em 2023 contra 540 em 2024 — o que
    introduziria deriva de covariável no desenho out-of-time.
    """
    from src.preprocessing.features import ARTEFATOS_AMOSTRAIS

    feats = selecionar_features(COLUNAS_EXEMPLO + ["alu_peso_amostral"])
    for col in ARTEFATOS_AMOSTRAIS:
        assert col not in feats


def test_nome_da_coluna_de_meta_confere_com_a_abt():
    """A coluna de meta usada na análise de risco tem de existir na ABT.

    A meta foi renomeada de `mun_meta_ano_alvo` para `mun_lag_meta_ano_alvo` quando se
    descobriu que ela deriva do resultado de 2023 (correlação 0,968) e precisa ser
    tratada como feature defasada. Este teste trava a divergência entre o SQL que
    produz a coluna e o código que a consome.
    """
    import inspect

    from src.evaluation.aplicacao import risco_de_nao_atingir_meta

    padrao = inspect.signature(risco_de_nao_atingir_meta).parameters["coluna_meta"].default
    sql = (Path(__file__).resolve().parents[1]
           / "sql" / "features" / "20_abt_aluno.sql").read_text(encoding="utf-8")
    assert padrao in sql, f"`{padrao}` não é produzida pela ABT"
