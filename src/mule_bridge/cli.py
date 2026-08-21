"""CLI do mule-bridge — a única camada que carrega lógica de negócio."""

from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from . import __version__, config, discovery, editorconfig, pomrewrite, reconcile
from .config import BridgeConfig, ProjectPair
from .errors import BridgeError, ConfigError, DiscoveryError, NonInteractiveError
from .sync import Direction, SyncPlan, sync_all

app = typer.Typer(
    name="ponte",
    help="Sync de projetos Mule entre a pasta de trabalho e o workspace do Anypoint Studio.",
    add_completion=False,
)
console = Console()
err = Console(stderr=True)


def _fail(exc: BridgeError) -> typer.Exit:
    err.print(f"[bold red]erro:[/] {exc}")
    return typer.Exit(1)


def _choose(title: str, options: list[str], *, flag: str, default: int = 1) -> int:
    """Mostra as opções encontradas e pede a escolha — nunca adivinha sozinha.

    Sem terminal interativo (extensão de IDE, agente de IA, CI) não há como perguntar: o
    erro lista as opções encontradas e ensina a flag que dispensa o prompt.
    """
    # Sempre perguntar, mesmo com uma opcao so. Resolver sozinho parecia poupar uma ida e
    # volta, mas e onde o erro passa sem ninguem ver: num teste de instalacao do zero, o
    # unico candidato oferecido como par do RAML era o projeto da API, e o comando o
    # escolheu calado — gravando um pareamento errado que so apareceu quando o
    # `parastudio` criou uma pasta de lixo no workspace. O pareamento e do usuario.
    console.print(f"\n[bold]{title}[/]")
    for i, opt in enumerate(options, 1):
        console.print(f"  [cyan]{i}[/]. {opt}")

    try:
        choice = typer.prompt("Escolha", default=str(default))
    except (typer.Abort, EOFError, OSError) as exc:
        # Sem terminal para ler a resposta (extensão de IDE, agente de IA, CI): em vez de
        # abortar sem explicação, ensina a flag que dispensa o prompt.
        exemplo = f"{flag} {options[0].split()[0]}" if options else flag
        raise NonInteractiveError(
            f"{title.rstrip(':')} — não há terminal interativo para perguntar.\n"
            f"Repita o comando escolhendo pela flag, ex: {exemplo}"
        ) from exc
    try:
        idx = int(choice)
    except ValueError:
        idx = 0
    if not 1 <= idx <= len(options):
        raise typer.BadParameter(f"Escolha entre 1 e {len(options)}.")
    return idx - 1


def _pick(
    title: str, options: list[str], *, flag: str, given: str | None = None, default: int = 1
) -> int:
    """Resolve uma escolha pelo nome vindo da flag, ou cai no prompt interativo.

    A comparação é pelo primeiro token de cada rótulo, que é o nome da pasta — assim
    `--raml pedidos-raml` casa com o rótulo "pedidos-raml  (sugerido)".
    """
    if given is None:
        return _choose(title, options, flag=flag, default=default)

    alvo = given.strip().lower()
    for i, opt in enumerate(options):
        if opt.split()[0].lower() == alvo:
            return i

    disponiveis = ", ".join(o.split()[0] for o in options)
    raise ConfigError(f"{flag} {given!r} nao encontrado. Opcoes: {disponiveis}")


