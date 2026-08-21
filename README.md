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

Três palavras: `raml`, `api`, `force`. Uma é obrigatória — sem ela o comando recusa em vez
de adivinhar.

**`raml` e `api` fazem merge**, como um `git merge`. Arquivo que só você editou fica como
está. Arquivo novo que você criou continua lá. Arquivo que os dois mexeram é combinado
linha por linha — e se as mudanças se cruzarem na mesma linha, ele pergunta antes de gravar.

**`force` copia por cima, sem merge.** É a única palavra que pode fazer trabalho
desaparecer, e em `pararepo` o trabalho é o seu. Raramente é o que você quer.

Não se combinam: `pararepo raml force` é recusado — fazer merge e sobrescrever são
decisões opostas.

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
candidato só, porque um pareamento errado só aparece depois, quando um comando escreve no
lugar indevido.

O resultado fica no `.mule-bridge.toml`. **Adicione ao `.gitignore`**: guarda o caminho do
seu workspace, que não serve para os colegas.

Sem terminal para responder (agente de IA, extensão de IDE, CI), passe por flag:

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

É um merge de três pontas, o mesmo que o git faz: compara **três** versões do arquivo, não
duas — a base (como estava antes de qualquer um mexer), a sua, e a que chegou. Com a base dá
para saber quem mudou o quê, e por isso as duas mudanças podem ficar em vez de uma vencer.

A base vem do cache local do Maven (`~/.m2`) no `pararepo raml`, e do último commit do seu
repositório no `pararepo api`.

### O que o comando mostra

```console
$ ponte pararepo raml

RAML 1.1.54 -> 1.1.55

┏━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┓
┃ o que                     ┃ arquivos ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━┩
│ merge (seu + o que veio)  │        2 │
│ novos, vindos do Exchange │        7 │
│ só seus, intocados        │        1 │
│ sem mudança               │       15 │
│ em conflito               │        0 │
└───────────────────────────┴──────────┘

10 arquivo(s) atualizado(s) em pedidos-raml.
```

| A linha | Quer dizer |
|---|---|
| merge | os dois mexeram, em lugares diferentes — ficaram as duas mudanças |
| novos, vindos do Exchange | só existe do outro lado — entra |
| **só seus, intocados** | **só você editou, ou só você criou — não é tocado** |
| sem mudança | ninguém mexeu |
| **em conflito** | **os dois mexeram na mesma linha — precisa de decisão** |

Zero em conflito quer dizer que o merge resolveu tudo sozinho.

### Quando há conflito

Ele mostra os dois lados e pergunta: `1` a sua, `2` a que veio, `3` você digita o texto
final. Responde e ele grava.

**Nunca fica marcador `<<<<<<<` no arquivo**, e não existe segundo comando para rodar —
sair do conflito é responder a pergunta.

Num agente de IA, onde não há terminal para digitar, ele imprime os dois lados e **não grava
nada**. O agente combina as versões e roda de novo.

### Depois, no git

O que veio de fora vai para um **commit separado** (`chore(raml): especificacao pedidos
1.1.55`). Então o `M` e o `??` que sobram no `git status` são os arquivos que **você** editou
e criou — o `git diff` mostra a sua mudança, não a diferença entre duas versões da
especificação.

Falta um passo manual: apontar o `pom.xml` para a versão nova.

## O que a ferramenta não faz sozinha

- **Mexer no `pom.xml` do repositório.** Para o Studio ler seu RAML local a referência precisa
  mudar — e essa reescrita acontece **só no workspace**. Aqui ele segue apontando para o
  Exchange com a versão travada, que é o que vai para o remoto.
- **Remover arquivo.** Um que só existe de um lado continua lá: o merge acrescenta e
  combina, nunca apaga. Se você apagou algo aqui, apague no outro lado também.
- **Escrever com conflito pendente** — nem os arquivos que deram certo.
- **Sincronizar `.git`, `target`, `.mule`, `.settings`** e outros artefatos de build.
- **Rodar em segundo plano.** Copiar arquivos enquanto o scaffold do Studio reescreve os
  mesmos arquivos é receita para perder trabalho. Você decide quando.

## Com agentes de IA

O `ponte` é um comando de terminal, então qualquer agente que execute comandos usa direto —
basta pedir *"manda pro Studio"*. Para ele saber que a ferramenta existe num projeto, cole
[docs/AGENTS-exemplo.md](docs/AGENTS-exemplo.md) no `AGENTS.md` / `CLAUDE.md` daquele repo.

No Claude Code há a skill `/ponte`. Instale pedindo ao próprio Claude Code:

> Instale a skill do mule-bridge em `~/.claude/skills/ponte/SKILL.md`, copiando o conteúdo
> de https://github.com/igordiascardoso/mule-bridge/blob/main/.claude/skills/ponte/SKILL.md

Reinicie a sessão e os mesmos oito comandos valem com barra, no chat:

```
/ponte parastudio raml        /ponte pararepo raml
/ponte parastudio api         /ponte pararepo api
/ponte parastudio force       /ponte pararepo force
/ponte status                 /ponte init
```

A skill **nunca acrescenta `force` por conta própria**: essa palavra é sempre do usuário.

## Se `ponte` não for encontrado

O pacote instalou, mas o terminal não sabe onde procurar. **Abriu um terminal novo depois de
instalar?** É a causa mais comum. Se não resolver, rode `python -m pipx ensurepath`, feche e
abra outro. E `python -m mule_bridge` funciona sem depender do `PATH`.

## Licença

[MIT](LICENSE) © Igor Dias Cardoso — [contribuindo](CONTRIBUTING.md)
