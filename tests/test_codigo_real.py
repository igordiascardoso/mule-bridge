"""Reconciliacao de CODIGO, nao de comentarios.

O resto da suite prova a mecanica com edicoes faceis — uma linha de comentario no topo, um
campo a mais. Comentario e o caso mais benigno que existe: nao tem indentacao significativa,
nao referencia nada, e o merge acerta quase sempre.

Este arquivo usa o que o usuario realmente edita:

    RAML  — types com properties aninhadas, endpoints com metodos e respostas,
            `!include`, `securedBy`, traits, exemplos, enums
    Mule  — flows com processadores encadeados, DataWeave dentro de <ee:set-payload>,
            error-handler, sub-flows, referencias entre arquivos por nome

E cobre as formas de conflito que so aparecem em codigo: dois campos adicionados no mesmo
type, um endpoint novo dentro do mesmo recurso, um processador inserido no meio de um flow
que o outro lado tambem alterou.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
from conftest_codigo import MULE_BASE, RAML_BASE

from mule_bridge import reconcile


def _escreve(pasta: Path, arquivos: dict[str, str]) -> Path:
    pasta.mkdir(parents=True, exist_ok=True)
    for rel, conteudo in arquivos.items():
        p = pasta / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(conteudo, encoding="utf-8")
    return pasta


@pytest.fixture
def tres(tmp_path):
    return {k: tmp_path / k for k in ("local", "base", "novo")}


def _rec(tres, meu: str, novo: str, base: str, rel: str = "api.raml"):
    _escreve(tres["local"], {rel: meu})
    _escreve(tres["base"], {rel: base})
    _escreve(tres["novo"], {rel: novo})
    return reconcile.reconciliar(tres["local"], tres["base"], tres["novo"], "1.0", "1.1")


# --- RAML: types ----------------------------------------------------------------


def test_eu_adiciono_property_eles_adicionam_outra_no_mesmo_type(tres):
    """Duas properties novas no mesmo `Veiculo`, em pontos distintos do bloco."""
    meu = RAML_BASE.replace(
        "      chassi:\n",
        "      renavam:\n        type: string\n        minLength: 11\n      chassi:\n",
    )
    novo = RAML_BASE.replace(
        "        enum: [DISPONIVEL, ARREMATADO, RETIRADO]\n",
        "        enum: [DISPONIVEL, ARREMATADO, RETIRADO]\n"
        "      anoFabricacao:\n        type: integer\n",
    )

    r = _rec(tres, meu, novo, RAML_BASE)
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "api.raml").read_text(encoding="utf-8")

    assert r.limpo, f"conflitos: {[c.caminho for c in r.conflitos]}"
    assert "renavam:" in final and "minLength: 11" in final, "minha property inteira"
    assert "anoFabricacao:" in final, "a property nova deles"
    assert final.count("      chassi:") == 1, "nada duplicado"


def test_eu_mudo_o_pattern_da_placa_eles_mudam_o_enum(tres):
    """Duas regras de validacao diferentes, no mesmo type: tem de juntar."""
    meu = RAML_BASE.replace(
        '        pattern: "^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"',
        '        pattern: "^[A-Z]{3}-?[0-9]{4}$"',
    )
    novo = RAML_BASE.replace(
        "        enum: [DISPONIVEL, ARREMATADO, RETIRADO]",
        "        enum: [DISPONIVEL, ARREMATADO, RETIRADO, CANCELADO]",
    )

    r = _rec(tres, meu, novo, RAML_BASE)
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "api.raml").read_text(encoding="utf-8")

    assert r.limpo
    assert "^[A-Z]{3}-?[0-9]{4}$" in final, "meu pattern"
    assert "CANCELADO" in final, "o enum novo deles"


def test_os_dois_mudam_o_mesmo_pattern_conflita(tres):
    """Mesma linha, regras incompativeis: nao ha combinacao possivel, so decisao."""
    meu = RAML_BASE.replace(
        '        pattern: "^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"',
        '        pattern: "^[A-Z]{3}-?[0-9]{4}$"',
    )
    novo = RAML_BASE.replace(
        '        pattern: "^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"',
        '        pattern: "^[A-Z]{4}[0-9]{3}$"',
    )
    antes = meu

    r = _rec(tres, meu, novo, RAML_BASE)

    assert not r.limpo
    with pytest.raises(reconcile.ReconcileError):
        reconcile.aplicar(r, tres["local"])
    assert (tres["local"] / "api.raml").read_text(encoding="utf-8") == antes


def test_eu_adiciono_type_novo_eles_adicionam_outro(tres):
    """Dois types novos, cada um depois de um bloco diferente."""
    meu = RAML_BASE.replace(
        "\n/veiculos:",
        "\n  Arrematante:\n    type: object\n    properties:\n"
        "      cpf:\n        type: string\n        minLength: 11\n\n/veiculos:",
    )
    novo = RAML_BASE.replace(
        "  Lance:\n",
        "  Documento:\n    type: object\n    properties:\n      url: string\n  Lance:\n",
    )

    r = _rec(tres, meu, novo, RAML_BASE)
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "api.raml").read_text(encoding="utf-8")

    assert r.limpo
    assert "Arrematante:" in final and "cpf:" in final
    assert "Documento:" in final and "url: string" in final
    assert "Lance:" in final, "o type que ja existia continua"


# --- RAML: endpoints ------------------------------------------------------------


def test_eu_adiciono_metodo_eles_adicionam_endpoint(tres):
    """Eu ponho um POST em /veiculos, eles criam /leiloes: recursos independentes."""
    meu = RAML_BASE.replace(
        "  /{id}:\n",
        "  post:\n    body:\n      type: Veiculo\n    responses:\n      201:\n  /{id}:\n",
    )
    novo = RAML_BASE.rstrip() + (
        "\n\n/leiloes:\n  securedBy: [jwt]\n  get:\n    responses:\n      200:\n"
    )

    r = _rec(tres, meu, novo, RAML_BASE)
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "api.raml").read_text(encoding="utf-8")

    assert r.limpo
    assert "  post:\n    body:\n      type: Veiculo" in final, "meu metodo novo"
    assert "/leiloes:" in final, "o recurso novo deles"


def test_eu_adiciono_resposta_de_erro_eles_adicionam_outra(tres):
    """Dois codigos de resposta no mesmo metodo — o caso classico de merge em RAML."""
    meu = RAML_BASE.replace(
        "        404:\n          description: Veiculo nao encontrado",
        "        403:\n          description: Sem permissao\n"
        "        404:\n          description: Veiculo nao encontrado",
    )
    novo = RAML_BASE.replace(
        "      409:\n        description: Lance menor que o atual",
        "      409:\n        description: Lance menor que o atual\n"
        "      422:\n        description: Veiculo ja arrematado",
    )

    r = _rec(tres, meu, novo, RAML_BASE)
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "api.raml").read_text(encoding="utf-8")

    assert r.limpo
    assert "403:" in final and "Sem permissao" in final
    assert "422:" in final and "ja arrematado" in final


def test_include_novo_dos_dois_lados_no_mesmo_ponto_conflita(tres):
    """Dois `!include` no mesmo lugar: a ordem e escolha humana."""
    meu = RAML_BASE.replace(
        "traits:\n", "traits:\n  auditado: !include traits/auditado.raml\n"
    )
    novo = RAML_BASE.replace(
        "traits:\n", "traits:\n  cacheado: !include traits/cacheado.raml\n"
    )

    r = _rec(tres, meu, novo, RAML_BASE)

    assert not r.limpo, "dois includes no mesmo ponto pedem decisao de ordem"
    c = r.conflitos[0]
    assert "auditado" in c.meu and "cacheado" in c.novo


def test_include_conflitante_resolvido_mantendo_os_dois(tres):
    """E a resolucao natural: os dois traits, um em cada linha."""
    meu = RAML_BASE.replace(
        "traits:\n", "traits:\n  auditado: !include traits/auditado.raml\n"
    )
    novo = RAML_BASE.replace(
        "traits:\n", "traits:\n  cacheado: !include traits/cacheado.raml\n"
    )
    r = _rec(tres, meu, novo, RAML_BASE)

    combinado = RAML_BASE.replace(
        "traits:\n",
        "traits:\n  auditado: !include traits/auditado.raml\n"
        "  cacheado: !include traits/cacheado.raml\n",
    )
    reconcile.aplicar(r, tres["local"], resolucoes={"api.raml": combinado})
    final = (tres["local"] / "api.raml").read_text(encoding="utf-8")

    assert "auditado" in final and "cacheado" in final
    assert "<<<<<<<" not in final


def test_arquivo_de_include_novo_vem_junto(tres):
    """A versao nova traz um `!include` e o arquivo apontado por ele."""
    novo = RAML_BASE.replace(
        "securitySchemes:\n", "securitySchemes:\n  captcha: !include security/captcha.raml\n"
    )
    _escreve(tres["local"], {"api.raml": RAML_BASE, "security/jwt.raml": "type: x-custom\n"})
    _escreve(tres["base"], {"api.raml": RAML_BASE, "security/jwt.raml": "type: x-custom\n"})
    _escreve(
        tres["novo"],
        {
            "api.raml": novo,
            "security/jwt.raml": "type: x-custom\n",
            "security/captcha.raml": "type: x-custom\ndescribedBy:\n  headers:\n    X-Captcha:\n",
        },
    )

    r = reconcile.reconciliar(tres["local"], tres["base"], tres["novo"], "1.0", "1.1")
    reconcile.aplicar(r, tres["local"])

    assert r.limpo
    assert "captcha: !include" in (tres["local"] / "api.raml").read_text(encoding="utf-8")
    assert (tres["local"] / "security" / "captcha.raml").is_file(), "o include tem de existir"


# --- Mule XML: flows ------------------------------------------------------------


def test_eu_edito_o_dataweave_eles_adicionam_flow(tres):
    """O caso mais comum do dia a dia: eu mexo na transformacao, o scaffold gera flow."""
    meu = MULE_BASE.replace(
        "    situacao: v.situacao\n", "    situacao: v.situacao,\n    renavam: v.renavam\n"
    )
    novo = MULE_BASE.replace(
        "</mule>",
        """    <flow name="get-veiculos-id">
        <http:listener config-ref="api-httpListenerConfig" path="/veiculos/{id}"/>
        <db:select config-ref="postgres-config">
            <db:sql>SELECT * FROM veiculo WHERE id = :id</db:sql>
        </db:select>
    </flow>
