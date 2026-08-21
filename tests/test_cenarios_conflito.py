"""Todos os casos de conflito, um por um, e o que acontece em cada um.

Este arquivo existe para responder uma pergunta concreta: quando os dois lados mexem no
mesmo arquivo, o que sobra? O resultado depende de **onde** cada lado mexeu, e a diferenca
entre "junta sozinho" e "vira conflito" e a garantia central da ferramenta.

Os quatro casos, do mais facil ao mais espinhoso:

    1. linhas diferentes, longe uma da outra  -> junta sozinho, os dois ficam
    2. linhas diferentes, mas vizinhas        -> o git ainda junta? (testado abaixo)
    3. a mesma linha, com textos diferentes   -> conflito, nada e escrito
    4. a mesma linha, com o mesmo texto       -> nem conflito e: e uma mudanca so

E o ciclo de vida de um conflito depois de detectado: recusa, resolucao, aplicacao.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from mule_bridge import reconcile
from mule_bridge.reconcile import ReconcileError

BASE = """#%RAML 1.0
title: Leilao
version: v1
types:
  Leilao:
    properties:
      id: integer
      placa:
        type: string
        description: Placa do veiculo
      lance:
        type: number
        description: Valor do lance
      captcha:
        type: string
        description: Token do reCAPTCHA
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


def _montar(dirs, meu: str, novo: str, base: str = BASE):
    """Monta as tres pontas e reconcilia, sem escrever nada na pasta local."""
    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": base})
    _escreve(dirs["novo"], {"api.raml": novo})
    return reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1.1.54", "1.1.55")


# --- Caso 1: linhas distantes -----------------------------------------------------


def test_linhas_distantes_ficam_as_duas(dirs):
    """O caso comum: eu mexo no topo, o Exchange mexe no fim. Os dois sobrevivem."""
    meu = BASE.replace("version: v1", "version: v1\n# nota minha: em homologacao")
    novo = BASE.replace(
        "        description: Token do reCAPTCHA",
        "        description: Token do reCAPTCHA\n      cor:\n        type: string",
    )

    r = _montar(dirs, meu, novo)

    assert r.limpo, f"nao devia conflitar: {[c.caminho for c in r.conflitos]}"
    assert r.juntados == ["api.raml"]
    final = r.resultado["api.raml"]
    assert "nota minha: em homologacao" in final, "minha edicao tem de sobreviver"
    assert "cor:" in final, "a novidade do Exchange tem de entrar"


# --- Caso 2: linhas vizinhas ------------------------------------------------------


def test_linhas_vizinhas_o_git_ainda_junta(dirs):
    """Duas linhas de distancia. O merge de tres pontas trabalha por blocos de contexto,
    entao vale registrar onde exatamente esta o limite entre "junta" e "conflita"."""
    meu = BASE.replace(
        "        description: Placa do veiculo",
        "        description: Placa no padrao Mercosul",
    )
    novo = BASE.replace(
        "        description: Valor do lance",
        "        description: Valor do lance em reais",
    )

    r = _montar(dirs, meu, novo)

    assert r.limpo, "linhas separadas por outras linhas ainda juntam"
    final = r.resultado["api.raml"]
    assert "Mercosul" in final
    assert "em reais" in final


def test_linhas_coladas_ainda_juntam(dirs):
    """Linhas adjacentes, mas em blocos distintos: o git ainda resolve.

    Vale registrar porque a intuicao diz o contrario. O limite nao e a distancia em
    linhas, e se as mudancas *se tocam* — ver os testes de anexacao mais abaixo.
    """
    meu = BASE.replace("      lance:", "      lance: # meu comentario")
    novo = BASE.replace(
        "        type: number", "        type: number\n        required: true"
    )

    r = _montar(dirs, meu, novo)

    assert r.limpo, "blocos vizinhos mas nao sobrepostos juntam"
    final = r.resultado["api.raml"]
    assert "meu comentario" in final
    assert "required: true" in final


# --- Caso 3: a mesma linha, textos diferentes -------------------------------------


