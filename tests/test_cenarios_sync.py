"""Cenarios do sync de copia: as duas direcoes, as duas partes, --delete e o pom.xml.

O sync bruto (`parastudio` / `pararepo` sem reconciliacao) copia por cima. Os testes aqui
fixam o que ele preserva mesmo assim — sobretudo o `pom.xml` do repositorio, que nunca pode
passar a apontar para o RAML local — e o que o `--delete` faz em cada direcao.
"""

from __future__ import annotations

import pytest

from mule_bridge import pomrewrite
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


# --- O pom.xml do repositorio, em todos os caminhos ------------------------------


def test_o_pom_do_repo_nunca_aponta_local_em_nenhuma_combinacao(cfg, workspace):
    """A garantia mais importante da ferramenta, verificada nas seis combinacoes.

    Se o `pom.xml` daqui passar a apontar para uma pasta do disco, o build no GitLab quebra
    para todo mundo. Nenhum comando pode produzir esse estado.
    """
    pom_repo = workspace["work"] / "pedidos-api" / "pom.xml"

    for direcao in (Direction.PUSH, Direction.PULL):
        for parte in (None, "api", "raml"):
            sync_all(cfg, direcao, only=parte)
            assert not pomrewrite.has_local_pointer(pom_repo), (
                f"{direcao} {parte} apontou o pom do repo para o RAML local"
            )
            assert "1.1.54" in pom_repo.read_text(encoding="utf-8"), (
                f"{direcao} {parte} perdeu a versao travada do Exchange"
            )


def test_pararepo_nao_traz_o_pom_reescrito_de_volta(cfg, workspace):
    """Depois de um parastudio, o pom do Studio esta reescrito. Ele nao pode voltar."""
    sync_all(cfg, Direction.PUSH)
    assert pomrewrite.has_local_pointer(workspace["studio"] / "studio-pedidos" / "pom.xml")

    sync_all(cfg, Direction.PULL)

    pom_repo = workspace["work"] / "pedidos-api" / "pom.xml"
    assert not pomrewrite.has_local_pointer(pom_repo)
    assert "systemPath" not in pom_repo.read_text(encoding="utf-8")


def test_ida_e_volta_repetida_nao_degrada_o_pom(cfg, workspace):
    """Tres ciclos completos: o pom do repo tem de terminar identico ao que comecou."""
    pom_repo = workspace["work"] / "pedidos-api" / "pom.xml"
    antes = pom_repo.read_text(encoding="utf-8")

    for _ in range(3):
        sync_all(cfg, Direction.PUSH)
        sync_all(cfg, Direction.PULL)

    assert pom_repo.read_text(encoding="utf-8") == antes


# --- --delete, nas duas direcoes -------------------------------------------------


