"""Reescrita do `pom.xml` para apontar ao RAML local.

A regra central: essa reescrita só acontece **no destino**, ou seja, no workspace do
Studio. Na pasta de trabalho o `pom.xml` continua apontando para a dependência do
Exchange com a versão travada — é ela que vai para o git/GitLab.
"""

from __future__ import annotations

from pathlib import Path

from lxml import etree

MAVEN_NS = "http://maven.apache.org/POM/4.0.0"
_NS = {"m": MAVEN_NS}

#: Marca de que a dependência foi substituída pelo mule-bridge, para o `pull` saber
#: que aquela alteração é nossa e não deve voltar para a pasta de trabalho.
MARKER = " mule-bridge: apontando para o RAML local; original preservado abaixo "


def _is_raml_dependency(dep: etree._Element) -> bool:
    classifier = dep.find("m:classifier", _NS)
    return classifier is not None and (classifier.text or "").strip() == "raml"


def find_raml_dependency(tree: etree._ElementTree) -> etree._Element | None:
    """Devolve a `<dependency>` do RAML (classifier `raml`), se existir."""
    for dep in tree.getroot().iterfind(".//m:dependencies/m:dependency", _NS):
        if _is_raml_dependency(dep):
            return dep
    return None


def point_to_local_raml(pom: Path, raml_dir: Path) -> bool:
    """Reescreve `pom` para consumir o RAML de `raml_dir` via `systemPath`.

    A dependência original do Exchange é preservada como comentário logo acima, para que
    a substituição seja reversível e legível por quem abrir o arquivo no Studio.

    Devolve True se o arquivo foi alterado, False se não havia nada a fazer (sem
    dependência de RAML, ou já apontando para o local).
    """
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(pom), parser)

    dep = find_raml_dependency(tree)
    if dep is None:
        return False

    if dep.find("m:systemPath", _NS) is not None:
        return False  # já reescrito por uma execução anterior

    original = etree.tostring(dep, encoding="unicode").strip()

    scope = etree.SubElement(dep, f"{{{MAVEN_NS}}}scope")
    scope.text = "system"
    system_path = etree.SubElement(dep, f"{{{MAVEN_NS}}}systemPath")
    system_path.text = str(raml_dir.resolve())

    parent = dep.getparent()
    parent.insert(parent.index(dep), etree.Comment(MARKER))
    parent.insert(parent.index(dep), etree.Comment(f" {original} "))

    tree.write(str(pom), encoding="UTF-8", xml_declaration=True, pretty_print=False)
    return True


def has_local_pointer(pom: Path) -> bool:
    """True se este `pom.xml` já foi reescrito pelo mule-bridge."""
    try:
        return MARKER.strip() in pom.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
