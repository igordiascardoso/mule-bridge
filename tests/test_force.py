"""O vocabulário dos comandos: três palavras, uma delas obrigatória.

`raml` e `api` juntam o que os dois lados mudaram. `force` sobrescreve o destino sem juntar
— é a única palavra que pode fazer trabalho ser perdido, e por isso não se combina com as
outras. Sem palavra nenhuma o comando recusa: adivinhar é onde uma gravação sai errada,
sobretudo quando é um agente de IA digitando no chat.
"""

from __future__ import annotations

import subprocess
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from mule_bridge import config, exchange
from mule_bridge.cli import PALAVRAS, _parse_palavras, app
from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.exchange import ProjetoDesignCenter, VersaoExchange

GROUP_ID = "grupo-org-teste"

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


def test_sem_palavra_o_comando_recusa():
    """`ponte pararepo` sozinho nao existe: a palavra e o que diz o que fazer."""
    for entrada in (None, []):
        with pytest.raises(typer.BadParameter, match="Falta a palavra"):
            _parse_palavras(entrada, comando="pararepo")


def test_o_erro_de_falta_ensina_as_tres_formas():
    """Quem errou tem de sair do erro sabendo o que digitar."""
    with pytest.raises(typer.BadParameter) as e:
        _parse_palavras([], comando="parastudio")

    msg = str(e.value)
    for esperado in ("parastudio raml", "parastudio api", "parastudio force"):
        assert esperado in msg, msg


def test_force_sozinho():
    p = _parse_palavras(["force"], comando="pararepo")
    assert p.parte is None and p.force


def test_parte_sozinha():
    assert _parse_palavras(["raml"], comando="pararepo").parte == "raml"
    assert _parse_palavras(["api"], comando="pararepo").parte == "api"
    assert not _parse_palavras(["raml"], comando="pararepo").force


def test_force_nao_se_combina_com_parte():
    """`raml`/`api` juntam, `force` sobrescreve — pedir os dois e contraditorio.

    Recusar e melhor que escolher um: as duas leituras possiveis diferem em perder ou nao
    o trabalho do usuario, e nao ha default seguro para essa ambiguidade.
    """
    for palavras in (["raml", "force"], ["force", "api"]):
        with pytest.raises(typer.BadParameter, match="nao se combina"):
            _parse_palavras(palavras, comando="pararepo")


def test_o_erro_de_combinacao_mostra_as_duas_saidas():
    with pytest.raises(typer.BadParameter) as e:
        _parse_palavras(["raml", "force"], comando="pararepo")

    msg = str(e.value)
    assert "pararepo raml" in msg and "pararepo force" in msg, msg


def test_aceita_force_em_portugues():
    """Quem digita em portugues escreve 'forca'."""
    assert _parse_palavras(["forca"], comando="pararepo").force
    assert _parse_palavras(["força"], comando="pararepo").force


def test_maiuscula_e_espaco_nao_atrapalham():
    assert _parse_palavras([" FORCE "], comando="pararepo").force
    assert _parse_palavras(["RAML"], comando="pararepo").parte == "raml"


def test_aceita_a_palavra_com_hifen_por_engano():
    """Quem tem habito de CLI digita `--force`; nao ha motivo para recusar."""
    assert _parse_palavras(["--force"], comando="pararepo").force
    assert _parse_palavras(["--raml"], comando="pararepo").parte == "raml"


def test_o_vocabulario_tem_tres_palavras():
    """Cada palavra a mais e uma coisa a mais para o usuario — ou a IA — errar.

    Este teste falha quando alguem acrescenta uma palavra: e um lembrete de justificar a
    adicao, nao um impedimento. Sairam: "resolvido" (o conflito e resolvido na hora, sem
    segundo comando), "previa" e "tudo".
    """
    assert set(PALAVRAS) == {"raml", "api", "force"}


def test_palavra_que_saiu_do_vocabulario_e_recusada():
    """Viraram erro claro, em vez de serem ignoradas em silencio."""
    for palavra in ("resolvido", "previa", "tudo", "apagar"):
        with pytest.raises(typer.BadParameter, match="Nao entendi"):
            _parse_palavras([palavra], comando="pararepo")


def test_palavra_desconhecida_e_erro():
    """Melhor recusar que adivinhar: um typo nao pode virar gravacao silenciosa."""
    with pytest.raises(typer.BadParameter, match="Nao entendi"):
        _parse_palavras(["aplicar"], comando="pararepo")


