# mule-bridge

Você edita seu projeto Mule no repositório. O Anypoint Studio roda de outra pasta, o
workspace. As duas não se falam — o `ponte` faz essa ponte.

```bash
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

O comando é **`ponte`**. Precisa de Python 3.10+.

## Os oito comandos

```
ponte parastudio raml      faz o Studio ler o RAML que você edita
ponte parastudio api       copia sua API para o workspace
ponte parastudio force     copia RAML + API por cima do workspace
ponte parastudio           recusa: falta a palavra

ponte pararepo raml        junta a versão nova do RAML com a sua, e grava
ponte pararepo api         junta o que o Studio mudou com o que você mudou, e grava
ponte pararepo force       ⚠️  copia RAML + API por cima do seu repo, sem juntar
ponte pararepo             recusa: falta a palavra
```

**`parastudio` escreve no workspace. `pararepo` escreve no seu repositório.**

Três palavras: `raml`, `api`, `force`. Uma é obrigatória — sem ela o comando recusa em vez
de adivinhar.

- **`raml` e `api` juntam.** Se o outro lado mexeu numa parte do arquivo e você em outra, as
  duas mudanças ficam. Nada seu é perdido.
- **`force` sobrescreve.** É a única que pode fazer trabalho seu desaparecer. Use quando
  quiser descartar um lado inteiro de propósito.

Por isso não se combinam: `pararepo raml force` é recusado.

Mais dois:

```
ponte init      pareia o repo com um projeto do workspace (uma vez por projeto)
ponte status    mostra o que está pareado e quantos arquivos diferem
```

## Começando

```bash
cd c:\projetos\minha-api   # a raiz, onde ficam a pasta da API e a do RAML
ponte init
```

O `init` acha os projetos dos dois lados e pergunta cada escolha — inclusive quando há um
candidato só, porque um pareamento errado só aparece depois, quando um comando escreve no
lugar indevido.

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

Roda uma vez. O resultado fica no `.mule-bridge.toml` — **adicione ao `.gitignore`**, porque
guarda o caminho do seu workspace, que não serve para os colegas.

Sem terminal para responder (agente de IA, extensão de IDE, CI), passe as escolhas por flag:

```bash
ponte init --api pedidos-api --raml pedidos-raml \
  --studio-api minha-api --studio-raml minha-api-raml
```

`--raml nenhuma` para não sincronizar RAML, `--studio-root` se o workspace não está num
caminho usual, `--force` para refazer.

## O dia a dia

Editei o contrato e quero ver o Studio reagir:

```bash
ponte parastudio raml     # o Studio passa a ler o RAML que você edita
# o Studio roda o scaffold e cria os flows novos
ponte pararepo api        # traz os flows novos, sem perder seu código
```

Saiu versão nova do RAML no Exchange:

```bash
ponte pararepo raml       # junta com as suas edições
ponte parastudio api      # manda para o Studio testar
```

Depois de qualquer `parastudio` **não há passo extra** — o Studio detecta a mudança no disco
e redeploya sozinho. Sem reimportar, sem refresh.

## Como a junção funciona

`pararepo raml` não copia por cima: trata a versão do Exchange como base e **reaplica suas
edições em cima**, como um `git rebase`.

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

A versão vem do cache local do Maven (`~/.m2`), onde o Studio já guarda cada uma que baixou
— sem credencial do Exchange, sem estar online.

**O que veio de fora é commitado à parte** (`chore(raml): especificacao pedidos 1.1.55`).
O que sobra no `git status` é só o seu trabalho, então o `git diff` mostra só ele. Depois,
aponte o `pom.xml` para a versão nova.

`pararepo api` faz o mesmo, usando o último commit do repositório como base.

### Quando os dois mexeram na mesma linha

Não há como juntar sozinho, então o comando pergunta:

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

Você responde e ele grava. **Nunca fica marcador `<<<<<<<` no arquivo**, e não há segundo
comando — sair do conflito é responder.

Num agente de IA, onde não há terminal para digitar, ele imprime os dois lados e **não grava
nada** — o agente combina e roda de novo. Escolher um lado calado é onde uma mudança se
perde sem ninguém ver.

### `parastudio raml` não copia arquivo

Na maioria dos projetos o Studio consome o RAML como dependência do Exchange e não tem pasta
dele no workspace — copiar para lá criaria uma pasta que ninguém lê. O que faz o Studio
enxergar suas edições é a referência no `pom.xml`, e é ela que o comando aponta:

```console
$ ponte parastudio raml

