"""Cenarios da API: reconciliacao com o git como base, volume real e ida e volta.

O lado da API tem uma diferenca importante em relacao ao RAML: a base nao vem do cache do
Maven, vem do ultimo commit. Isso muda o que e "meu" e o que "veio de fora", e cria um caso
que o RAML nao tem — arquivo novo, ainda nao versionado, sem base nenhuma.

Os cenarios cobertos aqui:

    - scaffold do Studio adicionando flows a um application.xml grande
    - eu e o Studio mexendo no mesmo arquivo, em pontos diferentes e no mesmo ponto
    - arquivo que so existe de um lado, em cada direcao
    - arquivo sem base no git (nao versionado) divergindo
    - ciclo completo: parastudio -> mexer no Studio -> pararepo -> mexer aqui -> parastudio
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from mule_bridge import reconcile
from mule_bridge.config import BridgeConfig, ProjectPair
from mule_bridge.sync import Direction, sync_all

IGNORAR = {".git", "target", ".mule", ".settings"}


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.safecrlf=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _application_xml(flows: int, *, marca: str = "") -> str:
    """Um application.xml com muitos flows, como o real (139 flows no leilao)."""
    corpo = "\n".join(
        f'  <flow name="get-item-{i}">\n'
        f'    <logger message="item {i}"/>\n'
        f"  </flow>"
        for i in range(flows)
    )
    extra = f"\n  <!-- {marca} -->" if marca else ""
    return f'<?xml version="1.0" encoding="UTF-8"?>\n<mule>{extra}\n{corpo}\n</mule>\n'


@pytest.fixture
def projeto(tmp_path):
    """Um repo git com a API commitada, e uma copia representando o lado do Studio."""
    repo = tmp_path / "repo"
    api = repo / "leilao-api" / "src" / "main" / "mule"
    api.mkdir(parents=True)
    (api / "application.xml").write_text(_application_xml(40), encoding="utf-8")
    (api / "services").mkdir()
    (api / "services" / "leilao.xml").write_text(
        '<?xml version="1.0"?>\n<mule>\n  <sub-flow name="calcula"/>\n</mule>\n',
        encoding="utf-8",
    )

    _git(repo, "init", "-q")
    _git(repo, "config", "user.email", "t@t")
    _git(repo, "config", "user.name", "t")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "base")

    studio = tmp_path / "studio" / "detran-leilao"
    studio.mkdir(parents=True)
    import shutil

    shutil.copytree(repo / "leilao-api" / "src", studio / "src")
    return {"repo": repo, "local": repo / "leilao-api", "studio": studio}


def _rec(projeto):
    return reconcile.reconciliar_com_git(projeto["local"], projeto["studio"], IGNORAR)


# --- Scaffold: o caso que motivou o `pararepo api` --------------------------------


def test_scaffold_adiciona_flows_num_arquivo_grande(projeto):
    """O Studio roda o scaffold e o application.xml volta com flows novos."""
    novo = _application_xml(40).replace(
        "</mule>", '  <flow name="post-lance-gerado"/>\n</mule>'
    )
    (projeto["studio"] / "src" / "main" / "mule" / "application.xml").write_text(
        novo, encoding="utf-8"
    )

    r = _rec(projeto)
    reconcile.aplicar(r, projeto["local"])
    final = (projeto["local"] / "src" / "main" / "mule" / "application.xml").read_text(
        encoding="utf-8"
    )

    assert r.limpo
    assert "post-lance-gerado" in final
    assert final.count("<flow ") == 41, "os 40 originais continuam la"


def test_scaffold_e_minha_edicao_em_pontos_distintos(projeto):
    """Eu mexo no topo do arquivo, o scaffold acrescenta no fim: os dois sobrevivem.

    Este e o cenario de risco que faltava cobrir — o mesmo arquivo grande editado dos dois
    lados, que era onde o bug de perda de dados do RAML tinha aparecido.
    """
    rel = "src/main/mule/application.xml"
    (projeto["local"] / rel).write_text(
        _application_xml(40, marca="minha nota no topo"), encoding="utf-8"
    )
    (projeto["studio"] / rel).write_text(
        _application_xml(40).replace("</mule>", '  <flow name="scaffold-novo"/>\n</mule>'),
        encoding="utf-8",
    )

    r = _rec(projeto)
    reconcile.aplicar(r, projeto["local"])
    final = (projeto["local"] / rel).read_text(encoding="utf-8")

    assert r.limpo, f"conflitos: {[c.caminho for c in r.conflitos]}"
    assert "minha nota no topo" in final, "minha edicao nao pode ser perdida"
    assert "scaffold-novo" in final, "o que o Studio gerou tem de entrar"
    assert final.count("<flow ") == 41


def test_mesma_linha_nos_dois_lados_da_api_conflita(projeto):
    """Mesmo ponto, textos diferentes: nada e escrito, como no RAML."""
    rel = "src/main/mule/services/leilao.xml"
    (projeto["local"] / rel).write_text(
        '<?xml version="1.0"?>\n<mule>\n  <sub-flow name="calcula-local"/>\n</mule>\n',
        encoding="utf-8",
    )
    (projeto["studio"] / rel).write_text(
        '<?xml version="1.0"?>\n<mule>\n  <sub-flow name="calcula-studio"/>\n</mule>\n',
        encoding="utf-8",
    )
    antes = (projeto["local"] / rel).read_text(encoding="utf-8")

    r = _rec(projeto)

    assert [c.caminho for c in r.conflitos] == [rel]
    with pytest.raises(reconcile.ReconcileError):
        reconcile.aplicar(r, projeto["local"])
    assert (projeto["local"] / rel).read_text(encoding="utf-8") == antes


def test_muitos_arquivos_de_servico_mudando_de_uma_vez(projeto):
    """O leilao tem a logica espalhada em varios services/*.xml. Volume de arquivos."""
    for i in range(15):
        (projeto["studio"] / "src" / "main" / "mule" / "services" / f"s{i}.xml").write_text(
            f'<?xml version="1.0"?>\n<mule>\n  <sub-flow name="s{i}"/>\n</mule>\n',
            encoding="utf-8",
        )

    r = _rec(projeto)
    reconcile.aplicar(r, projeto["local"])

    assert len(r.so_deles) == 15
    assert r.limpo
    for i in range(15):
        assert (projeto["local"] / "src" / "main" / "mule" / "services" / f"s{i}.xml").is_file()


# --- Arquivos que existem so de um lado ------------------------------------------


def test_arquivo_so_meu_nao_e_apagado(projeto):
    """Criei um arquivo aqui que o Studio nao tem: ele fica."""
    rel = "src/main/mule/services/meu-novo.xml"
    (projeto["local"] / rel).write_text("<mule/>\n", encoding="utf-8")

    r = _rec(projeto)
    reconcile.aplicar(r, projeto["local"])

    assert rel in r.so_meus
    assert (projeto["local"] / rel).is_file()


def test_arquivo_nao_versionado_divergente_vira_conflito(projeto):
    """Sem base no git, nao ha como saber quem mudou o que — entao nao decidimos.

    Caso que so existe do lado da API: no RAML a base vem sempre do cache do Maven.
    """
    rel = "src/main/mule/services/sem-base.xml"
    (projeto["local"] / rel).write_text("<mule>local</mule>\n", encoding="utf-8")
    (projeto["studio"] / rel).write_text("<mule>studio</mule>\n", encoding="utf-8")

    r = _rec(projeto)

    assert [c.caminho for c in r.conflitos] == [rel]
    c = r.conflitos[0]
    assert c.base == "", "nao havia base"
    assert "local" in c.meu and "studio" in c.novo


def test_arquivo_apagado_no_studio_permanece_aqui(projeto):
    """O Studio nao tem mais o arquivo. Nao apagamos o do repo por conta propria."""
    rel = "src/main/mule/services/leilao.xml"
    (projeto["studio"] / rel).unlink()

    r = _rec(projeto)
    reconcile.aplicar(r, projeto["local"])

    assert rel in r.so_meus
    assert (projeto["local"] / rel).is_file(), "apagar aqui teria de ser pedido explicito"


# --- Ida e volta encadeada -------------------------------------------------------


def test_ciclo_completo_ida_e_volta_duas_vezes(projeto, tmp_path):
    """parastudio -> mexo no Studio -> pararepo -> mexo aqui -> parastudio.

    O ciclo inteiro, para garantir que nada se degrada a cada volta: o sync nao pode
    introduzir diferenca espuria que faca a proxima reconciliacao achar que houve mudanca.
    """
    cfg = BridgeConfig(
        work_root=projeto["repo"],
        studio_root=tmp_path / "studio",
        api=ProjectPair("leilao-api", "detran-leilao"),
        raml=None,
    )
    rel = "src/main/mule/application.xml"

    # 1. mando o que tenho para o Studio
    sync_all(cfg, Direction.PUSH, only="api")
    assert (projeto["studio"] / rel).read_text(encoding="utf-8") == (
        projeto["local"] / rel
    ).read_text(encoding="utf-8")

    # 2. o Studio gera um flow
    (projeto["studio"] / rel).write_text(
        _application_xml(40).replace("</mule>", '  <flow name="do-studio"/>\n</mule>'),
        encoding="utf-8",
    )

    # 3. traz de volta reconciliando, e commita como nova base
    r = _rec(projeto)
    assert r.limpo
    reconcile.aplicar(r, projeto["local"])
    _git(projeto["repo"], "add", "-A")
    _git(projeto["repo"], "commit", "-q", "-m", "scaffold")

    # 4. agora eu edito aqui
    atual = (projeto["local"] / rel).read_text(encoding="utf-8")
    (projeto["local"] / rel).write_text(
        atual.replace("<mule>", "<mule>\n  <!-- minha nota -->"), encoding="utf-8"
    )

    # 5. e mando de novo
    sync_all(cfg, Direction.PUSH, only="api")
    no_studio = (projeto["studio"] / rel).read_text(encoding="utf-8")

    assert "do-studio" in no_studio, "o que o Studio gerou sobreviveu ao ciclo"
    assert "minha nota" in no_studio, "e a minha edicao chegou la"

    # 6. uma reconciliacao agora nao deve achar mudanca nenhuma
    depois = _rec(projeto)
    assert depois.limpo
    assert depois.juntados == [] and depois.so_deles == [], (
        "o ciclo nao pode deixar diferenca residual"
    )


def test_pararepo_duas_vezes_seguidas_e_estavel(projeto):
    """Rodar de novo sem nada ter mudado nao pode reescrever nem inventar diferenca."""
    (projeto["studio"] / "src" / "main" / "mule" / "novo.xml").write_text(
        "<mule/>\n", encoding="utf-8"
    )

    primeira = _rec(projeto)
    reconcile.aplicar(primeira, projeto["local"])
    segunda = _rec(projeto)
    escritos = reconcile.aplicar(segunda, projeto["local"])

    assert escritos == 0, "a segunda passada nao deve escrever nada"
    assert segunda.limpo


# --- Dois commits: o de fora separado do meu -------------------------------------


def test_dois_commits_com_edicao_local_no_mesmo_lote(projeto):
    """O scaffold entra num commit; a minha edicao fica no working tree para eu revisar."""
    rel_meu = "src/main/mule/services/leilao.xml"
    (projeto["local"] / rel_meu).write_text(
        '<?xml version="1.0"?>\n<mule>\n  <sub-flow name="calcula"/>\n  <!-- meu -->\n</mule>\n',
        encoding="utf-8",
    )
    (projeto["studio"] / "src" / "main" / "mule" / "gerado.xml").write_text(
        "<mule/>\n", encoding="utf-8"
    )

    r = _rec(projeto)
    escritos, commitou = reconcile.aplicar_em_dois_commits(
        r, projeto["local"], projeto["repo"], "leilao-api", "chore: scaffold do Studio"
    )

    assert commitou and escritos >= 1
    log = _git(projeto["repo"], "log", "--oneline").stdout
    assert "scaffold do Studio" in log

    sujo = _git(projeto["repo"], "status", "--porcelain").stdout
    assert "leilao.xml" in sujo, "a minha edicao tem de ficar visivel, sem commit"
    assert "gerado.xml" not in sujo, "o que veio de fora ja foi commitado"
