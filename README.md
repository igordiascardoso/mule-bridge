<div align="center">

# mule-bridge

**Edite seu projeto Mule onde você quiser. O Anypoint Studio acompanha.**

Sincroniza o repositório onde você desenvolve com o workspace do Anypoint Studio —
sem excluir e reimportar o projeto a cada mudança.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-44%20passing-brightgreen)](tests/)
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
$ ponte parastudio

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
| Traz de volta os flows que o scaffold gerou | ❌ | ✅ `pararepo api` |
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

O pacote chama-se `mule-bridge`; o comando instalado é **`ponte`**.

<details>
<summary>Alternativas e solução de problemas</summary>

Sem pipx, o pip funciona igual:

```bash
pip install git+https://github.com/igordiascardoso/mule-bridge
```

Confirme que ficou disponível no terminal:

```bash
ponte --version
```

Se o comando não for encontrado, o diretório de scripts do Python não está no `PATH`.
`pipx ensurepath` resolve — depois abra um terminal novo.

</details>

## Começando

```bash
cd /caminho/do/seu/repo    # a raiz, onde ficam a pasta da API e a do RAML

ponte init           # pareia este repositório com um projeto do Studio
```

O `init` varre os dois lados e lista o que encontrou. Onde há mais de um candidato, ele
pede que você escolha pelo número; onde há um só, resolve e segue — perguntar o que não
tem alternativa só faria você digitar de novo:

```console
$ ponte init

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

> Esse arquivo guarda o caminho do **seu** workspace, que não serve para os colegas.
> Adicione-o ao `.gitignore` do projeto.


<details>
<summary>Sem terminal interativo (extensão de IDE, agente de IA, CI)</summary>

O `init` pergunta pelo terminal, mas nem sempre há um. Nesses casos ele lista o que
encontrou e ensina a flag que dispensa o prompt:

```console
$ ponte init

Projeto de API nesta pasta de trabalho:
  1. pedidos-api
erro: Projeto de API nesta pasta de trabalho — não há terminal interativo para perguntar.
Repita o comando escolhendo pela flag, ex: --api pedidos-api
```

Passando as escolhas, roda sem prompt nenhum:

```bash
ponte init --api pedidos-api --raml pedidos-raml \
  --studio-api minha-api --studio-raml minha-api-raml
```

Use `--raml nenhuma` para não sincronizar RAML, e `--studio-root` quando o workspace não
estiver num caminho padrão.

</details>

Daí em diante:

```bash
ponte parastudio     # suas edições  ->  Studio
ponte pararepo       # Studio        ->  seu repositório
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
mkdir -p ~/.claude/skills/ponte
curl -o ~/.claude/skills/ponte/SKILL.md   https://raw.githubusercontent.com/igordiascardoso/mule-bridge/main/.claude/skills/ponte/SKILL.md
```

Depois, dentro de uma sessão do Claude Code:

```
/ponte parastudio     # suas edições  ->  Studio
/ponte pararepo       # Studio        ->  seu repositório
/ponte status         # não altera nada
```

A skill não reimplementa nada: ela escolhe o comando certo, roda `--dry-run` antes de
operações de risco e nunca passa `--delete` sem você pedir. Para o `init`, ela lista os
projetos encontrados, pergunta qual é o correto e roda o comando com as flags da sua
escolha — funciona igual na extensão do VS Code, onde não há terminal para prompts.

## Comandos

| Comando | Para quê | Mexe em | Direção | O que faz |
|---|---|---|---|---|
| `ponte` | Cheguei no projeto e não sei o estado | nada | — | Só olha. Se não estiver pareado, faz o init |
| `ponte init` | Primeira vez neste projeto (uma vez só) | nada | — | Só grava o `.mule-bridge.toml` |
| `ponte status` | Ver o pareamento e o que iria pro Studio | nada | — | Só mostra, não escreve |
| `ponte parastudio` | Editei RAML **e** código, quero testar tudo | RAML + API | repo → Studio | Pega o RAML e a API do repo e sobrescreve os do Studio |
| `ponte parastudio raml` | Mexi só no contrato, quero ver o scaffold reagir | só RAML | repo → Studio | Pega o RAML do repo e sobrescreve o do Studio |
| `ponte parastudio api` | Mexi só em flow/service/java, quero rodar | só API | repo → Studio | Pega a API do repo e sobrescreve a do Studio |
| `ponte pararepo` | Raro — quero o Studio inteiro por cima | RAML + API | Studio → repo | ⚠️ Pega o RAML e a API do Studio e apaga suas edições do repo |
| `ponte pararepo raml` | Saiu versão nova no Exchange | só RAML | Exchange → repo | Pega o RAML novo do Exchange e junta com o do repo, **mantendo o que você editou** |
| `ponte pararepo api` | O Studio criou flows no scaffold, ou fiz um fix pontual direto no Studio | só API | Studio → repo | Pega a API do Studio e junta com a do repo, **mantendo o que você editou** |

> **Sobre o `pararepo` sem parte:** é o único comando que descarta trabalho seu. Use
> `pararepo raml` e `pararepo api` quando quiser o caminho de volta preservando o que você
> editou.

**Se você não editou nada no repo**, o `pararepo raml` e o `pararepo api` simplesmente
trazem o que veio do outro lado — não há nada para preservar, nem conflito possível.

**Se a pasta do RAML nem existir**, o `pararepo raml` a cria na raiz do repositório,
extraindo a versão que o projeto do Studio usa — útil num projeto novo, ou quando a pasta
se perdeu. O pareamento é atualizado junto.

**Flags:**

| Flag | Efeito |
|---|---|
| `--dry-run`, `-n` | Mostra o que seria feito, sem alterar nada. |
| `--aplicar` | Em `pararepo raml` e `pararepo api`: grava. Sem ela, é só prévia. |
| `--delete` | Remove no destino os arquivos que já não existem na origem. |
| `--work-root`, `-w` | Roda a partir de outro diretório, em vez do atual. |

### O dia a dia

Você editou o contrato e quer ver o Studio reagir:

```bash
ponte parastudio raml     # pega o RAML do repo e manda pro Studio
# o Studio roda o scaffold e cria os flows novos
ponte pararepo api        # pega a API do Studio e traz pro repo, sem perder seu código
git commit
```

Um colega publicou uma versão nova no Exchange:

```bash
ponte pararepo raml       # pega o RAML novo do Exchange e junta com o do repo
ponte parastudio          # pega o RAML e a API do repo e manda pro Studio testar
git commit
```

## Como a junção funciona

### `pararepo raml` — a versão nova sem perder o que você escreveu

Quando sai uma versão nova do RAML no Exchange, copiar por cima apagaria suas edições. O
`pararepo raml` faz o contrário: trata a versão do Exchange como base e **reaplica suas
edições por cima**, como um `git rebase`.

A versão a trazer é a mais alta já baixada no cache local do Maven (`~/.m2`) — tenha sido
o Studio (*Properties > Mule Project > APIs*) ou um `mvn dependency:get` quem a baixou, a
fonte é a mesma. O `pom.xml` do lado do Studio entra só como desempate.

```console
$ ponte pararepo raml


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

