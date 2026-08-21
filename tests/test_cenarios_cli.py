"""Os seis comandos pela CLI, como o usuario os digita, num repositorio git de verdade.

O resto da suite testa as funcoes. Aqui testamos o caminho inteiro: `ponte pararepo raml`,
com git, cache do Maven simulado, pom.xml dos dois lados e a saida que o usuario le. E onde
aparecem os erros de integracao — flag que nao chega na funcao, mensagem que engana,
comando que grava sem `--aplicar`.
"""

from __future__ import annotations

import subprocess
import zipfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from mule_bridge import config, pomrewrite
from mule_bridge.cli import app
from mule_bridge.config import BridgeConfig, ProjectPair

runner = CliRunner()

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

BASE_RAML = "#%RAML 1.0\ntitle: Pedidos\nversion: v1\ntypes:\n  Pedido:\n  Item:\n  Fim:\n"


def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-c", "core.safecrlf=false", *args],
        cwd=repo,
        capture_output=True,
        text=True,
        check=True,
    )


def _zip(m2: Path, versao: str, arquivos: dict[str, str]) -> None:
    destino = m2 / "grupo" / "pedidos" / versao / f"pedidos-{versao}-raml.zip"
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as z:
        for rel, conteudo in arquivos.items():
            z.writestr(rel, conteudo)


@pytest.fixture
def projeto(tmp_path, monkeypatch):
    """Repo git com API + RAML na 1.1.54, Studio na 1.1.55, cache com as duas."""
    work, studio = tmp_path / "repo", tmp_path / "ws"
    m2 = tmp_path / "casa" / ".m2" / "repository"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path / "casa"))

    api = work / "pedidos-api" / "src" / "main" / "mule"
    api.mkdir(parents=True)
    (api / "application.xml").write_text("<mule/>\n", encoding="utf-8")
    (work / "pedidos-api" / "pom.xml").write_text(POM.format(versao="1.1.54"), encoding="utf-8")

    raml = work / "pedidos-raml"
    raml.mkdir()
    (raml / "api.raml").write_text(BASE_RAML, encoding="utf-8")

    studio_api = studio / "studio-pedidos" / "src" / "main" / "mule"
    studio_api.mkdir(parents=True)
    (studio_api / "application.xml").write_text("<mule/>\n", encoding="utf-8")
    (studio / "studio-pedidos" / "pom.xml").write_text(
        POM.format(versao="1.1.55"), encoding="utf-8"
    )

    _zip(m2, "1.1.54", {"api.raml": BASE_RAML})
    _zip(
        m2,
        "1.1.55",
        {
            "api.raml": BASE_RAML.replace("  Item:\n", "  Item:\n    novo: string\n"),
            "domain/captcha.raml": "#%RAML 1.0 DataType\ntype: object\n",
        },
    )

    _git(work, "init", "-q")
    _git(work, "config", "user.email", "t@t")
    _git(work, "config", "user.name", "t")
    _git(work, "add", "-A")
    _git(work, "commit", "-q", "-m", "base")

    config.save(
        BridgeConfig(
            work_root=work,
            studio_root=studio,
            api=ProjectPair("pedidos-api", "studio-pedidos"),
            raml=ProjectPair("pedidos-raml", "nenhuma"),
        )
    )
    return {"work": work, "studio": studio, "raml": raml}


def _rodar(projeto, *args):
    return runner.invoke(app, [*args, "-w", str(projeto["work"])])


# --- pararepo raml: previa e aplicacao -------------------------------------------


def test_pararepo_raml_sem_aplicar_nao_escreve(projeto):
    """A previa e previa: nenhum byte muda no disco."""
    antes = (projeto["raml"] / "api.raml").read_text(encoding="utf-8")

    r = _rodar(projeto, "pararepo", "raml")

    assert r.exit_code == 0, r.output
    assert (projeto["raml"] / "api.raml").read_text(encoding="utf-8") == antes
    assert not (projeto["raml"] / "domain" / "captcha.raml").exists()


