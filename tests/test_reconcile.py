"""Reconciliacao do RAML: base do Exchange + edicoes locais por cima."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from mule_bridge import reconcile
from mule_bridge.reconcile import ReconcileError

BASE = """#%RAML 1.0
title: Leilao
types:
  Leilao:
    properties:
      id: integer
      placa:
        type: string
        description: Placa do veiculo
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


def _reconciliar(dirs):
    return reconcile.reconciliar(dirs["local"], dirs["base"], dirs["novo"], "1.1.54", "1.1.55")


# --- Caso 1: adicoes em pontos diferentes, o git junta sozinho -------------------


def test_adicoes_em_pontos_diferentes_juntam_sem_conflito(dirs):
    meu = BASE + "  Lance:\n    properties:\n      valor: number\n"
    novo = "#%RAML 1.0\ntitle: Leilao (Exchange)\n" + BASE.split("\n", 2)[2]

    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)

    assert r.limpo, [c.caminho for c in r.conflitos]
    final = r.resultado["api.raml"]
    assert "Lance:" in final, "a edicao local tem de sobreviver"
    assert "Leilao (Exchange)" in final, "a mudanca de fora tem de entrar"


def test_endpoint_novo_do_exchange_entra(dirs):
    _escreve(dirs["local"], {"api.raml": BASE})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE, "captcha.raml": "#%RAML 1.0\ntitle: Captcha\n"})

    r = _reconciliar(dirs)

    assert r.limpo
    assert "captcha.raml" in r.so_deles
    assert "Captcha" in r.resultado["captcha.raml"]


def test_arquivo_so_meu_permanece(dirs):
    _escreve(dirs["local"], {"api.raml": BASE, "meu-tipo.raml": "#%RAML 1.0\ntitle: Meu\n"})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE})

    r = _reconciliar(dirs)

    assert r.limpo
    assert "meu-tipo.raml" in r.so_meus
    assert r.resultado["meu-tipo.raml"] == "#%RAML 1.0\ntitle: Meu\n"


def test_edicao_local_sem_mudanca_de_fora_permanece(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE})

    r = _reconciliar(dirs)

    assert r.limpo
    assert "Mercosul" in r.resultado["api.raml"]


# --- Caso 3: os dois mudaram a mesma linha -> conflito, nada e escrito -----------


def test_mesma_linha_alterada_nos_dois_lados_vira_conflito(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    novo = BASE.replace("Placa do veiculo", "Placa (obrigatorio)")

    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)

    assert not r.limpo
    c = r.conflitos[0]
    assert c.caminho == "api.raml"
    assert "Mercosul" in c.meu and "obrigatorio" in c.novo
    assert "Placa do veiculo" in c.base, "a base precisa ir junto para dar contexto"


def test_conflito_pendente_impede_a_escrita(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    novo = BASE.replace("Placa do veiculo", "Placa (obrigatorio)")
    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)

    with pytest.raises(ReconcileError, match="sem resolucao"):
        reconcile.aplicar(r, dirs["local"])

    assert "Mercosul" in (dirs["local"] / "api.raml").read_text(encoding="utf-8"), (
        "a pasta do usuario nao pode ser tocada enquanto ha conflito"
    )


def test_conflito_resolvido_e_aplicado(dirs):
    meu = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul")
    novo = BASE.replace("Placa do veiculo", "Placa (obrigatorio)")
    _escreve(dirs["local"], {"api.raml": meu})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": novo})

    r = _reconciliar(dirs)
    combinado = BASE.replace("Placa do veiculo", "Placa no padrao Mercosul (obrigatorio)")
    escritos = reconcile.aplicar(r, dirs["local"], resolucoes={"api.raml": combinado})

    assert escritos == 1
    final = (dirs["local"] / "api.raml").read_text(encoding="utf-8")
    assert "Mercosul (obrigatorio)" in final