def test_mesma_linha_textos_diferentes_nao_escreve_nada(dirs):
    """O caso reCAPTCHA -> ALTCHA. Nenhum dos dois textos e escolhido, nada e gravado."""
    meu = BASE.replace("Token do reCAPTCHA", "Token do ALTCHA")
    novo = BASE.replace("Token do reCAPTCHA", "Token do reCAPTCHA v3")
    antes = (dirs["local"] / "api.raml") if dirs["local"].exists() else None
    del antes

    r = _montar(dirs, meu, novo)
    conteudo_antes = (dirs["local"] / "api.raml").read_text(encoding="utf-8")

    assert len(r.conflitos) == 1
    c = r.conflitos[0]
    assert "ALTCHA" in c.meu, "o conflito carrega a minha versao"
    assert "reCAPTCHA v3" in c.novo, "e a versao nova do Exchange"
    assert "api.raml" not in r.resultado, "sem resolucao, nao ha resultado a aplicar"

    with pytest.raises(ReconcileError, match="Ha conflitos sem resolucao"):
        reconcile.aplicar(r, dirs["local"])

    depois = (dirs["local"] / "api.raml").read_text(encoding="utf-8")
    assert depois == conteudo_antes, "o arquivo do usuario nao pode ter sido tocado"
    assert "<<<<<<<" not in depois, "e nao pode receber marcador de merge"


def test_o_conflito_mostra_os_dois_lados_para_decidir(dirs):
    """Quem for resolver precisa ver base, meu e novo — e o merge marcado como contexto."""
    meu = BASE.replace("Token do reCAPTCHA", "Token do ALTCHA")
    novo = BASE.replace("Token do reCAPTCHA", "Token do hCaptcha")

    c = _montar(dirs, meu, novo).conflitos[0]

    assert "reCAPTCHA" in c.base, "a base e o ponto de partida comum"
    assert "ALTCHA" in c.meu
    assert "hCaptcha" in c.novo
    assert "<<<<<<<" in c.merge_marcado and ">>>>>>>" in c.merge_marcado
    assert "sua versao" in c.merge_marcado, "os rotulos precisam dizer de quem e cada lado"


def test_resolucao_combinada_e_aplicada(dirs):
    """O elo que fechava o ciclo e nao estava coberto: decidir e aplicar de verdade."""
    meu = BASE.replace("Token do reCAPTCHA", "Token do ALTCHA")
    novo = BASE.replace(
        "        description: Token do reCAPTCHA",
        "        description: Token do reCAPTCHA\n        required: true",
    )
    r = _montar(dirs, meu, novo)
    assert not r.limpo, "o cenario precisa conflitar para o teste valer"

    # O texto que preserva as duas intencoes: o meu provedor e a obrigatoriedade deles.
    combinado = BASE.replace(
        "        description: Token do reCAPTCHA",
        "        description: Token do ALTCHA\n        required: true",
    )

    escritos = reconcile.aplicar(r, dirs["local"], resolucoes={"api.raml": combinado})

    final = (dirs["local"] / "api.raml").read_text(encoding="utf-8")
    assert escritos == 1
    assert "ALTCHA" in final, "a minha intencao ficou"
    assert "required: true" in final, "a deles tambem"
    assert "<<<<<<<" not in final


def test_resolver_um_conflito_nao_libera_o_outro(dirs):
    """Com dois conflitos, resolver um so nao autoriza a escrita — tudo ou nada."""
    _escreve(
        dirs["local"],
        {"a.raml": "linha: minha\n", "b.raml": "linha: minha\n"},
    )
    _escreve(dirs["base"], {"a.raml": "linha: base\n", "b.raml": "linha: base\n"})
    _escreve(dirs["novo"], {"a.raml": "linha: nova\n", "b.raml": "linha: nova\n"})
    r = reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1", "2")
    assert len(r.conflitos) == 2

    with pytest.raises(ReconcileError, match="b.raml"):
        reconcile.aplicar(r, dirs["local"], resolucoes={"a.raml": "linha: combinada\n"})

    assert (dirs["local"] / "a.raml").read_text(encoding="utf-8") == "linha: minha\n", (
        "nem o conflito resolvido pode ser escrito enquanto o outro esta pendente"
    )


