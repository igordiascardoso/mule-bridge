# mule-bridge

Você edita seu projeto Mule no repositório. O Anypoint Studio roda de outra pasta, o
workspace dele. As duas não se falam — o `ponte` faz essa ponte.

```bash
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

O comando é **`ponte`**. Precisa de Python 3.10+.

## Os seis jeitos de sincronizar

```
/ponte parastudio raml      faz o Studio ler o RAML que você edita — não copia nada, só muda o pom do workspace
/ponte parastudio api       copia sua API para o workspace, por cima e sem merge — o seu repo não é tocado
/ponte parastudio force     copia RAML + API para o workspace, por cima e sem merge — o seu repo não é tocado
/ponte parastudio           recusa: falta a palavra

/ponte pararepo raml        traz a versão nova do Exchange e faz MERGE na sua pasta de RAML — nada seu se perde
/ponte pararepo api         traz o que o Studio mudou e faz MERGE na sua pasta da API — nada seu se perde
/ponte pararepo force    ⚠️  copia RAML + API por cima do seu repo, SEM merge — apaga o que você não commitou
/ponte pararepo             recusa: falta a palavra
```

## E três que cuidam do pareamento

```
/ponte init      pareia o repo com um projeto do workspace (uma vez por projeto)
/ponte status    diz se as pastas dos dois lados estão no lugar, e onde ficam
/ponte caminho   reaponta o pareamento quando uma pasta saiu do lugar
```

Dois comandos, três palavras: `raml`, `api`, `force` — **uma delas é obrigatória**, e elas não
se combinam (`pararepo raml force` é recusado).

**Só o `pararepo` faz merge.** O `parastudio` copia por cima, e pode: o destino é o workspace,
que o Studio reconstrói. Já o `pararepo force` copia por cima do **seu** código — daí o ⚠️.

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
  --studio-api minha-api --studio-raml minha-api-raml
```

`--raml nenhuma` se não houver RAML, `--studio-root` se o workspace não está num caminho
usual, `--force` para refazer.

## O dia a dia

Editei o contrato e quero ver o Studio reagir:

```bash
/ponte parastudio raml     # o Studio passa a ler o RAML que você edita
# o Studio roda o scaffold e cria os flows novos
/ponte pararepo api        # traz os flows novos, sem perder seu código
```

Saiu versão nova do RAML no Exchange:

```bash
/ponte pararepo raml       # merge com as suas edições
/ponte parastudio api      # manda para o Studio testar
```

Depois de qualquer `parastudio` **não há passo extra** — o Studio detecta a mudança no disco
e redeploya sozinho.

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
- **Apagar arquivo.** Um que só existe de um lado continua lá. Se você apagou algo aqui,
  apague no outro lado também.

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
instalar?** É a causa mais comum. Se não resolver, rode `python -m pipx ensurepath`, feche e
abra outro. E `python -m mule_bridge` funciona sem depender do `PATH`.

## Licença

[MIT](LICENSE) © Igor Dias Cardoso — [contribuindo](CONTRIBUTING.md)
