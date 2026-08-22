"""O filtro por texto e a sugestao por semelhanca no menu de projeto do Design Center.

Ver docs/DESIGN-CENTER-CLI.md, "Filtro por texto parcial" e "Decisao: alem do filtro
exato, sugerir por semelhanca quando nao achar nada" — motivado por orgs com muitos
projetos, onde listar tudo sem filtro nao escala.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from typer.testing import CliRunner

from mule_bridge import config, exchange
from mule_bridge.cli import app
from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.exchange import ProjetoDesignCenter, VersaoExchange

runner = CliRunner()

GROUP_ID = "grupo-org-teste"
RAML_VALIDO = "#%RAML 1.0\ntitle: Pedidos\n"

PROJETOS = [
    ProjetoDesignCenter(id="p1", nome="pagamentos", modificado_em=datetime(2026, 8, 22, tzinfo=timezone.utc)),
    ProjetoDesignCenter(id="p2", nome="teste-ponte", modificado_em=datetime(2026, 8, 22, tzinfo=timezone.utc)),
    ProjetoDesignCenter(id="p3", nome="outro-projeto", modificado_em=datetime(2026, 8, 22, tzinfo=timezone.utc)),
]


@pytest.fixture
def cenario(tmp_path, monkeypatch):
    work = tmp_path / "repo"
    raml = work / "pedidos-raml"
    raml.mkdir(parents=True)
    (raml / "api.raml").write_text(RAML_VALIDO, encoding="utf-8")
    (raml / "exchange.json").write_text(
        f'{{"groupId": "{GROUP_ID}", "assetId": "pagamentos", "main": "api.raml", '
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

    monkeypatch.setattr(exchange, "listar_projetos_design_center", lambda: PROJETOS)

    def fake_baixar_projeto(nome, destino):
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "exchange.json").write_text(
            f'{{"groupId": "{GROUP_ID}", "assetId": "{nome}", "main": "api.raml", '
            f'"apiVersion": "v1", "version": "1.0.0"}}',
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
    chamadas = []
    monkeypatch.setattr(
        exchange, "upload_design_center", lambda nome, pasta: chamadas.append(nome)
    )
    return {"work": work, "chamadas": chamadas}


def test_enter_vazio_mostra_todos_os_projetos(cenario):
    """Sem filtro, a lista completa aparece — comportamento de antes preservado."""
    result = runner.invoke(
        app, ["paradesign", "raml", "-w", str(cenario["work"])], input="\n2\n"
    )

    assert result.exit_code == 0, result.output
    assert cenario["chamadas"] == ["teste-ponte"]
    assert "pagamentos" in result.output and "outro-projeto" in result.output


def test_filtro_por_substring_reduz_a_lista(cenario):
    """Um trecho que bate em um so projeto filtra a lista antes de perguntar."""
    result = runner.invoke(
        app, ["paradesign", "raml", "-w", str(cenario["work"])], input="pag\n1\n"
    )

    assert result.exit_code == 0, result.output
    assert cenario["chamadas"] == ["pagamentos"]


def test_filtro_sem_correspondencia_e_sem_semelhanca_e_erro(cenario):
    """Nada bate por substring, e nada e parecido o bastante: erro claro, sem adivinhar."""
    result = runner.invoke(
        app, ["paradesign", "raml", "-w", str(cenario["work"])], input="zzz-nada-a-ver\n"
    )

    assert result.exit_code != 0, result.output
    assert cenario["chamadas"] == []
    assert "Nenhum projeto" in result.output


def test_typo_sugere_por_semelhanca_e_pede_confirmacao(cenario):
    """Erro de digitacao comum (letras trocadas) nao bate por substring, mas e sugerido."""
    # "tset-ponte" nao contem "teste-ponte" como substring, mas e bem parecido.
    result = runner.invoke(
        app,
        ["paradesign", "raml", "-w", str(cenario["work"])],
        input="tset-ponte\n1\n",  # 1 = "sim, e esse" na confirmacao da sugestao
    )

    assert result.exit_code == 0, result.output
    assert "Voce quis dizer teste-ponte" in result.output
    assert cenario["chamadas"] == ["teste-ponte"]


def test_recusar_a_sugestao_deixa_digitar_de_novo(cenario):
    """Nunca autocompleta sozinho: recusar a sugestao volta a pedir o filtro."""
    result = runner.invoke(
        app,
        ["paradesign", "raml", "-w", str(cenario["work"])],
        # digita o typo, recusa a sugestao (2), digita de novo certo, escolhe o unico.
        input="tset-ponte\n2\nteste-ponte\n1\n",
    )

    assert result.exit_code == 0, result.output
    assert cenario["chamadas"] == ["teste-ponte"]


def test_filtro_e_case_insensitive(cenario):
    result = runner.invoke(
        app, ["paradesign", "raml", "-w", str(cenario["work"])], input="TESTE-PONTE\n1\n"
    )

    assert result.exit_code == 0, result.output
    assert cenario["chamadas"] == ["teste-ponte"]
