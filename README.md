<div align="center">

# mule-bridge

**Edite seu projeto Mule onde você quiser. O Anypoint Studio acompanha.**

Sincroniza o repositório onde você desenvolve com o workspace do Anypoint Studio —
sem excluir e reimportar o projeto a cada mudança.

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-148%20passing-brightgreen)](tests/)
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

### Por que não copiar e colar as pastas?

| | Copiar e colar | `mule-bridge` |
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

Três comandos, uma vez só:

```bash
python -m pip install --user pipx      # 1. instala o pipx, se ainda não tiver
python -m pipx ensurepath              # 2. deixa os comandos visíveis no terminal
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

**Feche o terminal e abra outro** — o passo 2 mexe no `PATH`, e a janela aberta não vê a
mudança. Então confirme:

```bash
ponte --version
```

O pacote chama-se `mule-bridge`; o comando instalado é **`ponte`**.

O `pipx` é recomendado porque instala a ferramenta isolada, sem misturar dependências com
os seus outros projetos Python.

<details>
<summary><b>Se <code>ponte</code> não for encontrado</b> — e outras formas de instalar</summary>

### `ponte: command not found` / `não é reconhecido como comando`

O pacote instalou, mas o terminal não sabe onde procurar o executável. Na ordem:

1. **Abriu um terminal novo depois do `ensurepath`?** É a causa mais comum.
2. Rode `python -m pipx ensurepath` de novo e leia a saída — ela diz qual pasta foi
   adicionada, ou avisa que já estava lá.
3. Ainda assim, chame pelo módulo para confirmar que o pacote está instalado:
   `python -m mule_bridge --version`. Se isso funcionar, o problema é só o `PATH`.

Para acertar o `PATH` à mão no Windows: *Iniciar → "variáveis de ambiente" → Variáveis de
Ambiente → em **Path** (do usuário) → Novo* → e cole o caminho que o `ensurepath` mostrou
(normalmente `C:\Users\seu-usuario\.local\bin`). Depois abra um terminal novo.

### Sem pipx, direto com pip

```bash
python -m pip install --user git+https://github.com/igordiascardoso/mule-bridge
```

Funciona igual, mas a pasta de scripts é outra — algo como
`C:\Users\seu-usuario\AppData\Roaming\Python\Python312\Scripts`. Se o comando não for
encontrado, é essa pasta que precisa entrar no `Path`. Para descobrir qual é a sua:

```bash
python -c "import sysconfig; print(sysconfig.get_path('scripts', 'nt_user'))"
```

### Sem mexer em `PATH` nenhum

Dá para chamar pelo módulo, sem depender de executável no caminho:

```bash
python -m mule_bridge parastudio
```

</details>

## Começando

```bash
cd c:\projetos\minha-api   # a raiz, onde ficam a pasta da API e a do RAML

ponte init                 # pareia este repositório com um projeto do Studio
```

O `init` varre os dois lados, lista o que encontrou e **pergunta cada escolha** — mesmo
quando há um candidato só. O pareamento é seu: uma pasta errada aqui só aparece muito
depois, quando um comando copia para o lugar indevido.

```console
$ ponte init

Qual é a API que você edita aqui?  (c:\projetos\minha-api)
  1. pedidos-api
Escolha [1]:

E o RAML dessa API, qual é?
  1. pedidos-raml  (sugerido)
  2. nenhuma — não sincronizar o RAML
Escolha [1]:

Onde fica o workspace do Anypoint Studio?
  1. C:\Users\voce\AnypointStudio\studio-workspace
  2. outro caminho — eu digito
Escolha [1]:

No Studio, qual projeto é o seu pedidos-api?
  1. minha-api  [api]
Escolha [1]:

