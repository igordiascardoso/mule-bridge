"""O `caminho` reaponta o pareamento quando uma pasta sai do lugar.

Ele nao repete as escolhas do `init`: a pergunta aqui e "onde ficou", nao "qual e o par".
Por isso `manter` e sempre a opcao 1 — corrigir um caminho nao pode custar redigitar os que
estavam certos.
"""

from __future__ import annotations

import shutil

from typer.testing import CliRunner

from mule_bridge import config
from mule_bridge.cli import app
from mule_bridge.config import BridgeConfig, ProjectPair

runner = CliRunner()


def _parear(workspace, *, raml: str | None = "pedidos-raml") -> None:
    config.save(
        BridgeConfig(
            work_root=workspace["work"],
            studio_root=workspace["studio"],
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=ProjectPair(raml, None) if raml else None,
        )
    )


def _rodar(workspace, respostas: str):
    return runner.invoke(
        app, ["caminho", "-w", str(workspace["work"])], input=respostas
    )


def test_enter_em_tudo_nao_muda_nada(workspace):
    """O default de cada pergunta e `manter`, entao Enter preserva o pareamento."""
    _parear(workspace)

    result = _rodar(workspace, "\n\n\n")

    assert result.exit_code == 0, result.output
    cfg = config.load(workspace["work"])
    assert cfg.studio_root == workspace["studio"]
    assert cfg.api.work == "pedidos-api"
    assert cfg.api.studio == "studio-pedidos"
    assert cfg.raml.work == "pedidos-raml"


def test_pasta_da_api_renomeada_e_reapontada(workspace):
    """O caso que traz o usuario aqui: a pasta existe com outro nome."""
    _parear(workspace)
    shutil.move(
        str(workspace["work"] / "pedidos-api"), str(workspace["work"] / "api-renomeada")
    )

    # Enter no workspace; no repo, a opcao 2 (a unica API achada no disco).
    result = _rodar(workspace, "\n2\n\n")

    assert result.exit_code == 0, result.output
    assert config.load(workspace["work"]).api.work == "api-renomeada"


def test_marca_o_que_nao_esta_no_disco(workspace):
    """A opcao `manter` vem marcada quando a pasta pareada nao existe.

    Sem a marca, o Enter — que e o default — manteria justamente o caminho quebrado.
    """
    _parear(workspace)
    shutil.rmtree(workspace["work"] / "pedidos-api")

    result = _rodar(workspace, "\n\n\n")

    assert "nao esta no disco" in result.output, result.output


def test_nao_pergunta_do_raml_quando_a_pasta_esta_no_lugar(workspace):
    """Pasta de RAML onde deveria: nada a corrigir, e o comando nao cobra um Enter por isso.

    Sao tres perguntas so — workspace, e os dois lados da API.
    """
    _parear(workspace)

    result = _rodar(workspace, "\n\n\n")

    assert result.exit_code == 0, result.output
    assert "pasta do RAML" not in result.output, result.output


def test_pergunta_do_raml_quando_a_pasta_foi_renomeada(workspace):
    """Renomeada e o unico caso do RAML que precisa de resposta."""
    _parear(workspace)
    shutil.move(
        str(workspace["work"] / "pedidos-raml"), str(workspace["work"] / "raml-renomeado")
    )

    result = _rodar(workspace, "\n\n\n2\n")

    assert result.exit_code == 0, result.output
    assert "mudou de nome" in result.output, result.output
    assert config.load(workspace["work"]).raml.work == "raml-renomeado"


def test_raml_apagado_sem_outro_por_perto_fica_como_esta(workspace):
    """Sem pasta e sem candidata, quem recria e o `pararepo raml` extraindo o zip.

    Perguntar aqui nao teria resposta possivel, e mudar o pareamento sozinho tiraria do
    `pararepo raml` a pasta que ele sabe criar.
    """
    _parear(workspace)
    shutil.rmtree(workspace["work"] / "pedidos-raml")

    result = _rodar(workspace, "\n\n\n")

    assert result.exit_code == 0, result.output
    assert "pararepo raml" in result.output, result.output
    assert config.load(workspace["work"]).raml.work == "pedidos-raml"


def test_sem_config_recusa_e_manda_parear(workspace):
    """Sem `.mule-bridge.toml` nao ha caminho a corrigir — ha pareamento a fazer."""
    result = _rodar(workspace, "\n")

    assert result.exit_code != 0
    assert "init" in result.output, result.output
