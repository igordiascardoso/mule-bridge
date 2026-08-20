from __future__ import annotations

from mule_bridge import pomrewrite


def test_aponta_para_raml_local_e_preserva_original(workspace):
    pom = workspace["studio"] / "studio-pedidos" / "pom.xml"
    raml = workspace["studio"] / "studio-pedidos-raml"

    assert pomrewrite.point_to_local_raml(pom, raml) is True

    text = pom.read_text(encoding="utf-8")
    assert str(raml.resolve()) in text
    assert "1.1.54" in text, "a dependência original do Exchange deve ficar como comentário"
    assert pomrewrite.has_local_pointer(pom)


def test_reescrita_e_idempotente(workspace):
    pom = workspace["studio"] / "studio-pedidos" / "pom.xml"
    raml = workspace["studio"] / "studio-pedidos-raml"
    pomrewrite.point_to_local_raml(pom, raml)
    assert pomrewrite.point_to_local_raml(pom, raml) is False


def test_pom_sem_dependencia_de_raml_fica_intacto(tmp_path):
    pom = tmp_path / "pom.xml"
    pom.write_text(
        '<?xml version="1.0"?><project xmlns="http://maven.apache.org/POM/4.0.0">'
        "<dependencies/></project>",
        encoding="utf-8",
    )
    before = pom.read_text(encoding="utf-8")
    assert pomrewrite.point_to_local_raml(pom, tmp_path) is False
    assert pom.read_text(encoding="utf-8") == before
