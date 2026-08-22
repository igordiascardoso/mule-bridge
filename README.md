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

- [Os jeitos de sincronizar](#os-jeitos-de-sincronizar)
- [E três que cuidam do pareamento](#e-três-que-cuidam-do-pareamento)
- [Começando](#começando)
- [Fluxos](#fluxos)
- [O merge: trazer o novo sem perder o seu](#o-merge-trazer-o-novo-sem-perder-o-seu)
- [Design Center e Exchange](#design-center-e-exchange)
- [Duas coisas que ele nunca faz](#duas-coisas-que-ele-nunca-faz)
- [Com agentes de IA](#com-agentes-de-ia)

</details>

## Os jeitos de sincronizar

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

  /ponte pararepo raml      traz a versão publicada no Exchange e faz MERGE
                            na sua pasta de RAML — nada seu se perde
  /ponte pararepo api       traz o que o Studio mudou e faz MERGE
                            na sua pasta da API — nada seu se perde
  /ponte pararepo force  ⚠️  copia RAML + API por cima do seu repo, SEM merge
                            apaga o que você não commitou
  /ponte pararepo           recusa: falta a palavra


▸ PARA O DESIGN CENTER / EXCHANGE          escreve no Anypoint, fora do seu repo

  /ponte paradesign raml    envia o RAML da sua pasta para o Design Center
                            só versiona lá — não publica no Exchange
  /ponte publicardesign     publica no Exchange a revisão atual do Design Center
                            mostra a versão publicada hoje antes de confirmar
```

## E três que cuidam do pareamento

```
/ponte init      pareia o repo com um projeto do workspace (uma vez por projeto)
/ponte status    diz se as pastas dos dois lados estão no lugar, e onde ficam
/ponte caminho   reaponta o pareamento quando uma pasta saiu do lugar
```

Dois comandos, três palavras: `raml`, `api`, `force` — **uma delas é obrigatória**, e elas não
se combinam (`pararepo raml force` é recusado). `paradesign` só aceita `raml`.

> [!IMPORTANT]
> **`paradesign raml` e `publicardesign` exigem a `anypoint-cli-v4` configurada** — são os
> únicos comandos que falam com o Design Center e o Exchange. Veja
> [Design Center e Exchange](#design-center-e-exchange) antes de usá-los. Os outros cinco
> comandos (Studio ↔ repo) continuam funcionando sem isso.

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
terminal, algo que você faz no Studio, ou algo confirmado no próprio terminal (Design Center
e Exchange).

> [!IMPORTANT]
> **O `parastudio` copia por cima.** Se o Studio gerou algo desde a última sincronização,
> traga com `pararepo` antes de mandar — senão você sobrescreve o que ele fez.
>
> E se os dois lados mexerem **no mesmo ponto do mesmo arquivo**, o `pararepo` para e
> pergunta qual versão fica. É raro: pontos diferentes ele junta sozinho, e na prática você
> mexe nos `services/` enquanto o scaffold mexe no `application.xml`. [Como ele
> pergunta](#quando-ele-pergunta).

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

O `pararepo raml` consulta o Exchange direto — não depende de ninguém ter feito o update no
Studio antes. O scaffold do Studio (que gera flows para endpoints novos) continua tendo um
gatilho só: **você fazer o update da versão** ali, quando quiser que o Studio também
acompanhe.

| | Onde | O que |
|---|---|---|
| 1 | terminal | `/ponte pararepo raml` — escolhe o projeto do Design Center, depois a versão do Exchange, e traz a especificação em merge com as suas edições |
| 2 | Studio | `Properties > Mule Project > APIs` → update da versão, se quiser o scaffold dos flows novos |
| 3 | terminal | `/ponte pararepo api` — traz o `application.xml` com os flows, em merge com o seu código |

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

**Para voltar ao Exchange** não há comando — mas nada foi destruído: a dependência original
ficou comentada no `pom.xml` do workspace, ao lado da nova. Apague a que tem `systemPath` e
descomente a que estava lá. (Ou apague o projeto no Studio e reimporte: o workspace é
descartável.)

### 4. Mudei código, sem tocar no RAML

Um flow, um `.java`, um `.dwl`.

| | Onde | O que |
|---|---|---|
| 1 | terminal | `/ponte parastudio api` — manda para o Studio testar |

> [!TIP]
> Não há passo extra depois — o Studio detecta a mudança no disco e redeploya sozinho.

### 5. Uma pasta saiu do lugar

Você renomeou a pasta, ou trocou de máquina e o workspace mudou de caminho.

| | Onde | O que |
|---|---|---|
| 1 | terminal | `/ponte status` — mostra qual lado está `NAO ENCONTRADA` |
| 2 | terminal | `/ponte caminho` — reaponta; `manter` é o default, então Enter passa pelos que estão certos |
| 3 | terminal | `/ponte status` — confirma que os dois lados respondem |

### 6. Editei o RAML e quero publicar uma versão nova

Substitui o fluxo manual de copiar e colar arquivo por arquivo na interface do Design
Center.

| | Onde | O que |
|---|---|---|
| 1 | seu editor | você edita a pasta de RAML do repositório |
| 2 | terminal | `/ponte paradesign raml` — escolhe o projeto e envia a pasta para o Design Center |
| 3 | terminal | `/ponte publicardesign` — mostra a versão publicada hoje, confirma, e publica a nova |

O `paradesign raml` só versiona no Design Center — quem quiser revisar antes de publicar
pode subir várias vezes sem afetar o Exchange. O `publicardesign` é o único passo que cria
uma versão nova, visível para quem consome a API.

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

**A pasta do RAML não existe?** Não há merge a fazer, então ele baixa a versão do Exchange
escolhida direto para uma pasta nova na raiz do repositório (`pedidos-raml/`, do nome do
artefato) e para. É o caso de um projeto recém-clonado.

**Ele commita parte sozinho.** Os arquivos que vieram do Exchange e você não tinha tocado vão
para um commit à parte (`chore(raml): especificacao pedidos 1.1.55`). Sem isso, o seu
`git status` teria dezenas de arquivos de fora misturados com as suas duas linhas. O que
envolve o seu trabalho fica sem commit, para você revisar.

Depois, suba a versão no `pom.xml` — isso o comando não faz. Se esquecer, nada quebra: o
merge parte da versão que a **sua pasta** tem, não da que o `pom.xml` aponta. Pular versões
(da `1.1.52` direto para a `1.1.55`) também funciona.

## Design Center e Exchange

`paradesign raml` e `publicardesign` falam com o Anypoint pela `anypoint-cli-v4` — os outros
comandos não precisam disso.

> [!IMPORTANT]
> **Pré-requisito, uma vez por máquina:**
> ```bash
> node -v                                    # precisa ser 22 ou mais novo
> npm install -g anypoint-cli-v4-public
> anypoint-cli-v4 conf client_id SEU_ID
> anypoint-cli-v4 conf client_secret SEU_SECRET
> ```
> A credencial (Connected App com os escopos `Design Center Developer` e `Exchange
> Contributor`) fica cifrada na própria máquina, fora do `ponte` e fora do repositório. Sem
> isso, `pararepo raml`, `paradesign raml` e `publicardesign` recusam com o erro da própria
> `anypoint-cli-v4`.

**Qual projeto do Design Center?** Se houver mais de um na sua organização, ele pergunta —
digite um trecho do nome para filtrar, ou Enter para ver todos. Errou a digitação? Ele sugere
o mais parecido e pede confirmação antes de seguir; nunca decide por conta própria.

**Qual versão do Exchange?** No `pararepo raml`, depois de escolher o projeto, um menu com a
mais atual, as duas anteriores, e a opção de digitar outra versão qualquer.

**Antes de enviar ou publicar**, ele verifica se os arquivos `.raml` do projeto têm o
cabeçalho certo (`#%RAML 1.0`) — o Exchange às vezes aceita e publica um RAML malformado sem
avisar, então essa checagem acontece antes, não depois.

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

No Claude Code há a skill `/ponte`, e **o `init` já a instala** — nada a baixar ou copiar à
mão. Ela fica em `~/.claude/skills/`, que serve as duas formas de usar o Claude Code: o
terminal e a extensão do VS Code. Abra uma sessão nova (em qualquer das duas) e os mesmos
comandos valem com barra: `/ponte pararepo api`.

Cada `init` grava a versão que acompanha a CLI, então a skill nunca fica atrás do que os
comandos fazem. Ela **nunca acrescenta `force` por conta própria**: essa palavra é sempre do
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