def test_delete_no_parastudio_remove_no_studio(cfg, workspace):
    """Apaguei aqui, quero que suma la. O destino e o workspace do Studio."""
    sync_all(cfg, Direction.PUSH)
    orfao = workspace["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "orfao.xml"
    orfao.write_text("<mule/>", encoding="utf-8")

    sync_all(cfg, Direction.PUSH, delete=True)

    assert not orfao.exists()


def test_delete_no_pararepo_remove_no_repo(cfg, workspace):
    """A direcao perigosa: o destino sao os arquivos versionados."""
    sync_all(cfg, Direction.PUSH)
    meu = workspace["work"] / "pedidos-api" / "src" / "main" / "mule" / "so-daqui.xml"
    meu.write_text("<mule/>", encoding="utf-8")

    sync_all(cfg, Direction.PULL, delete=True)

    assert not meu.exists(), "com --delete explicito, remove mesmo — e por isso que exige pedido"


def test_sem_delete_o_arquivo_extra_no_destino_fica(cfg, workspace):
    """O padrao e nunca apagar: sem a flag, nada e removido em nenhuma direcao."""
    sync_all(cfg, Direction.PUSH)
    extra = workspace["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "extra.xml"
    extra.write_text("<mule/>", encoding="utf-8")
    meu = workspace["work"] / "pedidos-api" / "src" / "main" / "mule" / "meu.xml"
    meu.write_text("<mule/>", encoding="utf-8")

    sync_all(cfg, Direction.PUSH)
    sync_all(cfg, Direction.PULL)

    assert extra.exists() and meu.exists()


def test_delete_nao_remove_o_pom_apontado(cfg, workspace):
    """O pom do Studio e um caso especial: reescrito, nao copiado. O --delete nao o come."""
    sync_all(cfg, Direction.PUSH)
    pom_studio = workspace["studio"] / "studio-pedidos" / "pom.xml"

    sync_all(cfg, Direction.PULL, delete=True)

    assert pom_studio.is_file()


# --- dry-run, em tudo -----------------------------------------------------------


def test_dry_run_nao_escreve_em_nenhuma_combinacao(cfg, workspace):
    """Se o dry-run alterar qualquer byte, a promessa da flag esta rompida."""
    sync_all(cfg, Direction.PUSH)

    def instantaneo():
        alvo = {}
        for raiz in (workspace["work"], workspace["studio"]):
            for p in sorted(raiz.rglob("*")):
                if p.is_file():
                    alvo[str(p)] = p.read_bytes()
        return alvo

    antes = instantaneo()
    for direcao in (Direction.PUSH, Direction.PULL):
        for parte in (None, "api", "raml"):
            sync_all(cfg, direcao, only=parte, dry_run=True)
            sync_all(cfg, direcao, only=parte, dry_run=True, delete=True)

    assert instantaneo() == antes, "dry-run alterou o disco"


# --- Volume e estrutura ---------------------------------------------------------


def test_arvore_profunda_e_copiada_inteira(cfg, workspace):
    """Subpastas aninhadas: o sync nao pode achatar nem perder nivel."""
    fundo = (
        workspace["work"] / "pedidos-api" / "src" / "main" / "mule" / "a" / "b" / "c" / "d"
    )
    fundo.mkdir(parents=True)
    (fundo / "fundo.xml").write_text("<mule/>", encoding="utf-8")

    sync_all(cfg, Direction.PUSH)

    espelho = (
        workspace["studio"]
        / "studio-pedidos"
        / "src"
        / "main"
        / "mule"
        / "a"
        / "b"
        / "c"
        / "d"
        / "fundo.xml"
    )
    assert espelho.is_file()


def test_muitos_arquivos_de_uma_vez(cfg, workspace):
    """Cem arquivos numa passada, para o caso de haver limite acidental."""
    pasta = workspace["work"] / "pedidos-api" / "src" / "main" / "mule" / "muitos"
    pasta.mkdir()
    for i in range(100):
        (pasta / f"f{i}.xml").write_text(f"<mule>{i}</mule>", encoding="utf-8")

    sync_all(cfg, Direction.PUSH)

    destino = workspace["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "muitos"
    assert len(list(destino.glob("*.xml"))) == 100


def test_target_e_ignorado_nas_duas_direcoes(cfg, workspace):
    """Artefato de build nao atravessa a ponte em nenhum sentido."""
    (workspace["studio"] / "studio-pedidos" / "target").mkdir(exist_ok=True)
    (workspace["studio"] / "studio-pedidos" / "target" / "build.jar").write_text(
        "x", encoding="utf-8"
    )

    sync_all(cfg, Direction.PULL)

    assert not (workspace["work"] / "pedidos-api" / "target" / "build.jar").exists()


def test_arquivo_binario_atravessa_intacto(cfg, workspace):
    """Keystore, certificado, jar de lib: nao pode ser corrompido por decodificacao."""
    bruto = bytes(range(256)) * 8
    origem = workspace["work"] / "pedidos-api" / "src" / "main" / "resources"
    origem.mkdir(parents=True, exist_ok=True)
    (origem / "keystore.jks").write_bytes(bruto)

    sync_all(cfg, Direction.PUSH)

    destino = (
        workspace["studio"] / "studio-pedidos" / "src" / "main" / "resources" / "keystore.jks"
    )
    assert destino.read_bytes() == bruto
