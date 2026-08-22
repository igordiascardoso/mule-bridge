"""`paradesign raml` (upload) e `publicardesign` (publish), tudo mockado.

Cobre o caminho feliz dos dois comandos novos e a validacao de RAML antes de
subir/publicar (ver docs/DESIGN-CENTER-CLI.md, "O RAML mal formado nao sempre falha").
"""

from __future__ import annotations

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
RAML_VALIDO = "#%RAML 1.0\ntitle: Pedidos\n"
PROJETO_DC = ProjetoDesignCenter(
    id="proj-1", nome="pedidos", modificado_em=datetime(2026, 8, 22, tzinfo=timezone.utc)
)


@pytest.fixture
def cenario(tmp_path):
    """Repo pareado, com a pasta de RAML ja no disco (como se viesse de um pararepo raml)."""
    work = tmp_path / "repo"
    raml = work / "pedidos-raml"
    raml.mkdir(parents=True)
    (raml / "api.raml").write_text(RAML_VALIDO, encoding="utf-8")
    (raml / "exchange.json").write_text(
        f'{{"groupId": "{GROUP_ID}", "assetId": "pedidos", "main": "api.raml", '
        f'"apiVersion": "v1", "version": "1.0.0"}}',
        encoding="utf-8",
    )

    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=tmp_path / "ws",
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=ProjectPair("pedidos-raml", None),
        )
    )
    return {"work": work, "raml": raml}


def _mock_projeto_ja_publicado(monkeypatch, *, main_no_design_center: str = "api.raml"):
    """O unico projeto do Design Center, ja publicado uma vez no Exchange."""
    monkeypatch.setattr(exchange, "listar_projetos_design_center", lambda: [PROJETO_DC])

    def fake_baixar_projeto(nome, destino):
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "api.raml").write_text(RAML_VALIDO, encoding="utf-8")
        (destino / "exchange.json").write_text(
            f'{{"groupId": "{GROUP_ID}", "assetId": "pedidos", '
            f'"main": "{main_no_design_center}", "apiVersion": "v1", "version": "1.0.0"}}',
            encoding="utf-8",
        )
        return destino

    monkeypatch.setattr(exchange, "baixar_projeto_design_center", fake_baixar_projeto)
    monkeypatch.setattr(
        exchange,
        "listar_versoes_exchange",
        lambda g, a: [
            VersaoExchange(versao="1.0.0", publicado_em=datetime(2026, 8, 22, tzinfo=timezone.utc))
        ],
    )


# --- paradesign raml -------------------------------------------------------------------


def test_paradesign_sem_a_palavra_raml_recusa(cenario):
    result = runner.invoke(app, ["paradesign", "-w", str(cenario["work"])])

    assert result.exit_code != 0


def test_paradesign_sem_pasta_de_raml_recusa(tmp_path):
    work = tmp_path / "repo"
    work.mkdir()
    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=tmp_path / "ws",
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=None,
        )
    )

    result = runner.invoke(app, ["paradesign", "raml", "-w", str(work)])

    assert result.exit_code != 0
    assert "pararepo raml" in result.output


def test_paradesign_faz_upload(cenario, monkeypatch):
    _mock_projeto_ja_publicado(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        exchange, "upload_design_center", lambda nome, pasta: chamadas.append((nome, pasta))
    )

    result = runner.invoke(app, ["paradesign", "raml", "-w", str(cenario["work"])], input="1\n")

    assert result.exit_code == 0, result.output
    assert chamadas == [("pedidos", cenario["raml"])]
    assert "publicardesign" in result.output


def test_paradesign_dry_run_nao_envia(cenario, monkeypatch):
    _mock_projeto_ja_publicado(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        exchange, "upload_design_center", lambda nome, pasta: chamadas.append((nome, pasta))
    )

    result = runner.invoke(
        app, ["paradesign", "raml", "--dry-run", "-w", str(cenario["work"])], input="1\n"
    )

    assert result.exit_code == 0, result.output
    assert chamadas == []


def test_paradesign_recusa_raml_sem_cabecalho(cenario, monkeypatch):
    """Regressao central: RAML mal formado nao pode subir calado."""
    _mock_projeto_ja_publicado(monkeypatch)
    (cenario["raml"] / "api.raml").write_text(
        "# comentario antes do cabecalho\n#%RAML 1.0\ntitle: X\n", encoding="utf-8"
    )
    chamadas = []
    monkeypatch.setattr(
        exchange, "upload_design_center", lambda nome, pasta: chamadas.append((nome, pasta))
    )

    result = runner.invoke(app, ["paradesign", "raml", "-w", str(cenario["work"])], input="1\n")

    assert result.exit_code != 0, result.output
    assert "cabecalho" in result.output.lower() or "#%RAML" in result.output
    assert chamadas == [], "nao pode subir um RAML invalido"


