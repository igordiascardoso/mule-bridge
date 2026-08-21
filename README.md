# mule-bridge

Você edita seu projeto Mule no repositório. O Anypoint Studio roda de outra pasta, o
workspace dele. As duas não se falam — o `ponte` faz essa ponte.

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

ponte pararepo raml        faz merge da versão nova do RAML com a sua, e grava
ponte pararepo api         faz merge do que o Studio mudou com o que você mudou
ponte pararepo force       ⚠️  copia RAML + API por cima do seu repo, sem merge
ponte pararepo             recusa: falta a palavra
```

**`parastudio` escreve no workspace. `pararepo` escreve no seu repositório.**

Três palavras: `raml`, `api`, `force` — uma é obrigatória. `raml` e `api` fazem merge e não
perdem nada do seu trabalho; `force` copia por cima e pode apagá-lo, então raramente é o que
você quer. Não se combinam: `pararepo raml force` é recusado.

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
ponte parastudio raml     # o Studio passa a ler o RAML que você edita
# o Studio roda o scaffold e cria os flows novos
ponte pararepo api        # traz os flows novos, sem perder seu código
```

Saiu versão nova do RAML no Exchange:

```bash
ponte pararepo raml       # merge com as suas edições
ponte parastudio api      # manda para o Studio testar
```

Depois de qualquer `parastudio` **não há passo extra** — o Studio detecta a mudança no disco
e redeploya sozinho.

## O merge

`pararepo raml` e `pararepo api` não copiam por cima — eles fazem merge, como um `git merge`.

Cada arquivo cai num destes casos:

- os dois mexeram em **pontos diferentes** → ficam as duas mudanças
- **só existe** do outro lado → entra
- **só você** editou ou criou → ele não chega perto
- os dois mexeram na **mesma linha** → ele pergunta qual fica

No fim ele imprime quantos arquivos caíram em cada caso, e quantos foram gravados.

Se a pasta do RAML ainda não existe, não há merge a fazer: `pararepo raml` extrai a versão
que o Studio usa para uma pasta nova na raiz, e para.

### Quando ele pergunta

```console
api.raml — as duas versoes mexeram nas mesmas linhas

1. a sua versao (a que esta no repositorio):
     meu: string

2. a versao que veio:
     novo: string

Fica qual? 1 = a sua, 2 = a que veio, 3 = eu escrevo [1]:
```

Você responde e ele grava. **Não fica marcador `<<<<<<<` no arquivo** e não há segundo
comando — responder é o que resolve.

Num agente de IA, onde não há terminal para digitar, ele mostra as duas versões e **não grava
nada**. O agente combina e roda de novo.

### Depois

No `pararepo raml`, o que veio do Exchange e você não tinha tocado é **commitado sozinho**
(`chore(raml): especificacao pedidos 1.1.55`) — senão dezenas de arquivos de fora se
misturariam com as suas duas linhas no `git status`. O resto fica sem commit, para você
revisar. Falta subir a versão no `pom.xml`, que o comando não mexe.

O `pararepo api` não commita nada: é pouco arquivo, e tudo fica no working tree.

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
