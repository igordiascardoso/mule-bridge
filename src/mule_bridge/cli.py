"""CLI do mule-bridge — a única camada que carrega lógica de negócio."""

from __future__ import annotations

import shutil
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import typer
from rich.console import Console
from rich.syntax import Syntax
from rich.table import Table

from . import __version__, config, discovery, editorconfig, exchange, pomrewrite, ramlvalidate, reconcile
from .config import BridgeConfig, ProjectPair
from .errors import BridgeError, ConfigError, DiscoveryError, NonInteractiveError
from .exchange import ExchangeError
from .sync import Direction, SyncPlan, sync_all

app = typer.Typer(
    name="ponte",
    help="Sync de projetos Mule entre a pasta de trabalho e o workspace do Anypoint Studio.",
    add_completion=False,
)


def _aceitar_utf8(stream) -> None:
    """Passa o stream para UTF-8, para o conteudo do projeto nunca derrubar a saida.

    No Windows a saida redirecionada (arquivo, pipe, log de CI, agente de IA) vem em
    `cp1252`, que nao tem `→` nem `═`. Imprimir um arquivo em conflito que contenha um
    deles levantava `UnicodeEncodeError` no meio do `_mostrar_conflito` — e o conflito
    ficava sem como ser resolvido. O que se imprime aqui e o codigo do usuario, e ele pode
    ter qualquer caractere; quem exibe e que tem de aguentar.
    """
    try:
        stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        # Stream sem `reconfigure` — o buffer de teste do CliRunner, por exemplo. Nesses
        # casos o encoding nao vem do console do Windows, entao nao ha o que consertar.
        pass


# `file=None` de proposito: o rich resolve `sys.stdout` a cada escrita, e nao aqui no
# import. Prender o stream agora quebraria quem o substitui depois — o `CliRunner` dos
# testes faz exatamente isso, e as mensagens iriam para o stream antigo.
_aceitar_utf8(sys.stdout)
_aceitar_utf8(sys.stderr)
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


@dataclass
class ProjetoEscolhido:
    """O projeto do Design Center escolhido, com os dados do Exchange ja lidos.

    `group_id`/`asset_id`/`main` vem do `exchange.json` dentro do proprio projeto — a
    unica fonte confiavel do vinculo com o Exchange (ver docs/DESIGN-CENTER-CLI.md, "Um
    projeto do Design Center por par": cruzar por nome e armadilha confirmada). `None`
    quando o projeto nunca foi publicado, e portanto nao tem `exchange.json` ainda.
    """

    id: str
    nome: str
    group_id: str | None
    asset_id: str | None
    main: str | None
    api_version: str | None


def _baixar_para_ler_exchange_json(projeto_id: str, nome: str) -> dict | None:
    """Baixa um projeto do Design Center numa pasta temporaria so para ler o exchange.json.

    E o unico jeito confiavel de achar o vinculo com o Exchange antes de decidir qual
    projeto usar — o `project list` nao traz `assetId`. `None` quando o projeto ainda nao
    tem `exchange.json` (nunca publicado) ou a leitura falha.
    """
    with tempfile.TemporaryDirectory(prefix="mule-bridge-dc-") as tmp:
        destino = Path(tmp) / nome
        try:
            exchange.baixar_projeto_design_center(nome, destino)
            return exchange.ler_exchange_json(destino)
        except ExchangeError:
            return None


def _escolher_projeto_design_center() -> ProjetoEscolhido:
    """Lista os projetos do Design Center e pede qual usar — nunca cruza por nome.

    Baixa cada projeto numa pasta temporaria so para ler o `exchange.json` de dentro e
    mostrar a versao do Exchange no menu, sempre rotulada explicitamente como tal e
    sempre a mais recente (ver docs/DESIGN-CENTER-CLI.md, "Formato decidido para o menu").
    Essa linha e so para ajudar a escolher o projeto — nunca decide nada por conta propria.
    """
    projetos = exchange.listar_projetos_design_center()
    if not projetos:
        raise ExchangeError(
            "Nenhum projeto no Design Center desta organizacao. Crie um primeiro "
            "(`anypoint-cli-v4 designcenter project create`)."
        )

    console.print("[dim]Consultando o Exchange de cada projeto...[/]")
    infos = [_baixar_para_ler_exchange_json(p.id, p.nome) for p in projetos]

    labels = []
    for p, info in zip(projetos, infos):
        rotulo_dc = f"modificado {exchange.em_brasilia(p.modificado_em)}"
        if info is None:
            rotulo_ex = "nunca publicado no Exchange"
        else:
            versoes = exchange.listar_versoes_exchange(info["groupId"], info["assetId"])
            rotulo_ex = (
                f"versao no Exchange: {versoes[0].versao} "
                f"(latest, {exchange.em_brasilia(versoes[0].publicado_em)})"
                if versoes
                else "nunca publicado no Exchange"
            )
        labels.append(f"{p.nome}  ({rotulo_dc})   {rotulo_ex}")

    idx = _choose("Qual projeto do Design Center?", labels, flag="--designcenter")
    escolhido, info = projetos[idx], infos[idx]

    return ProjetoEscolhido(
        id=escolhido.id,
        nome=escolhido.nome,
        group_id=info["groupId"] if info else None,
        asset_id=info["assetId"] if info else None,
        main=info["main"] if info else None,
        api_version=info.get("apiVersion") if info else None,
    )


