"""Testes do `init`, com foco no modo sem terminal interativo."""

from __future__ import annotations

from typer.testing import CliRunner

from mule_bridge import config
from mule_bridge.cli import app

runner = CliRunner()


def _args(workspace, **extra):
    base = [
        "init",
        "-w",
        str(workspace["work"]),
        "-s",
        str(workspace["studio"]),
    ]
    for k, v in extra.items():
        base += [f"--{k.replace('_', '-')}", v]
    return base


def test_init_por_flags_nao_pergunta_nada(workspace):
    """O modo usado por agentes de IA e extensoes de IDE: escolha inteira via flag."""
    result = runner.invoke(
        app,
        _args(
            workspace,
            api="pedidos-api",
            raml="pedidos-raml",
            studio_api="studio-pedidos",
            studio_raml="studio-pedidos-raml",
        ),
        input="",  # nenhum prompt deve consumir stdin
    )

    assert result.exit_code == 0, result.output
    cfg = config.load(workspace["work"])
    assert cfg.api.work == "pedidos-api"
    assert cfg.api.studio == "studio-pedidos"
    assert cfg.raml.studio == "studio-pedidos-raml"


def test_sem_terminal_o_erro_ensina_a_flag(workspace):
    """Sem stdin e sem flags, orienta em vez de abortar sem explicacao."""
    result = runner.invoke(app, _args(workspace), input="")

    assert result.exit_code == 1
    assert "--api" in result.output
    assert "pedidos-api" in result.output, "deve listar a opcao encontrada"


def test_flag_com_nome_inexistente_lista_as_opcoes(workspace):
    result = runner.invoke(app, _args(workspace, api="nao-existe"), input="")

    assert result.exit_code == 1
    assert "pedidos-api" in result.output


def test_raml_nenhuma_desliga_o_sync_do_raml(workspace):
    result = runner.invoke(
        app,
        _args(workspace, api="pedidos-api", raml="nenhuma", studio_api="studio-pedidos"),
        input="",
    )

    assert result.exit_code == 0, result.output
    cfg = config.load(workspace["work"])
    assert cfg.raml is None
    assert len(cfg.pairs) == 1


def test_nao_sobrescreve_config_existente_sem_force(workspace):
    argumentos = _args(
        workspace,
        api="pedidos-api",
        raml="nenhuma",
        studio_api="studio-pedidos",
    )
    assert runner.invoke(app, argumentos, input="").exit_code == 0

    segunda = runner.invoke(app, argumentos, input="")
    assert segunda.exit_code == 1
    assert "--force" in segunda.output