Config gravada em c:\projetos\minha-api\.mule-bridge.toml
```

**Workspace em outro lugar?** A última opção é sempre digitar o caminho. Se a busca não
achar nada — Studio instalado noutro drive, workspace numa pasta de rede — ele pede o
caminho direto. No Studio, ele aparece em *File → Switch Workspace*.

O pareamento fica em `.mule-bridge.toml`, na raiz do repositório — o `init` roda uma vez só.

Se as pastas do projeto forem repositórios git próprios (o caso comum: a API com seu
remoto, ao lado da pasta do RAML), o `init` também escreve um `.vscode/settings.json` para
que as edições feitas dentro delas apareçam no painel do editor — sem isso, VS Code e seus
forks (Trae, Cursor) listam apenas o repositório da raiz.

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

**Pedindo em português.** Como o `ponte` é um comando de terminal, qualquer agente que
execute comandos (Claude Code, Codex CLI) consegue usá-lo. Basta pedir *"sincroniza pro
Studio"*. Para que o agente saiba que a ferramenta existe num projeto, cole o trecho de
[docs/AGENTS-exemplo.md](docs/AGENTS-exemplo.md) no `AGENTS.md`/`CLAUDE.md` daquele
projeto — assim ele sabe quando acionar a ferramenta sem você explicar a cada sessão.

**Com barra, no Claude Code.** Instale a skill uma vez e o `/ponte` fica disponível em todos
os seus projetos. O jeito mais simples é pedir ao próprio Claude Code, numa sessão qualquer:

> Instale a skill do mule-bridge em `~/.claude/skills/ponte/SKILL.md`, copiando o conteúdo
> de https://github.com/igordiascardoso/mule-bridge/blob/main/.claude/skills/ponte/SKILL.md

Ou baixe o arquivo à mão: crie a pasta `.claude\skills\ponte` dentro do seu diretório de
usuário (`C:\Users\seu-usuario`) e salve o
[SKILL.md](.claude/skills/ponte/SKILL.md) lá dentro.

Em qualquer um dos casos, **reinicie a sessão** — as skills são carregadas na abertura.
Depois:

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
| `ponte parastudio raml` | Quero que o Studio leia o RAML que eu edito | só RAML | repo → Studio | Aponta o `pom.xml` do Studio para a sua pasta (ou copia, se houver pasta de RAML no workspace) |
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
se perdeu. O pareamento é atualizado junto, e a pasta recém-criada é **commitada como
base**: assim o `git status` fica limpo, e a partir dali mostra só o que **você** editar,
não a diferença entre duas versões do Exchange. Esse commit toca apenas a pasta do RAML,
sem levar nada mais que esteja em curso no repositório.

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

### `parastudio raml` — faz o Studio ler o RAML que você edita

Na maioria dos projetos o Studio consome o RAML como dependência do Exchange, sem pasta
própria no workspace — copiar arquivos para lá criaria uma pasta que ninguém lê. O que faz
o Studio enxergar suas edições é a referência no `pom.xml`, e é ela que este comando
aponta para a sua pasta:

```console
$ ponte parastudio raml

Apontando o Studio para C:\projetos\minha-api\pedidos-raml
Pronto: o Studio agora lê o RAML da sua pasta.
```

Feito isso, você edita o RAML e salva — o Studio detecta e redeploya, sem mais comandos.

Se o workspace tiver uma pasta de RAML de verdade (projetos onde a especificação é
importada como projeto próprio), o comando copia os arquivos normalmente.

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

**Os casos:**

| Situação | O que acontece |
|---|---|
| Você e o outro lado mexeram em pontos diferentes | Junta sozinho, os dois lados preservados |
| Só um dos lados mexeu | Entra direto, sem cerimônia |
| Os dois chegaram ao mesmo texto | Não é conflito: é uma mudança só |
| **Os dois mexeram no mesmo ponto** | Para, mostra as duas versões, e **não escreve nada** |
| **Os dois acrescentaram no mesmo lugar** | Para: não há como saber qual vem primeiro |

As duas últimas linhas são a mesma regra vista de dois ângulos: a junção resolve enquanto
as mudanças **não se tocam**. Duas linhas distantes juntam mesmo estando no mesmo arquivo;
dois blocos acrescentados no fim do arquivo, não — nesse caso a decisão é qual ordem você
quer, e ela é sua.

O mesmo vale para `pararepo api`, que usa o último commit do repositório como base: o que
você mudou desde ele é seu, o que aparece diferente do lado do Studio veio de lá.

**Resolvendo um conflito.** Edite o arquivo combinando as duas versões e rode de novo com
`--resolvido --aplicar` — isso diz "já combinei, aceite o que está na pasta":

```bash
ponte pararepo raml --resolvido --aplicar
```

Sem essa flag o comando não aplicaria: para ele, o texto combinado ainda divergia dos dois
lados, e ele repetiria o mesmo conflito para sempre. Depois de aplicar, aponte o `pom.xml`
para a versão nova — é isso que fecha o ciclo e encerra o aviso.

**O que vem de fora é commitado à parte.** Ao aplicar, os arquivos que chegaram do
Exchange sem cruzar com edição sua vão para um commit próprio
(`chore(raml): especificacao leilao 1.1.55`). O que sobra no `git status` é o seu trabalho
— então um `git diff` mostra só ele, em vez de misturar as duas coisas.

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

pytest          # 148 testes
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
- [x] Separar o commit do que veio de fora do commit das suas edições
- [x] **Skill do Claude Code** — `/ponte parastudio` dentro de uma sessão
- [ ] **MCP server** — os mesmos comandos como ferramentas MCP, para clients que não sejam
      o Claude Code
- [x] **`AGENTS.md` de exemplo** — [docs/AGENTS-exemplo.md](docs/AGENTS-exemplo.md)

## Contribuindo

Issues e PRs são bem-vindos. Para mudanças de comportamento, um teste junto ajuda bastante —
a suíte roda em menos de um segundo.

## Licença

[MIT](LICENSE) © Igor Dias Cardoso
