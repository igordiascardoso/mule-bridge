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


def test_parastudio_raml_sem_pasta_no_studio_aponta_o_pom(cfg, workspace):
    """Sem pasta no workspace, "mandar o RAML" e apontar o pom.xml para a pasta local.

    O Studio consome o RAML como dependencia do Exchange: copiar criaria uma pasta que
    ninguem le, enquanto a referencia no pom.xml e o que o faz ler o RAML editado.
    """
    import shutil

    from typer.testing import CliRunner

    from mule_bridge import config as configmod
    from mule_bridge import pomrewrite
    from mule_bridge.cli import app

    shutil.rmtree(workspace["studio"] / "studio-pedidos-raml")
    cfg.raml = ProjectPair("pedidos-raml", "studio-pedidos-raml")
    configmod.save(cfg)

    result = CliRunner().invoke(
        app, ["parastudio", "raml", "-w", str(workspace["work"])], input=""
    )

    assert result.exit_code == 0, result.output
    pom_studio = workspace["studio"] / "studio-pedidos" / "pom.xml"
    assert pomrewrite.has_local_pointer(pom_studio), "o pom do Studio deve apontar local"
    assert str(workspace["work"] / "pedidos-raml") in pom_studio.read_text(encoding="utf-8")

    pom_repo = workspace["work"] / "pedidos-api" / "pom.xml"
    assert not pomrewrite.has_local_pointer(pom_repo), "o pom do repo nao pode ser tocado"
    assert not (workspace["studio"] / "studio-pedidos-raml").exists(), "nao cria pasta"


def test_parastudio_raml_ja_apontado_nao_repete(cfg, workspace):
    """Rodar de novo nao deve reescrever nem confundir: so confirma que ja esta ligado."""
    import shutil

    from typer.testing import CliRunner

    from mule_bridge import config as configmod
    from mule_bridge.cli import app

    shutil.rmtree(workspace["studio"] / "studio-pedidos-raml")
    cfg.raml = ProjectPair("pedidos-raml", "studio-pedidos-raml")
    configmod.save(cfg)
    args = ["parastudio", "raml", "-w", str(workspace["work"])]

    CliRunner().invoke(app, args, input="")
    segunda = CliRunner().invoke(app, args, input="")

    assert segunda.exit_code == 0
    assert "ja le o RAML" in segunda.output


def test_parastudio_sem_parte_nao_cria_pasta_de_raml_no_workspace(workspace):
    """Regressao encontrada num teste de instalacao do zero.

    Quando o RAML nao tem pasta no workspace (o normal: o Studio o consome do Exchange), o
    `init` gravava `studio` apontando para o nome da pasta local. O `pararepo raml` passou a
    funcionar, mas o `parastudio` sem argumento passou a copiar o RAML para um destino
    inexistente — criando no workspace do Studio uma pasta que ninguem le.
    """
    import shutil

    from mule_bridge import config as configmod

    shutil.rmtree(workspace["studio"] / "studio-pedidos-raml")
    cfg = BridgeConfig(
        work_root=workspace["work"],
        studio_root=workspace["studio"],
        api=ProjectPair("pedidos-api", "studio-pedidos"),
        raml=ProjectPair("pedidos-raml", None),
    )
    configmod.save(cfg)

    plans = sync_all(configmod.load(workspace["work"]), Direction.PUSH)

    assert set(plans) == {"pedidos-api"}, "o RAML sem par no Studio nao entra na copia"
    assert not (workspace["studio"] / "pedidos-raml").exists()
    assert not (workspace["studio"] / "studio-pedidos-raml").exists()


def test_pedir_raml_sem_par_no_studio_orienta(workspace):
    """`parastudio raml` explicito: erro que ensina o caminho, em vez de copiar lixo."""
    cfg = BridgeConfig(
        work_root=workspace["work"],
        studio_root=workspace["studio"],
        api=ProjectPair("pedidos-api", "studio-pedidos"),
        raml=ProjectPair("pedidos-raml", None),
    )

    with pytest.raises(SyncError, match="parastudio raml"):
        sync_all(cfg, Direction.PUSH, only="raml")


def test_config_sem_par_no_studio_sobrevive_ao_roundtrip(workspace):
    """O `None` tem de atravessar gravar-e-ler: senao o bug volta na proxima execucao."""
    from mule_bridge import config as configmod

    configmod.save(
        BridgeConfig(
            work_root=workspace["work"],
            studio_root=workspace["studio"],
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=ProjectPair("pedidos-raml", None),
        )
    )

    lida = configmod.load(workspace["work"])

    assert lida.raml is not None, "a pasta local tem de continuar registrada"
    assert lida.raml.work == "pedidos-raml"
    assert lida.raml.studio is None, "a ausencia de par tem de ser preservada"
    assert lida.pairs == [lida.api], "e o RAML fica fora da copia"


def test_config_antiga_com_nenhuma_e_lida_como_sem_par(workspace):
    """Compatibilidade: configs gravadas antes registravam a string 'nenhuma'."""
    from mule_bridge import config as configmod

    (workspace["work"] / ".mule-bridge.toml").write_text(
        "[studio]\n"
        f'root = "{workspace["studio"].as_posix()}"\n'
        "[api]\n"
        'work = "pedidos-api"\n'
        'studio = "studio-pedidos"\n'
        "[raml]\n"
        'work = "pedidos-raml"\n'
        'studio = "nenhuma"\n',
        encoding="utf-8",
    )

    lida = configmod.load(workspace["work"])

    assert lida.raml.studio is None
    assert lida.pairs == [lida.api]
