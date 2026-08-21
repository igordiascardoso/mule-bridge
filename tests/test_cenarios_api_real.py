"""Reconciliacao da API contra o projeto Mule real, quando ele existe nesta maquina.

O `application.xml` do leilao tem ~1500 linhas e 139 flows, e a logica se espalha por 27
arquivos em `src/main/mule/`. Nenhum fixture de teste reproduz isso: um arquivo de tres
linhas junta facil, um de mil e onde aparece o problema de verdade.

O cenario montado aqui e o de risco real do `pararepo api`: o Studio roda o scaffold e
acrescenta flows, e **eu editei o mesmo arquivo** na mesma rodada. E onde uma edicao local
poderia desaparecer em silencio.

Nada e escrito no projeto do usuario: tudo acontece numa copia em pasta temporaria, com um
git proprio. Os testes sao pulados quando o projeto nao esta presente.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

from mule_bridge import reconcile

#: Projeto real usado como massa de teste. Ajustar aqui adapta o arquivo a outra maquina.
REPO_REAL = Path("CAMINHO-REMOVIDO")
STUDIO_REAL = Path("CAMINHO-REMOVIDO")

IGNORAR = {".git", "target", ".mule", ".settings", "pom.xml", ".classpath", ".project"}

pytestmark = pytest.mark.skipif(
    not (REPO_REAL / "src" / "main" / "mule").is_dir(),
    reason="projeto Mule real nao esta presente nesta maquina",
)


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.safecrlf=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


@pytest.fixture
def copia(tmp_path):
    """Copia isolada do projeto real, com git proprio e um lado "Studio" espelhado."""
    sem_lixo = shutil.ignore_patterns(".git", "target", ".mule", ".settings")

    local = tmp_path / "api"
    shutil.copytree(REPO_REAL, local, ignore=sem_lixo)
    _git(local, "init", "-q")
    _git(local, "config", "user.email", "t@t")
    _git(local, "config", "user.name", "t")
    _git(local, "add", "-A")
    _git(local, "commit", "-q", "-m", "base")

    studio = tmp_path / "studio"
    shutil.copytree(local, studio, ignore=sem_lixo)
    return {"local": local, "studio": studio}


def _app(raiz: Path) -> Path:
    return raiz / "src" / "main" / "mule" / "application.xml"


def _scaffold(caminho: Path, quantos: int = 8) -> None:
    """Simula o scaffold do Studio: flows novos acrescentados no fim do arquivo."""
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    corte = texto.rfind("</mule>")
    novos = "".join(
        f'    <flow name="scaffold-novo-{i}">\n'
        f'        <logger message="gerado"/>\n'
        f"    </flow>\n"
        for i in range(quantos)
    )
    caminho.write_text(texto[:corte] + novos + texto[corte:], encoding="utf-8")


def _nota_no_topo(caminho: Path, marca: str = "MINHA-NOTA-NO-TOPO") -> None:
    texto = caminho.read_text(encoding="utf-8", errors="replace")
    fim_tag = texto.index(">", texto.index("<mule")) + 1
    caminho.write_text(
        texto[:fim_tag] + f"\n    <!-- {marca} -->" + texto[fim_tag:], encoding="utf-8"
    )


def test_o_projeto_real_tem_o_volume_que_justifica_este_arquivo(copia):
    """Guarda-chuva: se o projeto encolher, os testes abaixo perdem o sentido."""
    texto = _app(copia["local"]).read_text(encoding="utf-8", errors="replace")

    assert len(texto.splitlines()) > 500, "esperado um application.xml grande"
    assert texto.count("<flow ") > 50, "esperado muitos flows"


def test_scaffold_e_minha_edicao_no_mesmo_arquivo_grande(copia):
    """O cenario de risco do `pararepo api`, no arquivo real de 1500 linhas."""
    antes = _app(copia["local"]).read_text(encoding="utf-8", errors="replace")
    flows_antes = antes.count("<flow ")

    _scaffold(_app(copia["studio"]))
    _nota_no_topo(_app(copia["local"]))

    r = reconcile.reconciliar_com_git(copia["local"], copia["studio"], IGNORAR)
    assert r.limpo, f"nao devia conflitar: {[c.caminho for c in r.conflitos]}"
    reconcile.aplicar(r, copia["local"])

    final = _app(copia["local"]).read_text(encoding="utf-8", errors="replace")
    assert "MINHA-NOTA-NO-TOPO" in final, "a edicao local foi perdida"
    assert final.count("scaffold-novo-") == 8, "os flows do scaffold nao entraram"
    assert final.count("<flow ") == flows_antes + 8, "algum flow original desapareceu"
    assert "<<<<<<<" not in final


def test_nenhum_arquivo_do_projeto_fica_com_marcador(copia):
    """Varredura em todos os 27 arquivos: marcador de merge quebraria o deploy."""
    _scaffold(_app(copia["studio"]))
    _nota_no_topo(_app(copia["local"]))

    r = reconcile.reconciliar_com_git(copia["local"], copia["studio"], IGNORAR)
    reconcile.aplicar(r, copia["local"])

    sujos = [
        str(p.relative_to(copia["local"]))
        for p in copia["local"].rglob("*.xml")
        if p.is_file() and "<<<<<<<" in p.read_text(encoding="utf-8", errors="replace")
    ]
    assert sujos == [], f"marcador de merge escrito em {sujos}"


def test_scaffold_em_varios_arquivos_de_servico(copia):
    """O leilao espalha a logica em services/*.xml — o scaffold mexe em varios de uma vez."""
    servicos = sorted((copia["studio"] / "src" / "main" / "mule").rglob("*.xml"))[:6]
    assert len(servicos) >= 3, "esperado varios arquivos de logica"

    for p in servicos:
        texto = p.read_text(encoding="utf-8", errors="replace")
        corte = texto.rfind("</mule>")
        if corte < 0:
            continue
        p.write_text(
            texto[:corte] + '    <sub-flow name="gerado"/>\n' + texto[corte:], encoding="utf-8"
        )

    r = reconcile.reconciliar_com_git(copia["local"], copia["studio"], IGNORAR)
    reconcile.aplicar(r, copia["local"])

    for p in servicos:
        rel = p.relative_to(copia["studio"])
        conteudo = (copia["local"] / rel).read_text(encoding="utf-8", errors="replace")
        assert "gerado" in conteudo, f"{rel} nao recebeu o que o Studio gerou"


def test_sem_mudanca_nenhuma_nao_escreve_nada(copia):
    """Rodar com os dois lados iguais tem de ser um no-op completo."""
    r = reconcile.reconciliar_com_git(copia["local"], copia["studio"], IGNORAR)
    escritos = reconcile.aplicar(r, copia["local"])

    assert escritos == 0
    assert r.limpo
    assert _git(copia["local"], "status", "--porcelain").stdout == ""


def test_conflito_real_no_application_xml_nao_escreve(copia):
    """Os dois lados mexendo no mesmo ponto do arquivo real: recusa sem tocar no disco."""
    _nota_no_topo(_app(copia["local"]), "VERSAO-LOCAL")
    _nota_no_topo(_app(copia["studio"]), "VERSAO-STUDIO")
    antes = _app(copia["local"]).read_text(encoding="utf-8", errors="replace")

    r = reconcile.reconciliar_com_git(copia["local"], copia["studio"], IGNORAR)

    assert not r.limpo, "mesma posicao com textos diferentes tem de conflitar"
    with pytest.raises(reconcile.ReconcileError):
        reconcile.aplicar(r, copia["local"])
    assert _app(copia["local"]).read_text(encoding="utf-8", errors="replace") == antes


def test_dois_commits_no_projeto_real(copia):
    """No volume real: o scaffold vira commit e a minha edicao fica no working tree."""
    _scaffold(_app(copia["studio"]))
    gerado = copia["studio"] / "src" / "main" / "mule" / "flow-novo-do-studio.xml"
    gerado.write_text('<?xml version="1.0"?>\n<mule/>\n', encoding="utf-8")

    servico = sorted((copia["local"] / "src" / "main" / "mule").glob("**/*.xml"))
    meu = next(p for p in servico if p.name != "application.xml")
    meu.write_text(
        meu.read_text(encoding="utf-8", errors="replace") + "\n<!-- meu ajuste -->\n",
        encoding="utf-8",
    )

    r = reconcile.reconciliar_com_git(copia["local"], copia["studio"], IGNORAR)
    _escritos, commitou = reconcile.aplicar_em_dois_commits(
        r, copia["local"], copia["local"], ".", "chore: scaffold do Studio"
    )

    assert commitou
    assert "scaffold do Studio" in _git(copia["local"], "log", "--oneline").stdout
    sujo = _git(copia["local"], "status", "--porcelain").stdout
    assert meu.name in sujo, "a minha edicao tem de ficar visivel para revisao"
