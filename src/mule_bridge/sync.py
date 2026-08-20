"""Motor de sync nas duas direções, com o pom.xml como caso especial."""

from __future__ import annotations

import filecmp
import shutil
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from . import pomrewrite
from .config import BridgeConfig, ProjectPair
from .errors import SyncError


class Direction(str, Enum):
    PUSH = "push"  # pasta de trabalho -> workspace do Studio
    PULL = "pull"  # workspace do Studio -> pasta de trabalho


@dataclass
class SyncPlan:
    """O que uma execução faria/fez, por caminho relativo ao projeto."""

    direction: Direction
    copied: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)
    rewritten: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return len(self.copied) + len(self.deleted) + len(self.rewritten)


def _excluded(rel: Path, excludes: list[str]) -> bool:
    return any(part in excludes for part in rel.parts)


def _walk(root: Path, excludes: list[str]) -> dict[Path, Path]:
    """Mapeia caminho relativo -> caminho absoluto de todos os arquivos não excluídos."""
    out: dict[Path, Path] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root)
        if not _excluded(rel, excludes):
            out[rel] = p
    return out


def _same(a: Path, b: Path) -> bool:
    return b.exists() and filecmp.cmp(a, b, shallow=False)


def sync_pair(
    pair: ProjectPair,
    cfg: BridgeConfig,
    direction: Direction,
    *,
    raml_dir: Path | None = None,
    delete: bool = False,
    dry_run: bool = False,
) -> SyncPlan:
    """Sincroniza um par de pastas numa direção.

    `raml_dir`, quando informado num `push`, dispara a reescrita do `pom.xml` só no
    destino. No `pull`, o `pom.xml` reescrito é ignorado, para que o
    apontamento local nunca volte para a pasta de trabalho.
    """
    work = cfg.work_root / pair.work
    studio = cfg.studio_root / pair.studio
    src, dst = (work, studio) if direction is Direction.PUSH else (studio, work)

    if not src.is_dir():
        raise SyncError(f"Origem não existe: {src}")
    dst.mkdir(parents=True, exist_ok=True)

    plan = SyncPlan(direction=direction)
    src_files = _walk(src, cfg.excludes)

    for rel, src_file in sorted(src_files.items()):
        dst_file = dst / rel
        is_pom = rel.as_posix() == "pom.xml"

        # No pull, um pom.xml já reescrito é nosso — nunca volta para a pasta de trabalho.
        if direction is Direction.PULL and is_pom and pomrewrite.has_local_pointer(src_file):
            plan.skipped.append(rel.as_posix())
            continue

        needs_rewrite = (
            direction is Direction.PUSH and is_pom and raml_dir is not None
        )

        if not needs_rewrite and _same(src_file, dst_file):
            continue

        if dry_run:
            (plan.rewritten if needs_rewrite else plan.copied).append(rel.as_posix())
            continue

        dst_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_file, dst_file)

        if needs_rewrite and pomrewrite.point_to_local_raml(dst_file, raml_dir):
            plan.rewritten.append(rel.as_posix())
        else:
            plan.copied.append(rel.as_posix())

    if delete:
        for rel in sorted(_walk(dst, cfg.excludes)):
            if rel not in src_files:
                plan.deleted.append(rel.as_posix())
                if not dry_run:
                    (dst / rel).unlink()

    return plan


def sync_all(
    cfg: BridgeConfig, direction: Direction, *, delete: bool = False, dry_run: bool = False
) -> dict[str, SyncPlan]:
    """Sincroniza API e RAML juntos — uma mudança no RAML afeta a API."""
    raml_dir = None
    if direction is Direction.PUSH and cfg.raml is not None:
        raml_dir = cfg.studio_root / cfg.raml.studio

    plans: dict[str, SyncPlan] = {}
    for pair in cfg.pairs:
        is_api = pair is cfg.api
        plans[pair.work] = sync_pair(
            pair,
            cfg,
            direction,
            raml_dir=raml_dir if is_api else None,
            delete=delete,
            dry_run=dry_run,
        )
    return plans
