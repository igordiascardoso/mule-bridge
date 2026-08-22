"""Validacao do cabecalho #%RAML, sabendo distinguir fragmentos de !include."""

from __future__ import annotations

from pathlib import Path

from mule_bridge import ramlvalidate


def _escreve(pasta: Path, arquivos: dict[str, str]) -> None:
    for rel, conteudo in arquivos.items():
        p = pasta / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo, encoding="utf-8")


def test_arquivo_valido_nao_e_problema(tmp_path):
    _escreve(tmp_path, {"api.raml": "#%RAML 1.0\ntitle: X\n"})

    assert ramlvalidate.validar(tmp_path, main="api.raml") == []


def test_arquivo_sem_cabecalho_e_problema(tmp_path):
    _escreve(tmp_path, {"api.raml": "# comentario\ntitle: X\n"})

    problemas = ramlvalidate.validar(tmp_path, main="api.raml")

    assert [p.caminho for p in problemas] == ["api.raml"]


def test_fragmento_de_include_nao_precisa_de_cabecalho(tmp_path):
    """Regressao real: fragmento incluido nao tem #%RAML e nao deveria ser acusado."""
    _escreve(
        tmp_path,
        {
            "api.raml": "#%RAML 1.0\ntitle: X\n/recurso:\n  !include domain/fragmento.raml\n",
            "domain/fragmento.raml": "post:\n  displayName: Um recurso\n",
        },
    )

    assert ramlvalidate.validar(tmp_path, main="api.raml") == []


def test_include_com_aspas_tambem_e_reconhecido(tmp_path):
    _escreve(
        tmp_path,
        {
            "api.raml": '#%RAML 1.0\ntitle: X\n/recurso:\n  !include "domain/frag.raml"\n',
            "domain/frag.raml": "post:\n  displayName: Y\n",
        },
    )

    assert ramlvalidate.validar(tmp_path, main="api.raml") == []


def test_main_sempre_e_checado_mesmo_se_citado_como_include(tmp_path):
    """Um projeto nao deveria incluir o proprio main, mas se acontecer, main ainda valida."""
    _escreve(
        tmp_path,
        {
            "api.raml": "sem cabecalho\n",
            "outro.raml": "#%RAML 1.0\ntitle: X\n!include api.raml\n",
        },
    )

    problemas = ramlvalidate.validar(tmp_path, main="api.raml")

    assert [p.caminho for p in problemas] == ["api.raml"]


def test_varios_fragmentos_e_so_um_defeito_real(tmp_path):
    """Caso do projeto real: muitos includes legitimos, um defeito real no main."""
    _escreve(
        tmp_path,
        {
            "api.raml": "#DEFEITO-ANTES-DO-CABECALHO\n#%RAML 1.0\ntitle: X\n",
            "domain/a.raml": "get:\n  displayName: A\n",
            "domain/b.raml": "post:\n  displayName: B\n",
            "types/tipos.raml": "type: object\n",
        },
    )
    (tmp_path / "api.raml").write_text(
        "#DEFEITO-ANTES-DO-CABECALHO\n#%RAML 1.0\ntitle: X\n"
        "/a:\n  !include domain/a.raml\n/b:\n  !include domain/b.raml\n"
        "types:\n  T: !include types/tipos.raml\n",
        encoding="utf-8",
    )

    problemas = ramlvalidate.validar(tmp_path, main="api.raml")

    assert [p.caminho for p in problemas] == ["api.raml"]


def test_arquivo_vazio_e_problema(tmp_path):
    _escreve(tmp_path, {"api.raml": "\n\n"})

    problemas = ramlvalidate.validar(tmp_path, main="api.raml")

    assert [p.caminho for p in problemas] == ["api.raml"]