def _escolher_versao_exchange(projeto: ProjetoEscolhido) -> str:
    """Menu de 4 opcoes para trazer uma versao do Exchange: latest + 2 anteriores + livre.

    Formato decidido em docs/DESIGN-CENTER-CLI.md ("Decisao de design: menu de versoes ao
    trazer do Exchange"): numero da versao + data, e a quarta opcao aceita qualquer versao
    digitada, nao so as tres mais recentes.
    """
    if projeto.group_id is None or projeto.asset_id is None:
        raise ExchangeError(
            f"O projeto {projeto.nome} nunca foi publicado no Exchange — nao ha versao "
            "para trazer. Publique primeiro com `ponte publicardesign`."
        )

    versoes = exchange.listar_versoes_exchange(projeto.group_id, projeto.asset_id)
    if not versoes:
        raise ExchangeError(f"Nenhuma versao publicada de {projeto.asset_id} no Exchange.")

    DIGITO = "outra versao — eu digito"
    labels = [
        f"{'mais atual — ' if i == 0 else ''}{v.versao}  ({exchange.em_brasilia(v.publicado_em)})"
        for i, v in enumerate(versoes[:3])
    ]
    labels.append(DIGITO)

    idx = _choose("Qual versao do RAML trazer?", labels, flag="--versao-exchange")
    if idx < len(versoes[:3]):
        return versoes[idx].versao

    try:
        return typer.prompt("Versao").strip()
    except (typer.Abort, EOFError, OSError) as exc:
        raise NonInteractiveError(
            "Qual versao do RAML trazer? — nao ha terminal interativo para perguntar.\n"
            "Repita o comando com `--versao-exchange <versao>`."
        ) from exc


def _validar_raml_ou_falhar(pasta: Path, main: str) -> None:
    """Recusa upload/publish quando o `.raml` principal nao tem o cabecalho `#%RAML`.

    O Exchange nem sempre recusa isso — as vezes publica em silencio, sem a documentacao
    que o time espera (ver docs/DESIGN-CENTER-CLI.md, "O RAML mal formado nao sempre
    falha"). Checar antes de chamar a CLI e a unica forma de nao deixar isso passar calado.
    """
    problemas = ramlvalidate.validar(pasta, main=main)
    if not problemas:
        return
    detalhes = "\n".join(
        f"  {p.caminho}: primeira linha e {p.primeira_linha!r}, esperava comecar com #%RAML"
        for p in problemas
    )
    raise ExchangeError(
        f"{len(problemas)} arquivo(s) sem o cabecalho #%RAML — o Exchange pode aceitar "
        "isso e publicar sem documentacao, em silencio. Corrija antes de continuar:\n"
        f"{detalhes}"
    )


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


#: A skill viaja dentro do pacote, e nao e baixada: `init` sem rede tem de funcionar.
SKILL_NO_PACOTE = Path(__file__).parent / "skill" / "SKILL.md"