def _escolher_workspace() -> Path:
    """Pergunta onde fica o workspace do Studio, sempre com a saída de digitar o caminho.

    A busca automática nunca cobre todos os casos — workspace noutro drive, em pasta de
    rede, num caminho que só o usuário conhece. Então a última opção da lista é sempre
    "outro caminho", e quando nada é encontrado o prompt já pede o caminho direto.
    """
    workspaces = discovery.find_studio_workspaces()
    OUTRO = "outro caminho — eu digito"

    if workspaces:
        idx = _choose(
            "Onde fica o workspace do Anypoint Studio?",
            [*(str(w) for w in workspaces), OUTRO],
            flag="--studio-root",
        )
        if idx < len(workspaces):
            return workspaces[idx]
    else:
        console.print(
            "\n[yellow]Nao encontrei o workspace do Studio nos caminhos usuais.[/]\n"
            "[dim]No Studio, o caminho aparece em File > Switch Workspace.[/]"
        )

    try:
        digitado = typer.prompt("Caminho do workspace")
    except (typer.Abort, EOFError, OSError) as exc:
        raise NonInteractiveError(
            "Onde fica o workspace do Anypoint Studio? — não há terminal interativo "
            "para perguntar.\n"
            "Repita o comando com o caminho, ex: "
            "--studio-root ~/AnypointStudio/studio-workspace"
        ) from exc

    return Path(digitado.strip().strip('"').strip("'"))


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
        console.print(f"ponte (mule-bridge) {__version__}")
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
    api_name: str | None = typer.Option(
        None, "--api", help="Nome da pasta da API, em vez de escolher no prompt."
    ),
    raml_name: str | None = typer.Option(
        None, "--raml", help="Nome da pasta do RAML, ou 'nenhuma' para nao sincronizar."
    ),
    studio_api_name: str | None = typer.Option(
        None, "--studio-api", help="Nome do projeto no workspace correspondente a API."
    ),
    studio_raml_name: str | None = typer.Option(
        None, "--studio-raml", help="Nome do projeto no workspace correspondente ao RAML."
    ),
    force: bool = typer.Option(False, "--force", help="Sobrescreve uma config existente."),
) -> None:
    """Pareia esta pasta de trabalho com um projeto do workspace do Studio.

    Sem as flags de escolha, pergunta interativamente. Passando `--api`, `--raml`,
    `--studio-api` e `--studio-raml`, roda sem prompt nenhum — que é como um agente de IA
    ou uma extensão de IDE conseguem executá-lo.
    """
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
        api = apis[
            _pick(
                f"Qual e a API que voce edita aqui?  ({work_root})",
                [p.name for p in apis],
                flag="--api",
                given=api_name,
            )
        ]

        raml_local = discovery.guess_raml_sibling(api, local)
        ramls = [p for p in local if p.kind == "raml"]
        if ramls:
            labels = [f"{p.name}{'  (sugerido)' if p is raml_local else ''}" for p in ramls]
            labels.append("nenhuma — nao sincronizar o RAML")
            default = ramls.index(raml_local) + 1 if raml_local else len(labels)
            idx = _pick(
                f"E o RAML dessa API, qual e?  ({work_root})",
                labels,
                flag="--raml",
                given=raml_name,
                default=default,
            )
            raml_local = ramls[idx] if idx < len(ramls) else None

        # Lado do workspace do Studio.
        if studio_root is None:
            studio_root = _escolher_workspace()
        studio_root = studio_root.expanduser().resolve()
        if not studio_root.is_dir():
            raise DiscoveryError(f"Esse caminho nao existe: {studio_root}")

        remote = discovery.find_projects(studio_root)
        if not remote:
            raise DiscoveryError(f"Nenhum projeto encontrado em {studio_root}.")
        names = [f"{p.name}  [{p.kind}]" for p in remote]
        studio_api = remote[
            _pick(
                f"No Studio, qual projeto e o seu {api.name}?  ({studio_root})",
                names,
                flag="--studio-api",
                given=studio_api_name,
            )
        ]

        studio_raml = None
        if raml_local is not None:
            # O projeto ja pareado com a API nao pode ser oferecido como par do RAML: e
            # sempre resposta errada, e antes ele aparecia como a unica opcao — a ponto de
            # o exemplo da flag sugerir justamente o pareamento equivocado.
            candidatos = [p for p in remote if p.name != studio_api.name]
            labels = [
                *(f"{p.name}  [{p.kind}]" for p in candidatos),
                "nenhuma — o RAML so existe aqui, nao no Studio",
            ]
            # O normal e nao haver pasta: o Studio consome o RAML como dependencia do
            # Exchange. Por isso "nenhuma" e o padrao, e nao a primeira pasta da lista.
            idx = _pick(
                f"No Studio, qual pasta e o seu {raml_local.name}?  ({studio_root})",
                labels,
                flag="--studio-raml",
                given=studio_raml_name,
                default=len(labels),
            )
            studio_raml = candidatos[idx] if idx < len(candidatos) else None

        cfg = BridgeConfig(
            work_root=work_root,
            studio_root=studio_root,
            api=ProjectPair(api.name, studio_api.name),
            # `studio=None` quando o RAML nao tem pasta no workspace, que e o normal: o
            # Studio o consome como dependencia do Exchange. A pasta local e guardada de
            # todo modo, para o `pararepo raml` saber onde ela fica.
            raml=(
                ProjectPair(raml_local.name, studio_raml.name if studio_raml else None)
                if raml_local
                else None
            ),
        )
        written = config.save(cfg)
    except BridgeError as exc:
        raise _fail(exc) from exc

    console.print(f"\n[green]Config gravada em[/] {written}")

    if cfg.raml is None:
        console.print(
            "\n[yellow]Sem pasta de RAML neste repositorio.[/]\n"
            "Rode [bold]ponte pararepo raml --aplicar[/] para cria-la com a "
            "especificacao que o Studio usa."
        )

    if editorconfig.precisa_config(work_root):
        aninhados = ", ".join(editorconfig.repos_aninhados(work_root))
        escrito = editorconfig.escrever(work_root)
        console.print(
            f"\n[dim]{aninhados} sao repositorios proprios — sem config, o editor "
            f"mostraria so o da raiz.\nEscrevi {escrito.relative_to(work_root)} para as "
            "edicoes deles aparecerem (VS Code, Trae, Cursor).[/]"
        )


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


