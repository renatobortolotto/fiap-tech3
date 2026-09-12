"""Testes das partições de validação.

Uma partição malfeita é vazamento por outro nome: se o mesmo município aparece no
treino e no teste, o modelo reconhece o território em vez de generalizar.
"""
import numpy as np
import pandas as pd

from src.modeling.dataset import cv_agrupada, split_espacial, split_temporal
from src.preprocessing.features import ALVO


def _base(n=4000, seed=0):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "ano": rng.choice([2023, 2024], n),
        "id_municipio": rng.choice([f"m{i}" for i in range(120)], n),
        "sigla_uf": rng.choice(list("ABCDE"), n),
        ALVO: rng.integers(0, 2, n).astype(bool),
    })


def test_split_temporal_nao_mistura_anos():
    treino, teste = split_temporal(_base())
    assert set(treino["ano"]) == {2023}
    assert set(teste["ano"]) == {2024}


def test_split_espacial_nao_compartilha_municipios():
    treino, teste = split_espacial(_base())
    assert not set(treino["id_municipio"]) & set(teste["id_municipio"])
    assert len(treino) + len(teste) == 4000


def test_cv_agrupada_mantem_municipios_inteiros_na_dobra():
    df = _base()
    cv = cv_agrupada(n_splits=4)
    for idx_tr, idx_va in cv.split(df, df[ALVO], groups=df["id_municipio"]):
        mun_tr = set(df.iloc[idx_tr]["id_municipio"])
        mun_va = set(df.iloc[idx_va]["id_municipio"])
        assert not mun_tr & mun_va, "município apareceu em treino e validação"


def test_estratos_de_cobertura_classificam_corretamente():
    from src.evaluation.metrics import estratos_de_cobertura

    treino = pd.DataFrame({"id_municipio": ["a", "b"], "sigla_uf": ["X", "X"]})
    teste = pd.DataFrame({"id_municipio": ["a", "c", "z"],
                          "sigla_uf": ["X", "X", "Y"]})
    assert list(estratos_de_cobertura(treino, teste)) == [
        "município visto", "município novo (UF vista)", "UF nova"
    ]