</mule>""",
    )

    r = _rec(tres, meu, novo, MULE_BASE, rel="application.xml")
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "application.xml").read_text(encoding="utf-8")

    assert r.limpo, f"conflitos: {[c.caminho for c in r.conflitos]}"
    assert "renavam: v.renavam" in final, "minha alteracao no DataWeave"
    assert 'flow name="get-veiculos-id"' in final, "o flow que o scaffold gerou"
    assert final.count("<flow ") == 3


def test_eu_adiciono_processador_no_meio_de_um_flow(tres):
    """Insiro um logger antes do db:select; eles mexem no outro flow."""
    meu = MULE_BASE.replace(
        '        <db:select config-ref="postgres-config">\n'
        "            <db:sql>SELECT id, placa, chassi, situacao FROM veiculo</db:sql>",
        '        <logger level="INFO" message="consultando veiculos"/>\n'
        '        <db:select config-ref="postgres-config">\n'
        "            <db:sql>SELECT id, placa, chassi, situacao FROM veiculo</db:sql>",
    )
    novo = MULE_BASE.replace(
        '        <flow-ref name="valida-lance"/>',
        '        <flow-ref name="valida-lance"/>\n'
        '        <flow-ref name="verifica-limite"/>',
    )

    r = _rec(tres, meu, novo, MULE_BASE, rel="application.xml")
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "application.xml").read_text(encoding="utf-8")

    assert r.limpo
    assert 'message="consultando veiculos"' in final
    assert 'flow-ref name="verifica-limite"' in final


def test_os_dois_mexem_no_mesmo_sql_conflita(tres):
    """Mesma query alterada de formas diferentes: decisao do usuario."""
    meu = MULE_BASE.replace(
        "SELECT id, placa, chassi, situacao FROM veiculo",
        "SELECT id, placa, chassi, situacao, renavam FROM veiculo",
    )
    novo = MULE_BASE.replace(
        "SELECT id, placa, chassi, situacao FROM veiculo",
        "SELECT id, placa, chassi, situacao FROM veiculo WHERE ativo = true",
    )
    antes = meu

    r = _rec(tres, meu, novo, MULE_BASE, rel="application.xml")

    assert not r.limpo
    with pytest.raises(reconcile.ReconcileError):
        reconcile.aplicar(r, tres["local"])
    assert (tres["local"] / "application.xml").read_text(encoding="utf-8") == antes

    # E a combinacao das duas intencoes e aplicavel.
    combinado = MULE_BASE.replace(
        "SELECT id, placa, chassi, situacao FROM veiculo",
        "SELECT id, placa, chassi, situacao, renavam FROM veiculo WHERE ativo = true",
    )
    reconcile.aplicar(r, tres["local"], resolucoes={"application.xml": combinado})
    final = (tres["local"] / "application.xml").read_text(encoding="utf-8")
    assert "renavam FROM veiculo WHERE ativo = true" in final


def test_eu_adiciono_error_handler_eles_adicionam_outro_tipo(tres):
    """Dois `on-error` no mesmo error-handler, em posicoes distintas."""
    meu = MULE_BASE.replace(
        '            <on-error-propagate type="DB:CONNECTIVITY">',
        '            <on-error-continue type="APP:NAO_ENCONTRADO">\n'
        '                <ee:transform>\n'
        '                    <ee:message>\n'
        '                        <ee:set-payload>{"erro": "nao encontrado"}</ee:set-payload>\n'
        "                    </ee:message>\n"
        "                </ee:transform>\n"
        "            </on-error-continue>\n"
        '            <on-error-propagate type="DB:CONNECTIVITY">',
    )
    novo = MULE_BASE.replace(
        "            </on-error-propagate>\n",
        "            </on-error-propagate>\n"
        '            <on-error-propagate type="DB:QUERY_EXECUTION">\n'
        '                <logger level="ERROR" message="query falhou"/>\n'
        "            </on-error-propagate>\n",
    )

    r = _rec(tres, meu, novo, MULE_BASE, rel="application.xml")
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "application.xml").read_text(encoding="utf-8")

    assert r.limpo
    assert "APP:NAO_ENCONTRADO" in final, "meu handler"
    assert "DB:QUERY_EXECUTION" in final, "o handler deles"


def test_cdata_com_dataweave_multilinha_sobrevive(tres):
    """DataWeave dentro de CDATA: nao pode ser quebrado nem escapado."""
    meu = MULE_BASE.replace(
        "payload map (v) -> {",
        "payload filter (v) -> v.situacao == 'DISPONIVEL' map (v) -> {",
    )
    novo = MULE_BASE.replace("</mule>", '    <flow name="outro"/>\n</mule>')

    r = _rec(tres, meu, novo, MULE_BASE, rel="application.xml")
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "application.xml").read_text(encoding="utf-8")

    assert r.limpo
    assert "filter (v) -> v.situacao == 'DISPONIVEL'" in final
    assert "<![CDATA[%dw 2.0" in final, "o CDATA continua intacto"
    assert "]]>" in final


def test_entidade_xml_escapada_nao_e_corrompida(tres):
    """`&lt;=` dentro de uma expressao: nao pode virar `<=` nem ser re-escapado."""
    meu = MULE_BASE.replace(
        '<when expression="#[payload.valor &lt;= 0]">',
        '<when expression="#[payload.valor &lt;= 0 or payload.valor &gt; 1000000]">',
    )
    novo = MULE_BASE.replace("</mule>", '    <flow name="novo"/>\n</mule>')

    r = _rec(tres, meu, novo, MULE_BASE, rel="application.xml")
    reconcile.aplicar(r, tres["local"])
    final = (tres["local"] / "application.xml").read_text(encoding="utf-8")

    assert r.limpo
    assert "&lt;= 0 or payload.valor &gt; 1000000" in final
    assert "<= 0 or" not in final, "a entidade nao pode ter sido desescapada"


# --- Varios arquivos, como num projeto de verdade -------------------------------


def test_projeto_inteiro_com_multiplos_arquivos_de_codigo(tres):
    """Cinco arquivos, cada um editado de um lado diferente."""
    base_files = {
        "api.raml": RAML_BASE,
        "security/jwt.raml": "type: x-custom\ndescribedBy:\n  headers:\n    Authorization:\n",
        "types/veiculo.raml": "#%RAML 1.0 DataType\ntype: object\nproperties:\n  id: integer\n",
        "application.xml": MULE_BASE,
        "services/lance.xml": '<?xml version="1.0"?>\n<mule>\n'
        '    <sub-flow name="calcula-incremento">\n'
        '        <set-variable variableName="minimo" value="#[payload.valor * 1.05]"/>\n'
        "    </sub-flow>\n</mule>\n",
    }
    _escreve(tres["base"], base_files)

    # Eu mexo no RAML principal e num service.
    meus = dict(base_files)
    meus["api.raml"] = RAML_BASE.replace(
        "      chassi:\n", "      renavam:\n        type: string\n      chassi:\n"
    )
    meus["services/lance.xml"] = base_files["services/lance.xml"].replace(
        "payload.valor * 1.05", "payload.valor * 1.10"
    )
    _escreve(tres["local"], meus)

    # Eles mexem no type, no application e trazem um arquivo novo.
    deles = dict(base_files)
    deles["types/veiculo.raml"] = base_files["types/veiculo.raml"] + "  placa: string\n"
    deles["application.xml"] = MULE_BASE.replace(
        "</mule>", '    <flow name="delete-veiculo"/>\n</mule>'
    )
    deles["types/lance.raml"] = "#%RAML 1.0 DataType\ntype: object\n"
    _escreve(tres["novo"], deles)

    r = reconcile.reconciliar(tres["local"], tres["base"], tres["novo"], "1.0", "1.1")
    reconcile.aplicar(r, tres["local"])

    def ler(rel):
        return (tres["local"] / rel).read_text(encoding="utf-8")

    assert r.limpo, f"conflitos: {[c.caminho for c in r.conflitos]}"
    assert "renavam:" in ler("api.raml"), "minha edicao no RAML"
    assert "1.10" in ler("services/lance.xml"), "minha edicao no service"
    assert "placa: string" in ler("types/veiculo.raml"), "a edicao deles no type"
    assert 'name="delete-veiculo"' in ler("application.xml"), "o flow novo deles"
    assert (tres["local"] / "types" / "lance.raml").is_file(), "o arquivo novo deles"


def test_nenhum_arquivo_de_codigo_fica_invalido(tres):
    """Depois de aplicar, todo XML tem de continuar parseavel e todo RAML legivel.

    Um merge que produz XML quebrado nao levanta erro aqui — quebra no deploy. Entao o
    teste faz o que o Studio faria: tenta parsear.
    """
    from xml.etree import ElementTree

    meu = MULE_BASE.replace(
        '        <flow-ref name="valida-lance"/>',
        '        <flow-ref name="valida-lance"/>\n'
        '        <logger level="DEBUG" message="lance validado"/>',
    )
    novo = MULE_BASE.replace(
        "    <sub-flow name=\"valida-lance\">",
        '    <sub-flow name="verifica-saldo">\n'
        '        <logger level="INFO" message="saldo ok"/>\n'
        "    </sub-flow>\n\n"
        '    <sub-flow name="valida-lance">',
    )

    r = _rec(tres, meu, novo, MULE_BASE, rel="application.xml")
    reconcile.aplicar(r, tres["local"])
    bruto = (tres["local"] / "application.xml").read_text(encoding="utf-8")

    assert r.limpo
    # Se o merge quebrou a arvore, isto levanta ParseError.
    raiz = ElementTree.fromstring(bruto)
    nomes = {e.get("name") for e in raiz.iter() if e.get("name")}
    assert {"get-veiculos", "post-lances", "valida-lance", "verifica-saldo"} <= nomes
    assert "lance validado" in bruto


# --- Via git (o caminho do `pararepo api`) --------------------------------------


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.safecrlf=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def test_scaffold_de_verdade_sobre_codigo_meu(tmp_path):
    """`pararepo api` com base no git: scaffold real contra edicao real, em XML valido."""
    from xml.etree import ElementTree

    local = tmp_path / "api"
    _escreve(
        local,
        {
            "src/main/mule/application.xml": MULE_BASE,
            "src/main/mule/services/lance.xml": '<?xml version="1.0"?>\n<mule>\n'
            '    <sub-flow name="calc"/>\n</mule>\n',
        },
    )
    _git(local, "init", "-q")
    _git(local, "config", "user.email", "t@t")
    _git(local, "config", "user.name", "t")
    _git(local, "add", "-A")
    _git(local, "commit", "-q", "-m", "base")

    studio = tmp_path / "studio"
    _escreve(
        studio,
        {
            # O scaffold adiciona dois flows e um sub-flow no fim.
            "src/main/mule/application.xml": MULE_BASE.replace(
                "</mule>",
                '    <flow name="put-veiculos-id">\n'
                '        <http:listener config-ref="api-httpListenerConfig" '
                'path="/veiculos/{id}"/>\n'
                '        <logger level="INFO" message="gerado pelo scaffold"/>\n'
                "    </flow>\n"
                '    <flow name="delete-lances-id">\n'
                '        <http:listener config-ref="api-httpListenerConfig" '
                'path="/lances/{id}"/>\n'
                "    </flow>\n"
                "</mule>",
            ),
            "src/main/mule/services/lance.xml": '<?xml version="1.0"?>\n<mule>\n'
            '    <sub-flow name="calc"/>\n</mule>\n',
        },
    )

    # Eu, ao mesmo tempo, alterei o DataWeave do primeiro flow.
    alvo = local / "src" / "main" / "mule" / "application.xml"
    alvo.write_text(
        MULE_BASE.replace(
            "    situacao: v.situacao\n", "    situacao: v.situacao,\n    ativo: true\n"
        ),
        encoding="utf-8",
    )

    r = reconcile.reconciliar_com_git(local, studio, {".git", "target"})
    reconcile.aplicar(r, local)
    final = alvo.read_text(encoding="utf-8")

    assert r.limpo, f"conflitos: {[c.caminho for c in r.conflitos]}"
    assert "ativo: true" in final, "minha edicao no DataWeave"
    assert 'name="put-veiculos-id"' in final and 'name="delete-lances-id"' in final
    assert final.count("<flow ") == 4
    ElementTree.fromstring(final)  # tem de continuar valido
