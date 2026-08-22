# mule-bridge

Você edita seu projeto Mule no repositório. O Anypoint Studio roda de outra pasta, o
workspace dele. As duas não se falam — o `ponte` faz essa ponte.

```bash
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

O comando é **`ponte`**. Precisa de Python 3.10+.

## Os oito comandos

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

**`parastudio` escreve no workspace. `pararepo` escreve no seu repositório.** O outro lado é
só lido.

**O merge existe em dois comandos só: `pararepo raml` e `pararepo api`** — e ele grava sempre
no seu repositório, nunca no workspace. Os outros copiam por cima: no `parastudio` isso é
seguro, porque o destino é o workspace, que o Studio reconstrói; no `pararepo force` não,
porque o destino é o seu código.

Uma das três palavras — `raml`, `api`, `force` — é obrigatória, e elas não se combinam:
`pararepo raml force` é recusado.

A barra é a forma do Claude Code, com a [skill instalada](#com-agentes-de-ia). Em qualquer
outro terminal são os mesmos comandos sem ela: `ponte pararepo api`.

Mais três, que não sincronizam nada — cuidam do pareamento:

```
/ponte init      pareia o repo com um projeto do workspace (uma vez por projeto)
/ponte status    diz se as pastas dos dois lados estão no lugar, e onde ficam
/ponte caminho   reaponta o pareamento quando uma pasta saiu do lugar
```

## Começando

```bash
cd c:\projetos\minha-api   # a raiz, onde ficam a pasta da API e a do RAML
ponte init
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

## Trazer sem perder o que você fez

Você editou o RAML e sai uma versão nova no Exchange. Ou você mexeu num flow e o Studio
gerou outros. Copiar por cima apagaria o seu trabalho — então `pararepo raml` e
`pararepo api` não copiam: eles fazem **merge** das duas versões.

O merge escreve **no seu repositório**, e só nele. O workspace do Studio não é tocado:

| Comando | De onde vem o novo | Onde ele escreve |
|---|---|---|
| `pararepo raml` | a versão nova do RAML, do Exchange | a sua pasta do RAML (`pedidos-raml/`) |
| `pararepo api` | o que está no workspace do Studio | a sua pasta da API (`pedidos-api/`) |

Para cada arquivo dessa pasta, ele compara a **sua versão** (a que está no repositório) com a
**versão que chegou** (do Exchange, ou do workspace):

| O que aconteceu com o arquivo | O que fica gravado no seu repositório |
|---|---|
| só você editou | a sua, intacta — ele nem abre o arquivo |
| só a versão que chegou mudou | a que chegou, no lugar da sua |
| os dois mudaram, **em linhas diferentes** | um arquivo com as duas mudanças dentro |
| os dois mudaram, **na mesma linha** | ele **pergunta**: a sua, a que chegou, ou o que você digitar |
| existe só no seu repositório | a sua, onde está — não é apagada |
| existe só do outro lado | a que chegou, criada na sua pasta |

**Só a mesma linha precisa de você.** Aí ele mostra os dois lados e espera:

```console
api.raml — as duas versoes mexeram nas mesmas linhas

1. a sua versao (a que esta no repositorio):
     meu: string

2. a versao que veio:
     novo: string

Fica qual? 1 = a sua, 2 = a que veio, 3 = eu escrevo [1]:
```

Você responde, ele grava o arquivo na sua pasta com a versão escolhida, e acabou. Não sobra
marcador `<<<<<<<` dentro dele, e não há segundo comando para rodar.

Num agente de IA não existe onde digitar a resposta — então ele mostra as duas versões e
**não grava nada, em nenhum arquivo**. O agente escreve a versão combinada na sua pasta e
roda o comando de novo.

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
