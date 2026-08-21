"""Config de editor para repositorios aninhados.

O problema: quando as pastas do projeto sao repositorios git proprios dentro da raiz (o
caso comum de `pedidos-api/` com seu remoto, ao lado de `pedidos-raml/`), o VS Code por
padrao lista so o repositorio da raiz. As edicoes feitas dentro das pastas aninhadas
existem para o git, mas nao aparecem no painel do editor — e nao ver o que se mudou e
justamente o que esta ferramenta tenta evitar.

`.vscode/settings.json` resolve isso, e serve tambem para os forks do VS Code (Trae,
Cursor, Windsurf), que leem o mesmo arquivo. IDEs da familia IntelliJ — incluindo o
proprio Anypoint Studio — usam outro formato e ficam de fora.
"""

from __future__ import annotations

import json
from pathlib import Path

CHAVES = {
    "git.repositoryScanMaxDepth": 2,
    "git.openRepositoryInParentFolders": "always",
    "git.detectSubmodules": False,
}

_NOTA = (
    "Escrito pelo mule-bridge: sem isto o painel de controle de codigo lista so o "
    "repositorio da raiz, e as edicoes nos repositorios aninhados nao aparecem."
)


def repos_aninhados(raiz: Path) -> list[str]:
    """Nomes das pastas filhas que sao repositorios git proprios."""
    if not raiz.is_dir():
        return []
    return sorted(
        p.name
        for p in raiz.iterdir()
        if p.is_dir() and not p.name.startswith(".") and (p / ".git").exists()
    )


def precisa_config(raiz: Path) -> bool:
    """True quando ha repo aninhado e a config ainda nao cobre isso."""
    if not repos_aninhados(raiz):
        return False

    atual = _ler(raiz / ".vscode" / "settings.json")
    return any(atual.get(k) != v for k, v in CHAVES.items())


def _ler(arquivo: Path) -> dict:
    """Le o settings.json, tolerando ausencia e conteudo invalido."""
    if not arquivo.is_file():
        return {}
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    return dados if isinstance(dados, dict) else {}


def escrever(raiz: Path) -> Path:
    """Acrescenta as chaves ao `.vscode/settings.json`, preservando o que ja existe.

    Nunca sobrescreve um valor que o usuario tenha definido de proposito: se a chave ja
    esta la, ela fica como esta.
    """
    destino = raiz / ".vscode" / "settings.json"
    cfg = _ler(destino)

    for chave, valor in CHAVES.items():
        cfg.setdefault(chave, valor)
    cfg.setdefault("//", _NOTA)

    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return destino
