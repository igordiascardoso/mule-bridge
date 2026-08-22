"""Validacao de RAML antes de subir/publicar: o cabecalho `#%RAML` certo, no arquivo certo.

Existe porque o Exchange nem sempre recusa RAML mal formado — as vezes publica em
silencio, sem a documentacao (Endpoints/Summary) que o time espera, e nada na saida do
comando avisa disso. Achados que motivam esta logica, documentados em
`docs/DESIGN-CENTER-CLI.md`:

- Um `.raml` sem `#%RAML` na primeira linha nao-vazia falha ao publicar (as vezes com erro
  claro, as vezes em silencio) — EXCETO quando ele e um fragmento de `!include`, que nunca
  tem esse cabecalho por definicao (e nao deve ter).
- Validar ingenuamente "todo .raml comeca com #%RAML" da falso positivo: contra um projeto
  real, 13 de 23 arquivos eram fragmentos de include e foram acusados de problema por
  engano. A validacao precisa primeiro descobrir quais `.raml` sao includes.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

#: `!include algo.raml` ou `!include "algo.raml"` — aspas opcionais, so captura .raml/.yaml.
_INCLUDE = re.compile(r"!include\s+['\"]?([^\s'\"]+\.(?:raml|yaml|yml))['\"]?")


@dataclass
class ProblemaRaml:
    """Um `.raml` sem o cabecalho `#%RAML`, que nao e explicado por ser um include."""

    caminho: str
    primeira_linha: str


def _includes_citados(pasta: Path) -> set[str]:
    """Caminhos (relativos a `pasta`) citados em `!include` por qualquer `.raml`/`.yaml`."""
    citados: set[str] = set()
    for arquivo in pasta.rglob("*"):
        if not arquivo.is_file() or arquivo.suffix.lower() not in {".raml", ".yaml", ".yml"}:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        base = arquivo.parent
        for m in _INCLUDE.finditer(texto):
            alvo = (base / m.group(1)).resolve()
            try:
                citados.add(alvo.relative_to(pasta.resolve()).as_posix())
            except ValueError:
                pass  # include aponta para fora da pasta — nao e nosso para validar
    return citados


def _primeira_linha_nao_vazia(texto: str) -> str:
    for linha in texto.splitlines():
        if linha.strip():
            return linha.strip()
    return ""


def validar(pasta: Path, *, main: str) -> list[ProblemaRaml]:
    """Verifica o cabecalho `#%RAML` de todo `.raml` do projeto que nao seja um include.

    `main` sempre entra na checagem mesmo se (por engano) estiver listado como include de
    outro arquivo — e o arquivo que o Exchange de fato le como contrato, e um projeto nunca
    deveria incluir seu proprio main.
    """
    includes = _includes_citados(pasta) - {main}
    problemas = []

    for arquivo in sorted(pasta.rglob("*.raml")):
        rel = arquivo.relative_to(pasta).as_posix()
        if rel in includes:
            continue
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        primeira = _primeira_linha_nao_vazia(texto)
        if not primeira.startswith("#%RAML"):
            problemas.append(ProblemaRaml(caminho=rel, primeira_linha=primeira))

    return problemas
