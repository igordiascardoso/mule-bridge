"""Sincronizar so uma das partes: `parastudio raml`, `pararepo api`, etc."""

from __future__ import annotations

import pytest

from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.errors import SyncError
from mule_bridge.sync import Direction, sync_all


@pytest.fixture
def cfg(workspace) -> BridgeConfig:
    return BridgeConfig(
        work_root=workspace["work"],
        studio_root=workspace["studio"],
        api=ProjectPair("pedidos-api", "studio-pedidos"),
        raml=ProjectPair("pedidos-raml", "studio-pedidos-raml"),
    )


def _edita_os_dois(workspace):
    (workspace["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml").write_text(
        "<mule><flow name='novo'/></mule>", encoding="utf-8"
    )
    (workspace["work"] / "pedidos-raml" / "api.raml").write_text(
        "#%RAML 1.0\ntitle: pedidos\n# editado\n", encoding="utf-8"
    )


def test_so_raml_nao_toca_na_api(cfg, workspace):
    _edita_os_dois(workspace)
    plans = sync_all(cfg, Direction.PUSH, only="raml")

    assert set(plans) == {"pedidos-raml"}
    api_destino = (
        workspace["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    )
    assert "novo" not in api_destino.read_text(encoding="utf-8")
    raml_destino = workspace["studio"] / "studio-pedidos-raml" / "api.raml"
    assert "editado" in raml_destino.read_text(encoding="utf-8")


def test_so_api_nao_toca_no_raml(cfg, workspace):
    _edita_os_dois(workspace)
    plans = sync_all(cfg, Direction.PUSH, only="api")

    assert set(plans) == {"pedidos-api"}
    raml_destino = workspace["studio"] / "studio-pedidos-raml" / "api.raml"
    assert "editado" not in raml_destino.read_text(encoding="utf-8")


def test_so_api_ainda_reescreve_o_pom(cfg, workspace):
    """A reescrita do pom.xml e do lado da API, entao continua valendo sozinha."""
    from mule_bridge import pomrewrite

    sync_all(cfg, Direction.PUSH, only="api")

    destino = workspace["studio"] / "studio-pedidos" / "pom.xml"
    assert pomrewrite.has_local_pointer(destino)
    origem = workspace["work"] / "pedidos-api" / "pom.xml"
    assert not pomrewrite.has_local_pointer(origem)


def test_sem_filtro_sincroniza_os_dois(cfg, workspace):
    _edita_os_dois(workspace)
    plans = sync_all(cfg, Direction.PUSH)

    assert set(plans) == {"pedidos-api", "pedidos-raml"}


def test_pedir_raml_sem_raml_configurado_falha(workspace):
    cfg = BridgeConfig(
        work_root=workspace["work"],
        studio_root=workspace["studio"],
        api=ProjectPair("pedidos-api", "studio-pedidos"),
        raml=None,
    )

    with pytest.raises(SyncError, match="nao tem pasta de RAML"):
        sync_all(cfg, Direction.PUSH, only="raml")


def test_pararepo_so_raml(cfg, workspace):
    sync_all(cfg, Direction.PUSH)
    (workspace["studio"] / "studio-pedidos-raml" / "api.raml").write_text(
        "#%RAML 1.0\ntitle: pedidos\n# veio do Studio\n", encoding="utf-8"
    )

    sync_all(cfg, Direction.PULL, only="raml")

    local = workspace["work"] / "pedidos-raml" / "api.raml"
    assert "veio do Studio" in local.read_text(encoding="utf-8")