# --- Caso 4: a mesma linha, o mesmo texto ----------------------------------------


def test_mesma_alteracao_nos_dois_lados_nao_e_conflito(dirs):
    """Eu e o Exchange chegamos ao mesmo texto. Nao ha o que decidir."""
    igual = BASE.replace("Token do reCAPTCHA", "Token do ALTCHA")

    r = _montar(dirs, igual, igual)

    assert r.limpo
    assert r.inalterados == ["api.raml"], "meu == novo: nada a fazer"
    assert "ALTCHA" in r.resultado["api.raml"]


def test_eu_desfaco_o_que_o_exchange_traz(dirs):
    """Eu removi uma linha que a versao nova mantem e altera. Isso e decisao minha."""
    meu = BASE.replace("      captcha:\n        type: string\n", "")
    meu = meu.replace("        description: Token do reCAPTCHA\n", "")
    novo = BASE.replace("Token do reCAPTCHA", "Token do reCAPTCHA v3")

    r = _montar(dirs, meu, novo)

    assert not r.limpo, "apagar o que eles editaram e um conflito, nao um silencio"


# --- Arquivos inteiros: criados, apagados, renomeados ----------------------------


def test_arquivo_que_os_dois_criaram_diferente_conflita(dirs):
    """Sem base comum, nao ha merge de tres pontas possivel."""
    _escreve(dirs["local"], {"api.raml": BASE, "novo.raml": "meu: conteudo\n"})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE, "novo.raml": "deles: conteudo\n"})

    r = reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1", "2")

    assert [c.caminho for c in r.conflitos] == ["novo.raml"]


def test_exchange_apaga_arquivo_que_eu_editei_mantem_o_meu(dirs):
    """Eles removeram, eu tinha editado: o meu fica e e reportado como edicao minha."""
    _escreve(dirs["local"], {"api.raml": BASE, "extra.raml": "editado: por mim\n"})
    _escreve(dirs["base"], {"api.raml": BASE, "extra.raml": "original: do exchange\n"})
    _escreve(dirs["novo"], {"api.raml": BASE})

    r = reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1", "2")
    reconcile.aplicar(r, dirs["local"])

    assert "extra.raml" in r.so_meus
    assert (dirs["local"] / "extra.raml").is_file(), "minha edicao nao pode desaparecer"


def test_exchange_apaga_arquivo_que_eu_nao_toquei(dirs):
    """Sem edicao minha, a remocao do Exchange nao me interessa: sai do resultado."""
    _escreve(dirs["local"], {"api.raml": BASE, "velho.raml": "original: do exchange\n"})
    _escreve(dirs["base"], {"api.raml": BASE, "velho.raml": "original: do exchange\n"})
    _escreve(dirs["novo"], {"api.raml": BASE})

    r = reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1", "2")

    assert "velho.raml" not in r.resultado
    assert "velho.raml" not in r.so_meus


def test_renomear_do_lado_do_exchange_e_visto_como_apagar_e_criar(dirs):
    """Nao rastreamos rename. Documentado aqui porque muda o que o usuario ve.

    O resultado pratico: o arquivo novo entra e o antigo permanece na pasta local. Nao ha
    perda de conteudo, mas sobra um arquivo duplicado que o usuario tem de remover.
    """
    _escreve(dirs["local"], {"antigo.raml": "titulo: leilao\n"})
    _escreve(dirs["base"], {"antigo.raml": "titulo: leilao\n"})
    _escreve(dirs["novo"], {"novo-nome.raml": "titulo: leilao\n"})

    r = reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1", "2")

    assert "novo-nome.raml" in r.so_deles, "o nome novo entra"
    assert "antigo.raml" not in r.resultado, "o antigo sai do resultado, mas fica no disco"


def test_pasta_nova_inteira_do_exchange(dirs):
    """O caso real do leilao: `domain/captcha.raml` existindo so na versao nova."""
    _escreve(dirs["local"], {"api.raml": BASE})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(
        dirs["novo"],
        {"api.raml": BASE, "domain/captcha.raml": "#%RAML 1.0 DataType\ntype: object\n"},
    )

    r = reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1", "2")
    reconcile.aplicar(r, dirs["local"])

    assert "domain/captcha.raml" in r.so_deles
    assert (dirs["local"] / "domain" / "captcha.raml").is_file(), "subpasta tem de ser criada"



