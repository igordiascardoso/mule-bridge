"""Chamadas a anypoint-cli-v4: tudo mockado, nunca bate em rede/credencial de verdade."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from mule_bridge import exchange
from mule_bridge.exchange import ExchangeError


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


@pytest.fixture(autouse=True)
def _sem_cli_de_verdade(monkeypatch):
    """Garante que nenhum teste chame o subprocess real por engano."""
    monkeypatch.setattr(exchange.shutil, "which", lambda _cmd: "anypoint-cli-v4")


def _mock_run(monkeypatch, resultado_por_chamada):
    """`resultado_por_chamada`: lista de _Proc, uma por chamada, na ordem esperada."""
    chamadas = []

    def fake_run(args, **kwargs):
        chamadas.append(args)
        return resultado_por_chamada[len(chamadas) - 1]

    monkeypatch.setattr(exchange.subprocess, "run", fake_run)
    return chamadas


def test_listar_projetos_design_center(monkeypatch):
    dados = [
        {
            "id": "abc-1",
            "name": "teste-ponte",
            "lastUpdatedDate": "2026-08-22T16:40:27.181+00:00",
        },
        {"id": "abc-2", "name": "outro-projeto", "lastUpdatedDate": None},
    ]
    chamadas = _mock_run(monkeypatch, [_Proc(stdout=json.dumps(dados))])

    projetos = exchange.listar_projetos_design_center()

    assert [p.nome for p in projetos] == ["teste-ponte", "outro-projeto"]
    assert projetos[0].modificado_em is not None
    assert projetos[1].modificado_em is None
    assert "designcenter" in chamadas[0]
    assert "list" in chamadas[0]


def test_listar_versoes_exchange_filtra_por_asset_id_e_tipo(monkeypatch):
    """O `mule-plugin-*` (extension) e outro assetId nao podem aparecer na lista."""
    dados = [
        {
            "assetId": "teste-ponte",
            "type": "rest-api",
            "version": "1.4.0",
            "createdDate": "2026-08-22T16:40:21.232Z",
        },
        {
            "assetId": "mule-plugin-teste-ponte",
            "type": "extension",
            "version": "1.3.0",
            "createdDate": "2026-08-22T16:29:39.737Z",
        },
        {
            "assetId": "teste-ponte",
            "type": "rest-api",
            "version": "1.3.0",
            "createdDate": "2026-08-22T16:29:35.730Z",
        },
        {
            "assetId": "outro-asset",
            "type": "rest-api",
            "version": "9.9.9",
            "createdDate": "2026-08-22T16:29:35.730Z",
        },
    ]
    _mock_run(monkeypatch, [_Proc(stdout=json.dumps(dados))])

    versoes = exchange.listar_versoes_exchange("grupo-x", "teste-ponte")

    assert [v.versao for v in versoes] == ["1.4.0", "1.3.0"]


def test_listar_versoes_exchange_vazio_quando_nunca_publicado(monkeypatch):
    _mock_run(monkeypatch, [_Proc(stdout="[]")])

    assert exchange.listar_versoes_exchange("grupo-x", "nunca-publicado") == []


def test_em_brasilia_converte_utc(monkeypatch):
    dt = exchange._parse_data("2026-08-22T16:40:21.232Z")
    assert exchange.em_brasilia(dt) == "22/08 13:40"


def test_em_brasilia_sem_data():
    assert exchange.em_brasilia(None) == "data desconhecida"


def test_ler_exchange_json(tmp_path):
    pasta = tmp_path / "projeto"
    pasta.mkdir()
    (pasta / "exchange.json").write_text(
        json.dumps({"assetId": "x", "groupId": "g"}), encoding="utf-8"
    )

    assert exchange.ler_exchange_json(pasta) == {"assetId": "x", "groupId": "g"}


def test_ler_exchange_json_ausente(tmp_path):
    with pytest.raises(ExchangeError, match="exchange.json"):
        exchange.ler_exchange_json(tmp_path / "sem-nada")


def test_baixar_versao_exchange_extrai_e_remove_o_zip(monkeypatch, tmp_path):
    destino = tmp_path / "destino"
    destino.mkdir()

    def fake_run(args, **kwargs):
        # Simula o efeito real do comando: grava um .zip de nome-hash em `destino`.
        zip_path = destino / "hash-imprevisivel.zip"
        with zipfile.ZipFile(zip_path, "w") as z:
            z.writestr("api.raml", "#%RAML 1.0\ntitle: X\n")
            z.writestr("exchange.json", "{}")
        return _Proc(stdout="Asset downloaded")

    monkeypatch.setattr(exchange.subprocess, "run", fake_run)

    resultado = exchange.baixar_versao_exchange("grupo", "asset", "1.0.0", destino)

    assert resultado == destino
    assert (destino / "api.raml").is_file()
    assert not list(destino.glob("*.zip")), "o zip baixado deve ser removido apos extrair"


def test_baixar_versao_exchange_sem_zip_e_erro(monkeypatch, tmp_path):
    destino = tmp_path / "destino"
    destino.mkdir()
    monkeypatch.setattr(exchange.subprocess, "run", lambda args, **kw: _Proc(stdout="ok"))

    with pytest.raises(ExchangeError, match="nao criou um .zip"):
        exchange.baixar_versao_exchange("grupo", "asset", "1.0.0", destino)


def test_upload_design_center_chama_a_cli_certa(monkeypatch, tmp_path):
    chamadas = _mock_run(monkeypatch, [_Proc()])

    exchange.upload_design_center("meu-projeto", tmp_path)

    assert chamadas[0][1:4] == ["designcenter", "project", "upload"]
    assert "meu-projeto" in chamadas[0]
    assert str(tmp_path) in chamadas[0]


def test_publicar_exchange_sempre_passa_main_explicito(monkeypatch):
    """Regressao: publicar sem --main publica o placeholder em silencio (ver doc)."""
    chamadas = _mock_run(monkeypatch, [_Proc()])

    exchange.publicar_exchange(
        "meu-projeto", main="api.raml", api_version="v1", versao="1.0.0"
    )

    assert "--main" in chamadas[0]
    assert chamadas[0][chamadas[0].index("--main") + 1] == "api.raml"


def test_run_traduz_403_em_mensagem_de_escopo(monkeypatch):
    _mock_run(
        monkeypatch,
        [_Proc(returncode=1, stderr="Error: Forbidden — status 403")],
    )

    with pytest.raises(ExchangeError, match="escopo"):
        exchange.listar_projetos_design_center()


def test_run_cli_nao_encontrada(monkeypatch):
    def fake_run(args, **kwargs):
        raise FileNotFoundError()

    monkeypatch.setattr(exchange.subprocess, "run", fake_run)

    with pytest.raises(ExchangeError, match="npm install"):
        exchange.listar_projetos_design_center()


def test_run_erro_generico_mostra_ultima_linha(monkeypatch):
    _mock_run(
        monkeypatch,
        [_Proc(returncode=1, stderr="linha 1\nCannot parse document with specified vendor.")],
    )

    with pytest.raises(ExchangeError, match="Cannot parse document"):
        exchange.listar_projetos_design_center()
