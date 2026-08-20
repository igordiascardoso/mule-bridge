from __future__ import annotations

import pytest

from mule_bridge import config, pomrewrite
from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.sync import Direction, sync_all


@pytest.fixture
def cfg(workspace) -> BridgeConfig:
    return BridgeConfig(
        work_root=workspace["work"],
        studio_root=workspace["studio"],
        api=ProjectPair("pedidos-api", "studio-pedidos"),
        raml=ProjectPair("pedidos-raml", "studio-pedidos-raml"),
    )


def test_push_copia_edicao_e_ignora_target(cfg, workspace):
    (workspace["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='novo'/></mule>", encoding="utf-8"
    )
    # o target/ do lado do Studio comeca vazio, para provar que nada foi copiado para la
    (workspace["studio"] / "studio-pedidos" / "target" / "junk.jar").unlink()
    plans = sync_all(cfg, Direction.PUSH)

    dst = workspace["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    assert "novo" in dst.read_text(encoding="utf-8")
    assert all("target/junk.jar" not in p.copied for p in plans.values())
    assert not (workspace["studio"] / "studio-pedidos" / "target" / "junk.jar").exists()


def test_push_reescreve_pom_so_no_destino(cfg, workspace):
    sync_all(cfg, Direction.PUSH)

    origem = workspace["work"] / "pedidos-api" / "pom.xml"
    destino = workspace["studio"] / "studio-pedidos" / "pom.xml"

    assert not pomrewrite.has_local_pointer(origem), "a pasta de trabalho vai para o git intacta"
    assert pomrewrite.has_local_pointer(destino)
    assert "<classifier>raml</classifier>" in origem.read_text(encoding="utf-8")


def test_pull_nao_traz_o_pom_apontado_ao_raml_local(cfg, workspace):
    sync_all(cfg, Direction.PUSH)
    plans = sync_all(cfg, Direction.PULL)

    origem = workspace["work"] / "pedidos-api" / "pom.xml"
    assert not pomrewrite.has_local_pointer(origem)
    assert "pom.xml" in plans["pedidos-api"].skipped


def test_pull_traz_flow_gerado_pelo_scaffold(cfg, workspace):
    sync_all(cfg, Direction.PUSH)
    scaffolded = workspace["studio"] / "studio-pedidos" / "src" / "main" / "mule"
    (scaffolded / "application.xml").write_text(
        r"<mule><flow name='get:\captcha\challenge'/></mule>", encoding="utf-8"
    )
    sync_all(cfg, Direction.PULL)

    trabalho = workspace["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    assert "captcha" in trabalho.read_text(encoding="utf-8")


def test_dry_run_nao_altera_nada(cfg, workspace):
    destino = workspace["studio"] / "studio-pedidos" / "pom.xml"
    antes = destino.read_text(encoding="utf-8")
    plans = sync_all(cfg, Direction.PUSH, dry_run=True)

    assert destino.read_text(encoding="utf-8") == antes
    assert plans["pedidos-api"].total > 0


def test_delete_remove_orfao_no_destino(cfg, workspace):
    orfao = workspace["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "antigo.xml"
    orfao.write_text("<mule/>", encoding="utf-8")

    sync_all(cfg, Direction.PUSH, delete=True)
    assert not orfao.exists()


def test_config_sobrevive_ao_roundtrip(cfg, workspace):
    config.save(cfg)
    lida = config.load(workspace["work"])

    assert lida.studio_root == cfg.studio_root
    assert lida.api == cfg.api
    assert lida.raml == cfg.raml
