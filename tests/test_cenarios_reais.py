"""Cenarios rodados contra o RAML real do Exchange, quando ele existe no cache local.

Estes testes usam os zips que o Maven ja baixou na maquina. Diferente do resto da suite,
eles nao montam RAMLs de brinquedo: exercitam a reconciliacao contra especificacoes de
milhares de linhas, com as mudancas que o Exchange de fato publicou entre uma versao e
outra — que e onde aparecem os casos que ninguem inventaria (arquivo novo numa subpasta,
bloco de documentacao reescrito, `!include` novo no meio do arquivo).

Sao pulados quando o cache nao tem duas versoes do artefato, para a suite continuar
rodando em qualquer maquina e no CI.
"""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest

from mule_bridge import reconcile
from mule_bridge.reconcile import ReconcileError

#: Artefato usado para os testes reais. Trocar aqui adapta o arquivo a outro projeto.
GRUPO = "GRUPO-REMOVIDO"
ARTEFATO = "leilao"


def _versoes() -> list[str]:
    return reconcile.versoes_no_cache(GRUPO, ARTEFATO)


pytestmark = pytest.mark.skipif(
    len(_versoes()) < 2,
    reason="precisa de pelo menos duas versoes do RAML no cache do Maven",
)


@pytest.fixture
def versoes() -> list[str]:
    return _versoes()


@pytest.fixture
def extrair(tmp_path):
    """Extrai uma versao do cache para uma pasta propria."""

    def _extrair(versao: str, nome: str = "raml") -> Path:
        destino = tmp_path / f"{nome}-{versao}"
        return reconcile.extrair(
            reconcile.caminho_no_cache(GRUPO, ARTEFATO, versao), destino
        )

    return _extrair


def _linha_que_eles_mudaram(base: Path, novo: Path) -> tuple[str, int]:
    """Acha um arquivo e uma linha que o Exchange alterou entre as duas versoes.

    Serve para montar o caso duro de verdade: eu editando exatamente onde eles editaram.
    """
    for p in sorted(base.rglob("*.raml")):
        rel = p.relative_to(base).as_posix()
        q = novo / rel
        if not q.is_file():
            continue
        velho = p.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        atual = q.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if velho == atual:
            continue
        for tag, i1, i2, _j1, _j2 in difflib.SequenceMatcher(None, velho, atual).get_opcodes():
            if tag in ("replace", "delete") and i2 > i1:
                return rel, i1
    pytest.skip("nenhuma linha alterada entre as versoes disponiveis")


# --- Sem edicao local: todo salto de versao tem de ser limpo ---------------------


def test_todo_salto_de_versao_sem_edicao_local_e_limpo(versoes, extrair):
    """Quem nao editou nada nunca deve ver conflito, em nenhum par de versoes."""
    for i, base_v in enumerate(versoes):
        for nova_v in versoes[i + 1 :]:
            pasta = extrair(base_v, f"limpo-{base_v}-{nova_v}")
            r = reconcile.preparar(pasta, GRUPO, ARTEFATO, base_v, nova_v)

            assert r.limpo, f"{base_v} -> {nova_v} conflitou sem edicao local"
            assert r.total_mudancas > 0, f"{base_v} -> {nova_v} nao viu mudanca nenhuma"


def test_salto_de_varias_versoes_traz_os_arquivos_novos(versoes, extrair):
    """Pular versoes nao pode perder arquivo: o alvo e sempre a versao final inteira."""
    base_v, nova_v = versoes[0], versoes[-1]
    pasta = extrair(base_v, "salto")

    r = reconcile.preparar(pasta, GRUPO, ARTEFATO, base_v, nova_v)
    reconcile.aplicar(r, pasta)

    alvo = extrair(nova_v, "alvo")
    for p in alvo.rglob("*.raml"):
        rel = p.relative_to(alvo).as_posix()
        assert (pasta / rel).is_file(), f"{rel} da versao {nova_v} nao chegou"


# --- Com edicao local em vários arquivos ----------------------------------------


def test_edicoes_locais_sobrevivem_a_um_salto_grande(versoes, extrair):
    """Uma nota em cada um de varios arquivos, atravessando todas as versoes do cache."""
    base_v, nova_v = versoes[0], versoes[-1]
    pasta = extrair(base_v, "editado")

    editados = []
    for p in sorted(pasta.rglob("*.raml"))[:5]:
        original = p.read_text(encoding="utf-8", errors="replace")
        p.write_text(f"# NOTA-LOCAL-{p.stem}\n{original}", encoding="utf-8")
        editados.append(p.relative_to(pasta).as_posix())

    r = reconcile.preparar(pasta, GRUPO, ARTEFATO, base_v, nova_v)
    assert r.limpo, f"notas no topo nao deviam conflitar: {[c.caminho for c in r.conflitos]}"
    reconcile.aplicar(r, pasta)

    for rel in editados:
        conteudo = (pasta / rel).read_text(encoding="utf-8", errors="replace")
        assert "NOTA-LOCAL" in conteudo, f"a minha edicao em {rel} foi perdida"