def test_pararepo_raml_com_aplicar_escreve_e_commita(projeto):
    """Com a flag, aplica: arquivo novo entra e o que veio de fora vai para um commit."""
    r = _rodar(projeto, "pararepo", "raml", "--aplicar")

    assert r.exit_code == 0, r.output
    assert (projeto["raml"] / "domain" / "captcha.raml").is_file()
    log = _git(projeto["work"], "log", "--oneline").stdout
    assert "1.1.55" in log, f"a base do Exchange devia ter virado commit; log:\n{log}"


def test_pararepo_raml_preserva_edicao_local(projeto):
    """O ponto central: minha edicao continua la depois de trazer a versao nova."""
    caminho = projeto["raml"] / "api.raml"
    caminho.write_text(
        BASE_RAML.replace("version: v1", "version: v1\n# MINHA-NOTA"), encoding="utf-8"
    )

    r = _rodar(projeto, "pararepo", "raml", "--aplicar")

    assert r.exit_code == 0, r.output
    final = caminho.read_text(encoding="utf-8")
    assert "MINHA-NOTA" in final, "a edicao local foi perdida"
    assert "novo: string" in final, "a mudanca do Exchange nao entrou"


def test_pararepo_raml_com_conflito_nao_escreve_e_explica(projeto):
    """Conflito pela CLI: sai sem escrever e diz ao usuario o que fazer."""
    caminho = projeto["raml"] / "api.raml"
    caminho.write_text(
        BASE_RAML.replace("  Item:\n", "  Item:\n    meu: string\n"), encoding="utf-8"
    )
    antes = caminho.read_text(encoding="utf-8")

    r = _rodar(projeto, "pararepo", "raml", "--aplicar")

    assert caminho.read_text(encoding="utf-8") == antes, "nada podia ser escrito"
    assert "<<<<<<<" not in caminho.read_text(encoding="utf-8")
    assert "conflito" in r.output.lower(), f"a saida tem de falar de conflito:\n{r.output}"


def test_pararepo_raml_duas_vezes_e_estavel(projeto):
    """Rodar de novo sem nada novo nao reescreve nem cria commit vazio."""
    _rodar(projeto, "pararepo", "raml", "--aplicar")
    commits_antes = _git(projeto["work"], "log", "--oneline").stdout.count("\n")

    r = _rodar(projeto, "pararepo", "raml", "--aplicar")

    assert r.exit_code == 0, r.output
    assert _git(projeto["work"], "log", "--oneline").stdout.count("\n") == commits_antes


def test_git_status_mostra_so_a_minha_edicao(projeto):
    """A razao de ser dos dois commits: depois da operacao, o diff e so o meu trabalho."""
    (projeto["raml"] / "api.raml").write_text(
        BASE_RAML.replace("version: v1", "version: v1\n# MINHA-NOTA"), encoding="utf-8"
    )

    _rodar(projeto, "pararepo", "raml", "--aplicar")

    sujo = _git(projeto["work"], "status", "--porcelain").stdout
    assert "api.raml" in sujo, "a minha edicao tem de aparecer como mudanca minha"
    assert "captcha.raml" not in sujo, "o que veio do Exchange ja foi commitado"


# --- parastudio raml: liga o systemPath -----------------------------------------


def test_parastudio_raml_aponta_o_pom_do_studio(projeto):
    """Mandar o RAML para o Studio e fazer o pom dele ler a minha pasta."""
    r = _rodar(projeto, "parastudio", "raml")

    assert r.exit_code == 0, r.output
    pom_studio = projeto["studio"] / "studio-pedidos" / "pom.xml"
    assert pomrewrite.has_local_pointer(pom_studio)
    assert str(projeto["raml"]) in pom_studio.read_text(encoding="utf-8")


def test_parastudio_raml_nao_toca_no_pom_do_repo(projeto):
    """E a garantia que protege o build do GitLab."""
    antes = (projeto["work"] / "pedidos-api" / "pom.xml").read_text(encoding="utf-8")

    _rodar(projeto, "parastudio", "raml")

    assert (projeto["work"] / "pedidos-api" / "pom.xml").read_text(encoding="utf-8") == antes


def test_parastudio_raml_nao_cria_pasta_no_workspace(projeto):
    """Regressao: uma versao anterior copiava o RAML e criava pasta que ninguem lia."""
    _rodar(projeto, "parastudio", "raml")

    assert not (projeto["studio"] / "pedidos-raml").exists()
    assert not (projeto["studio"] / "studio-pedidos-raml").exists()


