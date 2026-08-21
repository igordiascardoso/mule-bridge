# Contribuindo

```bash
git clone https://github.com/igordiascardoso/mule-bridge
cd mule-bridge
pip install -e ".[dev]"

pytest          # 201 testes
ruff check .
```

A lógica vive inteira em [`src/mule_bridge/`](src/mule_bridge/): `discovery` acha os
projetos, `sync` move arquivos, `reconcile` faz o merge, `pomrewrite` cuida do `pom.xml`,
`config` lembra o pareamento. A CLI é a única camada com lógica de negócio — a skill e o
`AGENTS.md` só a acionam.

Para mudanças de comportamento, um teste junto ajuda: a suíte roda em menos de um segundo.

## Os testes contra projeto real

Treze testes rodam contra um projeto Mule e um RAML de verdade, e são **pulados por padrão**
— nenhum caminho ou identificador de organização fica no código, que é público. Para
rodá-los, aponte os seus:

```bash
PONTE_TESTE_API=/caminho/para/uma-api \
PONTE_TESTE_GRUPO=<groupId> PONTE_TESTE_ARTEFATO=<artifactId> pytest
```

O projeto apontado nunca é alterado — os testes trabalham sobre uma cópia temporária.

## Roadmap

Falta um **MCP server**, expondo os mesmos comandos como ferramentas MCP, para clients que
não sejam o Claude Code.
