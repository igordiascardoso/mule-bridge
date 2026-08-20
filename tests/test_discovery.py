from __future__ import annotations

from mule_bridge import discovery


def test_encontra_api_e_raml_como_filhos_diretos(workspace):
    found = discovery.find_projects(workspace["work"])
    assert {(p.name, p.kind) for p in found} == {
        ("pedidos-api", "api"),
        ("pedidos-raml", "raml"),
    }


def test_sugere_raml_irmao_pelo_prefixo(workspace):
    found = discovery.find_projects(workspace["work"])
    api = next(p for p in found if p.kind == "api")
    assert discovery.guess_raml_sibling(api, found).name == "pedidos-raml"


def test_pasta_inexistente_nao_quebra(tmp_path):
    assert discovery.find_projects(tmp_path / "nada") == []
