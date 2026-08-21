"""Quando a pasta do RAML nao existe, o pararepo raml a cria em vez de falhar."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mule_bridge import config
from mule_bridge.cli import app
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


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    """Repo com API mas SEM pasta de RAML, e o Studio apontando para a 1.1.55."""
    work, studio = tmp_path / "repo", tmp_path / "ws"
    m2 = tmp_path / "casa" / ".m2" / "repository"

    api = work / "pedidos-api" / "src" / "main" / "mule"
    api.mkdir(parents=True)
    (work / "pedidos-api" / "pom.xml").write_text(POM.format(versao="1.1.54"), encoding="utf-8")

    studio_api = studio / "studio-pedidos" / "src" / "main" / "mule"
    studio_api.mkdir(parents=True)
    (studio / "studio-pedidos" / "pom.xml").write_text(
        POM.format(versao="1.1.55"), encoding="utf-8"
    )

    destino = m2 / "grupo" / "pedidos" / "1.1.55" / "pedidos-1.1.55-raml.zip"
    destino.parent.mkdir(parents=True)
    with zipfile.ZipFile(destino, "w") as z:
        z.writestr("api.raml", "#%RAML 1.0\ntitle: Pedidos\n")
        z.writestr("domain/captcha.raml", "#%RAML 1.0\ntitle: Captcha\n")

    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "casa"))

    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=studio,
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=None,
        )
    )
    return {"work": work, "studio": studio}


def test_dry_run_nao_cria_a_pasta(cenario):
    result = runner.invoke(
        app, ["pararepo", "raml", "-w", str(cenario["work"]), "--dry-run"]
    )

    assert result.exit_code == 0, result.output
    assert not (cenario["work"] / "pedidos-raml").exists()


def test_cria_a_pasta_com_a_versao_do_studio(cenario):
    result = runner.invoke(
        app, ["pararepo", "raml", "-w", str(cenario["work"])]
    )

    assert result.exit_code == 0, result.output
    pasta = cenario["work"] / "pedidos-raml"
    assert (pasta / "api.raml").is_file()
    assert (pasta / "domain" / "captcha.raml").is_file(), "deve trazer a 1.1.55, do Studio"


def test_grava_o_pareamento_da_pasta_criada(cenario):
    runner.invoke(app, ["pararepo", "raml", "-w", str(cenario["work"])])

    cfg = config.load(cenario["work"])
    assert cfg.raml is not None
    assert cfg.raml.work == "pedidos-raml"


def test_nao_sobrescreve_pasta_existente_fora_da_config(cenario):
    """Config sem RAML mas pasta no disco: adota a pasta, nunca extrai por cima.

    Regressao: a pasta podia conter trabalho local nao pareado, e extrair por cima
    apagava tudo — o oposto do que a ferramenta existe para fazer.
    """
    pasta = cenario["work"] / "pedidos-raml"
    pasta.mkdir()
    (pasta / "api.raml").write_text("#%RAML 1.0\ntitle: MEU TRABALHO\n", encoding="utf-8")

    result = runner.invoke(
        app, ["pararepo", "raml", "-w", str(cenario["work"])]
    )

    assert "MEU TRABALHO" in (pasta / "api.raml").read_text(encoding="utf-8"), (
        f"a edicao local foi sobrescrita. saida:\n{result.output}"
    )
