"""Casos de borda que degradam em silencio: encoding, fim de linha, volume, nomes.

Sao os erros que nao levantam excecao. Um BOM comido, um CRLF virado LF, um acento
convertido para `?` — nada disso quebra o comando, mas suja o diff do usuario com centenas
de linhas que ele nao mexeu, ou pior, corrompe a especificacao. No Windows isso e a fonte
mais comum de "mudou o arquivo inteiro e eu nao toquei nele".
"""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from mule_bridge import reconcile
from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.sync import Direction, sync_all

POM_MIN = (
    '<?xml version="1.0"?>'
    '<project xmlns="http://maven.apache.org/POM/4.0.0">'
    "<artifactId>a</artifactId></project>"
)

#: Uma base com pontos de insercao separados, para exercitar encoding sem cair no
#: conflito de anexacao simultanea (que ja e coberto em test_cenarios_conflito).
BASE_ACENTOS = "﻿#%RAML 1.0\ntitle: Leilão\nversion: v1\ntypes:\n  Meu:\n  Deles:\n  Fim:\n"


@pytest.fixture
def tres(tmp_path):
    """As tres pontas em pastas separadas."""
    pastas = {k: tmp_path / k for k in ("local", "base", "novo")}
    for p in pastas.values():
        p.mkdir()
    return pastas


def _por(tres, rel: str, meu: str, base: str, novo: str):
    (tres["local"] / rel).write_text(meu, encoding="utf-8")
    (tres["base"] / rel).write_text(base, encoding="utf-8")
    (tres["novo"] / rel).write_text(novo, encoding="utf-8")
    return reconcile.reconciliar(tres["local"], tres["base"], tres["novo"], "1", "2")


# --- Encoding -------------------------------------------------------------------


def test_bom_e_acentos_sobrevivem_a_reconciliacao(tres):
    """RAML com BOM e portugues acentuado: nada pode ser reescrito por acidente."""
    meu = BASE_ACENTOS.replace("  Meu:\n", "  Meu:\n    nota: coração\n")
    novo = BASE_ACENTOS.replace("  Deles:\n", "  Deles:\n    desc: Notificação\n")

    r = _por(tres, "a.raml", meu, BASE_ACENTOS, novo)
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "a.raml").read_text(encoding="utf-8")

    assert r.limpo
    assert final.startswith("﻿"), "o BOM foi comido"
    assert "Leilão" in final, "acento do titulo corrompido"
    assert "coração" in final, "acento da minha edicao corrompido"
    assert "Notificação" in final, "acento da versao nova corrompido"


def test_crlf_atravessa_o_sync_byte_a_byte(tmp_path):
    """Se o sync normalizar fim de linha, o proximo git diff mostra o arquivo inteiro."""
    work, studio = tmp_path / "w", tmp_path / "s"
    (work / "api" / "src" / "main" / "mule").mkdir(parents=True)
    (studio / "sapi" / "src" / "main" / "mule").mkdir(parents=True)
    (work / "api" / "pom.xml").write_text(POM_MIN, encoding="utf-8")
    (studio / "sapi" / "pom.xml").write_text(POM_MIN, encoding="utf-8")

    bruto = b'<mule>\r\n  <flow name="a"/>\r\n</mule>\r\n'
    (work / "api" / "src" / "main" / "mule" / "a.xml").write_bytes(bruto)

    cfg = BridgeConfig(
        work_root=work, studio_root=studio, api=ProjectPair("api", "sapi"), raml=None
    )
    sync_all(cfg, Direction.PUSH, only="api")

    destino = studio / "sapi" / "src" / "main" / "mule" / "a.xml"
    assert destino.read_bytes() == bruto, "o fim de linha foi normalizado"


def test_arquivo_com_byte_invalido_nao_derruba_o_comando(tres):
    """Um arquivo mal codificado no meio da pasta nao pode abortar a operacao toda."""
    (tres["base"] / "ok.raml").write_text("a: 1\nfim: x\n", encoding="utf-8")
    (tres["local"] / "ok.raml").write_text("a: 1\nfim: x\nmeu: 2\n", encoding="utf-8")
    (tres["novo"] / "ok.raml").write_text("a: 1\nnovo: 3\nfim: x\n", encoding="utf-8")
    for p in tres.values():
        (p / "quebrado.raml").write_bytes(b"titulo: \xff\xfe invalido\n")

    r = reconcile.reconciliar(tres["local"], tres["base"], tres["novo"], "1", "2")
    reconcile.aplicar(r, tres["local"])

    assert "novo: 3" in (tres["local"] / "ok.raml").read_text(encoding="utf-8")


