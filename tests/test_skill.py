"""A skill viaja no pacote, e o `init` a instala — instalar a ferramenta e um passo so."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from mule_bridge import cli
from mule_bridge.cli import app

runner = CliRunner()

REPO = Path(__file__).resolve().parent.parent


def test_a_copia_do_repo_nao_divergiu_da_do_pacote():
    """`.claude/skills/ponte/` e a do pacote sao o mesmo texto, em dois lugares.

    A do pacote e a que o `init` instala; a do repo e a que o Claude Code le quando a sessao
    roda aqui dentro. Editar uma e esquecer a outra faz a ferramenta ensinar duas coisas
    diferentes — este teste e o que impede isso de passar.
    """
    no_pacote = cli.SKILL_NO_PACOTE
    no_repo = REPO / ".claude" / "skills" / "ponte" / "SKILL.md"

    assert no_pacote.is_file(), f"a skill do pacote nao esta em {no_pacote}"
    assert no_repo.is_file(), f"a skill do repo nao esta em {no_repo}"
    assert no_pacote.read_text(encoding="utf-8") == no_repo.read_text(encoding="utf-8"), (
        "as duas copias da skill divergiram — copie a do pacote para .claude/skills/ponte/"
    )


def test_instala_a_skill_quando_ha_claude(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".claude").mkdir()

    destino = cli._instalar_skill()

    assert destino == tmp_path / ".claude" / "skills" / "ponte" / "SKILL.md"
    assert destino.read_text(encoding="utf-8") == cli.SKILL_NO_PACOTE.read_text(
        encoding="utf-8"
    )


def test_sobrescreve_a_skill_que_estiver_la(tmp_path, monkeypatch):
    """A skill acompanha a versao da CLI: uma velha faz o `/ponte` sugerir comando que morreu."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    antiga = tmp_path / ".claude" / "skills" / "ponte" / "SKILL.md"
    antiga.parent.mkdir(parents=True)
    antiga.write_text("versao antiga, de outro contrato\n", encoding="utf-8")

    cli._instalar_skill()

    assert "versao antiga" not in antiga.read_text(encoding="utf-8")


def test_sem_claude_nao_instala_nem_comenta(tmp_path, monkeypatch):
    """Quem nao usa Claude Code nao precisa ouvir sobre skill."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    assert cli._instalar_skill() is None
    assert not (tmp_path / ".claude").exists()


def test_erro_ao_gravar_nao_derruba_o_init(tmp_path, monkeypatch):
    """O trabalho do `init` e o pareamento; um extra nao pode fazer o comando falhar."""
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
    (tmp_path / ".claude").mkdir()

    def _nega(*args, **kwargs):
        raise OSError("perfil gerenciado, sem escrita")

    monkeypatch.setattr("mule_bridge.cli.shutil.copyfile", _nega)

    assert cli._instalar_skill() is None  # nao levanta


def test_o_init_instala_a_skill_e_diz_onde(workspace, tmp_path, monkeypatch):
    """O caminho que o usuario percorre: um `init`, e a skill esta pronta."""
    casa = tmp_path / "casa"
    (casa / ".claude").mkdir(parents=True)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: casa))

    result = runner.invoke(
        app,
        [
            "init",
            "-w",
            str(workspace["work"]),
            "-s",
            str(workspace["studio"]),
            "--api",
            "pedidos-api",
            "--raml",
            "pedidos-raml",
            "--studio-api",
            "studio-pedidos",
            "--studio-raml",
            "studio-pedidos-raml",
        ],
        input="",
    )

    assert result.exit_code == 0, result.output
    assert (casa / ".claude" / "skills" / "ponte" / "SKILL.md").is_file()
    assert "Skill do Claude Code instalada" in result.output, result.output
