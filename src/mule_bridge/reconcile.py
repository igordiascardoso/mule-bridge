"""Reconciliacao do RAML: base do Exchange + suas edicoes por cima.

O problema que este modulo resolve: o RAML publicado no Exchange e a base, e as suas
edicoes vivem por cima dela. Quando sai uma versao nova la fora, copiar por cima
destruiria o seu trabalho — o certo e reaplicar as suas edicoes sobre a base nova, que e
o que um `git rebase` faz.

A mecanica e um merge de tres pontas por arquivo:

    base   = o RAML como veio do Exchange na versao antiga (do cache do Maven)
    meu    = a sua pasta de RAML, com as suas edicoes
    novo   = o RAML do Exchange na versao nova

Adicoes em pontos diferentes do arquivo o `git merge-file` junta sozinho. Sobra conflito
so quando os dois lados mexeram no mesmo ponto — e nesse caso **nada e escrito**: os
arquivos em conflito sao reportados para quem chamou decidir.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

from .errors import BridgeError

#: Arquivo de metadados do Exchange; muda a cada publicacao e nao carrega contrato nenhum.
IGNORADOS = {"exchange.json"}


class ReconcileError(BridgeError):
    """Falha ao montar a reconciliacao (base ausente, zip corrompido, etc.)."""


@dataclass
class Conflito:
    """Um arquivo cujo merge o git nao resolveu sozinho."""

    caminho: str
    base: str
    meu: str
    novo: str
    merge_marcado: str


@dataclass
class Reconciliacao:
    """Resultado de uma reconciliacao, antes de qualquer coisa ser escrita em disco."""

    versao_base: str
    versao_nova: str
    juntados: list[str] = field(default_factory=list)
    inalterados: list[str] = field(default_factory=list)
    so_meus: list[str] = field(default_factory=list)
    so_deles: list[str] = field(default_factory=list)
    conflitos: list[Conflito] = field(default_factory=list)
    #: conteudo final por caminho relativo, aplicado so quando nao ha conflito pendente
    resultado: dict[str, str] = field(default_factory=dict)

    @property
    def limpo(self) -> bool:
        """True quando da para aplicar sem nenhuma decisao humana."""
        return not self.conflitos

    @property
    def total_mudancas(self) -> int:
        return len(self.juntados) + len(self.so_deles) + len(self.conflitos)


def base_do_git(pasta: Path, rel: str) -> str | None:
    """Conteudo de um arquivo como esta no ultimo commit, ou None se nao versionado.

    Para os arquivos da API nao existe um "publicado no Exchange" que sirva de base — o
    ponto zero comum e o ultimo commit: o que voce mudou desde ele e seu, o que aparece
    diferente do lado do Studio veio de la.
    """
    proc = subprocess.run(
        ["git", "show", f"HEAD:./{rel}"],
        cwd=pasta,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc.stdout if proc.returncode == 0 else None


def em_repo_git(pasta: Path) -> bool:
    """True se `pasta` esta dentro de uma arvore git com pelo menos um commit."""
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=pasta,
        capture_output=True,
        text=True,
    )
    return proc.returncode == 0


def reconciliar_com_git(pasta_local: Path, pasta_studio: Path, ignorar: set[str]) -> Reconciliacao:
    """Reconcilia a pasta local com a do Studio, usando o ultimo commit como base.

    Mesma logica do RAML, com a base vindo do git em vez do cache do Maven. Arquivos nao
    versionados nao tem base: se diferem, viram conflito, porque nao ha como saber quem
    mudou o que.
    """
    r = Reconciliacao(versao_base="HEAD", versao_nova="workspace do Studio")

    meus = {
        p.relative_to(pasta_local).as_posix(): p
        for p in pasta_local.rglob("*")
        if p.is_file() and not any(parte in ignorar for parte in p.relative_to(pasta_local).parts)
    }
    deles = {
        p.relative_to(pasta_studio).as_posix(): p
        for p in pasta_studio.rglob("*")
        if p.is_file() and not any(parte in ignorar for parte in p.relative_to(pasta_studio).parts)
    }

    for rel in sorted(set(meus) | set(deles)):
        meu, novo = _ler(meus.get(rel)), _ler(deles.get(rel))

        if rel not in deles:
            r.so_meus.append(rel)
            r.resultado[rel] = meu
            continue
        if rel not in meus:
            r.so_deles.append(rel)
            r.resultado[rel] = novo
            continue
        if meu == novo:
            r.inalterados.append(rel)
            r.resultado[rel] = meu
            continue

        base = base_do_git(pasta_local, rel)
        if base is None:
            # Sem base: nao da para saber quem mudou o que, entao nao decidimos sozinhos.
            r.conflitos.append(
                Conflito(caminho=rel, base="", meu=meu, novo=novo, merge_marcado="")
            )
            continue

        if meu == base:
            r.so_deles.append(rel)
            r.resultado[rel] = novo
            continue
        if base == novo:
            r.so_meus.append(rel)
            r.resultado[rel] = meu
            continue

        juntado, conflitou = _merge_tres_pontas(meu, base, novo)
        if conflitou:
            r.conflitos.append(
                Conflito(caminho=rel, base=base, meu=meu, novo=novo, merge_marcado=juntado)
            )
        else:
            r.juntados.append(rel)
            r.resultado[rel] = juntado

    return r


def caminho_no_cache(grupo: str, artefato: str, versao: str, m2: Path | None = None) -> Path:
    """Caminho do zip do RAML no cache local do Maven."""
    raiz = m2 or (Path.home() / ".m2" / "repository")
    return raiz / grupo / artefato / versao / f"{artefato}-{versao}-raml.zip"


def versoes_no_cache(grupo: str, artefato: str, m2: Path | None = None) -> list[str]:
    """Versoes do RAML ja baixadas, da mais antiga para a mais nova."""
    raiz = (m2 or (Path.home() / ".m2" / "repository")) / grupo / artefato
    if not raiz.is_dir():
        return []

    achadas = []
    for d in raiz.iterdir():
        if d.is_dir() and caminho_no_cache(grupo, artefato, d.name, m2).is_file():
            achadas.append(d.name)
    return sorted(achadas, key=_ordem_versao)


def mais_novas_que(versoes: list[str], atual: str) -> list[str]:
    """Filtra as versoes posteriores a `atual`, na ordem numerica."""
    return [v for v in versoes if _ordem_versao(v) > _ordem_versao(atual)]


def _ordem_versao(v: str) -> tuple:
    """Ordena 1.1.9 antes de 1.1.10, que a ordem alfabetica erraria."""
    partes = []
    for pedaco in v.replace("-", ".").split("."):
        partes.append((0, int(pedaco)) if pedaco.isdigit() else (1, pedaco))
    return tuple(partes)


def extrair(zip_raml: Path, destino: Path) -> Path:
    """Extrai o zip do RAML publicado para uma pasta."""
    if not zip_raml.is_file():
        raise ReconcileError(
            f"RAML nao encontrado no cache do Maven: {zip_raml}\n"
            "Abra o projeto no Studio e deixe ele baixar essa versao primeiro."
        )
    destino.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_raml) as z:
            z.extractall(destino)
    except zipfile.BadZipFile as exc:
        raise ReconcileError(f"Zip do RAML corrompido: {zip_raml}") from exc
    return destino


def _arquivos(raiz: Path) -> dict[str, Path]:
    return {
        p.relative_to(raiz).as_posix(): p
        for p in raiz.rglob("*")
        if p.is_file() and p.name not in IGNORADOS
    }


def _ler(p: Path | None) -> str:
    return p.read_text(encoding="utf-8", errors="replace") if p and p.is_file() else ""


def _merge_tres_pontas(meu: str, base: str, novo: str) -> tuple[str, bool]:
    """Roda `git merge-file` nos tres conteudos.

    Devolve (resultado, houve_conflito). Com conflito, o resultado vem com os marcadores
    `<<<<<<<`/`>>>>>>>` — usado so para mostrar o contexto a quem for decidir, nunca
    escrito direto na pasta do usuario.
    """
    with tempfile.TemporaryDirectory() as tmp:
        t = Path(tmp)
        (t / "meu").write_text(meu, encoding="utf-8")
        (t / "base").write_text(base, encoding="utf-8")
        (t / "novo").write_text(novo, encoding="utf-8")

        proc = subprocess.run(
            [
                "git",
                "merge-file",
                "-p",
                "-L",
                "sua versao",
                "-L",
                "base (Exchange)",
                "-L",
                "Exchange novo",
                str(t / "meu"),
                str(t / "base"),
                str(t / "novo"),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )

    if proc.returncode < 0:
        raise ReconcileError(f"git merge-file falhou: {proc.stderr.strip()}")
    return proc.stdout, proc.returncode != 0


def reconciliar(
    pasta_local: Path, base_dir: Path, novo_dir: Path, versao_base: str, versao_nova: str
) -> Reconciliacao:
    """Reconcilia a pasta local contra uma base e uma versao nova, sem escrever nada.

    Nada e gravado aqui de proposito: quem chama decide o que fazer com os conflitos
    antes de aplicar. Ver `aplicar`.
    """
    r = Reconciliacao(versao_base=versao_base, versao_nova=versao_nova)

    meus, bases, novos = _arquivos(pasta_local), _arquivos(base_dir), _arquivos(novo_dir)
    todos = sorted(set(meus) | set(bases) | set(novos))

    for rel in todos:
        meu, base, novo = _ler(meus.get(rel)), _ler(bases.get(rel)), _ler(novos.get(rel))

        if rel not in novos and rel in bases:
            # O Exchange removeu o arquivo. Se voce nao mexeu nele, some; se mexeu,
            # e uma decisao — mantemos o seu e reportamos como edicao sua.
            if meu and meu != base:
                r.so_meus.append(rel)
                r.resultado[rel] = meu
            continue

        if rel not in meus:
            r.so_deles.append(rel)
            r.resultado[rel] = novo
            continue

        if meu == novo:
            r.inalterados.append(rel)
            r.resultado[rel] = meu
            continue

        if meu == base:
            # Voce nao editou: a versao nova entra limpa.
            r.so_deles.append(rel)
            r.resultado[rel] = novo
            continue

        if base == novo:
            # So voce mexeu: sua edicao permanece.
            r.so_meus.append(rel)
            r.resultado[rel] = meu
            continue

        juntado, conflitou = _merge_tres_pontas(meu, base, novo)
        if conflitou:
            r.conflitos.append(
                Conflito(caminho=rel, base=base, meu=meu, novo=novo, merge_marcado=juntado)
            )
        else:
            r.juntados.append(rel)
            r.resultado[rel] = juntado

    return r


def aplicar(
    r: Reconciliacao, pasta_local: Path, *, resolucoes: dict[str, str] | None = None
) -> int:
    """Escreve o resultado na pasta local. Devolve quantos arquivos foram alterados.

    Recusa-se a aplicar enquanto houver conflito sem resolucao — e essa recusa que
    garante que uma edicao sua nunca seja sobrescrita em silencio.
    """
    resolucoes = resolucoes or {}

    pendentes = [c.caminho for c in r.conflitos if c.caminho not in resolucoes]
    if pendentes:
        raise ReconcileError(
            "Ha conflitos sem resolucao — nada foi escrito: " + ", ".join(pendentes)
        )

    final = dict(r.resultado)
    final.update(resolucoes)

    escritos = 0
    for rel, conteudo in sorted(final.items()):
        destino = pasta_local / rel
        if destino.is_file() and destino.read_text(encoding="utf-8", errors="replace") == conteudo:
            continue
        destino.parent.mkdir(parents=True, exist_ok=True)
        destino.write_text(conteudo, encoding="utf-8")
        escritos += 1
    return escritos


def preparar(
    pasta_local: Path,
    grupo: str,
    artefato: str,
    versao_base: str,
    versao_nova: str,
    m2: Path | None = None,
) -> Reconciliacao:
    """Monta a reconciliacao a partir das duas versoes do cache do Maven."""
    tmp = Path(tempfile.mkdtemp(prefix="mule-bridge-"))
    try:
        base = extrair(caminho_no_cache(grupo, artefato, versao_base, m2), tmp / "base")
        novo = extrair(caminho_no_cache(grupo, artefato, versao_nova, m2), tmp / "novo")
        return reconciliar(pasta_local, base, novo, versao_base, versao_nova)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