# --- Nomes de arquivo -----------------------------------------------------------


def test_nome_com_espaco_e_acento(tres):
    """`tipo de dados ção.raml` — nome que quebra quem monta comando por string."""
    rel = "tipo de dados ção.raml"
    r = _por(tres, rel, "a: 1\nfim: x\nmeu: 1\n", "a: 1\nfim: x\n", "a: 1\nnovo: 2\nfim: x\n")
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / rel).read_text(encoding="utf-8")

    assert r.limpo
    assert "novo: 2" in final and "meu: 1" in final


def test_subpasta_profunda_com_acento(tres):
    """Caminho aninhado com acento, criado pela aplicacao."""
    rel = "domínio/sub/atenção.raml"
    (tres["novo"] / rel).parent.mkdir(parents=True)
    (tres["novo"] / rel).write_text("novo: 1\n", encoding="utf-8")

    r = reconcile.reconciliar(tres["local"], tres["base"], tres["novo"], "1", "2")
    reconcile.aplicar(r, tres["local"])

    assert (tres["local"] / rel).is_file()


# --- Volume e vazio -------------------------------------------------------------


def test_arquivo_de_milhoes_de_linhas_e_rapido(tres):
    """Um RAML gigante nao pode fazer o comando parecer travado."""
    corpo = "linha\n" * 200_000
    inicio = time.monotonic()
    r = _por(tres, "b.raml", "meu: 1\n" + corpo, corpo, corpo + "nova\n")
    decorrido = time.monotonic() - inicio

    assert r.limpo
    assert decorrido < 30, f"reconciliacao de 200k linhas levou {decorrido:.1f}s"


def test_pastas_vazias_nao_quebram(tres):
    """Nada de um lado, nada do outro: resultado vazio, sem excecao."""
    r = reconcile.reconciliar(tres["local"], tres["base"], tres["novo"], "1", "2")

    assert r.limpo
    assert r.total_mudancas == 0
    assert reconcile.aplicar(r, tres["local"]) == 0


def test_arquivo_vazio_dos_dois_lados(tres):
    """Arquivo de zero byte e um caso valido, nao uma ausencia."""
    r = _por(tres, "vazio.raml", "", "", "")

    assert r.limpo
    assert "vazio.raml" in r.inalterados


def test_arquivo_que_o_exchange_esvaziou(tres):
    """Eles zeraram o conteudo e eu nao mexi: o esvaziamento e a mudanca."""
    r = _por(tres, "a.raml", "a: 1\n", "a: 1\n", "")

    reconcile.aplicar(r, tres["local"])
    assert (tres["local"] / "a.raml").read_text(encoding="utf-8") == ""


# --- Idempotencia ---------------------------------------------------------------


def test_aplicar_duas_vezes_nao_escreve_de_novo(tres):
    """A segunda aplicacao tem de contar zero: `_gravar` compara antes de escrever."""
    r = _por(tres, "a.raml", "a: 1\nfim: x\nmeu: 1\n", "a: 1\nfim: x\n", "a: 1\nnovo: 2\nfim: x\n")

    primeira = reconcile.aplicar(r, tres["local"])
    segunda = reconcile.aplicar(r, tres["local"])

    assert primeira == 1
    assert segunda == 0, "reescrever igual sujaria o mtime e o diff do editor"


def test_mtime_nao_muda_quando_o_conteudo_e_igual(tres):
    """O Studio observa o disco: um write inutil dispara redeploy sem motivo."""
    r = _por(tres, "a.raml", "a: 1\nfim: x\nmeu: 1\n", "a: 1\nfim: x\n", "a: 1\nnovo: 2\nfim: x\n")
    reconcile.aplicar(r, tres["local"])
    alvo = Path(tres["local"] / "a.raml")
    antes = alvo.stat().st_mtime_ns

    reconcile.aplicar(r, tres["local"])

    assert alvo.stat().st_mtime_ns == antes