def test_duas_partes_diferentes_e_erro():
    with pytest.raises(typer.BadParameter, match="uma palavra so"):
        _parse_palavras(["raml", "api"], comando="pararepo")


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

    # `pararepo raml` agora busca do Exchange (mockado), nao do cache do Maven acima —
    # o cache continua so para o `parastudio`/`pararepo api`, que nao mudaram.
    projeto_dc = ProjetoDesignCenter(
        id="proj-1", nome="pedidos", modificado_em=datetime(2026, 8, 22, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(exchange, "listar_projetos_design_center", lambda: [projeto_dc])

    def fake_baixar_projeto(nome, destino):
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "exchange.json").write_text(
            f'{{"groupId": "{GROUP_ID}", "assetId": "pedidos", "main": "api.raml", '
            f'"apiVersion": "v1", "version": "1.1.0"}}',
            encoding="utf-8",
        )
        return destino

    monkeypatch.setattr(exchange, "baixar_projeto_design_center", fake_baixar_projeto)
    monkeypatch.setattr(
        exchange,
        "listar_versoes_exchange",
        lambda g, a: [
            VersaoExchange(versao="1.1.0", publicado_em=datetime(2026, 8, 22, tzinfo=timezone.utc))
        ],
    )

    def fake_baixar_versao(group_id, asset_id, versao, destino):
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "api.raml").write_text(BASE_RAML, encoding="utf-8")
        if versao == "1.1.0":
            (destino / "domain").mkdir(exist_ok=True)
            (destino / "domain" / "novo.raml").write_text(
                "#%RAML 1.0 DataType\ntype: object\n", encoding="utf-8"
            )
        return destino

    monkeypatch.setattr(exchange, "baixar_versao_exchange", fake_baixar_versao)

    return {"work": work, "studio": studio, "raml": raml}


def _rodar(projeto, *args):
    entrada = "\n1\n1\n" if args[:1] == ("raml",) else None
    return runner.invoke(
        app, ["pararepo", *args, "-w", str(projeto["work"])], input=entrada
    )


def test_pararepo_sem_palavra_nao_escreve(projeto):
    """O comando nu nao roda: recusa antes de tocar em qualquer arquivo."""
    alvo = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    (projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='do-studio'/></mule>\n", encoding="utf-8"
    )
    antes = alvo.read_text(encoding="utf-8")

    r = _rodar(projeto)

    assert r.exit_code != 0, r.output
    assert alvo.read_text(encoding="utf-8") == antes, "nao pode gravar sem palavra"


def test_parastudio_sem_palavra_nao_escreve(projeto):
    """A recusa vale nos dois comandos: a grade e simetrica."""
    r = runner.invoke(app, ["parastudio", "-w", str(projeto["work"])])

    assert r.exit_code != 0, r.output


def test_pararepo_force_sobrescreve(projeto):
    alvo = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    (projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='do-studio'/></mule>\n", encoding="utf-8"
    )

    r = _rodar(projeto, "force")

    assert r.exit_code == 0, r.output
    assert "do-studio" in alvo.read_text(encoding="utf-8")


def test_pararepo_raml_grava_na_hora(projeto):
    """Sem prévia e sem segundo comando: a palavra `raml` ja e a autorizacao."""
    r = _rodar(projeto, "raml")

    assert r.exit_code == 0, r.output
    assert (projeto["raml"] / "domain" / "novo.raml").is_file()


def test_pararepo_api_grava_na_hora(projeto):
    (projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='do-scaffold'/></mule>\n", encoding="utf-8"
    )

    r = _rodar(projeto, "api")

    assert r.exit_code == 0, r.output
    alvo = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    assert "do-scaffold" in alvo.read_text(encoding="utf-8")


def test_dry_run_nao_grava(projeto):
    """A flag escondida continua servindo a quem automatiza."""
    r = _rodar(projeto, "raml", "--dry-run")

    assert r.exit_code == 0, r.output
    assert not (projeto["raml"] / "domain" / "novo.raml").exists()


def test_parastudio_api_copia_para_o_workspace(projeto):
    """O destino e o workspace, que e descartavel — reimportar o projeto reconstroi."""
    (projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='meu'/></mule>\n", encoding="utf-8"
    )

    r = runner.invoke(app, ["parastudio", "api", "-w", str(projeto["work"])])

    assert r.exit_code == 0, r.output
    destino = (
        projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    )
    assert "meu" in destino.read_text(encoding="utf-8")
