"""CLI do mule-bridge — a única camada que carrega lógica de negócio."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, config, discovery
from .config import BridgeConfig, ProjectPair
from .errors import BridgeError, DiscoveryError
from .sync import Direction, SyncPlan, sync_all

app = typer.Typer(
    name="mule-bridge",
    help="Sync de projetos Mule entre a pasta de trabalho e o workspace do Anypoint Studio.",
    add_completion=False,
)
console = Console()
err = Console(stderr=True)


def _fail(exc: BridgeError) -> typer.Exit:
    err.print(f"[bold red]erro:[/] {exc}")
    return typer.Exit(1)


def _choose(title: str, options: list[str], *, default: int = 1) -> int:
    """Mostra as opções encontradas e pede a escolha — nunca adivinha sozinha."""
    console.print(f"\n[bold]{title}[/]")
    for i, opt in enumerate(options, 1):
        console.print(f"  [cyan]{i}[/]. {opt}")
    choice = typer.prompt("Escolha", default=str(default))
    try:
        idx = int(choice)
    except ValueError:
        idx = 0
    if not 1 <= idx <= len(options):
        raise typer.BadParameter(f"Escolha entre 1 e {len(options)}.")
    return idx - 1


def _resolve_root(work_root: Path | None) -> Path:
    """Resolve a raiz da pasta de trabalho no momento da chamada, nao do import."""
    return (work_root or Path.cwd()).resolve()


def _load(work_root: Path) -> BridgeConfig:
    return config.load(work_root)


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Mostra a versão e sai."),
) -> None:
    if version:
        console.print(f"mule-bridge {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        console.print(ctx.get_help())
        raise typer.Exit()


@app.command()
def init(
    work_root: Path | None = typer.Option(
        None, "--work-root", "-w", help="Raiz da pasta de trabalho (default: diretorio atual)."
    ),
    studio_root: Path | None = typer.Option(
        None, "--studio-root", "-s", help="Workspace do Studio (pula a busca automática)."
    ),
    force: bool = typer.Option(False, "--force", help="Sobrescreve uma config existente."),
) -> None:
    """Pareia esta pasta de trabalho com um projeto do workspace do Studio."""
    work_root = _resolve_root(work_root)
    if config.exists(work_root) and not force:
        err.print(
            f"[yellow]Já existe {config.CONFIG_NAME} em {work_root}.[/] Use --force para refazer."
        )
        raise typer.Exit(1)

    try:
        # Lado da pasta de trabalho.
        local = discovery.find_projects(work_root)
        apis = [p for p in local if p.kind == "api"]
        if not apis:
            raise DiscoveryError(
                f"Nenhum projeto Mule encontrado em {work_root} "
                "(esperado: pasta com pom.xml e src/main/mule)."
            )
        api = apis[_choose("Projeto de API nesta pasta de trabalho:", [p.name for p in apis])]

        raml_local = discovery.guess_raml_sibling(api, local)
        ramls = [p for p in local if p.kind == "raml"]
        if ramls:
            labels = [f"{p.name}{'  (sugerido)' if p is raml_local else ''}" for p in ramls]
            labels.append("nenhuma — não sincronizar RAML")
            default = ramls.index(raml_local) + 1 if raml_local else len(labels)
            idx = _choose("Pasta do RAML correspondente:", labels, default=default)
            raml_local = ramls[idx] if idx < len(ramls) else None

        # Lado do workspace do Studio.
        if studio_root is None:
            workspaces = discovery.find_studio_workspaces()
            if not workspaces:
                raise DiscoveryError(
                    "Nenhum workspace do Studio encontrado nos caminhos padrão. "
                    "Informe com --studio-root."
                )
            studio_root = workspaces[
                _choose("Workspace do Anypoint Studio:", [str(w) for w in workspaces])
            ]
        studio_root = studio_root.expanduser().resolve()

        remote = discovery.find_projects(studio_root)
        if not remote:
            raise DiscoveryError(f"Nenhum projeto encontrado em {studio_root}.")
        names = [f"{p.name}  [{p.kind}]" for p in remote]
        studio_api = remote[_choose(f"Projeto no workspace correspondente a {api.name}:", names)]

        studio_raml = None
        if raml_local is not None:
            labels = [*names, "nenhuma — o RAML só existe na pasta de trabalho"]
            idx = _choose(f"Pasta no workspace correspondente a {raml_local.name}:", labels)
            studio_raml = remote[idx] if idx < len(remote) else None

        cfg = BridgeConfig(
            work_root=work_root,
            studio_root=studio_root,
            api=ProjectPair(api.name, studio_api.name),
            raml=(
                ProjectPair(raml_local.name, studio_raml.name)
                if raml_local and studio_raml
                else None
            ),
        )
        written = config.save(cfg)
    except BridgeError as exc:
        raise _fail(exc) from exc

    console.print(f"\n[green]Config gravada em[/] {written}")


def _report(plans: dict[str, SyncPlan], dry_run: bool) -> None:
    table = Table(title="dry-run — nada foi alterado" if dry_run else None)
    table.add_column("projeto")
    table.add_column("copiados", justify="right")
    table.add_column("pom reescrito", justify="right")
    table.add_column("removidos", justify="right")
    table.add_column("ignorados", justify="right")
    for name, plan in plans.items():
        table.add_row(
            name,
            str(len(plan.copied)),
            str(len(plan.rewritten)),
            str(len(plan.deleted)),
            str(len(plan.skipped)),
        )
    console.print(table)

    if sum(p.total for p in plans.values()) == 0:
        console.print("[dim]Nada a sincronizar — os dois lados já estão iguais.[/]")


def _run(direction: Direction, work_root: Path | None, delete: bool, dry_run: bool) -> None:
    try:
        cfg = _load(_resolve_root(work_root))
        plans = sync_all(cfg, direction, delete=delete, dry_run=dry_run)
    except BridgeError as exc:
        raise _fail(exc) from exc
    _report(plans, dry_run)


@app.command()
def push(
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(
        False, "--delete", help="Remove no workspace o que ja nao existe na pasta de trabalho."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Só mostra o que faria."),
) -> None:
    """Pasta de trabalho -> workspace do Studio (reescreve o pom.xml só no destino)."""
    _run(Direction.PUSH, work_root, delete, dry_run)


@app.command()
def pull(
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(
        False, "--delete", help="Remove na pasta de trabalho o que ja nao existe no workspace."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Só mostra o que faria."),
) -> None:
    """Workspace do Studio -> pasta de trabalho (ignora o pom.xml apontado ao RAML local)."""
    _run(Direction.PULL, work_root, delete, dry_run)


@app.command()
def status(
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
) -> None:
    """Mostra o pareamento configurado e o que um push faria agora."""
    try:
        cfg = _load(_resolve_root(work_root))
    except BridgeError as exc:
        raise _fail(exc) from exc

    console.print(f"[bold]trabalho:[/] {cfg.work_root}")
    console.print(f"[bold]workspace:[/] {cfg.studio_root}")
    for pair in cfg.pairs:
        console.print(f"  {pair.work}  ->  {pair.studio}")
    console.print()
    _run(Direction.PUSH, work_root, False, True)


if __name__ == "__main__":  # pragma: no cover
    app()
