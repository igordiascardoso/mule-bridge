"""A palavra `force` do `pararepo`: gravar tem de ser deliberado.

O `pararepo` escreve no repositório do usuário, e o uso principal é digitado no chat de um
agente de IA. Uma flag no fim da linha (`--aplicar`) passa batida ali; uma palavra a mais no
comando, não. Daí `ponte pararepo force`.

Estes testes cobrem o que a suíte de cenários não pegava, porque ela chama a função com
`--aplicar` em vez de passar os argumentos como o usuário os digita.
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mule_bridge import config
from mule_bridge.cli import _parse_palavras, app
from mule_bridge.config import BridgeConfig, ProjectPair

runner = CliRunner()

POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <artifactId>pedidos-api</artifactId>
  <dependencies>
    <dependency>
      <groupId>grupo</groupId>
      <artifactId>pedidos</artifactId>
      <version>{versao}</version>
      <classifier>raml</classifier>
      <type>zip</type>
    </dependency>
  </dependencies>
</project>
"""

BASE_RAML = "#%RAML 1.0\ntitle: Pedidos\nversion: v1\ntypes:\n  Pedido:\n  Item:\n  Fim:\n"


# --- O parser, isolado ----------------------------------------------------------


def test_sem_palavras_e_previa_de_tudo():
    assert _parse_palavras(None) == (None, False)
    assert _parse_palavras([]) == (None, False)


def test_force_sozinho():
    assert _parse_palavras(["force"]) == (None, True)


def test_parte_sem_force():
    assert _parse_palavras(["raml"]) == ("raml", False)
    assert _parse_palavras(["api"]) == ("api", False)


def test_ordem_nao_importa():
    """No chat ninguem lembra a ordem — as duas formas tem de valer."""
    assert _parse_palavras(["raml", "force"]) == ("raml", True)
    assert _parse_palavras(["force", "raml"]) == ("raml", True)


def test_aceita_a_palavra_em_portugues():
    """Quem digita em portugues escreve 'forca' ou 'força'."""
    assert _parse_palavras(["forca"]) == (None, True)
    assert _parse_palavras(["força"]) == (None, True)


def test_maiuscula_e_espaco_nao_atrapalham():
    assert _parse_palavras([" FORCE "]) == (None, True)
    assert _parse_palavras(["RAML"]) == ("raml", False)


def test_tudo_e_explicito_para_as_duas_partes():
    assert _parse_palavras(["tudo", "force"]) == (None, True)


def test_palavra_desconhecida_e_erro():
    """Melhor recusar que adivinhar: um typo nao pode virar gravacao silenciosa."""
    import typer

    with pytest.raises(typer.BadParameter, match="Nao entendi"):
        _parse_palavras(["aplicar"])


def test_duas_partes_diferentes_e_erro():
    import typer

    with pytest.raises(typer.BadParameter, match="uma parte"):
        _parse_palavras(["raml", "api"])


# --- Pelo comando, ponta a ponta ------------------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.safecrlf=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    """Repo com API + RAML na 1.0.0, Studio na 1.1.0, cache com as duas."""
    work, studio = tmp_path / "repo", tmp_path / "ws"
    m2 = tmp_path / "casa" / ".m2" / "repository"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "casa"))

    api = work / "pedidos-api" / "src" / "main" / "mule"
    api.mkdir(parents=True)
    (api / "application.xml").write_text("<mule/>\n", encoding="utf-8")
    (work / "pedidos-api" / "pom.xml").write_text(POM.format(versao="1.0.0"), encoding="utf-8")

    raml = work / "pedidos-raml"
    raml.mkdir()
    (raml / "api.raml").write_text(BASE_RAML, encoding="utf-8")

    studio_api = studio / "studio-pedidos" / "src" / "main" / "mule"
    studio_api.mkdir(parents=True)
    (studio_api / "application.xml").write_text("<mule/>\n", encoding="utf-8")
    (studio / "studio-pedidos" / "pom.xml").write_text(
        POM.format(versao="1.1.0"), encoding="utf-8"
    )

    for versao, extra in (("1.0.0", False), ("1.1.0", True)):
        destino = m2 / "grupo" / "pedidos" / versao / f"pedidos-{versao}-raml.zip"
        destino.parent.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(destino, "w") as z:
            z.writestr("api.raml", BASE_RAML)
            if extra:
                z.writestr("domain/novo.raml", "#%RAML 1.0 DataType\ntype: object\n")

    _git(work, "init", "-q")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")

    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=studio,
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=ProjectPair("pedidos-raml", None),
        )
    )
    return {"work": work, "studio": studio, "raml": raml}


def _rodar(projeto, *args):
    return runner.invoke(app, ["pararepo", *args, "-w", str(projeto["work"])])


def test_sem_force_a_copia_nao_grava(projeto):
    """O caso que motivou a mudanca: `pararepo` sozinho nao pode escrever no repo."""
    alvo = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    (projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='do-studio'/></mule>\n", encoding="utf-8"
    )
    antes = alvo.read_text(encoding="utf-8")

    r = _rodar(projeto)

    assert r.exit_code == 0, r.output
    assert alvo.read_text(encoding="utf-8") == antes, "sem force nao pode gravar"
    assert "previa" in r.output
    assert "pararepo force" in r.output, "e tem de ensinar como gravar"


def test_com_force_a_copia_grava(projeto):
    alvo = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    (projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='do-studio'/></mule>\n", encoding="utf-8"
    )

    r = _rodar(projeto, "force")

    assert r.exit_code == 0, r.output
    assert "do-studio" in alvo.read_text(encoding="utf-8")


def test_force_no_raml_grava(projeto):
    """`pararepo raml force` faz o mesmo que a flag `--aplicar` fazia."""
    r = _rodar(projeto, "raml", "force")

    assert r.exit_code == 0, r.output
    assert (projeto["raml"] / "domain" / "novo.raml").is_file()


def test_raml_sem_force_e_previa(projeto):
    r = _rodar(projeto, "raml")

    assert r.exit_code == 0, r.output
    assert not (projeto["raml"] / "domain" / "novo.raml").exists()
    assert "previa" in r.output


def test_aplicar_continua_valendo(projeto):
    """A flag antiga nao pode quebrar para quem ja a usa em script."""
    r = _rodar(projeto, "raml", "--aplicar")

    assert r.exit_code == 0, r.output
    assert (projeto["raml"] / "domain" / "novo.raml").is_file()


def test_dry_run_vence_o_force(projeto):
    """Pedir os dois e contraditorio; a previa e a leitura segura."""
    alvo = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    (projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='x'/></mule>\n", encoding="utf-8"
    )
    antes = alvo.read_text(encoding="utf-8")

    _rodar(projeto, "force", "--dry-run")

    assert alvo.read_text(encoding="utf-8") == antes


def test_parastudio_nao_exige_force(projeto):
    """A protecao e so do lado que escreve no repositorio.

    `parastudio` grava no workspace do Studio, que e descartavel — reimportar o projeto
    reconstroi. Exigir a palavra ali seria atrito sem ganho.
    """
    (projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='meu'/></mule>\n", encoding="utf-8"
    )

    r = runner.invoke(app, ["parastudio", "-w", str(projeto["work"])])

    assert r.exit_code == 0, r.output
    destino = (
        projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    )
    assert "meu" in destino.read_text(encoding="utf-8")
