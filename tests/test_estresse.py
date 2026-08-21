"""Estresse: centenas de merges combinatorios, validando a ESTRUTURA do resultado.

Os outros arquivos testam cenarios escolhidos a dedo. Este gera combinacoes em volume e
verifica o que nenhum `assert "texto" in final` pega: se o arquivo resultante **continua
sendo XML/YAML valido**. Um merge que produz XML quebrado nao levanta erro nenhum na
ferramenta — quebra depois, no deploy do Studio, longe da causa.

Tres verificacoes por resultado:

    1. parseia (ElementTree para XML, yaml.load para RAML)
    2. nao contem marcador de merge
    3. as duas intencoes estao presentes — nada foi perdido em silencio

E a cascata: aplicar merges em sequencia, cada um sobre o resultado do anterior, para
garantir que o arquivo nao degrada ao longo de varias versoes do Exchange.
"""

from __future__ import annotations

import itertools
from pathlib import Path
from xml.etree import ElementTree

import pytest
from conftest_codigo import MULE_BASE, RAML_BASE

from mule_bridge import reconcile

yaml = pytest.importorskip("yaml", reason="pyyaml só é usado para validar o RAML")


class _LoaderRaml(yaml.SafeLoader):
    """RAML usa tags proprias (`!include`) que o loader padrao rejeita."""


_LoaderRaml.add_multi_constructor("!", lambda loader, suffix, node: None)


#: Edicoes plausiveis no XML Mule: cada par e (trecho original, trecho alterado).
EDICOES_XML: list[tuple[str, str]] = [
    (
        "    situacao: v.situacao\n",
        "    situacao: v.situacao,\n    marca: v.marca\n",
    ),
    (
        "<db:sql>SELECT id, sku, ean, situacao FROM produto</db:sql>",
        "<db:sql>SELECT id, sku FROM produto WHERE ativo = true</db:sql>",
    ),
    (
        '<flow-ref name="valida-pedido"/>',
        '<flow-ref name="valida-pedido"/>\n        <logger message="validado"/>',
    ),
    ("</mule>", '    <flow name="flow-novo-a"/>\n</mule>'),
    (
        '<logger level="ERROR" message="banco indisponivel"/>',
        '<logger level="ERROR" message="banco fora"/>\n'
        '                <raise-error type="APP:DB_FORA"/>',
    ),
    ('type="DB:CONNECTIVITY"', 'type="DB:CONNECTIVITY, DB:QUERY_EXECUTION"'),
    ('path="/produtos"', 'path="/api/v2/produtos"'),
    (
        '<when expression="#[payload.valor &lt;= 0]">',
        '<when expression="#[payload.valor &lt;= 0 or payload.valor &gt; 9999]">',
    ),
]

#: O mesmo para o RAML.
EDICOES_RAML: list[tuple[str, str]] = [
    ("      ean:\n", "      marca:\n        type: string\n      ean:\n"),
    (
        "        enum: [ATIVO, ESGOTADO, DESCONTINUADO]",
        "        enum: [DISPONIVEL, ARREMATADO, DESCONTINUADO, DEVOLVIDO]",
    ),
    (
        "  Pedido:\n",
        "  Documento:\n    type: object\n    properties:\n      url: string\n  Pedido:\n",
    ),
    ("        minLength: 17\n", "        minLength: 17\n        required: true\n"),
    ("      dataHora: datetime", "      dataHora: datetime\n      origem: string"),
    (
        "        404:\n          description: Produto nao encontrado",
        "        403:\n          description: Sem permissao\n"
        "        404:\n          description: Produto nao encontrado",
    ),
    (
        "      tamanho:\n        type: integer\n        default: 20",
        "      tamanho:\n        type: integer\n        default: 50\n        maximum: 100",
    ),
    (
        "description: Codigo interno do produto",
        "description: Codigo interno (obrigatorio)",
    ),
]


def _tres(tmp_path: Path, nome: str, meu: str, base: str, novo: str, rel: str):
    pastas = {}
    for chave, conteudo in (("local", meu), ("base", base), ("novo", novo)):
        d = tmp_path / f"{nome}-{chave}"
        d.mkdir(parents=True)
        (d / rel).write_text(conteudo, encoding="utf-8")
        pastas[chave] = d
    return pastas


def _marca(alterado: str) -> str:
    """A primeira linha nao vazia do trecho alterado, para procurar no resultado."""
    for linha in alterado.splitlines():
        if linha.strip():
            return linha.strip()
    return ""


# --- XML Mule -------------------------------------------------------------------


