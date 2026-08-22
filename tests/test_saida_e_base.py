"""Duas regressoes observadas em projeto real, cada uma com o seu caso minimo.

A saida: o conteudo do usuario pode ter qualquer caractere, e mostra-lo nao pode derrubar
o comando. A base do merge: ela vem da pasta, nunca do `pom.xml`, que fica atrasado.
"""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mule_bridge import cli, config, exchange
from mule_bridge.cli import app
from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.exchange import ProjetoDesignCenter, VersaoExchange

runner = CliRunner()

GROUP_ID = "grupo-org-teste"

#: Caracteres fora do cp1252 achados em codigo Mule de verdade: a seta de um comentario de
#: regra de negocio, e a moldura de um bloco de separacao.
SETA = "→"
MOLDURA = "═"

POM = """<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <artifactId>pedidos-api</artifactId>
  <dependencies>
    <dependency>
      <groupId>grupo</groupId>
      <artifactId>pedidos</artifactId>
      <version>{versao}</version>
      <classifier>raml</classifier>
      <type>zip</type>
    </dependency>
  </dependencies>
</project>
"""


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.safecrlf=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


# --- A base do merge vem da pasta, nao do pom -----------------------------------------


@pytest.fixture
def tres_versoes(tmp_path, monkeypatch):
    """Exchange mockado com 1.1.52, 1.1.53 e 1.1.54, cada uma mexendo num arquivo.

    A pasta local fica na 1.1.52 (lido do `exchange.json` de dentro dela) e a escolha do
    menu de versao vai direto para a 1.1.54 — o salto que aparece quando se pula versao.
    """
    work, studio = tmp_path / "repo", tmp_path / "ws"

    api = work / "pedidos-api" / "src" / "main" / "mule"
    api.mkdir(parents=True)
    (work / "pedidos-api" / "pom.xml").write_text(POM.format(versao="1.1.54"), encoding="utf-8")
    (studio / "studio-pedidos" / "src" / "main" / "mule").mkdir(parents=True)
    (studio / "studio-pedidos" / "pom.xml").write_text(
        POM.format(versao="1.1.54"), encoding="utf-8"
    )

    conteudo_por_versao = {
        "1.1.52": {"api.raml": "#%RAML 1.0\ntitle: Pedidos\n", "tipos.raml": "T: v52\n"},
        "1.1.53": {"api.raml": "#%RAML 1.0\ntitle: Pedidos\n", "tipos.raml": "T: v53\n"},
        "1.1.54": {"api.raml": "#%RAML 1.0\ntitle: Pedidos\n", "tipos.raml": "T: v54\n"},
    }
    projeto_dc = ProjetoDesignCenter(
        id="proj-1", nome="pedidos", modificado_em=datetime(2026, 8, 22, tzinfo=timezone.utc)
    )
    monkeypatch.setattr(exchange, "listar_projetos_design_center", lambda: [projeto_dc])

    def fake_baixar_projeto(nome, destino):
        destino.mkdir(parents=True, exist_ok=True)
        (destino / "exchange.json").write_text(
            f'{{"groupId": "{GROUP_ID}", "assetId": "pedidos", "main": "api.raml", '
            f'"apiVersion": "v1", "version": "1.1.54"}}',
            encoding="utf-8",
        )
        return destino

    monkeypatch.setattr(exchange, "baixar_projeto_design_center", fake_baixar_projeto)
    monkeypatch.setattr(
        exchange,
        "listar_versoes_exchange",
        lambda g, a: [
            VersaoExchange(versao=v, publicado_em=datetime(2026, 8, 22, tzinfo=timezone.utc))
            for v in sorted(conteudo_por_versao, reverse=True)
        ],
    )

    def fake_baixar_versao(group_id, asset_id, versao, destino):
        destino.mkdir(parents=True, exist_ok=True)
        for rel, texto in conteudo_por_versao[versao].items():
            (destino / rel).write_text(texto, encoding="utf-8")
        return destino

    monkeypatch.setattr(exchange, "baixar_versao_exchange", fake_baixar_versao)

    # A pasta local fica na 1.1.52, com o exchange.json dizendo essa versao — e dele que
    # `versao_da_pasta` le a base, nunca do pom (que aqui aponta para a 1.1.54).
    pasta_raml = work / "pedidos-raml"
    fake_baixar_versao(GROUP_ID, "pedidos", "1.1.52", pasta_raml)
    (pasta_raml / "exchange.json").write_text(
        f'{{"groupId": "{GROUP_ID}", "assetId": "pedidos", "main": "api.raml", '
        f'"apiVersion": "v1", "version": "1.1.52"}}',
        encoding="utf-8",
    )

    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=studio,
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=ProjectPair("pedidos-raml", None),
        )
    )
    _git(work, "init", "-q")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base 1.1.52")
    return {"work": work}


def test_a_base_do_merge_e_a_versao_da_pasta_e_nao_a_do_pom(tres_versoes):
    """Pasta na 1.1.52 com o pom na 1.1.54: o merge parte da 1.1.52.

    Regressao com conflito falso: partindo do pom, tudo que mudou entre a versao da pasta
    e a do pom entrava no merge como se fosse edicao do usuario. Num projeto real, pasta na
    1.1.52 com o pom na 1.1.54 rendia tres conflitos em arquivos nunca abertos — exatamente
    os tres que mudaram entre as duas versoes.
    """
    work = tres_versoes["work"]

    # 1 = unico projeto do Design Center; 1 = mais atual (1.1.54) no menu de versoes.
    result = runner.invoke(app, ["pararepo", "raml", "-w", str(work)], input="1\n1\n")

    assert "1.1.52 -> 1.1.54" in result.output, (
        f"a base deveria ser a da pasta (1.1.52), nao a do pom (1.1.54):\n{result.output}"
    )
    assert result.exit_code == 0, f"nao devia haver conflito a resolver:\n{result.output}"
    assert (work / "pedidos-raml" / "tipos.raml").read_text(encoding="utf-8") == "T: v54\n", (
        "o arquivo que so o Exchange mexeu devia chegar sem perguntar nada"
    )