def _parse_parte(parte: str | None) -> str | None:
    """Traduz o argumento opcional `raml`/`api` para o filtro do motor de sync."""
    if parte is None:
        return None
    valor = parte.strip().lower()
    if valor in {"raml", "api"}:
        return valor
    if valor in {"tudo", "todos", "all"}:
        return None
    raise typer.BadParameter(f"Parte {parte!r} desconhecida — use 'raml', 'api', ou nada (tudo).")


def _run(
    direction: Direction,
    work_root: Path | None,
    delete: bool,
    dry_run: bool,
    parte: str | None = None,
) -> None:
    try:
        cfg = _load(_resolve_root(work_root))
        plans = sync_all(
            cfg, direction, only=_parse_parte(parte), delete=delete, dry_run=dry_run
        )
    except BridgeError as exc:
        raise _fail(exc) from exc
    _report(plans, dry_run)


@app.command()
def parastudio(
    parte: str | None = typer.Argument(
        None, help="'raml' ou 'api' para mandar so uma parte. Sem nada, manda as duas."
    ),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(
        False, "--delete", help="Remove no workspace o que ja nao existe na pasta de trabalho."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Só mostra o que faria."),
) -> None:
    """Manda o que voce editou aqui para o workspace do Studio."""
    if _parse_parte(parte) == "raml":
        try:
            cfg = _load(_resolve_root(work_root))
        except BridgeError as exc:
            raise _fail(exc) from exc
        sem_pasta_no_studio = cfg.raml is not None and (
            cfg.raml.studio is None or not (cfg.studio_root / cfg.raml.studio).is_dir()
        )
        if sem_pasta_no_studio:
            # O Studio consome o RAML como dependencia, sem pasta propria no workspace:
            # copiar criaria lixo que ninguem le. O que faz ele enxergar o RAML editado e
            # a referencia no `pom.xml`, entao e ela que apontamos aqui.
            _apontar_raml_local(cfg, dry_run)
            return
    _run(Direction.PUSH, work_root, delete, dry_run, parte)


@app.command()
def pararepo(
    parte: str | None = typer.Argument(
        None, help="'raml' ou 'api' para trazer so uma parte. Sem nada, traz as duas."
    ),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(
        False, "--delete", help="Remove na pasta de trabalho o que ja nao existe no workspace."
    ),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Só mostra o que faria."),
    aplicar: bool = typer.Option(
        False, "--aplicar", help="So para 'raml': grava o resultado da juncao."
    ),
    resolvido: bool = typer.Option(
        False,
        "--resolvido",
        help="Ja combinei os conflitos na mao: aceita o que esta na pasta e fecha a base.",
    ),
) -> None:
    """Traz para o seu repositorio o que mudou no workspace do Studio.

    `pararepo raml` nao e uma copia: ele traz a versao nova do RAML **juntando** com as
    suas edicoes, para que nada do seu trabalho seja sobrescrito.
    """
    alvo = _parse_parte(parte)
    if alvo == "raml":
        _juntar_raml(work_root, aplicar, dry_run, resolvido=resolvido)
        return
    if alvo == "api":
        _juntar_api(work_root, aplicar, dry_run, resolvido=resolvido)
        return
    _run(Direction.PULL, work_root, delete, dry_run, parte)


def _apontar_raml_local(cfg: BridgeConfig, dry_run: bool) -> None:
    """Aponta o `pom.xml` do Studio para a pasta local do RAML.

    Quando o Studio consome o RAML como dependencia do Exchange, nao ha pasta para onde
    copiar — o que o faz ler o RAML editado e a referencia no `pom.xml`. Entao "mandar o
    RAML para o Studio" e, aqui, apontar essa referencia para a sua pasta.
    """
    raml_dir = cfg.work_root / cfg.raml.work
    pom = cfg.studio_root / cfg.api.studio / "pom.xml"

    if not pom.is_file():
        raise ConfigError(f"Nao achei o pom.xml do projeto no Studio: {pom}")

    if pomrewrite.has_local_pointer(pom):
        console.print(
            f"[green]O Studio ja le o RAML de {cfg.raml.work}.[/]\n"
            "[dim]Edite a pasta e salve — ele detecta a mudanca e redeploya sozinho.[/]"
        )
        return

    console.print(f"[bold]Apontando o Studio para {raml_dir}[/]")
    if dry_run:
        console.print("\n[dim]Isso foi uma previa — rode sem --dry-run para aplicar.[/]")
        return

    if pomrewrite.point_to_local_raml(pom, raml_dir):
        console.print(
            "[green]Pronto:[/] o Studio agora le o RAML da sua pasta.\n"
            "[dim]A dependencia do Exchange ficou preservada como comentario no pom.xml "
            "do workspace. O do repo nao foi tocado.[/]"
        )
    else:
        console.print(
            "[yellow]O pom.xml do Studio nao referencia um RAML do Exchange[/] — "
            "nao havia o que apontar."
        )


def _juntar_api(
    work_root: Path | None, aplicar: bool, dry_run: bool, *, resolvido: bool = False
) -> None:
    """Traz o que mudou na API do lado do Studio, juntando com as edicoes locais.

    A base e o ultimo commit do repositorio. Quando a pasta nao esta versionada nao ha
    base possivel, e caimos na copia direta de antes — avisando.
    """
    try:
        cfg = _load(_resolve_root(work_root))
        local = cfg.work_root / cfg.api.work
        studio = cfg.studio_root / cfg.api.studio

        if not reconcile.em_repo_git(local):
            console.print(
                "[yellow]A pasta da API nao esta num repositorio git com commits —[/] "
                "sem base para juntar, seguindo com copia direta."
            )
            _run(Direction.PULL, work_root, False, dry_run, "api")
            return

        ignorar = set(cfg.excludes) | {"pom.xml"}
        r = reconcile.reconciliar_com_git(local, studio, ignorar)
    except BridgeError as exc:
        raise _fail(exc) from exc

    _report_raml(r, origem="Studio")
    console.print("[dim]O pom.xml nao entra: o do repo segue apontando para o Exchange.[/]")

    resolucoes = None
    if not r.limpo:
        if not resolvido:
            console.print(
                "\n[yellow]Nada foi escrito.[/] Combine as duas versoes no arquivo e rode "
                "de novo com [bold]--resolvido --aplicar[/], ou peca ao seu agente de IA "
                "para combina-las."
            )
            raise typer.Exit(1)
        resolucoes = reconcile.resolucoes_do_disco(r, local)
        console.print(
            f"\n[yellow]--resolvido:[/] aceitando o que esta em {cfg.api.work} "
            f"para {', '.join(sorted(resolucoes))}."
        )

    if dry_run or not aplicar:
        console.print("\n[dim]Isso foi uma previa — rode com --aplicar para gravar.[/]")
        return

    escritos = reconcile.aplicar(r, local, resolucoes=resolucoes)
    console.print(f"\n[green]{escritos} arquivo(s) atualizado(s) em {cfg.api.work}.[/]")


@app.command(hidden=True)
def push(
    parte: str | None = typer.Argument(None),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(False, "--delete"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n"),
) -> None:
    """Apelido de `parastudio`, mantido para nao quebrar quem ja usava."""
    _run(Direction.PUSH, work_root, delete, dry_run, parte)


@app.command(hidden=True)
def pull(
    parte: str | None = typer.Argument(None),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(False, "--delete"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n"),
) -> None:
    """Apelido de `pararepo`, mantido para nao quebrar quem ja usava."""
    _run(Direction.PULL, work_root, delete, dry_run, parte)


@app.command(hidden=True)
def juntarraml(
    versao_nova: str | None = typer.Argument(None),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    aplicar: bool = typer.Option(False, "--aplicar"),
) -> None:
    """Apelido de `pararepo raml`, mantido para nao quebrar quem ja usava."""
    _juntar_raml(work_root, aplicar, False, versao_nova)


def _juntar_raml(
    work_root: Path | None,
    aplicar: bool,
    dry_run: bool = False,
    versao_nova: str | None = None,
    *,
    resolvido: bool = False,
) -> None:
    """Traz a versao nova do RAML preservando as edicoes locais (base + suas por cima).

    Nada e escrito enquanto houver conflito: os arquivos em conflito sao listados com os
    dois lados, para serem resolvidos antes.
    """
    try:
        cfg = _load(_resolve_root(work_root))

        coords = pomrewrite.read_raml_coords(cfg.work_root / cfg.api.work / "pom.xml")
        if coords is None:
            raise ConfigError("O pom.xml nao referencia um RAML do Exchange.")
        grupo, artefato, versao_atual = coords

        # Sem pasta no disco nao ha nada a preservar, e a criamos. Mas se a config diz
        # `raml = None` e a pasta existe, ela pode ter trabalho dentro: adotamos a que
        # esta la em vez de extrair por cima.
        if cfg.raml is None:
            candidata = cfg.work_root / f"{artefato}-raml"
            if candidata.is_dir():
                cfg.raml = ProjectPair(candidata.name, candidata.name)
                config.save(cfg)
                console.print(f"[dim]Adotando a pasta {candidata.name}, que ja existe.[/]")
            else:
                _criar_pasta_raml(cfg, grupo, artefato, dry_run or not aplicar)
                return
        elif not (cfg.work_root / cfg.raml.work).is_dir():
            _criar_pasta_raml(cfg, grupo, artefato, dry_run or not aplicar)
            return

        if versao_nova is None:
            versao_nova = _versao_alvo(cfg, grupo, artefato, versao_atual)

        r = reconcile.preparar(
            cfg.work_root / cfg.raml.work, grupo, artefato, versao_atual, versao_nova
        )
    except BridgeError as exc:
        raise _fail(exc) from exc

    _report_raml(r)

    pasta_raml = cfg.work_root / cfg.raml.work
    resolucoes = None
    if not r.limpo:
        if not resolvido:
            console.print(
                "\n[yellow]Nada foi escrito.[/] Combine as duas versoes no arquivo e rode "
                "de novo com [bold]--resolvido --aplicar[/], ou peca ao seu agente de IA "
                "para combina-las."
            )
            raise typer.Exit(1)
        # O usuario afirma ter combinado: o conteudo em disco passa a ser a resolucao.
        resolucoes = reconcile.resolucoes_do_disco(r, pasta_raml)
        console.print(
            f"\n[yellow]--resolvido:[/] aceitando o que esta em {cfg.raml.work} "
            f"para {', '.join(sorted(resolucoes))}."
        )

    if dry_run or not aplicar:
        console.print("\n[dim]Isso foi uma previa — rode com --aplicar para gravar.[/]")
        return

    escritos, commitou = reconcile.aplicar_em_dois_commits(
        r,
        pasta_raml,
        cfg.work_root,
        cfg.raml.work,
        f"chore(raml): especificacao {artefato} {versao_nova}",
        resolucoes=resolucoes,
    )
    console.print(f"\n[green]{escritos} arquivo(s) atualizado(s) em {cfg.raml.work}.[/]")

    if commitou:
        console.print(
            f"[dim]O que veio do Exchange foi commitado a parte "
            f"(chore(raml): {artefato} {versao_nova}).\n"
            "O que restou no git e o seu trabalho — de um `git diff` para ver so ele.[/]"
        )
    console.print(
        f"[dim]Lembre de apontar o pom.xml para {versao_nova} quando for commitar.[/]"
    )


def _criar_pasta_raml(cfg: BridgeConfig, grupo: str, artefato: str, previa: bool) -> None:
    """Cria a pasta do RAML na raiz do repositorio, extraindo a versao que o Studio usa.

    Sem pasta nao ha nada para preservar, entao nao ha o que perguntar: pega a versao que
    o projeto do Studio aponta (ou a mais alta do cache) e extrai. Quando a config ainda
    nao tem a pasta, ela e gravada junto, para os proximos comandos ja acharem.
    """
    pom_studio = cfg.studio_root / cfg.api.studio / "pom.xml"
    versao = None
    if pom_studio.is_file():
        c = pomrewrite.read_raml_coords(pom_studio)
        versao = c[2] if c else None
    if versao is None:
        disponiveis = reconcile.versoes_no_cache(grupo, artefato)
        if not disponiveis:
            raise ConfigError(
                f"O RAML de {artefato} nao esta no cache do Maven.\n"
                "Abra o projeto no Studio para ele baixar a especificacao primeiro."
            )
        versao = disponiveis[-1]

    nome = cfg.raml.work if cfg.raml else f"{artefato}-raml"
    destino = cfg.work_root / nome

    if destino.is_dir():
        # Rede de seguranca: extrair aqui sobrescreveria o que estiver dentro.
        raise ConfigError(
            f"A pasta {nome} ja existe — nao vou extrair por cima dela.\n"
            "Rode `ponte init --force` para pareá-la, e o comando passa a juntar."
        )

    console.print(f"[bold]A pasta do RAML nao existe — criando de {artefato} {versao}.[/]")
    console.print(f"  destino: {destino}")

    if previa:
        console.print("\n[dim]Isso foi uma previa — rode com --aplicar para criar.[/]")
        return

    reconcile.extrair(reconcile.caminho_no_cache(grupo, artefato, versao), destino)
    quantos = sum(1 for p in destino.rglob("*") if p.is_file())
    console.print(f"[green]{quantos} arquivo(s) extraido(s) em {nome}.[/]")

    if cfg.raml is None:
        cfg.raml = ProjectPair(nome, nome)
        config.save(cfg)
        console.print(f"[dim]Pareamento atualizado: {nome} agora faz parte do sync.[/]")

    # A pasta acabou de nascer do Exchange, entao ela e a base — nao uma alteracao sua.
    # Commitar aqui faz o git partir dela: dai em diante o diff mostra so o seu trabalho.
    # A extracao ja aconteceu, entao uma falha aqui e avisada, nao aborta o comando.
    try:
        if reconcile.commitar_base(
            cfg.work_root, nome, f"chore(raml): base da especificacao {artefato} {versao}"
        ):
            console.print(
                f"[green]Pronto:[/] {nome} esta na {versao} e commitada como base.\n"
                "[dim]O git esta limpo — daqui em diante ele mostra so o que voce editar.[/]"
            )
        else:
            console.print(
                f"[green]Pronto:[/] {nome} esta na {versao}.\n"
                f"[dim]{nome} nao esta sob git, entao nao ha base a commitar.[/]"
            )
    except BridgeError as exc:
        console.print(f"[yellow]Os arquivos estao no disco, mas nao commitei a base:[/] {exc}")
        console.print(f"[dim]Para commitar: git add {nome} && git commit[/]")


def _versao_alvo(cfg: BridgeConfig, grupo: str, artefato: str, versao_atual: str) -> str:
    """Descobre para qual versao do RAML trazer.

    A mais alta ja baixada no cache do Maven e o alvo — em desenvolvimento e sempre ela
    que interessa, tenha sido o Studio ou um `mvn dependency:get` quem a baixou. O
    `pom.xml` do lado do Studio entra so como desempate, quando o cache nao tem nada mais
    novo mas o Studio aponta para outra versao.
    """
    mais_altas = reconcile.mais_novas_que(
        reconcile.versoes_no_cache(grupo, artefato), versao_atual
    )
    if mais_altas:
        return mais_altas[-1]

    pom_studio = cfg.studio_root / cfg.api.studio / "pom.xml"
    if pom_studio.is_file():
        coords = pomrewrite.read_raml_coords(pom_studio)
        if coords and coords[2] != versao_atual:
            console.print(f"[dim]O Studio aponta para a {coords[2]} — trazendo essa versao.[/]")
            return coords[2]

    raise ConfigError(
        f"Nao ha versao mais nova para trazer — a mais alta baixada e a {versao_atual}.\n"
        "Faca o update do Exchange no Studio (Properties > Mule Project > APIs) primeiro."
    )


def _report_raml(r: reconcile.Reconciliacao, origem: str = "Exchange") -> None:
    rotulo = "API: " if r.versao_base == "HEAD" else "RAML "
    console.print(f"[bold]{rotulo}{r.versao_base} -> {r.versao_nova}[/]\n")

    tabela = Table()
    tabela.add_column("o que")
    tabela.add_column("arquivos", justify="right")
    tabela.add_row("juntados (seu + deles)", str(len(r.juntados)))
    tabela.add_row(f"novos, vindos do {origem}", str(len(r.so_deles)))
    tabela.add_row("so seus, preservados", str(len(r.so_meus)))
    tabela.add_row("sem mudanca", str(len(r.inalterados)))
    tabela.add_row("[red]em conflito[/]", f"[red]{len(r.conflitos)}[/]")
    console.print(tabela)

    for rel in r.juntados:
        console.print(f"  [green]juntado[/]  {rel}")
    for rel in r.so_deles:
        console.print(f"  [cyan]novo[/]     {rel}")

    for c in r.conflitos:
        console.print(f"\n[red]conflito em {c.caminho}[/] — os dois mexeram no mesmo ponto:")
        console.print("[dim]  sua versao:[/]")
        for linha in _trecho_conflitante(c.merge_marcado, "sua versao"):
            console.print(f"    {linha}")
        console.print("[dim]  Exchange novo:[/]")
        for linha in _trecho_conflitante(c.merge_marcado, "Exchange novo"):
            console.print(f"    {linha}")


def _trecho_conflitante(marcado: str, lado: str) -> list[str]:
    """Extrai do merge marcado so as linhas de um dos lados, para exibicao."""
    saida, dentro, qual = [], False, None
    for linha in marcado.splitlines():
        if linha.startswith("<<<<<<<"):
            dentro, qual = True, "sua versao"
            continue
        if linha.startswith("=======") and dentro:
            qual = "Exchange novo"
            continue
        if linha.startswith(">>>>>>>"):
            dentro, qual = False, None
            continue
        if dentro and qual == lado:
            saida.append(linha)
    return saida[:6] or ["(sem linhas)"]


@app.command()
def status(
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
) -> None:
    """Mostra o pareamento configurado e o que um parastudio faria agora."""
    try:
        cfg = _load(_resolve_root(work_root))
    except BridgeError as exc:
        raise _fail(exc) from exc

    console.print(f"[bold]trabalho:[/] {cfg.work_root}")
    console.print(f"[bold]workspace:[/] {cfg.studio_root}")
    for pair in (cfg.api, cfg.raml):
        if pair is None:
            continue
        if pair.studio is None:
            console.print(
                f"  {pair.work}  ->  [dim]sem pasta no workspace; o Studio le do Exchange[/]"
            )
        else:
            console.print(f"  {pair.work}  ->  {pair.studio}")
    console.print()
    _run(Direction.PUSH, work_root, False, True)


if __name__ == "__main__":  # pragma: no cover
    app()
