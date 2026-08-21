"""Persistência do par pasta-de-trabalho <-> workspace do Studio.

O arquivo fica na raiz da pasta de trabalho, como `.mule-bridge.toml`, para que o
pareamento escolhido uma vez seja lembrado nas execuções seguintes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import tomlkit

CONFIG_NAME = ".mule-bridge.toml"

#: Nunca copiados em nenhuma direção — artefatos de build, metadados de VCS e do Studio.
DEFAULT_EXCLUDES: tuple[str, ...] = (
    ".git",
    ".svn",
    "target",
    ".mule",
    ".settings",
    "__pycache__",
    ".DS_Store",
    CONFIG_NAME,
)


@dataclass
class ProjectPair:
    """Um par sincronizável: uma pasta na origem, a correspondente no destino."""

    work: str
    studio: str


@dataclass
class BridgeConfig:
    """Config resolvida de um repositório de trabalho."""

    work_root: Path
    studio_root: Path
    api: ProjectPair
    raml: ProjectPair | None = None
    excludes: list[str] = field(default_factory=lambda: list(DEFAULT_EXCLUDES))
    path: Path | None = None

    @property
    def pairs(self) -> list[ProjectPair]:
        """Pares a sincronizar; o RAML entra junto por ser pasta irmã da API."""
        return [p for p in (self.api, self.raml) if p is not None]


def config_path(work_root: Path) -> Path:
    return work_root / CONFIG_NAME


def exists(work_root: Path) -> bool:
    return config_path(work_root).is_file()


def load(work_root: Path) -> BridgeConfig:
    """Lê `.mule-bridge.toml` da raiz da pasta de trabalho."""
    from .errors import ConfigError

    p = config_path(work_root)
    if not p.is_file():
        raise ConfigError(
            f"Nenhuma config encontrada em {p}. Rode `ponte init` nesta pasta primeiro."
        )
    doc = tomlkit.parse(p.read_text(encoding="utf-8"))

    studio_root = Path(str(doc["studio"]["root"])).expanduser()
    api = ProjectPair(str(doc["api"]["work"]), str(doc["api"]["studio"]))

    raml = None
    if "raml" in doc:
        raml = ProjectPair(str(doc["raml"]["work"]), str(doc["raml"]["studio"]))

    excludes = [str(x) for x in doc.get("excludes", list(DEFAULT_EXCLUDES))]
    return BridgeConfig(
        work_root=work_root,
        studio_root=studio_root,
        api=api,
        raml=raml,
        excludes=excludes,
        path=p,
    )


def save(cfg: BridgeConfig) -> Path:
    """Grava a config na raiz da pasta de trabalho e devolve o caminho escrito."""
    doc = tomlkit.document()
    doc.add(tomlkit.comment("mule-bridge — pareamento pasta de trabalho <-> workspace do Studio"))

    studio = tomlkit.table()
    studio["root"] = str(cfg.studio_root)
    doc["studio"] = studio

    api = tomlkit.table()
    api["work"] = cfg.api.work
    api["studio"] = cfg.api.studio
    doc["api"] = api

    if cfg.raml is not None:
        raml = tomlkit.table()
        raml["work"] = cfg.raml.work
        raml["studio"] = cfg.raml.studio
        doc["raml"] = raml

    doc["excludes"] = cfg.excludes

    p = config_path(cfg.work_root)
    p.write_text(tomlkit.dumps(doc), encoding="utf-8")
    return p