def test_edicao_local_sobrevive_ao_salto_de_versao(tres_versoes):
    """Pular versoes preserva o que e do usuario, sem inventar conflito no resto."""
    work = tres_versoes["work"]
    meu = work / "pedidos-raml" / "api.raml"
    meu.write_text(meu.read_text(encoding="utf-8") + "\n/meu-endpoint:\n  get:\n", encoding="utf-8")

    result = runner.invoke(app, ["pararepo", "raml", "-w", str(work)], input="1\n1\n")

    assert result.exit_code == 0, f"a minha edicao nao colide com nada:\n{result.output}"
    assert "/meu-endpoint" in meu.read_text(encoding="utf-8"), "a edicao local foi perdida"


# --- A saida aceita o que o projeto tem dentro ----------------------------------------


@pytest.fixture
def conflito_com_caractere(tmp_path, monkeypatch):
    """Um conflito de mesma linha num arquivo que contem `→` e `═`."""
    work, studio = tmp_path / "repo", tmp_path / "ws"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "casa"))

    fonte = work / "pedidos-api" / "src" / "main" / "mule"
    fonte.mkdir(parents=True)
    (work / "pedidos-api" / "pom.xml").write_text(POM.format(versao="1.1.54"), encoding="utf-8")
    destino = studio / "studio-pedidos" / "src" / "main" / "mule"
    destino.mkdir(parents=True)
    (studio / "studio-pedidos" / "pom.xml").write_text(
        POM.format(versao="1.1.54"), encoding="utf-8"
    )

    # O caractere fica longe da linha do conflito, de proposito: para mostrar o arquivo o
    # comando imprime tudo, e era ao chegar nele que a saida caia.
    comum = (
        f"<mule>\n"
        f"    <!-- SUCATA {SETA} lote existente; CONSERVADO {SETA} sempre novo -->\n"
        f"    <!-- {MOLDURA * 20} -->\n"
    )
    (fonte / "servico.xml").write_text(
        comum + '    <logger name="base"/>\n</mule>\n', encoding="utf-8"
    )
    (destino / "servico.xml").write_text(
        comum + '    <logger name="studio"/>\n</mule>\n', encoding="utf-8"
    )
    _git(work, "init", "-q")

    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=studio,
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=None,
        )
    )
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")
    # Agora a minha versao divergindo da base, na MESMA linha que o Studio mexeu.
    (fonte / "servico.xml").write_text(
        comum + '    <logger name="meu"/>\n</mule>\n', encoding="utf-8"
    )
    return {"work": work, "arquivo": fonte / "servico.xml"}


def test_um_stream_cp1252_passa_a_aceitar_o_que_o_projeto_tem_dentro(tmp_path):
    """Depois do `_aceitar_utf8`, escrever `→` num stream cp1252 nao levanta mais nada.

    Regressao: no Windows a saida redirecionada vem em cp1252, que nao tem `→` nem `═`, e
    imprimir um arquivo em conflito que os contenha levantava `UnicodeEncodeError` dentro
    do `_mostrar_conflito` — o conflito ficava sem como ser resolvido, no CI e no agente de
    IA, onde a saida nunca e o terminal.

    O teste vai direto ao stream porque o `CliRunner` captura a saida em UTF-8 por conta
    propria: sob ele o defeito nunca aparece, e um teste que passasse pela CLI passaria
    igual com e sem a correcao.
    """
    alvo = tmp_path / "saida.txt"

    with alvo.open("w", encoding="cp1252") as stream:
        with pytest.raises(UnicodeEncodeError):
            stream.write(f"SUCATA {SETA} lote\n")

        cli._aceitar_utf8(stream)
        stream.write(f"SUCATA {SETA} lote {MOLDURA * 3}\n")

    escrito = alvo.read_text(encoding="utf-8")
    assert SETA in escrito and MOLDURA in escrito, f"a saida perdeu os caracteres: {escrito!r}"


def test_aceitar_utf8_nao_reclama_de_stream_sem_reconfigure():
    """O buffer de teste do CliRunner nao tem `reconfigure` — e isso nao pode ser erro."""

    class SemReconfigure:
        pass

    cli._aceitar_utf8(SemReconfigure())  # nao levanta


def test_o_caractere_do_arquivo_fica_intacto_apos_o_merge(conflito_com_caractere):
    """Aceitar UTF-8 na saida nao muda o que se grava: o arquivo mantem os caracteres."""
    arquivo = conflito_com_caractere["arquivo"]
    antes = arquivo.read_text(encoding="utf-8")

    runner.invoke(
        app, ["pararepo", "api", "-w", str(conflito_com_caractere["work"])], input="1\n"
    )

    depois = arquivo.read_text(encoding="utf-8")
    assert depois.count(SETA) == antes.count(SETA) == 2, "as setas do arquivo mudaram"
    assert depois.count(MOLDURA) == antes.count(MOLDURA), "a moldura do arquivo mudou"
