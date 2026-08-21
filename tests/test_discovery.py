from __future__ import annotations

from pathlib import Path

from mule_bridge import discovery


def _casa(monkeypatch, pasta: Path) -> None:
    """Aponta `~` e a busca para uma pasta de teste.

    `Path("~").expanduser()` le do ambiente, nao de `Path.home()` — trocar so o metodo
    deixaria a busca varrendo a maquina de verdade.
    """
    monkeypatch.setenv("USERPROFILE", str(pasta))
    monkeypatch.setenv("HOME", str(pasta))
    monkeypatch.setattr(discovery, "RAIZES_DE_BUSCA", ("~",))


def test_encontra_api_e_raml_como_filhos_diretos(workspace):
    found = discovery.find_projects(workspace["work"])
    assert {(p.name, p.kind) for p in found} == {
        ("pedidos-api", "api"),
        ("pedidos-raml", "raml"),
    }


def test_sugere_raml_irmao_pelo_prefixo(workspace):
    found = discovery.find_projects(workspace["work"])
    api = next(p for p in found if p.kind == "api")
    assert discovery.guess_raml_sibling(api, found).name == "pedidos-raml"


def test_pasta_inexistente_nao_quebra(tmp_path):
    assert discovery.find_projects(tmp_path / "nada") == []


# --- Busca do workspace do Studio ------------------------------------------------


def test_reconhece_workspace_pelo_metadata(tmp_path):
    """O `.metadata` e criado pelo Eclipse: e a marca mais confiavel de um workspace."""
    ws = tmp_path / "qualquer-nome"
    (ws / ".metadata").mkdir(parents=True)

    assert discovery.parece_workspace(ws)


def test_reconhece_workspace_por_conter_projeto_mule(tmp_path):
    """Sem `.metadata` (workspace movido de lugar), um projeto Mule dentro basta."""
    ws = tmp_path / "ws"
    projeto = ws / "minha-api" / "src" / "main" / "mule"
    projeto.mkdir(parents=True)
    (ws / "minha-api" / "pom.xml").write_text("<project/>", encoding="utf-8")

    assert discovery.parece_workspace(ws)


def test_pasta_comum_nao_e_workspace(tmp_path):
    """Nao pode dar falso positivo em qualquer diretorio."""
    comum = tmp_path / "Downloads"
    (comum / "coisas").mkdir(parents=True)

    assert not discovery.parece_workspace(comum)


def test_arquivo_nao_e_workspace(tmp_path):
    arquivo = tmp_path / "algo.txt"
    arquivo.write_text("x", encoding="utf-8")

    assert not discovery.parece_workspace(arquivo)


def test_encontra_workspace_no_caminho_padrao(tmp_path, monkeypatch):
    """O caso da instalacao normal: `~/AnypointStudio/studio-workspace`."""
    casa = tmp_path / "casa"
    ws = casa / "AnypointStudio" / "studio-workspace"
    (ws / ".metadata").mkdir(parents=True)
    _casa(monkeypatch, casa)

    achados = discovery.find_studio_workspaces()

    assert ws in achados


def test_encontra_workspace_com_nome_fora_do_padrao(tmp_path, monkeypatch):
    """Regressao: antes so tres caminhos fixos eram testados, e nomes assim ficavam de fora.

    Quem instalou o Studio noutro drive, ou nomeou o workspace do seu jeito, nao aparecia
    na lista — e a unica saida era descobrir a flag `--studio-root`.
    """
    casa = tmp_path / "casa"
    ws = casa / "AnypointStudio-workspace-do-trabalho"
    (ws / ".metadata").mkdir(parents=True)
    _casa(monkeypatch, casa)

    achados = discovery.find_studio_workspaces()

    assert ws in achados


def test_encontra_workspace_dentro_de_pasta_do_studio(tmp_path, monkeypatch):
    """`AnypointStudio/<nome-qualquer>/` — o workspace um nivel abaixo."""
    casa = tmp_path / "casa"
    ws = casa / "AnypointStudio" / "ws-do-cliente"
    (ws / ".metadata").mkdir(parents=True)
    _casa(monkeypatch, casa)

    assert ws in discovery.find_studio_workspaces()


def test_nao_repete_o_mesmo_caminho(tmp_path, monkeypatch):
    """O caminho padrao e a busca por nome acham o mesmo lugar: nao pode duplicar."""
    casa = tmp_path / "casa"
    ws = casa / "AnypointStudio" / "studio-workspace"
    (ws / ".metadata").mkdir(parents=True)
    _casa(monkeypatch, casa)

    achados = discovery.find_studio_workspaces()

    assert len(achados) == len(set(achados))


def test_sem_workspace_devolve_lista_vazia(tmp_path, monkeypatch):
    """Nada encontrado nao e erro: o `init` pede o caminho ao usuario."""
    casa = tmp_path / "vazia"
    casa.mkdir()
    _casa(monkeypatch, casa)

    assert discovery.find_studio_workspaces() == []


def test_pasta_anypoint_sem_workspace_dentro_nao_entra(tmp_path, monkeypatch):
    """A pasta de instalacao do Studio (com o executavel) nao e um workspace."""
    casa = tmp_path / "casa"
    instalacao = casa / "AnypointStudio"
    (instalacao / "plugins").mkdir(parents=True)
    (instalacao / "AnypointStudio.exe").write_text("x", encoding="utf-8")
    _casa(monkeypatch, casa)

    assert discovery.find_studio_workspaces() == []