Apontando o Studio para C:\projetos\minha-api\pedidos-raml
Pronto: o Studio agora lê o RAML da sua pasta.
```

Daí em diante você edita o RAML e salva — o Studio redeploya. Se o workspace tiver uma pasta
de RAML de verdade, o comando copia normalmente.

## Garantias

- **O `pom.xml` do repositório nunca é sobrescrito.** No `parastudio` a reescrita acontece só
  no destino; no `pararepo` o arquivo é ignorado. Seu repo segue apontando para o Exchange
  com a versão travada, que é o que vai para o remoto.
- **Nada é apagado.** Um arquivo removido de um lado continua no outro.
- **Nada é escrito com conflito pendente** — nem os arquivos que deram certo.
- **`.git`, `target`, `.mule`, `.settings`** e outros artefatos de build nunca são
  sincronizados. Configurável no `.mule-bridge.toml`.
- **Não há watcher automático.** Um processo copiando arquivos enquanto o scaffold do Studio
  reescreve os mesmos arquivos é receita para perder trabalho. Você decide quando.

## Com agentes de IA

O `ponte` é um comando de terminal, então qualquer agente que execute comandos (Claude Code,
Codex CLI) usa direto — basta pedir *"manda pro Studio"*. Para ele saber que a ferramenta
existe num projeto, cole [docs/AGENTS-exemplo.md](docs/AGENTS-exemplo.md) no `AGENTS.md` /
`CLAUDE.md` daquele repo.

No Claude Code há a skill `/ponte`. Instale pedindo ao próprio Claude Code:

> Instale a skill do mule-bridge em `~/.claude/skills/ponte/SKILL.md`, copiando o conteúdo
> de https://github.com/igordiascardoso/mule-bridge/blob/main/.claude/skills/ponte/SKILL.md

Reinicie a sessão — skills carregam na abertura. A skill escolhe o comando certo e **nunca
acrescenta `force` por conta própria**: essa palavra é sempre do usuário.

## Se `ponte` não for encontrado

O pacote instalou, mas o terminal não sabe onde procurar:

1. **Abriu um terminal novo depois de instalar?** É a causa mais comum.
2. Rode `python -m pipx ensurepath`, feche o terminal e abra outro.
3. Confirme que o pacote está lá: `python -m mule_bridge --version`. Se funcionar, o problema
   é só o `PATH` — e `python -m mule_bridge` serve como saída.

## Desenvolvimento

```bash
git clone https://github.com/igordiascardoso/mule-bridge
cd mule-bridge
pip install -e ".[dev]"

pytest          # 201 testes
ruff check .
```

Treze testes rodam contra um projeto Mule e um RAML de verdade e são **pulados por padrão** —
nenhum caminho ou identificador de organização fica no código, que é público. Para rodá-los:

```bash
PONTE_TESTE_API=/caminho/para/uma-api \
PONTE_TESTE_GRUPO=<groupId> PONTE_TESTE_ARTEFATO=<artifactId> pytest
```

O projeto apontado nunca é alterado — os testes trabalham sobre uma cópia temporária.

A lógica vive inteira em [`src/mule_bridge/`](src/mule_bridge/): `discovery` acha os
projetos, `sync` move arquivos, `reconcile` faz a junção, `pomrewrite` cuida do `pom.xml`,
`config` lembra o pareamento.

Falta no roadmap: **MCP server**, para clients que não sejam o Claude Code.

## Licença

[MIT](LICENSE) © Igor Dias Cardoso
