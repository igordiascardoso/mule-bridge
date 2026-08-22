<div align="center">

# 🌉 mule-bridge

**Você edita seu projeto Mule no repositório. O Anypoint Studio roda de outra pasta, o
workspace dele. As duas não se falam — o `ponte` faz essa ponte.**

[![licença MIT](https://img.shields.io/badge/licen%C3%A7a-MIT-1f6feb?style=flat-square)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-3776ab?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![skill /ponte](https://img.shields.io/badge/Claude_Code-skill%20%2Fponte-d97757?style=flat-square)](#com-agentes-de-ia)

</div>

```
        SEU REPO                             WORKSPACE DO STUDIO
   ┌───────────────────┐                    ┌───────────────────┐
   │  pedidos-api/     │ ──  parastudio  ──▶│  pedidos-api/     │
   │  pedidos-raml/    │                    │                   │
   │                   │◀──  pararepo   ────│  o scaffold gera  │
   │                   │      + merge       │  os flows novos   │
   └───────────────────┘                    └───────────────────┘
      você edita aqui                          o Studio roda aqui
```

```bash
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

O comando é **`ponte`**. Precisa de Python 3.10+.

<details>
<summary><b>Índice</b></summary>

- [Os seis jeitos de sincronizar](#os-seis-jeitos-de-sincronizar)
- [E três que cuidam do pareamento](#e-três-que-cuidam-do-pareamento)
- [Começando](#começando)
- [Fluxos](#fluxos)
- [O merge: trazer o novo sem perder o seu](#o-merge-trazer-o-novo-sem-perder-o-seu)
- [Duas coisas que ele nunca faz](#duas-coisas-que-ele-nunca-faz)
- [Com agentes de IA](#com-agentes-de-ia)

</details>

## Os seis jeitos de sincronizar

```
▸ PARA O STUDIO                                    escreve no workspace

  /ponte parastudio raml    faz o Studio ler o RAML que você edita
                            não copia nada, só muda o pom do workspace
  /ponte parastudio api     copia sua API para o workspace, por cima e sem merge
                            o seu repo não é tocado
  /ponte parastudio force   copia RAML + API para o workspace, por cima e sem merge
                            o seu repo não é tocado
  /ponte parastudio         recusa: falta a palavra


▸ PARA O REPO                                   escreve no seu repositório

  /ponte pararepo raml      traz a versão nova do Exchange e faz MERGE
                            na sua pasta de RAML — nada seu se perde
  /ponte pararepo api       traz o que o Studio mudou e faz MERGE
                            na sua pasta da API — nada seu se perde
  /ponte pararepo force  ⚠️  copia RAML + API por cima do seu repo, SEM merge
                            apaga o que você não commitou
  /ponte pararepo           recusa: falta a palavra
```

## E três que cuidam do pareamento

```
/ponte init      pareia o repo com um projeto do workspace (uma vez por projeto)
/ponte status    diz se as pastas dos dois lados estão no lugar, e onde ficam
/ponte caminho   reaponta o pareamento quando uma pasta saiu do lugar
```

Dois comandos, três palavras: `raml`, `api`, `force` — **uma delas é obrigatória**, e elas não
se combinam (`pararepo raml force` é recusado).

> [!IMPORTANT]
> **Só o `pararepo` faz merge.** O `parastudio` copia por cima, e pode: o destino é o
> workspace, que o Studio reconstrói. Já o `pararepo force` copia por cima do **seu**
> código — daí o ⚠️.

A barra é a forma do Claude Code, com a [skill instalada](#com-agentes-de-ia). Em qualquer
outro terminal são os mesmos comandos sem ela: `ponte pararepo api`.

## Começando

O `ponte` roda na pasta que **contém** o repositório clonado da API — não dentro dele. É de
lá que ele enxerga as duas pastas como irmãs:

```
c:\projetos\pedidos\          <- é aqui que se roda o init
├── pedidos-api\              <- o repositório clonado (a API)
└── pedidos-raml\             <- o RAML, extraído do Exchange
```

```bash
cd c:\projetos\pedidos
/ponte init
```

Ele acha os projetos dos dois lados e pergunta cada escolha — inclusive quando há um
candidato só, porque um pareamento errado só aparece muito depois.

O resultado fica no `.mule-bridge.toml`. **Adicione ao `.gitignore`**: é o caminho do *seu*
workspace.

Sem terminal para responder (agente de IA, IDE, CI), passe por flag:

```bash
ponte init --api pedidos-api --raml pedidos-raml \
  --studio-api pedidos-api --studio-raml pedidos-api-raml
```

`--raml nenhuma` se não houver RAML, `--studio-root` se o workspace não está num caminho
usual, `--force` para refazer.

## Fluxos

Seis situações, na ordem em que aparecem. A coluna **Onde** diz se o passo é um comando no
terminal ou algo que você faz no Studio.

> [!IMPORTANT]
> **O `parastudio` copia por cima.** Se o Studio gerou algo desde a última sincronização,
> traga com `pararepo` antes de mandar — senão você sobrescreve o que ele fez.

### 1. Primeira vez neste projeto

Clonou o repo e não tem nada configurado.

| | Onde | O que |
|---|---|---|
| 1 | terminal | `/ponte init` — pareia o repo com o projeto do workspace |
| 2 | terminal | `/ponte pararepo raml` — extrai a especificação e cria a pasta do RAML |

O `init` grava o `.mule-bridge.toml` e, se não houver pasta de RAML, já diz para rodar o
passo 2. A pasta nasce commitada como base: daí em diante o `git status` mostra só o que
**você** editar.

### 2. Saiu versão nova no Exchange

O scaffold do Studio tem um gatilho só: **você fazer o update da versão.** Ele então mexe no
`pom.xml`, no `.classpath` e no `application.xml` — inclusive criando flows para endpoints
novos. Tudo no workspace.

| | Onde | O que |
|---|---|---|
| 1 | Studio | `Properties > Mule Project > APIs` → update da versão. Ele oferece o scaffold; ao confirmar, gera os flows |
| 2 | terminal | `/ponte pararepo api` — traz o `application.xml` com os flows, em merge com o seu código |
| 3 | terminal | `/ponte pararepo raml` — traz a especificação nova, em merge com as suas edições |

O `pom.xml` do repo continua apontando para o Exchange. Suba a versão nele quando for
commitar — o comando não faz isso.

### 3. Quero editar o RAML e o Studio ler

O contrário do fluxo 2: em vez de baixar do Exchange, o Studio passa a ler a **sua** pasta.

| | Onde | O que |
|---|---|---|
| 1 | terminal | `/ponte parastudio raml` — reescreve o pom do workspace para apontar para a sua pasta |
| 2 | seu editor | você edita o RAML; o Studio já lê dali |

Não há scaffold aqui: o projeto saiu do Exchange, e é o `apikit` que relê a especificação
local.

### 4. Mudei código, sem tocar no RAML

Um flow, um `.java`, um `.dwl`.

| | Onde | O que |
|---|---|---|
| 1 | terminal | `/ponte parastudio api` — manda para o Studio testar |

> [!TIP]
> Não há passo extra depois — o Studio detecta a mudança no disco e redeploya sozinho.

### 5. Deu conflito

Os dois lados mexeram no mesmo ponto do mesmo arquivo. Nada é gravado até você decidir.

| | Onde | O que |
|---|---|---|
| 1 | terminal | ele mostra as duas versões e pergunta: `1` a sua, `2` a que veio, `3` eu escrevo |
| 2 | terminal | você responde, ele grava o arquivo e segue para o próximo |

É o único caso que te interrompe, e é raro — [como ele pergunta, e o que acontece sem
terminal](#quando-ele-pergunta).

### 6. Uma pasta saiu do lugar

Você renomeou a pasta, ou trocou de máquina e o workspace mudou de caminho.

| | Onde | O que |
|---|---|---|
| 1 | terminal | `/ponte status` — mostra qual lado está `NAO ENCONTRADA` |
| 2 | terminal | `/ponte caminho` — reaponta; `manter` é o default, então Enter passa pelos que estão certos |
| 3 | terminal | `/ponte status` — confirma que os dois lados respondem |

## O merge: trazer o novo sem perder o seu

Duas coisas mudam ao mesmo tempo, e você não quer escolher entre elas:

- você editou o RAML **e** saiu versão nova no Exchange
- você mexeu num flow **e** o Studio gerou outros no scaffold

Copiar por cima resolveria uma e apagaria a outra. Por isso `pararepo raml` e
`pararepo api` não copiam: **eles juntam as duas versões**, e gravam no repo.

Para decidir, ele compara três versões de cada arquivo: como era antes, como está no repo
agora, e como chegou.

### `/ponte pararepo raml` — vem do Exchange, grava no repo

| Mudou no repo | Mudou no Exchange | Fica no repo |
|---|---|---|
| sim | não | a versão do repo |
| não | sim | a versão do Exchange |
| sim | sim, em outro ponto | as duas mudanças, juntas |
| sim | sim, no mesmo ponto | **ele pergunta** |

### `/ponte pararepo api` — vem do workspace, grava no repo

| Mudou no repo | Mudou no workspace | Fica no repo |
|---|---|---|
| sim | não | a versão do repo |
| não | sim | a versão do workspace |
| sim | sim, em outro ponto | as duas mudanças, juntas |
| sim | sim, no mesmo ponto | **ele pergunta** |

Arquivo que existe num lado só: se está apenas no repo, fica; se chegou apenas do outro, é
criado no repo. Se o Exchange apagou um arquivo, ele sai do repo também — a não ser que você
o tivesse editado, e aí a versão do repo fica, porque apagar seria decidir por você.

### Quando ele pergunta

Só quando os dois mexeram no mesmo ponto. Ele mostra os dois lados e espera:

```console
api.raml — as duas versoes mexeram nas mesmas linhas

1. a sua versao (a que esta no repositorio):
     meu: string

2. a versao que veio:
     novo: string

Fica qual? 1 = a sua, 2 = a que veio, 3 = eu escrevo [1]:
```

Você escolhe, ele grava, e acabou — sem segundo comando para rodar. O arquivo fica limpo:
nada de `<<<<<<<` e `>>>>>>>` sobrando dentro dele para você limpar depois.

**Se não houver onde digitar** — um agente de IA, uma extensão de IDE, um CI — ele mostra as
duas versões e **não grava nada, em nenhum arquivo**. Quem chamou combina as versões no repo
e roda o comando de novo.

### Dois detalhes do `pararepo raml`

**A pasta do RAML não existe?** Não há merge a fazer, então ele extrai o zip da versão que o
Studio usa para uma pasta nova na raiz do repositório (`pedidos-raml/`, do nome do artefato) e
para. É o caso de um projeto recém-clonado.

**Ele commita parte sozinho.** Os arquivos que vieram do Exchange e você não tinha tocado vão
para um commit à parte (`chore(raml): especificacao pedidos 1.1.55`). Sem isso, o seu
`git status` teria dezenas de arquivos de fora misturados com as suas duas linhas. O que
envolve o seu trabalho fica sem commit, para você revisar.

Depois, suba a versão no `pom.xml` — isso o comando não faz. Se esquecer, nada quebra: o
merge parte da versão que a **sua pasta** tem, não da que o `pom.xml` aponta. Pular versões
(da `1.1.52` direto para a `1.1.55`) também funciona.

## Duas coisas que ele nunca faz

- **Mexer no `pom.xml` do seu repositório.** Para o Studio ler seu RAML local a referência
  precisa mudar, e essa reescrita acontece **só no workspace**. Aqui ele segue apontando para
  o Exchange, que é o que vai para o remoto.
- **Apagar arquivo por conta própria.** Nenhum dos comandos remove nada: um arquivo que
  existe só no repo continua lá, e um que existe só no workspace também — é assim que
  `.classpath` e `.project`, que o Studio gera para si, sobrevivem a um `parastudio`. Se você
  apagou um flow no repo, apague no workspace do Studio também — senão ele segue rodando lá.

Nem `.git`, `target`, `.mule` ou `.settings` são sincronizados — é lista configurável no
`.mule-bridge.toml`.

## Com agentes de IA

O `ponte` é um comando de terminal, então qualquer agente que execute comandos usa direto —
basta pedir *"manda pro Studio"*. Para ele saber que a ferramenta existe num projeto, cole
[docs/AGENTS-exemplo.md](docs/AGENTS-exemplo.md) no `AGENTS.md` / `CLAUDE.md` daquele repo.

No Claude Code há a skill `/ponte`. Instale pedindo ao próprio Claude Code:

> Instale a skill do mule-bridge em `~/.claude/skills/ponte/SKILL.md`, copiando o conteúdo
> de https://github.com/igordiascardoso/mule-bridge/blob/main/.claude/skills/ponte/SKILL.md

Reinicie a sessão e os mesmos comandos valem com barra — `/ponte pararepo api`, e assim por
diante. A skill **nunca acrescenta `force` por conta própria**: essa palavra é sempre do
usuário.

## Se `ponte` não for encontrado

O pacote instalou, mas o terminal não sabe onde procurar. **Abriu um terminal novo depois de
instalar?** É a causa mais comum — o `PATH` só vale para terminais abertos depois.

Se não resolver:

```bash
python -m pipx ensurepath
```

Feche o terminal, abra outro, e `ponte` responde.

## Licença

[MIT](LICENSE) © Igor Dias Cardoso — [contribuindo](CONTRIBUTING.md)