def _instalar_skill() -> Path | None:
    """Grava a skill do Claude Code em `~/.claude/skills/ponte/`, se houver onde.

    Instalar a ferramenta e um passo; a skill nao pode ser um segundo, porque e o passo que
    se esquece — e uma skill velha faz o `/ponte` sugerir comando que nao existe mais.

    Sobrescreve sempre: a skill acompanha a versao da CLI, e as duas desalinhadas e
    justamente o problema que isto resolve.

    Devolve o caminho gravado, ou None quando nao havia o que fazer — sem `~/.claude` (quem
    nao usa Claude Code nao precisa ouvir sobre skill) ou quando a copia falha. Nunca
    levanta: o trabalho do `init` e o pareamento, e um extra nao pode derrubar isso.
    """
    raiz = Path.home() / ".claude"
    if not raiz.is_dir() or not SKILL_NO_PACOTE.is_file():
        return None

    destino = raiz / "skills" / "ponte" / "SKILL.md"
    try:
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(SKILL_NO_PACOTE, destino)
    except OSError:
        return None
    return destino


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

    destino = _instalar_skill()
    if destino is not None:
        console.print(
            f"\n[dim]Skill do Claude Code instalada em {destino}.\n"
            "Abra uma sessao nova do Claude Code — no terminal ou na extensao do VS Code — e\n"
            "os comandos valem com barra: `/ponte pararepo api`.[/]"
        )

    if cfg.raml is None:
        console.print(
            "\n[yellow]Sem pasta de RAML neste repositorio.[/]\n"
            "Rode [bold]ponte pararepo raml[/] para cria-la com a "
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


#: As unicas palavras que os comandos aceitam, e nada mais. Cada palavra a mais e uma
#: coisa a mais para o usuario — ou para o agente de IA agindo por ele — errar.
#:
#: `raml` e `api` dizem sobre o que agir; `force` sobrescreve o destino sem juntar. Uma
#: das tres e obrigatoria: sem palavra, o comando recusa em vez de adivinhar.
PALAVRAS: dict[str, tuple[str, ...]] = {
    "raml": ("raml",),
    "api": ("api",),
    "force": ("force", "forca", "força"),
}


@dataclass
class Pedido:
    """O que o usuario pediu, ja traduzido das palavras do comando."""

    parte: str | None = None
    force: bool = False


def _parse_palavras(palavras: list[str] | None, *, comando: str) -> Pedido:
    """Traduz as palavras do comando, exigindo exatamente uma.

    Uma palavra desconhecida e recusada em vez de ignorada — um typo nao pode virar
    gravacao. E a ausencia de palavra tambem: `ponte pararepo` sozinho nao roda, porque
    a palavra e o que diz o que fazer.
    """
    pedido = Pedido()

    for bruta in palavras or []:
        valor = bruta.strip().lower().lstrip("-")
        canonica = next((k for k, v in PALAVRAS.items() if valor in v), None)

        if canonica in {"raml", "api"}:
            if pedido.parte is not None and pedido.parte != canonica:
                raise typer.BadParameter(
                    f"Escolha uma palavra so: veio '{pedido.parte}' e '{canonica}'."
                )
            pedido.parte = canonica
        elif canonica == "force":
            pedido.force = True
        else:
            raise typer.BadParameter(
                f"Nao entendi {bruta!r} — use 'raml', 'api' ou 'force'."
            )

    if pedido.force and pedido.parte is not None:
        raise typer.BadParameter(
            f"'force' sobrescreve tudo e nao se combina com '{pedido.parte}'. "
            f"Escolha um: `ponte {comando} {pedido.parte}` ou "
            f"`ponte {comando} force`."
        )

    if pedido.parte is None and not pedido.force:
        raise typer.BadParameter(
            f"Falta a palavra: `ponte {comando} raml`, `ponte {comando} api` ou "
            f"`ponte {comando} force`."
        )

    return pedido


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


def _mostrar_conflito(c: reconcile.Conflito) -> None:
    """Imprime os dois lados do arquivo em conflito, para quem for decidir."""
    console.print(
        f"\n[bold yellow]{c.caminho}[/] — as duas versoes mexeram nas mesmas linhas"
    )
    console.print("\n[cyan]1.[/] a sua versao (a que esta no repositorio):")
    console.print(Syntax(c.meu, "yaml", theme="ansi_dark", line_numbers=False))
    console.print("[cyan]2.[/] a versao que veio:")
    console.print(Syntax(c.novo, "yaml", theme="ansi_dark", line_numbers=False))


def _resolver_conflitos(r: reconcile.Reconciliacao) -> dict[str, str]:
    """Resolve cada conflito na hora, perguntando — nunca deixa marcador no arquivo.

    Sem terminal interativo (agente de IA no chat, IDE, CI) nao ha como perguntar: os dois
    lados sao impressos e o erro pede que quem chamou combine as versoes. E de proposito
    que nada seja gravado nesse caso — escolher um lado calado e onde uma mudanca se perde.
    """
    resolucoes: dict[str, str] = {}

    for c in r.conflitos:
        _mostrar_conflito(c)
        try:
            escolha = typer.prompt(
                "Fica qual? 1 = a sua, 2 = a que veio, 3 = eu escrevo",
                default="1",
            )
        except (typer.Abort, EOFError, OSError) as exc:
            arquivos = ", ".join(x.caminho for x in r.conflitos)
            raise NonInteractiveError(
                f"Conflito em {arquivos} — nao ha terminal interativo para perguntar, "
                "e nada foi escrito.\n"
                "Combine as duas versoes mostradas acima no arquivo e rode de novo."
            ) from exc

        valor = escolha.strip().lower()
        if valor in {"2", "veio", "nova"}:
            resolucoes[c.caminho] = c.novo
        elif valor in {"3", "escrevo", "escrever"}:
            resolucoes[c.caminho] = _digitar_conteudo(c.caminho)
        else:
            resolucoes[c.caminho] = c.meu

    return resolucoes


def _digitar_conteudo(caminho: str) -> str:
    """Le o conteudo final de um arquivo, colado no terminal, ate uma linha com so um ponto."""
    console.print(
        f"[dim]Cole o conteudo final de {caminho} e termine com uma linha "
        "contendo so um ponto.[/]"
    )
    linhas: list[str] = []
    while True:
        try:
            linha = typer.prompt("", prompt_suffix="", default="", show_default=False)
        except (typer.Abort, EOFError, OSError) as exc:
            raise NonInteractiveError(
                f"Nao ha terminal interativo para digitar o conteudo de {caminho}."
            ) from exc
        if linha.strip() == ".":
            break
        linhas.append(linha)
    return "\n".join(linhas) + "\n"


@app.command()
def parastudio(
    palavras: list[str] | None = typer.Argument(
        None, help="'raml', 'api' ou 'force'. Uma delas e obrigatoria."
    ),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(False, "--delete", hidden=True),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", hidden=True),
) -> None:
    """Manda para o workspace do Studio o que voce editou aqui.

    
    ponte parastudio raml     aponta o Studio para a sua pasta de RAML
    ponte parastudio api      copia a API do repositorio para o workspace
    ponte parastudio force    copia RAML + API por cima do workspace, sem merge
    """
    p = _parse_palavras(palavras, comando="parastudio")

    if p.parte == "raml":
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

    # `force` manda as duas partes; `raml`/`api` filtram. O destino e o workspace, que e
    # descartavel — por isso aqui a copia direta nao precisa de confirmacao.
    _run(Direction.PUSH, work_root, delete, dry_run, p.parte)


@app.command()
def pararepo(
    palavras: list[str] | None = typer.Argument(
        None, help="'raml', 'api' ou 'force'. Uma delas e obrigatoria."
    ),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    delete: bool = typer.Option(False, "--delete", hidden=True),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", hidden=True),
) -> None:
    """Traz para o seu repositorio o que mudou no workspace do Studio.

    
    ponte pararepo raml     merge da versao nova do RAML com as suas edicoes
    ponte pararepo api      merge do que o Studio mudou com o que voce mudou
    ponte pararepo force    copia RAML + API por cima do repo, sem merge

    Com `raml` ou `api` nada do seu trabalho e perdido: o que os dois lados mexeram em
    lugares diferentes o merge resolve sozinho, e o que colidiu na mesma linha ele
    pergunta antes de gravar.
    """
    p = _parse_palavras(palavras, comando="pararepo")

    if p.parte == "raml":
        _juntar_raml(work_root, dry_run)
        return
    if p.parte == "api":
        _juntar_api(work_root, dry_run)
        return
    # `force`: copia por cima, sem juntar. E a palavra que o usuario digitou que autoriza
    # escrever no repositorio dele sem merge nenhum.
    _run(Direction.PULL, work_root, delete, dry_run, None)


@app.command()
def paradesign(
    palavras: list[str] | None = typer.Argument(
        None, help="'raml'. E a unica palavra aceita, e e obrigatoria."
    ),
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", hidden=True),
) -> None:
    """Manda o RAML editado localmente para o Design Center, sem publicar no Exchange.


    ponte paradesign raml     upload do RAML local para o projeto do Design Center

    So versiona no Design Center (a revisao sobe a cada chamada); nao apaga o que existe
    la e nao existe local, e nao publica no Exchange — quem faz isso e `publicardesign`.
    """
    if not palavras or palavras[0].strip().lower() not in {"raml"}:
        raise typer.BadParameter("Falta a palavra: `ponte paradesign raml`.")

    try:
        cfg = _load(_resolve_root(work_root))
        if cfg.raml is None or not (cfg.work_root / cfg.raml.work).is_dir():
            raise ConfigError(
                "Nao ha pasta de RAML pareada e no disco. Rode `ponte pararepo raml` "
                "primeiro, para trazer uma versao do Exchange e criar a pasta."
            )
        pasta_raml = cfg.work_root / cfg.raml.work
        projeto = _escolher_projeto_design_center()

        # O `main` que vale e o da pasta que vai subir, se ela ja tiver um exchange.json
        # local (de um `pararepo raml` anterior) — cai para o do projeto no Design Center
        # so quando a pasta local ainda nao tem um (upload inicial, projeto novo).
        main = (
            exchange.ler_exchange_json(pasta_raml).get("main")
            if (pasta_raml / "exchange.json").is_file()
            else projeto.main
        ) or "api.raml"
        _validar_raml_ou_falhar(pasta_raml, main)
    except BridgeError as exc:
        raise _fail(exc) from exc

    console.print(f"[bold]Enviando {pasta_raml} para o Design Center ({projeto.nome})[/]")
    if dry_run:
        console.print("[dim]Isso foi uma previa — nada foi enviado.[/]")
        return

    try:
        exchange.upload_design_center(projeto.nome, pasta_raml)
    except BridgeError as exc:
        raise _fail(exc) from exc

    console.print(
        f"[green]Pronto:[/] {pasta_raml.name} enviado para o Design Center.\n"
        "[dim]Para publicar essa revisao no Exchange, rode `ponte publicardesign`.[/]"
    )


@app.command()
def publicardesign(
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", hidden=True),
) -> None:
    """Publica no Exchange a revisao atual do projeto no Design Center.

    Mostra a versao atualmente publicada (se houver) antes de confirmar, para nao
    publicar por engano pensando que "sempre foi a primeira vez". O `mainFile` e sempre
    passado explicitamente (lido do `exchange.json` do projeto) — publicar sem isso pode
    publicar o placeholder do Design Center em silencio (ver docs/DESIGN-CENTER-CLI.md).
    """
    try:
        _load(_resolve_root(work_root))  # so para validar que ha config nesta pasta
        projeto = _escolher_projeto_design_center()
        if projeto.asset_id is None or projeto.group_id is None:
            console.print(
                f"[yellow]{projeto.nome} nunca foi publicado no Exchange.[/] "
                "Esta sera a primeira versao."
            )
            versoes = []
        else:
            versoes = exchange.listar_versoes_exchange(projeto.group_id, projeto.asset_id)
            if versoes:
                console.print(
                    f"[bold]Versao publicada hoje:[/] {versoes[0].versao} "
                    f"({exchange.em_brasilia(versoes[0].publicado_em)})"
                )
            else:
                console.print(f"[yellow]{projeto.nome} nunca foi publicado no Exchange.[/]")
    except BridgeError as exc:
        raise _fail(exc) from exc

    if projeto.main is None:
        raise _fail(
            ExchangeError(
                f"Nao ha exchange.json em {projeto.nome} com um `main` definido — "
                "faca um `ponte paradesign raml` primeiro."
            )
        )

    try:
        # Valida o que esta de fato no Design Center agora — nao a pasta local, que pode
        # ja ter mudado desde o ultimo `paradesign raml` — porque e isso que o publish vai
        # publicar.
        with tempfile.TemporaryDirectory(prefix="mule-bridge-validar-") as tmp:
            destino = exchange.baixar_projeto_design_center(projeto.nome, Path(tmp) / "atual")
            _validar_raml_ou_falhar(destino, projeto.main)
    except BridgeError as exc:
        raise _fail(exc) from exc

    try:
        versao_nova = typer.prompt("Nova versao a publicar (formato X.Y.Z)")
    except (typer.Abort, EOFError, OSError) as exc:
        raise _fail(
            NonInteractiveError(
                "Nova versao a publicar — nao ha terminal interativo para perguntar."
            )
        ) from exc

    api_version = projeto.api_version or "v1"
    console.print(
        f"[bold]Publicando {projeto.nome} {versao_nova} no Exchange[/] (main: {projeto.main})"
    )
    if dry_run:
        console.print("[dim]Isso foi uma previa — nada foi publicado.[/]")
        return

    try:
        exchange.publicar_exchange(
            projeto.nome, main=projeto.main, api_version=api_version, versao=versao_nova
        )
    except BridgeError as exc:
        raise _fail(exc) from exc

    console.print(f"[green]Publicado:[/] {projeto.nome} {versao_nova} no Exchange.")


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
        console.print(
            "\n[dim]Isso foi uma previa — rode [bold]ponte parastudio raml[/bold] "
            "para apontar de verdade.[/]"
        )
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


def _juntar_api(work_root: Path | None, dry_run: bool = False) -> None:
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
                "sem base para o merge, seguindo com copia direta."
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
        try:
            resolucoes = _resolver_conflitos(r)
        except BridgeError as exc:
            raise _fail(exc) from exc

    if dry_run:
        return

    escritos = reconcile.aplicar(r, local, resolucoes=resolucoes)
    console.print(f"\n[green]{escritos} arquivo(s) atualizado(s) em {cfg.api.work}.[/]")


def _juntar_raml(
    work_root: Path | None,
    dry_run: bool = False,
    versao_nova: str | None = None,
) -> None:
    """Traz a versao nova do RAML do Exchange, preservando as edicoes locais.

    Comportamento mudado (ver docs/DESIGN-CENTER-CLI.md, "Decisao final: os tres
    comandos"): busca direto do Exchange, sem depender do Studio ter feito update. Dois
    passos obrigatorios, nesta ordem: escolher o projeto do Design Center, depois a
    versao do Exchange daquele projeto. So depois o merge roda, como antes.

    Os arquivos que os dois lados mexeram em lugares diferentes o merge junta sozinho. O
    que colidiu na mesma linha e perguntado na hora, e nada fica com marcador no arquivo.
    """
    try:
        cfg = _load(_resolve_root(work_root))

        # Sem pasta no disco nao ha nada a preservar, e a criamos. Mas se a config diz
        # `raml = None` e a pasta existe, ela pode ter trabalho dentro: adotamos a que
        # esta la em vez de extrair por cima — igual ao comportamento de sempre.
        pasta_raml = cfg.work_root / cfg.raml.work if cfg.raml else None
        if pasta_raml is not None and pasta_raml.is_dir():
            versao_atual = reconcile.versao_da_pasta(pasta_raml)
        else:
            versao_atual = None
            pasta_raml = None

        projeto = _escolher_projeto_design_center()
        if versao_nova is None:
            versao_nova = _escolher_versao_exchange(projeto)

        if cfg.raml is None:
            candidata = cfg.work_root / f"{projeto.asset_id}-raml"
            if candidata.is_dir():
                cfg.raml = ProjectPair(candidata.name, candidata.name)
                config.save(cfg)
                console.print(f"[dim]Adotando a pasta {candidata.name}, que ja existe.[/]")
                pasta_raml = candidata
                versao_atual = reconcile.versao_da_pasta(pasta_raml)
            else:
                _criar_pasta_raml(cfg, projeto, versao_nova, dry_run)
                return
        elif pasta_raml is None:
            _criar_pasta_raml(cfg, projeto, versao_nova, dry_run)
            return

        with tempfile.TemporaryDirectory(prefix="mule-bridge-exchange-") as tmp:
            novo_dir = exchange.baixar_versao_exchange(
                projeto.group_id, projeto.asset_id, versao_nova, Path(tmp) / "novo"
            )
            if versao_atual and versao_atual != versao_nova:
                base_dir = exchange.baixar_versao_exchange(
                    projeto.group_id, projeto.asset_id, versao_atual, Path(tmp) / "base"
                )
            else:
                base_dir = novo_dir

            r = reconcile.reconciliar(pasta_raml, base_dir, novo_dir, versao_atual or versao_nova, versao_nova)
    except BridgeError as exc:
        raise _fail(exc) from exc

    _report_raml(r)

    resolucoes = None
    if not r.limpo:
        try:
            resolucoes = _resolver_conflitos(r)
        except BridgeError as exc:
            raise _fail(exc) from exc

    if dry_run:
        return

    escritos, commitou = reconcile.aplicar_em_dois_commits(
        r,
        pasta_raml,
        cfg.work_root,
        cfg.raml.work,
        f"chore(raml): especificacao {projeto.asset_id} {versao_nova}",
        resolucoes=resolucoes,
    )
    console.print(f"\n[green]{escritos} arquivo(s) atualizado(s) em {cfg.raml.work}.[/]")

    if commitou:
        console.print(
            f"[dim]O que veio do Exchange foi commitado a parte "
            f"(chore(raml): {projeto.asset_id} {versao_nova}).\n"
            "O que restou no git e o seu trabalho — de um `git diff` para ver so ele.[/]"
        )


def _criar_pasta_raml(
    cfg: BridgeConfig, projeto: ProjetoEscolhido, versao: str, dry_run: bool = False
) -> None:
    """Cria a pasta do RAML na raiz do repositorio, baixando do Exchange.

    Sem pasta nao ha nada para preservar, entao nao ha o que perguntar: baixa a versao ja
    escolhida direto. Quando a config ainda nao tem a pasta, ela e gravada junto, para os
    proximos comandos ja acharem.
    """
    nome = cfg.raml.work if cfg.raml else f"{projeto.asset_id}-raml"
    destino = cfg.work_root / nome

    if destino.is_dir():
        # Rede de seguranca: extrair aqui sobrescreveria o que estiver dentro.
        raise ConfigError(
            f"A pasta {nome} ja existe — nao vou extrair por cima dela.\n"
            "Rode `ponte init --force` para pareá-la, e o comando passa a fazer merge."
        )

    console.print(f"[bold]A pasta do RAML nao existe — criando de {projeto.asset_id} {versao}.[/]")
    console.print(f"  destino: {destino}")

    if dry_run:
        return

    exchange.baixar_versao_exchange(projeto.group_id, projeto.asset_id, versao, destino)
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
            cfg.work_root, nome, f"chore(raml): base da especificacao {projeto.asset_id} {versao}"
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


def _report_raml(r: reconcile.Reconciliacao, origem: str = "Exchange") -> None:
    rotulo = "API: " if r.versao_base == "HEAD" else "RAML "
    console.print(f"[bold]{rotulo}{r.versao_base} -> {r.versao_nova}[/]\n")

    tabela = Table()
    tabela.add_column("o que")
    tabela.add_column("arquivos", justify="right")
    tabela.add_row("merge (seu + o que veio)", str(len(r.juntados)))
    tabela.add_row(f"novos, vindos do {origem}", str(len(r.so_deles)))
    tabela.add_row("so seus, intocados", str(len(r.so_meus)))
    tabela.add_row("sem mudanca", str(len(r.inalterados)))
    tabela.add_row("[red]em conflito[/]", f"[red]{len(r.conflitos)}[/]")
    console.print(tabela)

    for rel in r.juntados:
        console.print(f"  [green]merge[/]    {rel}")
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


def _trocar(rotulo: str, atual: str, opcoes: list[str], *, existe: bool) -> str:
    """Pergunta um caminho, com o de hoje como primeira opcao e default.

    Quem chega aqui veio de um `status` acusando pasta fora do lugar, e em geral so um dos
    caminhos mudou. Manter e a opcao 1 para que Enter seja a resposta certa nos outros —
    corrigir um caminho nao pode custar redigitar os que estavam certos. O que nao esta no
    disco vem marcado, para nao se manter por engano justamente o que quebrou.
    """
    # Sem colchetes: o rich os leria como marcacao de cor e engoliria o aviso.
    MANTER = f"manter: {atual}" + ("" if existe else "   <-- nao esta no disco")
    DIGITO = "outro — eu digito"
    candidatos = [o for o in opcoes if o != atual]

    idx = _choose(rotulo, [MANTER, *candidatos, DIGITO], flag="--work-root")
    if idx == 0:
        return atual
    if idx <= len(candidatos):
        return candidatos[idx - 1]

    try:
        digitado = typer.prompt(f"{rotulo} — caminho")
    except (typer.Abort, EOFError, OSError) as exc:
        raise NonInteractiveError(
            f"{rotulo} — nao ha terminal interativo para perguntar."
        ) from exc
    return digitado.strip().strip('"').strip("'")


@app.command()
def caminho(
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
) -> None:
    """Corrige os caminhos do pareamento, quando uma pasta saiu do lugar.

    O `status` diz qual pasta nao esta onde foi pareada; este comando reaponta. Pergunta os
    tres caminhos com o de hoje como default, entao corrigir um custa um Enter nos outros.
    Nao repete as escolhas do `init` — a pergunta aqui e "onde ficou", nao "qual e o par".
    """
    try:
        cfg = _load(_resolve_root(work_root))
    except BridgeError as exc:
        raise _fail(exc) from exc

    try:
        # Workspace do Studio: a raiz onde ficam os projetos, e o que mais muda de lugar
        # (troca de maquina, ou File > Switch Workspace).
        cfg.studio_root = Path(
            _trocar(
                "Onde fica o workspace do Anypoint Studio?",
                str(cfg.studio_root),
                [str(w) for w in discovery.find_studio_workspaces()],
                existe=cfg.studio_root.is_dir(),
            )
        )

        # As listas saem separadas por tipo: uma pasta de API nunca e candidata a RAML, e
        # oferece-la e convidar o pareamento errado — que so aparece muito depois.
        locais = discovery.find_projects(cfg.work_root)
        apis_locais = [p.name for p in locais if p.kind == "api"]
        ramls_locais = [p.name for p in locais if p.kind == "raml"]
        no_studio = [p.name for p in discovery.find_projects(cfg.studio_root)]

        cfg.api = ProjectPair(
            _trocar(
                "A pasta da API no seu repositorio",
                cfg.api.work,
                apis_locais,
                existe=(cfg.work_root / cfg.api.work).is_dir(),
            ),
            _trocar(
                "A pasta dela no workspace do Studio",
                cfg.api.studio or "",
                no_studio,
                existe=bool(cfg.api.studio)
                and (cfg.studio_root / cfg.api.studio).is_dir(),
            )
            or None,
        )

        # O RAML so entra em pergunta quando a pasta pareada nao esta no disco — e ai o
        # unico caso que precisa de resposta e o da pasta renomeada. Pasta que simplesmente
        # nao existe o `pararepo raml` recria extraindo o zip, sem precisar de conserto; e
        # pasta no lugar nao tem o que corrigir. Perguntar sempre so cobrava um Enter a
        # mais de quem veio consertar outra coisa.
        if cfg.raml is not None and not (cfg.work_root / cfg.raml.work).is_dir():
            if ramls_locais:
                cfg.raml = ProjectPair(
                    _trocar(
                        "A sua pasta do RAML mudou de nome. Qual e agora?",
                        cfg.raml.work,
                        ramls_locais,
                        existe=False,
                    ),
                    cfg.raml.studio,
                )
            else:
                console.print(
                    f"\n[dim]A pasta do RAML ({cfg.raml.work}) nao esta no disco, e nao ha "
                    "outra por perto.\nDeixei o pareamento como esta: `ponte pararepo raml` "
                    "extrai a especificacao e a cria de novo.[/]"
                )
    except BridgeError as exc:
        raise _fail(exc) from exc

    destino = config.save(cfg)
    console.print(f"\n[green]Caminhos gravados[/] em {destino}")
    console.print("[dim]Rode `ponte status` para conferir se os dois lados respondem.[/]")


@app.command()
def status(
    work_root: Path | None = typer.Option(None, "--work-root", "-w"),
) -> None:
    """Diz se os dois lados de cada par estao no lugar, e onde eles ficam.

    Uma pergunta so: o pareamento esta de pe? Quantos arquivos diferem e o que um
    `parastudio` copiaria e assunto do proprio `parastudio`, que ja mostra isso.
    """
    try:
        cfg = _load(_resolve_root(work_root))
    except BridgeError as exc:
        raise _fail(exc) from exc

    faltando: list[str] = []

    def _lado(rotulo: str, caminho: Path) -> None:
        """Uma linha dizendo se a pasta esta la, e outra com o caminho dela.

        O caminho vai sozinho na linha de baixo porque em Windows ele passa da largura do
        terminal: junto do rotulo, quebrava no meio e a marca de ok/FALTA sumia de vista.
        """
        if caminho.is_dir():
            console.print(f"  [green]conectado[/]     {rotulo}")
        else:
            console.print(f"  [red]NAO ENCONTRADA[/] {rotulo}")
            faltando.append(rotulo)
        console.print(f"                  [dim]{caminho}[/]")

    _lado("workspace do Studio", cfg.studio_root)

    for pair, nome in ((cfg.api, "API"), (cfg.raml, "RAML")):
        if pair is None:
            console.print(f"\n[bold]{nome}[/]  [dim]nao pareado[/]")
            continue

        console.print(f"\n[bold]{nome}[/]")
        _lado(f"a sua pasta ({pair.work})", cfg.work_root / pair.work)
        if pair.studio is None:
            # Caso normal do RAML: o Studio o consome como dependencia do Exchange, e nao
            # ha pasta correspondente no workspace. Nao e ausencia, e o desenho.
            console.print("  [dim]—               no workspace nao ha pasta:[/]")
            console.print("                  [dim]o Studio le a especificacao do Exchange[/]")
        else:
            _lado(f"no workspace ({pair.studio})", cfg.studio_root / pair.studio)

    if faltando:
        console.print(
            f"\n[yellow]Pareado, mas nao achei no disco:[/] {', '.join(faltando)}."
        )
        console.print(
            "[dim]A pasta foi movida ou renomeada depois do pareamento — o sync nao vai "
            "rodar assim.\nRode `ponte caminho` para reapontar, ou `ponte init --force` "
            "para parear tudo de novo.[/]"
        )
    else:
        console.print("\n[green]Tudo conectado.[/] Os dois lados de cada par estao no lugar.")


if __name__ == "__main__":  # pragma: no cover
    app()
