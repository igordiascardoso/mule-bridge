<div align="center">

# mule-bridge

**Edite seu projeto Mule onde você quiser. O Anypoint Studio acompanha.**

Sincroniza o repositório onde você desenvolve com o workspace do Anypoint Studio —
sem excluir e reimportar o projeto a cada mudança.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-36%20passing-brightgreen)](tests/)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230.svg)](https://github.com/astral-sh/ruff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](#contribuindo)

</div>

---

## O problema

Em muitos setups Mule, o código vive em dois lugares que não se falam:

```
c:\projetos\minha-api                              ~\AnypointStudio\studio-workspace\minha-api
├── minha-api/          você edita aqui       ✗     ├── minha-api/        o Studio roda daqui
└── minha-raml/         (git, IA, sua IDE)          └── ...
```

Uma alteração feita no repositório **simplesmente não aparece no Studio**. A saída de sempre
é excluir o projeto no Studio e reimportar do zero — a cada mudança.

E o tráfego é de mão dupla: quando o contrato RAML muda de versão, o scaffold do Studio
regenera o `application.xml` e pode **criar flows novos**. Isso precisa voltar para o
repositório sem atropelar o que você editou lá.

## A solução

```console
$ mule-bridge push

┏━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ projeto      ┃ copiados ┃ pom reescrito ┃ removidos ┃ ignorados ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
│ pedidos-api  │        3 │             1 │         0 │         0 │
│ pedidos-raml │        1 │             0 │         0 │         0 │
└──────────────┴──────────┴───────────────┴───────────┴───────────┘
```

O Studio detecta a mudança no disco e **redeploya sozinho**. Sem reimportar, sem refresh,
sem passo manual.

### Por que não um `cp -r`?

| | `cp` / `robocopy` | `mule-bridge` |
|---|---|---|
| Copia os arquivos do projeto | ✅ | ✅ |
| Ignora `target/`, `.mule`, `.settings` | manual | ✅ automático |
| Aponta o `pom.xml` para o RAML local **só no Studio** | ❌ | ✅ |
| Impede que esse apontamento vaze para o commit | ❌ | ✅ |
| Traz de volta os flows que o scaffold gerou | ❌ | ✅ `pull` |
| Mostra o que vai mudar antes de mudar | ❌ | ✅ `--dry-run` |

## Pré-requisitos

- **Python 3.10 ou superior** — confira com `python --version`.
- **git** — só para instalar direto do repositório; a ferramenta não usa git em execução.
- **Anypoint Studio**, com o workspace onde os projetos são importados.

Não precisa de Java nem Maven: o `mule-bridge` copia e reescreve arquivos — quem compila e
roda continua sendo o Studio.

## Instalação

Com [pipx](https://pipx.pypa.io) (recomendado — isola a ferramenta do resto do sistema):

```bash
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

<details>
<summary>Alternativas e solução de problemas</summary>

Sem pipx, o pip funciona igual:

```bash
pip install git+https://github.com/igordiascardoso/mule-bridge
```

Confirme que ficou disponível no terminal:

```bash
mule-bridge --version
```

Se o comando não for encontrado, o diretório de scripts do Python não está no `PATH`.
`pipx ensurepath` resolve — depois abra um terminal novo.

</details>

## Começando

```bash
cd /caminho/do/seu/repo    # a raiz, onde ficam a pasta da API e a do RAML

mule-bridge init           # pareia este repositório com um projeto do Studio
```

O `init` é **interativo**: ele varre os dois lados, lista o que encontrou e pede que você
escolha pelo número. Nada é adivinhado — nem qual pasta da API, nem qual projeto do Studio
corresponde a ela:

```console
$ mule-bridge init

Projeto de API nesta pasta de trabalho:
  1. pedidos-api

Pasta do RAML correspondente:
  1. pedidos-raml  (sugerido)
  2. nenhuma — não sincronizar RAML
Escolha [1]:

Workspace do Anypoint Studio:
  1. C:\Users\voce\AnypointStudio\studio-workspace

Projeto no workspace correspondente a pedidos-api:
  1. minha-api  [api]

Config gravada em c:\projetos\minha-api\.mule-bridge.toml
```

O pareamento fica em `.mule-bridge.toml`, na raiz do repositório — o `init` roda uma vez só.

<details>
<summary>Sem terminal interativo (extensão de IDE, agente de IA, CI)</summary>

O `init` pergunta pelo terminal, mas nem sempre há um. Nesses casos ele lista o que
encontrou e ensina a flag que dispensa o prompt:

```console
$ mule-bridge init

Projeto de API nesta pasta de trabalho:
  1. pedidos-api
erro: Projeto de API nesta pasta de trabalho — não há terminal interativo para perguntar.
Repita o comando escolhendo pela flag, ex: --api pedidos-api
```

Passando as escolhas, roda sem prompt nenhum:

```bash
mule-bridge init --api pedidos-api --raml pedidos-raml \
  --studio-api minha-api --studio-raml minha-api-raml
```

Use `--raml nenhuma` para não sincronizar RAML, e `--studio-root` quando o workspace não
estiver num caminho padrão.

</details>

Daí em diante:

```bash
mule-bridge parastudio     # suas edições  ->  Studio
mule-bridge pararepo       # Studio        ->  seu repositório
```

## Uso com agentes de IA

A CLI é a única camada com lógica — as outras são atalhos para acioná-la.

**Pedindo em português.** Como o `mule-bridge` é um comando de terminal, qualquer agente que
execute comandos (Claude Code, Codex CLI) consegue usá-lo. Basta pedir *"sincroniza pro
Studio"*. Para que o agente saiba que a ferramenta existe num projeto, documente-a no
`AGENTS.md`/`CLAUDE.md` daquele projeto.

**Com barra, no Claude Code.** Instale a skill uma vez e o comando fica disponível em todos
os seus projetos:

```bash
mkdir -p ~/.claude/skills/mulebridge
curl -o ~/.claude/skills/mulebridge/SKILL.md   https://raw.githubusercontent.com/igordiascardoso/mule-bridge/main/.claude/skills/mulebridge/SKILL.md
```

Depois, dentro de uma sessão do Claude Code:

```
/mulebridge parastudio     # suas edições  ->  Studio
/mulebridge pararepo       # Studio        ->  seu repositório
/mulebridge status         # não altera nada
```

A skill não reimplementa nada: ela escolhe o comando certo, roda `--dry-run` antes de
operações de risco e nunca passa `--delete` sem você pedir. Para o `init`, ela lista os
projetos encontrados, pergunta qual é o correto e roda o comando com as flags da sua
escolha — funciona igual na extensão do VS Code, onde não há terminal para prompts.

## Comandos

| Comando | O que faz |
|---|---|
| `init` | Descobre os projetos dos dois lados e grava o pareamento. |
| `status` | Mostra o pareamento atual e o que um `parastudio` faria agora. |
| `parastudio` | Leva o que você editou para o workspace do Studio. |
| `pararepo` | Traz de volta o que o Studio alterou por conta própria. |
| `juntarraml` | Traz a versão nova do RAML **preservando suas edições**. |

As duas direções aceitam uma parte opcional, quando só um lado mudou:

```bash
mule-bridge parastudio raml    # só o RAML
mule-bridge pararepo api       # só a API
mule-bridge parastudio         # os dois (padrão)
```

**Flags** de `parastudio` e `pararepo`:

| Flag | Efeito |
|---|---|
| `--dry-run`, `-n` | Mostra o que seria feito, sem alterar nada. |
| `--delete` | Remove no destino os arquivos que já não existem na origem. |
| `--work-root`, `-w` | Roda a partir de outro diretório, em vez do atual. |

> **Nota:** sem `--delete`, o sync só copia — nada é apagado em nenhum dos lados.
> No `parastudio` o destino é o workspace; no `pararepo`, o seu repositório.

### `juntarraml` — a versão nova sem perder o que você escreveu

Quando sai uma versão nova do RAML no Exchange, copiar por cima apagaria suas edições. O
`juntarraml` faz o contrário: trata a versão do Exchange como base e **reaplica suas
edições por cima**, como um `git rebase`.

```console
$ mule-bridge juntarraml

RAML 1.1.54 -> 1.1.55

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ o que                     ┃ arquivos ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ juntados (seu + deles)    │        2 │
│ novos, vindos do Exchange │        7 │
│ só seus, preservados      │        1 │
│ sem mudança               │       15 │
│ em conflito               │        0 │
└───────────────────────────┴──────────┘

Isso foi uma prévia — rode com --aplicar para gravar.
```

A base limpa sai do cache local do Maven (`~/.m2`), onde o Studio já guarda cada versão
publicada — não é preciso credencial do Exchange nem estar online.

**Os três casos:**

| Situação | O que acontece |
|---|---|
| Você e o Exchange mexeram em pontos diferentes | Junta sozinho, os dois lados preservados |
| Só um dos lados mexeu | Entra direto, sem cerimônia |
| **Os dois mudaram a mesma linha** | Para, mostra as duas versões, e **não escreve nada** |

No terceiro caso nenhum arquivo é tocado — nem os que deram certo. Sua pasta só é
alterada quando o resultado inteiro está resolvido, então uma edição sua nunca é
sobrescrita em silêncio.

## Como funciona

### O `pom.xml` é o único caso especial

O projeto referencia o RAML como dependência do Exchange, com a versão travada. Para testar
suas edições locais do RAML no Studio, essa referência precisa apontar para o arquivo local
— mas essa alteração **não pode ir para o commit**.

O `push` resolve isso reescrevendo o arquivo apenas do lado do Studio:

```
seu repositório  ──►  workspace do Studio
pom.xml                pom.xml
  Exchange, 1.1.54       RAML local (systemPath)
  ↑ intacto, é o          ↑ reescrito no destino, com a
    que vai pro git         dependência original preservada
                            como comentário
```

O `pull` reconhece o arquivo reescrito e o ignora, para que o apontamento local nunca volte
para o repositório.

### O que nunca é sincronizado

`.git`, `.svn`, `target`, `.mule`, `.settings`, `__pycache__` e `.DS_Store` — artefatos de
build e metadados. A lista é configurável em `.mule-bridge.toml`.

### Por que não há watcher automático

O sync roda sob demanda. Um processo em segundo plano copiando arquivos enquanto o scaffold
do Studio reescreve os mesmos arquivos é receita para perder trabalho — você decide quando
sincronizar, e o `--dry-run` deixa conferir antes.

## Desenvolvimento

```bash
git clone https://github.com/igordiascardoso/mule-bridge
cd mule-bridge
pip install -e ".[dev]"

pytest          # 36 testes
ruff check .    # lint
```

A lógica de negócio vive inteira na CLI ([`src/mule_bridge/`](src/mule_bridge/)):
`discovery` acha os projetos, `sync` move os arquivos, `pomrewrite` cuida do caso especial
do `pom.xml`, `config` lembra o pareamento.

## Roadmap

- [x] Descoberta interativa de projetos nos dois lados
- [x] Sync bidirecional (`push` / `pull`) com `--dry-run`
- [x] Reescrita do `pom.xml` isolada no workspace do Studio
- [x] **Reconciliação tipo `git rebase`** para o RAML (`juntarraml`)
- [ ] Mesma reconciliação para os arquivos da API (hoje `parastudio`/`pararepo` são cópia
      direta: se os dois lados alterarem o mesmo arquivo, o último a sincronizar vence)
- [x] **Skill do Claude Code** — `/mulebridge parastudio` dentro de uma sessão
- [ ] **MCP server** — os mesmos comandos como ferramentas MCP, para clients que não sejam
      o Claude Code
- [ ] **`AGENTS.md` de exemplo** — trecho pronto para colar num projeto Mule, para o agente
      saber sozinho quando acionar a ferramenta

## Contribuindo

Issues e PRs são bem-vindos. Para mudanças de comportamento, um teste junto ajuda bastante —
a suíte roda em menos de um segundo.

## Licença

[MIT](LICENSE) © Igor Dias Cardoso
