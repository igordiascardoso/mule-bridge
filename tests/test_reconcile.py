"""Reconciliacao do RAML: base do Exchange + edicoes locais por cima."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mule_bridge import reconcile
from mule_bridge.reconcile import ReconcileError

BASE = """#%RAML 1.0
title: Leilao
types:
  Leilao:
    properties:
      id: integer
      placa:
        type: string
        description: Placa do veiculo
"""


def _escreve(pasta: Path, arquivos: dict[str, str]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    for rel, conteudo in arquivos.items():
        p = pasta / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo, encoding="utf-8")
    return pasta


@pytest.fixture
def dirs(tmp_path):
    return {
        "local": tmp_path / "leilao-raml",
        "base": tmp_path / "base",
        "novo": tmp_path / "novo",
    }


def _reconciliar(dirs):
    return reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1.1.54", "1.1.55")


# --- Caso 1: adicoes em pontos diferentes, o git junta sozinho -------------------


def test_adicoes_em_pontos_diferentes_juntam_sem_conflito(dirs):
    meu = BASE + "  Lance:\n    properties:\n      valor: number\n"
    novo = "#%RAML 1.0\ntitle: Leilao (Exchange)\n" + BASE.split("\n", 2)[2]

    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)

    assert r.limpo, [c.caminho for c in r.conflitos]
    final = r.resultado["api.raml"]
    assert "Lance:" in final, "a edicao local tem de sobreviver"
    assert "Leilao (Exchange)" in final, "a mudanca de fora tem de entrar"


def test_endpoint_novo_do_exchange_entra(dirs):
    _escreve(dirs["local"], {"api.raml": BASE})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE, "captcha.raml": "#%RAML 1.0\ntitle: Captcha\n"})

    r = _reconciliar(dirs)

    assert r.limpo
    assert "captcha.raml" in r.so_deles
    assert "Captcha" in r.resultado["captcha.raml"]


def test_arquivo_so_meu_permanece(dirs):
    _escreve(dirs["local"], {"api.raml": BASE, "meu-tipo.raml": "#%RAML 1.0\ntitle: Meu\n"})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE})

    r = _reconciliar(dirs)

    assert r.limpo
    assert "meu-tipo.raml" in r.so_meus
    assert r.resultado["meu-tipo.raml"] == "#%RAML 1.0\ntitle: Meu\n"


def test_edicao_local_sem_mudanca_de_fora_permanece(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE})

    r = _reconciliar(dirs)

    assert r.limpo
    assert "Mercosul" in r.resultado["api.raml"]


# --- Caso 3: os dois mudaram a mesma linha -> conflito, nada e escrito -----------


def test_mesma_linha_alterada_nos_dois_lados_vira_conflito(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    novo = BASE.replace("Placa do veiculo", "Placa (obrigatorio)")

    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)

    assert not r.limpo
    c = r.conflitos[0]
    assert c.caminho == "api.raml"
    assert "Mercosul" in c.meu and "obrigatorio" in c.novo
    assert "Placa do veiculo" in c.base, "a base precisa ir junto para dar contexto"


def test_conflito_pendente_impede_a_escrita(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    novo = BASE.replace("Placa do veiculo", "Placa (obrigatorio)")
    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)

    with pytest.raises(ReconcileError, match="sem resolucao"):
        reconcile.aplicar(r, dirs["local"])

    assert "Mercosul" in (dirs["local"] / "api.raml").read_text(encoding="utf-8"), (
        "a pasta do usuario nao pode ser tocada enquanto ha conflito"
    )


def test_conflito_resolvido_e_aplicado(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    novo = BASE.replace("Placa do veiculo", "Placa (obrigatorio)")
    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)
    combinado = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul (obrigatorio)")
    escritos = reconcile.aplicar(r, dirs["local"], resolucoes={"api.raml": combinado})

    assert escritos == 1
    final = (dirs["local"] / "api.raml").read_text(encoding="utf-8")
    assert "Mercosul (obrigatorio)" in final


def test_aplicar_escreve_o_que_veio_de_fora(dirs):
    _escreve(dirs["local"], {"api.raml": BASE})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE, "captcha.raml": "#%RAML 1.0\ntitle: Captcha\n"})

    r = _reconciliar(dirs)
    escritos = reconcile.aplicar(r, dirs["local"])

    assert escritos == 1
    assert (dirs["local"] / "captcha.raml").is_file()


def test_exchange_json_e_ignorado(dirs):
    _escreve(dirs["local"], {"api.raml": BASE, "exchange.json": '{"version":"1.1.54"}'})
    _escreve(dirs["base"], {"api.raml": BASE, "exchange.json": '{"version":"1.1.54"}'})
    _escreve(dirs["novo"], {"api.raml": BASE, "exchange.json": '{"version":"1.1.55"}'})

    r = _reconciliar(dirs)

    assert "exchange.json" not in r.resultado
    assert r.limpo


# --- cache do Maven -------------------------------------------------------------


def _zip_raml(destino: Path, arquivos: dict[str, str]) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as z:
        for rel, conteudo in arquivos.items():
            z.writestr(rel, conteudo)
    return destino


def test_preparar_le_as_duas_versoes_do_cache(tmp_path):
    m2 = tmp_path / "m2"
    _zip_raml(reconcile.caminho_no_cache("g", "leilao", "1.1.54", m2), {"api.raml": BASE})
    _zip_raml(
        reconcile.caminho_no_cache("g", "leilao", "1.1.55", m2),
        {"api.raml": BASE, "captcha.raml": "#%RAML 1.0\ntitle: Captcha\n"},
    )
    local = _escreve(tmp_path / "leilao-raml", {"api.raml": BASE})

    r = reconcile.preparar(local, "g", "leilao", "1.1.54", "1.1.55", m2=m2)

    assert r.limpo
    assert "captcha.raml" in r.so_deles


def test_versao_ausente_no_cache_orienta(tmp_path):
    m2 = tmp_path / "m2"
    local = _escreve(tmp_path / "leilao-raml", {"api.raml": BASE})

    with pytest.raises(ReconcileError, match="Studio"):
        reconcile.preparar(local, "g", "leilao", "1.1.54", "1.1.99", m2=m2)


def test_versoes_ordenadas_numericamente(tmp_path):
    m2 = tmp_path / "m2"
    for v in ("1.1.9", "1.1.10", "1.1.54"):
        _zip_raml(reconcile.caminho_no_cache("g", "leilao", v, m2), {"api.raml": BASE})

    assert reconcile.versoes_no_cache("g", "leilao", m2) == ["1.1.9", "1.1.10", "1.1.54"]


def test_mais_novas_que_ignora_versoes_antigas():
    todas = ["1.1.52", "1.1.53", "1.1.54", "1.1.55"]

    assert reconcile.mais_novas_que(todas, "1.1.54") == ["1.1.55"]
    assert reconcile.mais_novas_que(todas, "1.1.55") == []
    assert reconcile.mais_novas_que(todas, "1.1.52") == ["1.1.53", "1.1.54", "1.1.55"]


def test_mais_novas_que_compara_numericamente():
    """1.1.9 e anterior a 1.1.10, ainda que a ordem alfabetica diga o contrario."""
    assert reconcile.mais_novas_que(["1.1.9", "1.1.10"], "1.1.9") == ["1.1.10"]
    assert reconcile.mais_novas_que(["1.1.9", "1.1.10"], "1.1.10") == []
