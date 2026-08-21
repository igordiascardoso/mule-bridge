"""Permite rodar a ferramenta como `python -m mule_bridge`.

Serve de saida para quem nao consegue — ou nao quer — mexer no `PATH` do sistema: o
executavel `ponte` fica numa pasta de scripts do Python que nem sempre esta no caminho, mas
o modulo e sempre alcancavel pelo proprio interpretador.
"""

from __future__ import annotations

from .cli import app

if __name__ == "__main__":
    app()
