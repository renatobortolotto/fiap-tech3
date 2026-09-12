"""Testes da documentação.

O README é o entregável principal do projeto e referencia dezenas de arquivos e
figuras. Um link quebrado só aparece quando alguém abre o documento — e, numa
entrega avaliada, isso é tarde demais. Estes testes tornam a verificação mecânica.
"""
import re
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
README = RAIZ / "README.md"
TEXTO = README.read_text(encoding="utf-8")


def test_readme_cobre_as_secoes_exigidas():
    """As 11 seções que o edital exige, na ordem, mais a de reprodução."""
    exigidas = [
        "Contexto do problema", "Objetivo analítico", "Base utilizada",
        "Etapas de modelagem", "Escolha do algoritmo", "Métricas de avaliação",
        "Interpretação dos resultados", "Insights encontrados",
        "Limitações do projeto", "Aplicação prática para políticas públicas",
        "Possíveis evoluções futuras",
    ]
    titulos = re.findall(r"^## \d+\. (.+)$", TEXTO, flags=re.MULTILINE)
    for i, secao in enumerate(exigidas):
        assert titulos[i] == secao, f"seção {i+1} deveria ser '{secao}', é '{titulos[i]}'"


def test_tabelas_do_readme_tem_colunas_consistentes():
    """Toda linha de uma tabela markdown precisa do mesmo número de separadores."""
    linhas = TEXTO.splitlines()
    bloco, inicio, problemas = [], None, []
    for i, linha in enumerate(linhas + [""]):
        if linha.strip().startswith("|"):
            inicio = i + 1 if inicio is None else inicio
            bloco.append(linha.count("|"))
        else:
            if len(bloco) >= 2 and len(set(bloco)) > 1:
                problemas.append(f"linha {inicio}: {sorted(set(bloco))}")
            bloco, inicio = [], None
    assert not problemas, f"tabelas com colunas inconsistentes: {problemas}"


def test_ancoras_do_sumario_resolvem():
    """Todo link `#secao` do sumário tem um título correspondente."""
    titulos = re.findall(r"^## (.+)$", TEXTO, flags=re.MULTILINE)
    ancoras = {
        re.sub(r"[^a-z0-9áâãàéêíóôõúüç\- ]", "", t.lower()).strip().replace(" ", "-")
        for t in titulos
    }
    referencias = re.findall(r"\]\(#([^)]+)\)", TEXTO)
    faltando = [r for r in referencias if r not in ancoras]
    assert not faltando, f"âncoras não resolvidas: {faltando}"


@pytest.mark.parametrize("padrao", [r"!\[[^\]]*\]\((images/[^)]+)\)",
                                    r"\]\((docs/[^)#]+)\)"])
def test_arquivos_referenciados_existem(padrao):
    """Figuras e documentos citados no README precisam existir no repositório.

    As figuras são geradas por `make eda`, `make modelo-a` e `make interpretar`;
    se este teste falhar num clone novo, rode `make tudo` antes.
    """
    referenciados = {m for m in re.findall(padrao, TEXTO)}
    ausentes = sorted(r for r in referenciados if not (RAIZ / r).exists())
    assert not ausentes, f"referenciados mas ausentes: {ausentes}"


def test_referencias_cruzadas_do_readme_resolvem():
    """Todo `§X.Y` citado no texto corresponde a uma seção ou subseção existente.

    O README se apoia fortemente em referências internas — cada achado aponta para
    onde a evidência está. Uma referência quebrada desfaz exatamente a cadeia de
    argumento que ela deveria sustentar.
    """
    existentes = set(re.findall(r"^#{2,3} (\d+(?:\.\d+)?)[\. ]", TEXTO, flags=re.MULTILINE))
    citadas = set(re.findall(r"§\s?(\d+(?:\.\d+)?)", TEXTO))
    faltando = sorted(citadas - existentes,
                      key=lambda x: [int(p) for p in x.split(".")])
    assert not faltando, f"referências a seções inexistentes: {faltando}"
