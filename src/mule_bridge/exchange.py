"""Chamadas à `anypoint-cli-v4`: Design Center e Exchange.

Toda a interação com a CLI da Anypoint vive aqui, isolada do resto — o `cli.py` não sabe
como ela é invocada, só o que ela devolve. A credencial nunca passa por este módulo: ela
já vive cifrada em `%APPDATA%` (configurada uma vez com `anypoint-cli-v4 conf`), e a CLI a
lê sozinha do ambiente.

Comportamentos confirmados em `docs/DESIGN-CENTER-CLI.md` que este módulo depende de:

- `exchange asset list` sem `--organizationId` devolve o catálogo público inteiro, não só
  a organização — por isso `--organizationId` é sempre passado.
- Não há filtro exato de `assetId` na CLI, só busca textual (`SEARCHTEXT`) — o filtro por
  igualdade é feito aqui, no cliente.
- Publicar um `rest-api` cria também um asset `extension` companheiro
  (`mule-plugin-<nome>`) que aparece misturado na mesma listagem — filtrado aqui por
  `type == "rest-api"`.
- `exchange asset download` grava um `.zip` com nome de hash, não a pasta extraída — a
  extração é feita aqui com `zipfile`, como já é feito para o cache do Maven em
  `reconcile.extrair`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .errors import BridgeError

CLI = "anypoint-cli-v4"

#: Sem isso a listagem de versoes de um asset publicado mais de 10 vezes vem truncada —
#: o default da CLI e 10 (visto no --help).
LIMITE_VERSOES = 100

#: Brasilia nao tem horario de verao desde 2019 — subtracao fixa, sem tabela sazonal.
BRASILIA = timezone(timedelta(hours=-3))


class ExchangeError(BridgeError):
    """Falha ao chamar `anypoint-cli-v4` (rede, credencial, escopo, ou saida inesperada)."""


@dataclass
class ProjetoDesignCenter:
    """Uma linha de `designcenter project list`."""

    id: str
    nome: str
    modificado_em: datetime | None


@dataclass
class VersaoExchange:
    """Uma linha de `exchange asset list`, já filtrada por assetId e tipo."""

    versao: str
    publicado_em: datetime | None


def _run(*args: str) -> str:
    """Roda a CLI e devolve o stdout; levanta `ExchangeError` com a causa em falha.

    Nunca `shell=True` — mesma regra de `reconcile.py`. O 403 da plataforma é traduzido
    aqui porque a mensagem original ("Forbidden") engana: parece credencial inválida, mas
    é quase sempre escopo faltando na Connected App (confirmado em
    docs/DESIGN-CENTER-CLI.md).
    """
    # No Windows a CLI e um `.cmd` do npm, nao um `.exe` — sem resolver a extensao pelo
    # `PATHEXT` (o que `shutil.which` faz e o `subprocess.run` sozinho nao faz sem
    # `shell=True`), o lancamento falha com "sistema nao pode encontrar o arquivo
    # especificado" mesmo com o comando no PATH. Confirmado testando contra a conta real.
    executavel = shutil.which(CLI) or CLI
    try:
        proc = subprocess.run(
            [executavel, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except FileNotFoundError as exc:
        raise ExchangeError(
            f"'{CLI}' nao encontrado. Instale com "
            "`npm install -g anypoint-cli-v4-public` (exige Node 22+) e configure a "
            "credencial com `anypoint-cli-v4 conf client_id`/`client_secret`."
        ) from exc

    if proc.returncode == 0:
        return proc.stdout

    saida = ((proc.stdout or "") + (proc.stderr or "")).strip()
    if "403" in saida or "Forbidden" in saida:
        raise ExchangeError(
            f"Sem permissao para `{' '.join(args)}` (403).\n"
            "Nao e credencial invalida — falta escopo na Connected App: "
            "'Design Center Developer' para ler/escrever no Design Center, "
            "'Exchange Contributor' para publicar no Exchange."
        )

    motivo = saida.splitlines()[-1] if saida else "erro desconhecido"
    raise ExchangeError(f"`{CLI} {' '.join(args)}` falhou: {motivo}")


def _parse_data(bruta: str | None) -> datetime | None:
    """ISO 8601 (com `Z` ou offset) para `datetime` com timezone, ou None."""
    if not bruta:
        return None
    try:
        return datetime.fromisoformat(bruta.replace("Z", "+00:00"))
    except ValueError:
        return None


def em_brasilia(dt: datetime | None) -> str:
    """Formata uma data em horario de Brasilia, para exibicao no menu."""
    if dt is None:
        return "data desconhecida"
    return dt.astimezone(BRASILIA).strftime("%d/%m %H:%M")


def listar_projetos_design_center() -> list[ProjetoDesignCenter]:
    """Todos os projetos do Design Center na organizacao corrente."""
    dados = json.loads(_run("designcenter", "project", "list", "--output", "json"))
    return [
        ProjetoDesignCenter(
            id=p["id"], nome=p["name"], modificado_em=_parse_data(p.get("lastUpdatedDate"))
        )
        for p in dados
    ]


def baixar_projeto_design_center(nome_projeto: str, destino: Path) -> Path:
    """Baixa o conteudo atual de um projeto do Design Center para `destino`.

    Diferente de `baixar_versao_exchange`: aqui o comando ja extrai a pasta sozinho, sem
    zip intermediario (confirmado nos testes desta investigacao).
    """
    _run("designcenter", "project", "download", nome_projeto, str(destino))
    return destino


def ler_exchange_json(pasta: Path) -> dict:
    """Le o `exchange.json` de um projeto do Design Center ja baixado.

    E dele que sai o `assetId`/`groupId` reais — cruzar por nome de projeto e armadilha
    confirmada (ver docs/DESIGN-CENTER-CLI.md, secao "Um projeto do Design Center por par").
    """
    alvo = pasta / "exchange.json"
    if not alvo.is_file():
        raise ExchangeError(f"Sem exchange.json em {pasta} — o projeto nunca foi publicado?")
    try:
        return json.loads(alvo.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise ExchangeError(f"exchange.json invalido em {alvo}") from exc


def listar_versoes_exchange(group_id: str, asset_id: str) -> list[VersaoExchange]:
    """Versoes publicadas de um asset, mais nova primeiro. Vazio se nunca publicado.

    Filtra por `assetId` exato (a CLI só tem busca textual) e por `type == "rest-api"`
    (o `extension` companheiro do publish aparece misturado na mesma listagem).
    """
    dados = json.loads(
        _run(
            "exchange",
            "asset",
            "list",
            asset_id,
            "--output",
            "json",
            "--organizationId",
            group_id,
            "--limit",
            str(LIMITE_VERSOES),
        )
    )
    return [
        VersaoExchange(versao=a["version"], publicado_em=_parse_data(a.get("createdDate")))
        for a in dados
        if a.get("assetId") == asset_id and a.get("type") == "rest-api"
    ]


def baixar_versao_exchange(group_id: str, asset_id: str, versao: str, destino: Path) -> Path:
    """Baixa e extrai uma versao publicada do Exchange; devolve a pasta extraida.

    O comando grava um `.zip` de nome imprevisivel (hash) dentro de `destino` — extraimos
    nos mesmos e removemos o zip, para `destino` conter so o RAML.
    """
    destino.mkdir(parents=True, exist_ok=True)
    antes = set(destino.iterdir())

    _run(
        "exchange",
        "asset",
        "download",
        f"{group_id}/{asset_id}/{versao}",
        str(destino),
        "--force",
    )

    novos = [p for p in destino.iterdir() if p not in antes and p.suffix == ".zip"]
    if not novos:
        raise ExchangeError(f"O download de {asset_id}/{versao} nao criou um .zip em {destino}.")
    zip_baixado = novos[0]

    try:
        with zipfile.ZipFile(zip_baixado) as z:
            z.extractall(destino)
    except zipfile.BadZipFile as exc:
        raise ExchangeError(f"Zip corrompido ao baixar {asset_id}/{versao}: {zip_baixado}") from exc
    finally:
        zip_baixado.unlink(missing_ok=True)

    return destino


def upload_design_center(nome_projeto: str, pasta_local: Path) -> None:
    """Envia o conteudo de `pasta_local` para o projeto do Design Center.

    Versiona no Design Center a cada chamada e nao apaga o que existe la e nao existe
    local (confirmado em docs/DESIGN-CENTER-CLI.md) — nao publica no Exchange.
    """
    _run("designcenter", "project", "upload", nome_projeto, str(pasta_local))


def publicar_exchange(
    nome_projeto: str, *, main: str, api_version: str, versao: str
) -> None:
    """Publica a revisao atual do Design Center como uma versao nova no Exchange.

    `main` é sempre passado explicitamente: projetos criados do zero pelo Design Center
    guardam no `exchange.json` um placeholder (`<nome-do-projeto>.raml`) como `main` por
    padrao, e publicar sem `--main` publica esse placeholder em silêncio — achado
    registrado em docs/DESIGN-CENTER-CLI.md ("CORRECAO IMPORTANTE").
    """
    _run(
        "designcenter",
        "project",
        "publish",
        nome_projeto,
        "--main",
        main,
        "--apiVersion",
        api_version,
        "--version",
        versao,
    )