def test_todas_as_combinacoes_de_edicao_xml(tmp_path):
    """Cada par de edicoes independentes: junta ou conflita, nunca corrompe."""
    juntados = conflitos = 0
    problemas: list[str] = []

    for i, (a, b) in enumerate(itertools.permutations(EDICOES_XML, 2)):
        meu, novo = MULE_BASE.replace(*a, 1), MULE_BASE.replace(*b, 1)
        if meu == MULE_BASE or novo == MULE_BASE:
            pytest.fail(f"edicao {i} nao casou com a massa — o teste nao provaria nada")

        p = _tres(tmp_path, f"x{i}", meu, MULE_BASE, novo, "a.xml")
        r = reconcile.reconciliar(p["local"], p["base"], p["novo"], "1", "2")

        if not r.limpo:
            conflitos += 1
            # Com conflito nada e escrito: o arquivo do usuario segue intacto e valido.
            ElementTree.fromstring((p["local"] / "a.xml").read_text(encoding="utf-8"))
            continue

        reconcile.aplicar(r, p["local"])
        juntados += 1
        final = (p["local"] / "a.xml").read_text(encoding="utf-8")

        if "<<<<<<<" in final:
            problemas.append(f"{i}: marcador de merge no arquivo")
            continue
        try:
            ElementTree.fromstring(final)
        except ElementTree.ParseError as exc:
            problemas.append(f"{i}: XML invalido — {exc}")
            continue
        for lado, edicao in (("minha", a), ("deles", b)):
            if (m := _marca(edicao[1])) and m not in final:
                problemas.append(f"{i}: perdeu a edicao {lado} ({m[:40]})")

    assert problemas == [], "\n".join(problemas)
    assert juntados > 0 and conflitos > 0, (
        f"a massa precisa exercitar os dois caminhos: {juntados} juntados, "
        f"{conflitos} conflitos"
    )


def test_todas_as_combinacoes_de_edicao_raml(tmp_path):
    """O mesmo para o RAML, validando que o resultado continua YAML parseavel."""
    juntados = conflitos = 0
    problemas: list[str] = []

    for i, (a, b) in enumerate(itertools.permutations(EDICOES_RAML, 2)):
        meu, novo = RAML_BASE.replace(*a, 1), RAML_BASE.replace(*b, 1)
        if meu == RAML_BASE or novo == RAML_BASE:
            pytest.fail(f"edicao {i} nao casou com a massa")

        p = _tres(tmp_path, f"r{i}", meu, RAML_BASE, novo, "api.raml")
        r = reconcile.reconciliar(p["local"], p["base"], p["novo"], "1", "2")

        if not r.limpo:
            conflitos += 1
            continue

        reconcile.aplicar(r, p["local"])
        juntados += 1
        final = (p["local"] / "api.raml").read_text(encoding="utf-8")

        if "<<<<<<<" in final:
            problemas.append(f"{i}: marcador de merge")
            continue
        try:
            yaml.load(final, Loader=_LoaderRaml)
        except yaml.YAMLError as exc:
            problemas.append(f"{i}: RAML invalido — {str(exc)[:80]}")
            continue
        for lado, edicao in (("minha", a), ("deles", b)):
            if (m := _marca(edicao[1])) and m not in final:
                problemas.append(f"{i}: perdeu a edicao {lado} ({m[:40]})")

    assert problemas == [], "\n".join(problemas)
    assert juntados > 0 and conflitos > 0


# --- Cascata: varias versoes seguidas -------------------------------------------


