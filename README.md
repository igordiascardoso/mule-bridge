<div align="center">

# mule-bridge

**Edite seu projeto Mule onde você quiser. O Anypoint Studio acompanha.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-201%20passing-brightgreen)](tests/)

</div>

---

## O problema

O código vive em dois lugares que não se falam:

```
c:\projetos\minha-api                    ~\AnypointStudio\studio-workspace\minha-api
você edita aqui              ✗           o Studio roda daqui
```

O que você edita no repositório não aparece no Studio. A saída de sempre é excluir o
projeto no Studio e reimportar — a cada mudança.

E o caminho de volta também importa: quando o RAML muda de versão, o scaffold do Studio
reescreve o `application.xml` e cria flows novos. Isso precisa voltar para o repositório
**sem atropelar o que você editou lá**.

## Os oito comandos

```
ponte parastudio raml      →  faz o Studio ler o RAML que você edita
ponte parastudio api       →  copia sua API do repo para o workspace
ponte parastudio force     →  copia tudo por cima do workspace
ponte parastudio           →  não existe: falta a palavra

ponte pararepo raml        →  junta a versão nova do RAML com a sua, e grava
ponte pararepo api         →  junta o que o Studio mudou com o que você mudou, e grava
ponte pararepo force       →  ⚠️  copia por cima do seu repo, sem juntar
ponte pararepo             →  não existe: falta a palavra
```

**`parastudio` escreve no workspace do Studio. `pararepo` escreve no seu repositório.**
É a única coisa que você precisa saber antes de rodar qualquer um.

O vocabulário são três palavras: `raml`, `api` e `force`. Uma delas é obrigatória — sem
palavra o comando recusa, em vez de adivinhar.

### O que `force` significa

`force` **sobrescreve sem juntar**. É a única palavra que pode fazer trabalho seu ser
perdido, e existe para o caso raro de você querer descartar um lado inteiro.

`raml` e `api` fazem o contrário: eles **juntam**. Se o outro lado mexeu numa parte do
arquivo e você em outra, as duas mudanças ficam. Nada do seu trabalho é perdido.

Por isso as palavras não se combinam: `ponte pararepo raml force` é recusado — ou você
junta, ou você sobrescreve.

## Instalação

```bash
python -m pip install --user pipx
python -m pipx ensurepath
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

**Feche o terminal e abra outro** — o `ensurepath` mexe no `PATH` e a janela aberta não vê
a mudança. Confirme com `ponte --version`.

O pacote chama-se `mule-bridge`; o comando é **`ponte`**. Precisa de Python 3.10+. Não
precisa de Java nem Maven — quem compila continua sendo o Studio.

<details>
<summary><b>Se <code>ponte</code> não for encontrado</b></summary>

O pacote instalou, mas o terminal não sabe onde procurar. Na ordem:

1. **Abriu um terminal novo depois do `ensurepath`?** É a causa mais comum.
2. Rode `python -m pipx ensurepath` de novo e leia a saída — ela diz qual pasta foi
   adicionada.
3. Confirme que o pacote está lá: `python -m mule_bridge --version`. Se isso funcionar, o
   problema é só o `PATH`.

No Windows, para acertar à mão: *Iniciar → "variáveis de ambiente" → Variáveis de Ambiente
→ **Path** (do usuário) → Novo* → cole o caminho que o `ensurepath` mostrou (normalmente
`C:\Users\seu-usuario\.local\bin`). Abra um terminal novo.

Sem mexer em `PATH` nenhum, dá para chamar pelo módulo:

```bash
python -m mule_bridge parastudio api
```

</details>

## Começando

```bash
cd c:\projetos\minha-api   # a raiz, onde ficam a pasta da API e a do RAML
ponte init                 # pareia este repositório com um projeto do Studio
```

O `init` varre os dois lados e **pergunta cada escolha**, mesmo quando há um candidato só —
uma pasta errada aqui só aparece muito depois, quando um comando copia para o lugar
indevido.

```console
$ ponte init

Qual é a API que você edita aqui?
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