def test_adicoes_grandes_em_pontos_distintos_somam(dirs):
    """O cenario que motivou o desenho: 50 linhas minhas, 100 delas, tudo aditivo.

    As adicoes vao para pontos diferentes do arquivo (eu num type, eles noutro), que e o
    caso comum de uma spec crescendo dos dois lados.
    """
    base = "#%RAML 1.0\ntitle: Leilao\ntypes:\n  Meus:\n  Deles:\n  Fim:\n"
    meu = base.replace(
        "  Meus:\n", "  Meus:\n" + "".join(f"    m{i}: string\n" for i in range(50))
    )
    novo = base.replace(
        "  Deles:\n", "  Deles:\n" + "".join(f"    d{i}: string\n" for i in range(100))
    )

    r = _montar(dirs, meu, novo, base=base)
    reconcile.aplicar(r, dirs["local"])
    final = (dirs["local"] / "api.raml").read_text(encoding="utf-8")

    assert r.limpo, "adicoes em pontos distintos nao deviam conflitar"
    assert final.count("    m") == 50, "todas as minhas 50 tem de estar la"
    assert final.count("    d") == 100, "e todas as 100 deles"


# --- O limite real: mudancas que se TOCAM -----------------------------------------
#
# A intuicao natural e "linhas diferentes = junta". O limite verdadeiro do merge de tres
# pontas e outro: ele junta enquanto as duas mudancas nao se sobrepoem. Quando ambos
# ACRESCENTAM no mesmo ponto — tipicamente o fim do arquivo — nao existe resposta certa
# para a ordem, e o git para. Os testes abaixo fixam esse contorno, porque e o que o
# usuario encontra na pratica e ele precisa saber que vai ter de decidir.


def test_os_dois_anexam_no_fim_pede_decisao(dirs):
    """Sem base para ordenar, "primeiro o meu" ou "primeiro o deles" e escolha humana."""
    base = "#%RAML 1.0\ntitle: Leilao\ntypes:\n"
    meu = base + "  Meu:\n    type: object\n"
    novo = base + "  Deles:\n    type: object\n"

    r = _montar(dirs, meu, novo, base=base)

    assert not r.limpo, "anexacao simultanea no mesmo ponto pede decisao"
    c = r.conflitos[0]
    assert "Meu:" in c.meu and "Deles:" in c.novo, "os dois lados ficam visiveis"


def test_anexacao_simultanea_resolvida_somando_os_dois(dirs):
    """A resolucao natural desse conflito: manter os dois, um depois do outro."""
    base = "#%RAML 1.0\ntitle: Leilao\ntypes:\n"
    meu = base + "  Meu:\n    type: object\n"
    novo = base + "  Deles:\n    type: object\n"
    r = _montar(dirs, meu, novo, base=base)

    soma = base + "  Deles:\n    type: object\n  Meu:\n    type: object\n"
    reconcile.aplicar(r, dirs["local"], resolucoes={"api.raml": soma})

    final = (dirs["local"] / "api.raml").read_text(encoding="utf-8")
    assert "Meu:" in final and "Deles:" in final
    assert "<<<<<<<" not in final


def test_eu_anexo_no_fim_eles_editam_o_meio_junta(dirs):
    """O contraste que fecha o quadro: se as mudancas nao se tocam, junta sozinho."""
    base = "#%RAML 1.0\ntitle: Leilao\nversion: v1\ntypes:\n  A:\n  B:\n  C:\n"
    meu = base + "  MeuNovo:\n    type: object\n"
    novo = base.replace("version: v1", "version: v2")

    r = _montar(dirs, meu, novo, base=base)
    reconcile.aplicar(r, dirs["local"])
    final = (dirs["local"] / "api.raml").read_text(encoding="utf-8")

    assert r.limpo
    assert "MeuNovo:" in final and "version: v2" in final