def test_paradesign_nao_falso_positivo_em_includes(cenario, monkeypatch):
    """Fragmento de !include nao tem, e nao deve precisar, do cabecalho."""
    _mock_projeto_ja_publicado(monkeypatch)
    (cenario["raml"] / "api.raml").write_text(
        "#%RAML 1.0\ntitle: X\n/recurso:\n  !include domain/frag.raml\n", encoding="utf-8"
    )
    (cenario["raml"] / "domain").mkdir()
    (cenario["raml"] / "domain" / "frag.raml").write_text(
        "post:\n  displayName: Y\n", encoding="utf-8"
    )
    chamadas = []
    monkeypatch.setattr(
        exchange, "upload_design_center", lambda nome, pasta: chamadas.append((nome, pasta))
    )

    result = runner.invoke(app, ["paradesign", "raml", "-w", str(cenario["work"])], input="1\n")

    assert result.exit_code == 0, result.output
    assert len(chamadas) == 1


# --- publicardesign ---------------------------------------------------------------------


def test_publicardesign_publica_com_o_main_correto(cenario, monkeypatch):
    _mock_projeto_ja_publicado(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        exchange,
        "publicar_exchange",
        lambda nome, *, main, api_version, versao: chamadas.append(
            (nome, main, api_version, versao)
        ),
    )

    result = runner.invoke(
        app, ["publicardesign", "-w", str(cenario["work"])], input="1\n1.1.0\n"
    )

    assert result.exit_code == 0, result.output
    assert chamadas == [("pedidos", "api.raml", "v1", "1.1.0")]
    assert "1.0.0" in result.output, "tem de mostrar a versao publicada atual antes de perguntar"


def test_publicardesign_dry_run_nao_publica(cenario, monkeypatch):
    _mock_projeto_ja_publicado(monkeypatch)
    chamadas = []
    monkeypatch.setattr(
        exchange,
        "publicar_exchange",
        lambda *a, **kw: chamadas.append((a, kw)),
    )

    result = runner.invoke(
        app,
        ["publicardesign", "--dry-run", "-w", str(cenario["work"])],
        input="1\n1.1.0\n",
    )

    assert result.exit_code == 0, result.output
    assert chamadas == []


def test_publicardesign_recusa_raml_sem_cabecalho_no_design_center(cenario, monkeypatch):
    """O que valida e o que esta no Design Center agora, nao a pasta local."""
    monkeypatch.setattr(exchange, "listar_projetos_design_center", lambda: [PROJETO_DC])

    def fake_baixar_projeto_invalido(nome, destino):
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "api.raml").write_text(
            "# defeito\n#%RAML 1.0\ntitle: X\n", encoding="utf-8"
        )
        (destino / "exchange.json").write_text(
            f'{{"groupId": "{GROUP_ID}", "assetId": "pedidos", "main": "api.raml", '
            f'"apiVersion": "v1", "version": "1.0.0"}}',
            encoding="utf-8",
        )
        return destino

    monkeypatch.setattr(exchange, "baixar_projeto_design_center", fake_baixar_projeto_invalido)
    monkeypatch.setattr(
        exchange,
        "listar_versoes_exchange",
        lambda g, a: [
            VersaoExchange(versao="1.0.0", publicado_em=datetime(2026, 8, 22, tzinfo=timezone.utc))
        ],
    )
    chamadas = []
    monkeypatch.setattr(
        exchange, "publicar_exchange", lambda *a, **kw: chamadas.append((a, kw))
    )

    result = runner.invoke(app, ["publicardesign", "-w", str(cenario["work"])], input="1\n")

    assert result.exit_code != 0, result.output
    assert "cabecalho" in result.output.lower() or "#%RAML" in result.output
    assert chamadas == [], "nao pode publicar um RAML invalido"


def test_publicardesign_sem_projeto_nunca_publicado(cenario, monkeypatch):
    """Primeira publicacao: nao ha versao anterior para mostrar, e o comando avisa disso."""
    monkeypatch.setattr(exchange, "listar_projetos_design_center", lambda: [PROJETO_DC])

    def fake_baixar_projeto_sem_exchange_json(nome, destino):
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "api.raml").write_text(RAML_VALIDO, encoding="utf-8")
        return destino  # sem exchange.json: nunca foi publicado

    monkeypatch.setattr(
        exchange, "baixar_projeto_design_center", fake_baixar_projeto_sem_exchange_json
    )

    result = runner.invoke(app, ["publicardesign", "-w", str(cenario["work"])], input="1\n")

    assert result.exit_code != 0, result.output
    assert "paradesign raml" in result.output