Com `--aplicar`, grava.

A base limpa sai do cache local do Maven (`~/.m2`), onde o Studio já guarda cada versão
publicada — não é preciso credencial do Exchange nem estar online.

**Os três casos:**

| Situação | O que acontece |
|---|---|
| Você e o outro lado mexeram em pontos diferentes | Junta sozinho, os dois lados preservados |
| Só um dos lados mexeu | Entra direto, sem cerimônia |
| **Os dois mudaram a mesma linha** | Para, mostra as duas versões, e **não escreve nada** |

O mesmo vale para `pararepo api`, que usa o último commit do repositório como base: o que
você mudou desde ele é seu, o que aparece diferente do lado do Studio veio de lá.

No terceiro caso nenhum arquivo é tocado — nem os que deram certo. Sua pasta só é
alterada quando o resultado inteiro está resolvido, então uma edição sua nunca é
sobrescrita em silêncio.

### O que nunca acontece

- **O `pom.xml` do repositório nunca é sobrescrito.** No `parastudio` a reescrita para o
  RAML local acontece só no destino; no `pararepo` o arquivo é ignorado. Seu repositório
  segue sempre apontando para o Exchange com a versão travada.
- **Nada é apagado sem `--delete`**, e essa flag nunca é passada por conta própria — nem
  pela skill.
- **Nada é escrito enquanto houver conflito** — nem os arquivos que deram certo.

## Como funciona

### O `pom.xml` é o único caso especial

O projeto referencia o RAML como dependência do Exchange, com a versão travada. Para testar
suas edições locais do RAML no Studio, essa referência precisa apontar para o arquivo local
— mas essa alteração **não pode ir para o commit**.

O `parastudio` resolve isso reescrevendo o arquivo apenas do lado do Studio:

```
seu repositório  ──►  workspace do Studio
pom.xml                pom.xml
  Exchange, 1.1.54       RAML local (systemPath)
  ↑ intacto, é o          ↑ reescrito no destino, com a
    que vai pro git         dependência original preservada
                            como comentário
```

O `pararepo` reconhece o arquivo reescrito e o ignora, para que o apontamento local nunca volte
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

pytest          # 44 testes
ruff check .    # lint
```

A lógica de negócio vive inteira na CLI ([`src/mule_bridge/`](src/mule_bridge/)):
`discovery` acha os projetos, `sync` move os arquivos, `pomrewrite` cuida do caso especial
do `pom.xml`, `config` lembra o pareamento.

## Roadmap

- [x] Descoberta interativa de projetos nos dois lados
- [x] Sync bidirecional (`parastudio` / `pararepo`) com `--dry-run`
- [x] Reescrita do `pom.xml` isolada no workspace do Studio
- [x] **Reconciliação tipo `git rebase`** para o RAML (`pararepo raml`)
- [x] Mesma reconciliação para os arquivos da API (`pararepo api`), usando o último commit
      como base
- [ ] Separar o commit do que veio de fora do commit das suas edições
- [x] **Skill do Claude Code** — `/ponte parastudio` dentro de uma sessão
- [ ] **MCP server** — os mesmos comandos como ferramentas MCP, para clients que não sejam
      o Claude Code
- [ ] **`AGENTS.md` de exemplo** — trecho pronto para colar num projeto Mule, para o agente
      saber sozinho quando acionar a ferramenta

## Contribuindo

Issues e PRs são bem-vindos. Para mudanças de comportamento, um teste junto ajuda bastante —
a suíte roda em menos de um segundo.

## Licença

[MIT](LICENSE) © Igor Dias Cardoso