# --- parastudio / pararepo api --------------------------------------------------


def test_parastudio_api_leva_o_codigo(projeto):
    (projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml").write_text(
        '<mule><flow name="meu"/></mule>\n', encoding="utf-8"
    )

    r = _rodar(projeto, "parastudio", "api")

    assert r.exit_code == 0, r.output
    destino = (
        projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    )
    assert "meu" in destino.read_text(encoding="utf-8")


def test_pararepo_api_traz_o_scaffold(projeto):
    (
        projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    ).write_text('<mule><flow name="scaffold"/></mule>\n', encoding="utf-8")

    r = _rodar(projeto, "pararepo", "api", "--aplicar")

    assert r.exit_code == 0, r.output
    local = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    assert "scaffold" in local.read_text(encoding="utf-8")


def test_pararepo_api_sem_aplicar_e_so_previa(projeto):
    """Como no raml, a API tambem exige --aplicar para gravar."""
    (
        projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    ).write_text('<mule><flow name="scaffold"/></mule>\n', encoding="utf-8")
    local = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    antes = local.read_text(encoding="utf-8")

    r = _rodar(projeto, "pararepo", "api")

    assert r.exit_code == 0, r.output
    assert local.read_text(encoding="utf-8") == antes, "sem a flag nao pode escrever"
    assert "previa" in r.output, "e tem de avisar que foi previa"


def test_pararepo_api_nao_altera_o_pom_do_repo(projeto):
    """Trazer a API de volta nao pode mudar como o repo aponta para o RAML."""
    _rodar(projeto, "parastudio", "raml")  # o pom do Studio fica apontando local
    antes = (projeto["work"] / "pedidos-api" / "pom.xml").read_text(encoding="utf-8")

    _rodar(projeto, "pararepo", "api", "--aplicar")

    depois = (projeto["work"] / "pedidos-api" / "pom.xml").read_text(encoding="utf-8")
    assert depois == antes
    assert "systemPath" not in depois
    assert "1.1.54" in depois, "a versao travada do Exchange tem de continuar"


# --- status ---------------------------------------------------------------------


def test_status_nao_altera_nada(projeto):
    def instantaneo():
        saida = {}
        for raiz in (projeto["work"], projeto["studio"]):
            for p in sorted(raiz.rglob("*")):
                if p.is_file() and ".git" not in p.parts:
                    saida[str(p)] = p.read_bytes()
        return saida

    antes = instantaneo()
    r = _rodar(projeto, "status")

    assert r.exit_code == 0, r.output
    assert instantaneo() == antes


def test_status_mostra_o_pareamento(projeto):
    r = _rodar(projeto, "status")

    assert "pedidos-api" in r.output
    assert "studio-pedidos" in r.output


# --- Ciclo completo pela CLI ----------------------------------------------------


def test_ciclo_completo_pela_cli(projeto):
    """raml novo -> parastudio -> scaffold no Studio -> pararepo api, tudo pela CLI."""
    _rodar(projeto, "pararepo", "raml", "--aplicar")
    assert (projeto["raml"] / "domain" / "captcha.raml").is_file()

    _rodar(projeto, "parastudio")
    _rodar(projeto, "parastudio", "raml")

    (
        projeto["studio"] / "studio-pedidos" / "src" / "main" / "mule" / "application.xml"
    ).write_text('<mule><flow name="captcha-gerado"/></mule>\n', encoding="utf-8")

    r = _rodar(projeto, "pararepo", "api", "--aplicar")
    assert r.exit_code == 0, r.output

    local = projeto["work"] / "pedidos-api" / "src" / "main" / "mule" / "application.xml"
    assert "captcha-gerado" in local.read_text(encoding="utf-8")

    pom_repo = (projeto["work"] / "pedidos-api" / "pom.xml").read_text(encoding="utf-8")
    assert "systemPath" not in pom_repo, "o ciclo inteiro nao pode sujar o pom do repo"
    assert pomrewrite.has_local_pointer(projeto["studio"] / "studio-pedidos" / "pom.xml")
