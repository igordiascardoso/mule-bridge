"""Descoberta de projetos nos dois lados.

A ferramenta nunca adivinha: ela lista o que encontrou de cada lado e a escolha final
é sempre da pessoa (ver `cli.init`).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

#: Caminhos default do workspace do Anypoint Studio, testados em ordem.
#:
#: A lista cobre os locais que a instalação padrão usa, mas não substitui a descoberta
#: real: quem instalou o Studio noutro drive, ou escolheu um workspace na hora de abrir,
#: não aparece aqui. Para esses, `workspaces_recentes_do_studio` lê o que o próprio
#: Studio registrou, e no fim o usuário sempre pode digitar o caminho.
STUDIO_WORKSPACE_HINTS: tuple[str, ...] = (
    "~/AnypointStudio/studio-workspace",
    "~/AnypointStudio-workspace",
    "~/AnypointStudio/workspace",
    "~/AnypointStudio",
    "~/Documents/AnypointStudio/studio-workspace",
    "~/Documents/AnypointStudio-workspace",
    "~/mule-workspace",
    "~/workspace",
)

#: Pastas onde procurar por workspaces, um nível abaixo. Cobre o caso de o Studio ter sido
#: instalado fora de `~` — comum quando o disco do usuário é pequeno e há um `D:` maior.
RAIZES_DE_BUSCA: tuple[str, ...] = (
    "~",
    "~/Documents",
    "C:/",
    "D:/",
    "E:/",
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


def parece_workspace(path: Path) -> bool:
    """Reconhece um workspace do Studio pela estrutura, não pelo nome.

    O `.metadata` é criado pelo Eclipse na primeira abertura, então está em todo workspace
    de verdade e em nenhuma pasta comum. Um diretório que só contém projetos Mule também
    conta: quem move o workspace de lugar às vezes deixa o `.metadata` atrás.
    """
    if not path.is_dir():
        return False
    if (path / ".metadata").is_dir():
        return True
    try:
        return any(is_mule_api(c) for c in path.iterdir() if c.is_dir())
    except OSError:
        # Sem permissão de leitura, ou drive de rede que caiu: não é candidato.
        return False


def find_studio_workspaces() -> list[Path]:
    """Workspaces do Studio prováveis nesta máquina, sem repetir caminho.

    Procura em três frentes, da mais provável para a mais custosa: os caminhos padrão da
    instalação, as pastas `AnypointStudio*` um nível abaixo das raízes conhecidas, e os
    diretórios que têm cara de workspace nessas mesmas raízes.

    Nunca é exaustivo — varrer o disco inteiro seria lento e ainda assim falharia num
    caminho de rede. É por isso que o `init` sempre oferece digitar o caminho à mão.
    """
    achados: list[Path] = []

    def somar(p: Path) -> None:
        if p.is_dir() and p not in achados:
            achados.append(p)

    for hint in STUDIO_WORKSPACE_HINTS:
        somar(Path(hint).expanduser())

    for raiz_bruta in RAIZES_DE_BUSCA:
        raiz = Path(raiz_bruta).expanduser()
        if not raiz.is_dir():
            continue
        try:
            filhos = sorted(raiz.iterdir())
        except OSError:
            continue

        for filho in filhos:
            if not filho.is_dir() or filho.name.startswith("$"):
                continue
            nome = filho.name.lower()
            if "anypoint" in nome or "mulesoft" in nome:
                somar(filho)
                try:
                    for neto in sorted(filho.iterdir()):
                        if neto.is_dir() and parece_workspace(neto):
                            somar(neto)
                except OSError:
                    continue
            elif "workspace" in nome and parece_workspace(filho):
                somar(filho)

    return [p for p in achados if parece_workspace(p)]


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