Config gravada em c:\projetos\minha-api\.mule-bridge.toml
```

Roda uma vez só. O pareamento fica em `.mule-bridge.toml`, na raiz.

> Esse arquivo guarda o caminho do **seu** workspace, que não serve para os colegas.
> Adicione-o ao `.gitignore`.

**Workspace em outro lugar?** A última opção é sempre digitar o caminho. No Studio, ele
aparece em *File → Switch Workspace*.

<details>
<summary>Sem terminal interativo (extensão de IDE, agente de IA, CI)</summary>

O `init` pergunta pelo terminal, mas nem sempre há um. Nesses casos ele lista o que
encontrou e ensina a flag que dispensa o prompt:

```bash
ponte init --api pedidos-api --raml pedidos-raml \
  --studio-api minha-api --studio-raml minha-api-raml
```

Use `--raml nenhuma` para não sincronizar RAML, `--studio-root` quando o workspace não
estiver num caminho padrão, e `--force` para refazer uma config existente.

</details>

## O dia a dia

Você editou o contrato e quer ver o Studio reagir:

```bash
ponte parastudio raml     # o Studio passa a ler o RAML que você edita
# o Studio roda o scaffold e cria os flows novos
ponte pararepo api        # traz os flows novos, sem perder seu código
git commit
```

Um colega publicou uma versão nova no Exchange:

```bash
ponte pararepo raml       # junta a versão nova com as suas edições
ponte parastudio api      # manda para o Studio testar
git commit
```

Para ver onde você está antes de mexer em nada:

```bash
ponte status              # o que está pareado e quantos arquivos diferem
```

## Como a junção funciona

### `pararepo raml` — a versão nova sem perder o que você escreveu

Copiar por cima apagaria suas edições. O `pararepo raml` faz o contrário: trata a versão do
Exchange como base e **reaplica suas edições em cima**, como um `git rebase`.

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

10 arquivo(s) atualizado(s) em pedidos-raml.
```

A versão a trazer é a mais alta já baixada no cache local do Maven (`~/.m2`) — não é preciso
credencial do Exchange nem estar online.

**O que vem de fora é commitado à parte.** Os arquivos que chegaram do Exchange sem cruzar
com edição sua vão para um commit próprio (`chore(raml): especificacao pedidos 1.1.55`). O
que sobra no `git status` é **só o seu trabalho** — então um `git diff` mostra só ele.

Depois de aplicar, aponte o `pom.xml` para a versão nova. É isso que fecha o ciclo.

### Quando os dois mexeram na mesma linha

Aí não há como juntar sozinho, e o comando **pergunta na hora**:

```console
api.raml — as duas versoes mexeram nas mesmas linhas

1. a sua versao (a que esta no repositorio):
   Item:
     meu: string

2. a versao que veio:
   Item:
     novo: string

Fica qual? 1 = a sua, 2 = a que veio, 3 = eu escrevo [1]:
```

Você responde e ele grava. **Nunca fica marcador de merge no arquivo**, e não há segundo
comando para rodar — sair do conflito é responder a pergunta.

Fora esse caso não há ambiguidade nenhuma:

| Situação | O que acontece |
|---|---|
| Vocês mexeram em pontos diferentes | Junta sozinho, os dois lados preservados |
| Só um dos lados mexeu | Entra direto |
| Os dois chegaram ao mesmo texto | Não é conflito: é uma mudança só |
| **Os dois mexeram no mesmo ponto** | Pergunta qual fica |

O mesmo vale para `pararepo api`, que usa o último commit do repositório como base.

**Num agente de IA, onde não há terminal para digitar**, o comando imprime as duas versões
e **não grava nada** — o agente combina os dois lados e roda de novo. Escolher um lado
calado é onde uma mudança se perde sem ninguém ver.

### `parastudio raml` — faz o Studio ler sua pasta

Na maioria dos projetos o Studio consome o RAML como dependência do Exchange, sem pasta
própria no workspace — copiar arquivos para lá criaria uma pasta que ninguém lê. O que faz
o Studio enxergar suas edições é a referência no `pom.xml`, e é ela que este comando aponta
para a sua pasta:

```console
$ ponte parastudio raml

Apontando o Studio para C:\projetos\minha-api\pedidos-raml
Pronto: o Studio agora lê o RAML da sua pasta.
```

Daí em diante você edita o RAML e salva — o Studio detecta e redeploya, sem mais comandos.

Se o workspace tiver uma pasta de RAML de verdade, o comando copia os arquivos normalmente.

### O que nunca acontece

- **O `pom.xml` do repositório nunca é sobrescrito.** No `parastudio` a reescrita acontece
  só no destino; no `pararepo` o arquivo é ignorado. Seu repositório segue apontando para o
  Exchange com a versão travada.
- **Nada é apagado.** Um arquivo removido de um lado continua no outro até você removê-lo lá.
- **Nada é escrito enquanto houver conflito pendente** — nem os arquivos que deram certo.
- **`.git`, `target`, `.mule`, `.settings`** e outros artefatos de build nunca são
  sincronizados. A lista é configurável em `.mule-bridge.toml`.

**Por que não há watcher automático:** um processo copiando arquivos enquanto o scaffold do
Studio reescreve os mesmos arquivos é receita para perder trabalho. Você decide quando
sincronizar.

## Com agentes de IA

A CLI é a única camada com lógica — o resto são atalhos para acioná-la.

**Pedindo em português.** Qualquer agente que execute comandos (Claude Code, Codex CLI)
consegue usar o `ponte`. Basta pedir *"sincroniza pro Studio"*. Para que ele saiba que a
ferramenta existe num projeto, cole o trecho de
[docs/AGENTS-exemplo.md](docs/AGENTS-exemplo.md) no `AGENTS.md`/`CLAUDE.md` daquele projeto.

**Com barra, no Claude Code.** Instale a skill uma vez e o `/ponte` fica disponível em todos
os seus projetos. O mais simples é pedir ao próprio Claude Code:

> Instale a skill do mule-bridge em `~/.claude/skills/ponte/SKILL.md`, copiando o conteúdo
> de https://github.com/igordiascardoso/mule-bridge/blob/main/.claude/skills/ponte/SKILL.md

**Reinicie a sessão** — skills são carregadas na abertura. Depois:

```
/ponte parastudio raml
/ponte pararepo api
/ponte status
```

A skill não reimplementa nada: ela escolhe o comando certo e **nunca acrescenta `force` por
conta própria** — essa palavra é sempre do usuário.

## Desenvolvimento

```bash
git clone https://github.com/igordiascardoso/mule-bridge
cd mule-bridge
pip install -e ".[dev]"

pytest          # 201 testes, menos de um segundo
ruff check .
```

Treze testes rodam contra um projeto Mule e um RAML de verdade e são **pulados por padrão**
— nenhum caminho ou identificador de organização fica no código, que é público. Para
rodá-los, aponte os seus:

```bash
PONTE_TESTE_API=/caminho/para/uma-api \
PONTE_TESTE_GRUPO=<groupId> PONTE_TESTE_ARTEFATO=<artifactId> pytest
```

O projeto apontado nunca é alterado: os testes trabalham sobre uma cópia temporária.

A lógica vive inteira em [`src/mule_bridge/`](src/mule_bridge/): `discovery` acha os
projetos, `sync` move os arquivos, `reconcile` faz a junção, `pomrewrite` cuida do
`pom.xml`, `config` lembra o pareamento.

## Roadmap

- [x] Sync bidirecional com descoberta interativa dos dois lados
- [x] Reescrita do `pom.xml` isolada no workspace do Studio
- [x] Reconciliação tipo `git rebase` para o RAML e para a API
- [x] Commit separado para o que veio de fora
- [x] Conflito resolvido na hora, sem segundo comando
- [x] Skill do Claude Code
- [ ] **MCP server** — os mesmos comandos como ferramentas MCP

## Licença

[MIT](LICENSE) © Igor Dias Cardoso