def test_aplicar_escreve_o_que_veio_de_fora(dirs):
    _escreve(dirs["local"], {"api.raml": BASE})
    _escreve(dirs["base"], {"api.raml": BASE})
    _escreve(dirs["novo"], {"api.raml": BASE, "captcha.raml": "#%RAML 1.0\ntitle: Captcha\n"})

    r = _reconciliar(dirs)
    escritos = reconcile.aplicar(r, dirs["local"])

    assert escritos == 1
    assert (dirs["local"] / "captcha.raml").is_file()


def test_exchange_json_e_ignorado(dirs):
    _escreve(dirs["local"], {"api.raml": BASE, "exchange.json": '{"version":"1.1.54"}'})
    _escreve(dirs["base"], {"api.raml": BASE, "exchange.json": '{"version":"1.1.54"}'})
    _escreve(dirs["novo"], {"api.raml": BASE, "exchange.json": '{"version":"1.1.55"}'})

    r = _reconciliar(dirs)

    assert "exchange.json" not in r.resultado
    assert r.limpo


# --- cache do Maven -------------------------------------------------------------


def _zip_raml(destino: Path, arquivos: dict[str, str]) -> Path:
    destino.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destino, "w") as z:
        for rel, conteudo in arquivos.items():
            z.writestr(rel, conteudo)
    return destino


def test_preparar_le_as_duas_versoes_do_cache(tmp_path):
    m2 = tmp_path / "m2"
    _zip_raml(reconcile.caminho_no_cache("g", "leilao", "1.1.54", m2), {"api.raml": BASE})
    _zip_raml(
        reconcile.caminho_no_cache("g", "leilao", "1.1.55", m2),
        {"api.raml": BASE, "captcha.raml": "#%RAML 1.0\ntitle: Captcha\n"},
    )
    local = _escreve(tmp_path / "leilao-raml", {"api.raml": BASE})

    r = reconcile.preparar(local, "g", "leilao", "1.1.54", "1.1.55", m2=m2)

    assert r.limpo
    assert "captcha.raml" in r.so_deles


def test_versao_ausente_no_cache_orienta(tmp_path):
    m2 = tmp_path / "m2"
    local = _escreve(tmp_path / "leilao-raml", {"api.raml": BASE})

    with pytest.raises(ReconcileError, match="Studio"):
        reconcile.preparar(local, "g", "leilao", "1.1.54", "1.1.99", m2=m2)


def test_versoes_ordenadas_numericamente(tmp_path):
    m2 = tmp_path / "m2"
    for v in ("1.1.9", "1.1.10", "1.1.54"):
        _zip_raml(reconcile.caminho_no_cache("g", "leilao", v, m2), {"api.raml": BASE})

    assert reconcile.versoes_no_cache("g", "leilao", m2) == ["1.1.9", "1.1.10", "1.1.54"]


def test_mais_novas_que_ignora_versoes_antigas():
    todas = ["1.1.52", "1.1.53", "1.1.54", "1.1.55"]

    assert reconcile.mais_novas_que(todas, "1.1.54") == ["1.1.55"]
    assert reconcile.mais_novas_que(todas, "1.1.55") == []
    assert reconcile.mais_novas_que(todas, "1.1.52") == ["1.1.53", "1.1.54", "1.1.55"]


def test_mais_novas_que_compara_numericamente():
    """1.1.9 e anterior a 1.1.10, ainda que a ordem alfabetica diga o contrario."""
    assert reconcile.mais_novas_que(["1.1.9", "1.1.10"], "1.1.9") == ["1.1.10"]
    assert reconcile.mais_novas_que(["1.1.9", "1.1.10"], "1.1.10") == []


def test_commitar_base_sem_nada_a_commitar_nao_e_falha(tmp_path):
    """Se a base ja era exatamente essa, nao ha commit — e isso nao e erro.

    Regressao: `False` aqui era reportado como "nao commitei", o que se lia como falha.
    """
    import subprocess

    repo = tmp_path / "repo"
    (repo / "raml").mkdir(parents=True)
    (repo / "raml" / "api.raml").write_text(BASE, encoding="utf-8")

    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "base"],
    ):
        subprocess.run(cmd, cwd=repo, capture_output=True)

    # Nada mudou desde o commit.
    assert reconcile.commitar_base(repo, "raml", "chore: base") is True


