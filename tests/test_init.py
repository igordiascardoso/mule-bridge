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
    """Sem stdin e sem flags, orienta em vez de abortar sem explicacao.

    A API tem uma opcao so e e resolvida sem perguntar; o primeiro prompt de verdade e o
    do RAML, que tem duas (a pasta encontrada e "nenhuma").
    """
    result = runner.invoke(app, _args(workspace), input="")

    assert result.exit_code == 1
    assert "--raml" in result.output
    assert "pedidos-raml" in result.output, "deve listar as opcoes encontradas"


def test_opcao_unica_nao_pergunta(workspace):
    """Uma opcao so nao e escolha — resolver sozinho poupa uma ida e volta inutil.

    Aqui a pasta da API e a unica candidata no repositorio, entao o init nao para nela.
    """
    result = runner.invoke(
        app, _args(workspace, raml="nenhuma", studio_api="studio-pedidos"), input=""
    )

    assert result.exit_code == 0, result.output
    assert "unica opcao" in result.output, "deve dizer que resolveu sozinho"
    cfg = config.load(workspace["work"])
    assert cfg.api.work == "pedidos-api", "a API foi resolvida sem perguntar"


def test_avisa_quando_nao_ha_pasta_de_raml(workspace):
    """Sem RAML, o init aponta o caminho em vez de gravar a config em silencio."""
    import shutil

    shutil.rmtree(workspace["work"] / "pedidos-raml")

    result = runner.invoke(app, _args(workspace, studio_api="studio-pedidos"), input="")

    assert result.exit_code == 0, result.output
    assert "pararepo raml" in result.output, "deve dizer como criar a pasta"


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


def test_raml_sem_par_no_studio_ainda_e_configurado(workspace):
    """O Studio consome o RAML como dependencia, sem pasta propria — isso e normal.

    Regressao: com `--studio-raml nenhuma` a secao [raml] nao era gravada, e o
    `pararepo raml` passava a dizer que o projeto nao tinha RAML configurado.
    """
    result = runner.invoke(
        app,
        _args(workspace, api="pedidos-api", raml="pedidos-raml", studio_api="studio-pedidos")
        + ["--studio-raml", "nenhuma"],
        input="",
    )

    assert result.exit_code == 0, result.output
    cfg = config.load(workspace["work"])
    assert cfg.raml is not None, "a pasta local do RAML tem de ser guardada"
    assert cfg.raml.work == "pedidos-raml"


def test_roda_como_modulo_python(tmp_path):
    """`python -m mule_bridge` e a saida de quem nao consegue mexer no PATH.

    O README documenta essa forma; sem `__main__.py` ela falha com "cannot be directly
    executed", e a pessoa fica sem alternativa nenhuma.
    """
    import subprocess
    import sys

    proc = subprocess.run(
        [sys.executable, "-m", "mule_bridge", "--version"],
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert proc.returncode == 0, proc.stderr
    assert "mule-bridge" in proc.stdout
