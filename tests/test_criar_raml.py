"""Quando a pasta do RAML nao existe, o `pararepo raml` a cria buscando do Exchange.

Comportamento mudado: antes lia do cache do Maven (o que o Studio ja tinha baixado);
agora busca direto do Exchange, passando por dois menus (projeto do Design Center, depois
versao do Exchange) — ver docs/DESIGN-CENTER-CLI.md, "Decisao final: os tres comandos".
"""

from __future__ import annotations

import zipfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mule_bridge import config, exchange
from mule_bridge.cli import app
from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.exchange import ProjetoDesignCenter, VersaoExchange

runner = CliRunner()

GROUP_ID = "grupo-org-teste"
PROJETO = ProjetoDesignCenter(
    id="proj-1", nome="pedidos", modificado_em=datetime(2026, 8, 22, tzinfo=timezone.utc)
)


@pytest.fixture
def cenario(tmp_path):
    """Repo com API mas SEM pasta de RAML, pareado, esperando o pararepo raml."""
    work = tmp_path / "repo"
    studio = tmp_path / "ws"
    (work / "pedidos-api" / "src" / "main" / "mule").mkdir(parents=True)
    (studio / "studio-pedidos").mkdir(parents=True)

    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=studio,
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=None,
        )
    )
    return {"work": work, "studio": studio}


def _mock_exchange(monkeypatch, *, versoes: list[str], conteudo: dict[str, str]):
    """Mocka o modulo exchange por completo — nunca bate na CLI real."""
    monkeypatch.setattr(exchange, "listar_projetos_design_center", lambda: [PROJETO])

    def fake_baixar_projeto(nome, destino):
        (destino).mkdir(parents=True, exist_ok=True)
        (destino / "exchange.json").write_text(
            '{"groupId": "%s", "assetId": "pedidos", "main": "api.raml", '
            '"apiVersion": "v1", "version": "%s"}' % (GROUP_ID, versoes[0]),
            encoding="utf-8",
        )
        return destino

    monkeypatch.setattr(exchange, "baixar_projeto_design_center", fake_baixar_projeto)

    def fake_listar_versoes(group_id, asset_id):
        assert group_id == GROUP_ID
        assert asset_id == "pedidos"
        return [
            VersaoExchange(versao=v, publicado_em=datetime(2026, 8, 22, tzinfo=timezone.utc))
            for v in versoes
        ]

    monkeypatch.setattr(exchange, "listar_versoes_exchange", fake_listar_versoes)

    def fake_baixar_versao(group_id, asset_id, versao, destino):
        destino.mkdir(parents=True, exist_ok=True)
        for rel, texto in conteudo.items():
            p = destino / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(texto, encoding="utf-8")
        return destino

    monkeypatch.setattr(exchange, "baixar_versao_exchange", fake_baixar_versao)


def test_dry_run_nao_cria_a_pasta(cenario, monkeypatch):
    _mock_exchange(
        monkeypatch,
        versoes=["1.1.55"],
        conteudo={"api.raml": "#%RAML 1.0\ntitle: Pedidos\n"},
    )

    result = runner.invoke(
        app,
        ["pararepo", "raml", "-w", str(cenario["work"]), "--dry-run"],
        input="1\n1\n",
    )

    assert result.exit_code == 0, result.output
    assert not (cenario["work"] / "pedidos-raml").exists()


def test_cria_a_pasta_com_a_versao_escolhida(cenario, monkeypatch):
    _mock_exchange(
        monkeypatch,
        versoes=["1.1.55"],
        conteudo={
            "api.raml": "#%RAML 1.0\ntitle: Pedidos\n",
            "domain/captcha.raml": "#%RAML 1.0\ntitle: Captcha\n",
        },
    )

    result = runner.invoke(
        app, ["pararepo", "raml", "-w", str(cenario["work"])], input="1\n1\n"
    )

    assert result.exit_code == 0, result.output
    pasta = cenario["work"] / "pedidos-raml"
    assert (pasta / "api.raml").is_file()
    assert (pasta / "domain" / "captcha.raml").is_file()


def test_grava_o_pareamento_da_pasta_criada(cenario, monkeypatch):
    _mock_exchange(
        monkeypatch, versoes=["1.1.55"], conteudo={"api.raml": "#%RAML 1.0\ntitle: X\n"}
    )

    runner.invoke(app, ["pararepo", "raml", "-w", str(cenario["work"])], input="1\n1\n")

    cfg = config.load(cenario["work"])
    assert cfg.raml is not None
    assert cfg.raml.work == "pedidos-raml"


def test_nao_sobrescreve_pasta_existente_fora_da_config(cenario, monkeypatch):
    """Config sem RAML mas pasta no disco: nao apaga trabalho local nao pareado."""
    _mock_exchange(
        monkeypatch, versoes=["1.1.55"], conteudo={"api.raml": "#%RAML 1.0\ntitle: X\n"}
    )
    pasta = cenario["work"] / "pedidos-raml"
    pasta.mkdir()
    (pasta / "api.raml").write_text("#%RAML 1.0\ntitle: MEU TRABALHO\n", encoding="utf-8")

    result = runner.invoke(
        app, ["pararepo", "raml", "-w", str(cenario["work"])], input="1\n1\n"
    )

    assert "MEU TRABALHO" in (pasta / "api.raml").read_text(encoding="utf-8"), (
        f"a edicao local foi sobrescrita. saida:\n{result.output}"
    )