def test_nenhum_marcador_de_merge_vaza_para_o_disco(versoes, extrair):
    """Depois de aplicar, nenhum arquivo pode conter `<<<<<<<`: isso quebraria o RAML."""
    base_v, nova_v = versoes[0], versoes[-1]
    pasta = extrair(base_v, "marcador")
    for p in sorted(pasta.rglob("*.raml"))[:5]:
        p.write_text(
            "# nota\n" + p.read_text(encoding="utf-8", errors="replace"), encoding="utf-8"
        )

    r = reconcile.preparar(pasta, GRUPO, ARTEFATO, base_v, nova_v)
    reconcile.aplicar(r, pasta)

    sujos = [
        str(p.relative_to(pasta))
        for p in pasta.rglob("*")
        if p.is_file() and "<<<<<<<" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert sujos == [], f"marcador de merge escrito em {sujos}"


# --- O caso duro: eu edito a mesma linha que o Exchange ------------------------


def test_conflito_real_recusa_escrever_e_depois_aceita_a_resolucao(versoes, extrair):
    """O ciclo completo de um conflito de verdade, no RAML de verdade.

    Este e o cenario do reCAPTCHA -> ALTCHA: o Exchange reescreveu um bloco de
    documentacao e eu havia mexido na mesma linha. Cobre as tres etapas — detectar,
    recusar sem tocar no arquivo, e aplicar a combinacao depois de decidida.
    """
    base_v, nova_v = versoes[-2], versoes[-1]
    base_dir, novo_dir = extrair(base_v, "cmp-base"), extrair(nova_v, "cmp-novo")
    rel, linha = _linha_que_eles_mudaram(base_dir, novo_dir)

    pasta = extrair(base_v, "duro")
    linhas = (pasta / rel).read_text(encoding="utf-8", errors="replace").splitlines(
        keepends=True
    )
    linhas[linha] = linhas[linha].rstrip("\r\n") + "  # EDICAO-MINHA\n"
    (pasta / rel).write_text("".join(linhas), encoding="utf-8")
    antes = (pasta / rel).read_text(encoding="utf-8", errors="replace")

    r = reconcile.preparar(pasta, GRUPO, ARTEFATO, base_v, nova_v)

    # 1. detectou
    assert rel in [c.caminho for c in r.conflitos], "editar a mesma linha tem de conflitar"

    # 2. recusou, sem tocar no arquivo
    with pytest.raises(ReconcileError, match="Ha conflitos sem resolucao"):
        reconcile.aplicar(r, pasta)
    depois = (pasta / rel).read_text(encoding="utf-8", errors="replace")
    assert depois == antes, "o arquivo do usuario foi alterado apesar do conflito"
    assert "<<<<<<<" not in depois

    # 3. aceita a combinacao: a versao nova deles com a minha marca de volta
    c = next(x for x in r.conflitos if x.caminho == rel)
    novas = c.novo.splitlines(keepends=True)
    novas[linha] = novas[linha].rstrip("\r\n") + "  # EDICAO-MINHA\n"
    reconcile.aplicar(r, pasta, resolucoes={rel: "".join(novas)})

    final = (pasta / rel).read_text(encoding="utf-8", errors="replace")
    assert "EDICAO-MINHA" in final, "a minha intencao tinha de ser preservada"
    assert "<<<<<<<" not in final


def test_edicao_longe_do_que_eles_mudaram_junta_sozinho(versoes, extrair):
    """No mesmo arquivo que eles alteraram, mas em outro ponto: junta sem perguntar."""
    base_v, nova_v = versoes[-2], versoes[-1]
    base_dir, novo_dir = extrair(base_v, "longe-base"), extrair(nova_v, "longe-novo")
    rel, _ = _linha_que_eles_mudaram(base_dir, novo_dir)

    pasta = extrair(base_v, "longe")
    original = (pasta / rel).read_text(encoding="utf-8", errors="replace")
    (pasta / rel).write_text(f"# NOTA-NO-TOPO\n{original}", encoding="utf-8")

    r = reconcile.preparar(pasta, GRUPO, ARTEFATO, base_v, nova_v)
    reconcile.aplicar(r, pasta)
    final = (pasta / rel).read_text(encoding="utf-8", errors="replace")

    assert rel in r.juntados, "mesmo arquivo, pontos distintos: devia juntar"
    assert "NOTA-NO-TOPO" in final
