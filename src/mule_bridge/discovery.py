"""Descoberta de projetos nos dois lados.

A ferramenta nunca adivinha: ela lista o que encontrou de cada lado e a escolha final
é sempre da pessoa (ver `cli.init`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Caminhos default do workspace do Anypoint Studio, testados em ordem.
STUDIO_WORKSPACE_HINTS: tuple[str, ...] = (
    "~/AnypointStudio/studio-workspace",
    "~/AnypointStudio-workspace",
    "~/AnypointStudio/workspace",
)


@dataclass
class MuleProject:
    """Uma pasta reconhecida como projeto Mule (ou como pasta de RAML irmã)."""

    path: Path
    kind: str  # "api" | "raml"

    @property
    def name(self) -> str:
        return self.path.name


def is_mule_api(path: Path) -> bool:
    """Projeto Mule: tem `pom.xml` e a pasta de flows `src/main/mule`."""
    return (path / "pom.xml").is_file() and (path / "src" / "main" / "mule").is_dir()


def is_raml_project(path: Path) -> bool:
    """Pasta de RAML: contém `.raml` na raiz ou em `src/main/resources/api`."""
    if any(path.glob("*.raml")):
        return True
    return any((path / "src" / "main" / "resources" / "api").glob("*.raml"))


def find_projects(root: Path) -> list[MuleProject]:
    """Lista os projetos diretamente sob `root`, sem descer recursivamente.

    Não é recursivo de propósito: tanto a raiz do repositório quanto o workspace do
    Studio guardam os projetos como filhos diretos (ex: `pedidos-api/`, `pedidos-raml/`).
    """
    if not root.is_dir():
        return []

    found: list[MuleProject] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir() or child.name.startswith("."):
            continue
        if is_mule_api(child):
            found.append(MuleProject(child, "api"))
        elif is_raml_project(child):
            found.append(MuleProject(child, "raml"))
    return found


def find_studio_workspaces() -> list[Path]:
    """Workspaces do Studio prováveis, nos caminhos default da máquina."""
    return [p for h in STUDIO_WORKSPACE_HINTS if (p := Path(h).expanduser()).is_dir()]


def guess_raml_sibling(api: MuleProject, candidates: list[MuleProject]) -> MuleProject | None:
    """Sugere a pasta de RAML irmã da API — só sugestão, a escolha continua da pessoa.

    Segue o padrão esperado: `pedidos-raml/` ao lado de `pedidos-api/`,
    ou seja, mesmo prefixo antes do sufixo `-api`.
    """
    ramls = [c for c in candidates if c.kind == "raml"]
    if not ramls:
        return None

    prefix = api.name[: -len("-api")] if api.name.endswith("-api") else api.name
    for r in ramls:
        if r.name.startswith(prefix):
            return r
    return ramls[0] if len(ramls) == 1 else None