def test_cascata_de_merges_nao_degrada_o_arquivo(tmp_path):
    """Cinco versoes do Exchange em sequencia, com uma edicao minha em cada rodada.

    O risco aqui e acumulativo: um merge que introduz uma diferenca minima de espaco em
    branco ou fim de linha faz o proximo achar mudanca onde nao houve, e a partir dali o
    arquivo degrada. Cada passo tem de continuar valido e conter tudo.
    """
    local = tmp_path / "cascata"
    local.mkdir()
    alvo = local / "a.xml"
    alvo.write_text(MULE_BASE, encoding="utf-8")

    for passo in range(5):
        atual = alvo.read_text(encoding="utf-8")
        base = tmp_path / f"cb{passo}"
        novo = tmp_path / f"cn{passo}"
        base.mkdir()
        novo.mkdir()
        (base / "a.xml").write_text(atual, encoding="utf-8")
        (novo / "a.xml").write_text(
            atual.replace("</mule>", f'    <flow name="gerado-{passo}"/>\n</mule>'),
            encoding="utf-8",
        )
        # E eu edito outro ponto do arquivo na mesma rodada — um processador novo dentro
        # do sub-flow, longe de onde eles mexeram, e num ponto que existe em toda rodada.
        alvo.write_text(
            atual.replace(
                "        </choice>\n",
                f'            <logger message="meu passo {passo}"/>\n        </choice>\n',
                1,
            ),
            encoding="utf-8",
        )

        r = reconcile.reconciliar(local, base, novo, str(passo), str(passo + 1))
        assert r.limpo, f"passo {passo} conflitou: {[c.caminho for c in r.conflitos]}"
        reconcile.aplicar(r, local)

        final = alvo.read_text(encoding="utf-8")
        raiz = ElementTree.fromstring(final)  # levanta se degradou
        nomes = {e.get("name") for e in raiz.iter() if e.get("name")}
        for anterior in range(passo + 1):
            assert f"gerado-{anterior}" in nomes, (
                f"no passo {passo}, o flow do passo {anterior} desapareceu"
            )
        for anterior in range(passo + 1):
            assert f'message="meu passo {anterior}"' in final, (
                f"no passo {passo}, a minha edicao do passo {anterior} desapareceu"
            )

    assert alvo.read_text(encoding="utf-8").count("<flow ") == 2 + 5


def test_cascata_no_raml_preserva_todas_as_minhas_edicoes(tmp_path):
    """Uma property minha por rodada, cinco rodadas: todas tem de sobreviver."""
    local = tmp_path / "casc-raml"
    local.mkdir()
    alvo = local / "api.raml"
    alvo.write_text(RAML_BASE, encoding="utf-8")

    for passo in range(5):
        atual = alvo.read_text(encoding="utf-8")
        base, novo = tmp_path / f"rb{passo}", tmp_path / f"rn{passo}"
        base.mkdir()
        novo.mkdir()
        (base / "api.raml").write_text(atual, encoding="utf-8")
        # Eles acrescentam um type novo no fim; eu, uma property no Veiculo.
        (novo / "api.raml").write_text(
            atual.replace(
                "  Pedido:\n", f"  TypeDeles{passo}:\n    type: object\n  Pedido:\n"
            ),
            encoding="utf-8",
        )
        alvo.write_text(
            atual.replace(
                "      ean:\n", f"      meuCampo{passo}: string\n      ean:\n"
            ),
            encoding="utf-8",
        )

        r = reconcile.reconciliar(local, base, novo, str(passo), str(passo + 1))
        assert r.limpo, f"passo {passo}: {[c.caminho for c in r.conflitos]}"
        reconcile.aplicar(r, local)

        final = alvo.read_text(encoding="utf-8")
        yaml.load(final, Loader=_LoaderRaml)
        for anterior in range(passo + 1):
            assert f"meuCampo{anterior}: string" in final, (
                f"passo {passo}: minha property do passo {anterior} sumiu"
            )
            assert f"TypeDeles{anterior}:" in final, (
                f"passo {passo}: o type deles do passo {anterior} sumiu"
            )


# --- Volume de arquivos ---------------------------------------------------------


def test_cinquenta_arquivos_de_codigo_de_uma_vez(tmp_path):
    """Um projeto com 50 XMLs, metade editada por mim, metade por eles."""
    base, local, novo = tmp_path / "b", tmp_path / "l", tmp_path / "n"
    for d in (base, local, novo):
        d.mkdir()

    for i in range(50):
        conteudo = MULE_BASE.replace("get-produtos", f"flow-{i}")
        (base / f"s{i}.xml").write_text(conteudo, encoding="utf-8")
        meu = (
            conteudo.replace('message="banco indisponivel"', f'message="meu {i}"')
            if i % 2 == 0
            else conteudo
        )
        (local / f"s{i}.xml").write_text(meu, encoding="utf-8")
        deles = (
            conteudo.replace("</mule>", f'    <flow name="deles-{i}"/>\n</mule>')
            if i % 2 == 1
            else conteudo
        )
        (novo / f"s{i}.xml").write_text(deles, encoding="utf-8")

    r = reconcile.reconciliar(local, base, novo, "1", "2")
    reconcile.aplicar(r, local)

    assert r.limpo
    for i in range(50):
        final = (local / f"s{i}.xml").read_text(encoding="utf-8")
        ElementTree.fromstring(final)
        if i % 2 == 0:
            assert f'message="meu {i}"' in final
        else:
            assert f'name="deles-{i}"' in final