def test_commitar_base_fora_de_repo_git(tmp_path):
    pasta = tmp_path / "solta"
    (pasta / "raml").mkdir(parents=True)

    assert reconcile.commitar_base(pasta, "raml", "chore: base") is False


def test_dois_commits_separam_o_de_fora_do_meu(tmp_path):
    """O que veio do Exchange e commitado a parte; o meu fica no working tree.

    Assim o `git diff` depois da operacao mostra so o trabalho da pessoa, em vez de
    misturar as duas coisas num diff unico.
    """
    import subprocess

    repo = tmp_path / "repo"
    local = _escreve(repo / "raml", {"api.raml": BASE})
    base = _escreve(tmp_path / "base", {"api.raml": BASE})
    novo = _escreve(
        tmp_path / "novo",
        {"api.raml": BASE, "captcha.raml": "#%RAML 1.0\ntitle: Captcha\n"},
    )

    for cmd in (
        ["git", "init", "-q"],
        ["git", "config", "user.email", "t@t"],
        ["git", "config", "user.name", "t"],
        ["git", "add", "-A"],
        ["git", "commit", "-q", "-m", "base"],
    ):
        subprocess.run(cmd, cwd=repo, capture_output=True)

    # edicao local, feita depois do commit
    (local / "api.raml").write_text(BASE + "  Meu:\n    type: object\n", encoding="utf-8")

    r = reconcile.reconciliar(local, base, novo, "1.1.54", "1.1.55")
    escritos, commitou = reconcile.aplicar_em_dois_commits(
        r, local, repo, "raml", "chore(raml): 1.1.55"
    )

    assert escritos == 1, "so o captcha.raml mudou de fato"
    assert commitou, "o que veio de fora deve ir para um commit proprio"

    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert "1.1.55" in log, "o commit do Exchange tem de existir"

    sujo = subprocess.run(
        ["git", "status", "--short"], cwd=repo, capture_output=True, text=True
    ).stdout
    assert "api.raml" in sujo, "a edicao local fica no working tree, para a pessoa revisar"
    assert "captcha.raml" not in sujo, "o que veio de fora ja foi commitado"


def test_dois_commits_fora_de_repo_git_apenas_grava(tmp_path):
    local = _escreve(tmp_path / "raml", {"api.raml": BASE})
    base = _escreve(tmp_path / "base", {"api.raml": BASE})
    novo = _escreve(tmp_path / "novo", {"api.raml": BASE, "novo.raml": "#%RAML 1.0\n"})

    r = reconcile.reconciliar(local, base, novo, "1.1.54", "1.1.55")
    escritos, commitou = reconcile.aplicar_em_dois_commits(
        r, local, tmp_path, "raml", "chore: base"
    )

    assert escritos == 1
    assert commitou is False
    assert (local / "novo.raml").is_file()


def test_dois_commits_recusa_com_conflito_pendente(tmp_path):
    meu = BASE.replace("Placa do veiculo", "Placa Mercosul")
    novo_txt = BASE.replace("Placa do veiculo", "Placa (obrigatorio)")
    local = _escreve(tmp_path / "raml", {"api.raml": meu})
    base = _escreve(tmp_path / "base", {"api.raml": BASE})
    novo = _escreve(tmp_path / "novo", {"api.raml": novo_txt})

    r = reconcile.reconciliar(local, base, novo, "1.1.54", "1.1.55")

    with pytest.raises(ReconcileError, match="sem resolucao"):
        reconcile.aplicar_em_dois_commits(r, local, tmp_path, "raml", "chore: base")

    assert "Mercosul" in (local / "api.raml").read_text(encoding="utf-8")
