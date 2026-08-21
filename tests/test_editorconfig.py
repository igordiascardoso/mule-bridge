"""Config de editor para que as edicoes em repos aninhados aparecam no painel."""

from __future__ import annotations

import json

from mule_bridge import editorconfig


def _repo(pasta):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / ".git").mkdir()
    return pasta


def test_detecta_repos_aninhados(tmp_path):
    _repo(tmp_path / "pedidos-api")
    _repo(tmp_path / "pedidos-web")
    (tmp_path / "pedidos-raml").mkdir()  # sem .git

    assert editorconfig.repos_aninhados(tmp_path) == ["pedidos-api", "pedidos-web"]


def test_sem_repo_aninhado_nao_precisa_config(tmp_path):
    (tmp_path / "pedidos-raml").mkdir()

    assert editorconfig.precisa_config(tmp_path) is False


def test_com_repo_aninhado_precisa_config(tmp_path):
    _repo(tmp_path / "pedidos-api")

    assert editorconfig.precisa_config(tmp_path) is True


def test_escreve_as_chaves(tmp_path):
    _repo(tmp_path / "pedidos-api")

    destino = editorconfig.escrever(tmp_path)
    cfg = json.loads(destino.read_text(encoding="utf-8"))

    assert cfg["git.repositoryScanMaxDepth"] == 2
    assert cfg["git.openRepositoryInParentFolders"] == "always"
    assert editorconfig.precisa_config(tmp_path) is False, "nao deve pedir de novo"


def test_preserva_o_que_o_usuario_ja_tinha(tmp_path):
    _repo(tmp_path / "pedidos-api")
    vsc = tmp_path / ".vscode"
    vsc.mkdir()
    (vsc / "settings.json").write_text(
        json.dumps({"workbench.colorTheme": "Meu Tema", "git.repositoryScanMaxDepth": 5}),
        encoding="utf-8",
    )

    cfg = json.loads(editorconfig.escrever(tmp_path).read_text(encoding="utf-8"))

    assert cfg["workbench.colorTheme"] == "Meu Tema", "nao pode perder config do usuario"
    assert cfg["git.repositoryScanMaxDepth"] == 5, "nem sobrescrever um valor escolhido"


def test_json_invalido_nao_quebra(tmp_path):
    _repo(tmp_path / "pedidos-api")
    vsc = tmp_path / ".vscode"
    vsc.mkdir()
    (vsc / "settings.json").write_text("{ isso nao e json", encoding="utf-8")

    cfg = json.loads(editorconfig.escrever(tmp_path).read_text(encoding="utf-8"))

    assert cfg["git.repositoryScanMaxDepth"] == 2
