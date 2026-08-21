# Trecho para o `AGENTS.md` / `CLAUDE.md` de um projeto Mule

Cole o bloco abaixo no arquivo de instruções do seu projeto Mule. É assim que qualquer
agente de IA que abra aquele repositório — Claude Code, Codex CLI, outro — descobre que a
ferramenta existe e quando acioná-la, mesmo sem skill nem MCP instalados.

Ajuste os nomes das pastas (`pedidos-api`, `pedidos-raml`) para os do seu projeto.

---

## Sincronização com o Anypoint Studio (`ponte`)

Este repositório é editado aqui, mas o Anypoint Studio roda a partir do próprio workspace,
numa pasta separada. As duas não se sincronizam sozinhas. A CLI `ponte`
([mule-bridge](https://github.com/igordiascardoso/mule-bridge)) faz essa ponte.

**Estrutura:** `pedidos-api/` (o código) e `pedidos-raml/` (a especificação) na raiz.

### Quando usar

| Situação | Comando |
|---|---|
| Editei o RAML ou o código e quero testar no Studio | `ponte parastudio` |
| Quero que o Studio leia o RAML que eu edito | `ponte parastudio raml` |
| Mexi só em flow/service/java | `ponte parastudio api` |
| Saiu versão nova do RAML no Exchange | `ponte pararepo raml force` |
| O Studio gerou flows no scaffold, ou fiz um fix direto nele | `ponte pararepo api force` |
| Quero ver o pareamento e o que está diferente | `ponte status` |

Depois de um `parastudio` **não há passo extra**: o Studio detecta a mudança no disco e
redeploya sozinho. Não sugira reimportar o projeto nem reiniciar o Studio.

### Regras

- **Rode a partir da raiz do repositório**, onde fica o `.mule-bridge.toml`.
- **Nenhum `pararepo` grava sem a palavra `force`** — sem ela é prévia. Rode primeiro sem,
  mostre o que aconteceria, e **só acrescente `force` depois de o usuário confirmar**. Nunca
  acrescente essa palavra por conta própria para "completar a tarefa".
- **Nunca passe `--delete`** sem o usuário pedir explicitamente: ele apaga no destino, e no
  `pararepo` o destino é este repositório.
- **O `pom.xml` daqui nunca deve ser alterado para apontar ao RAML local.** Essa reescrita
  acontece só no workspace do Studio; aqui ele segue apontando para o Exchange com a versão
  travada, que é o que vai para o remoto. A ferramenta já cuida disso — não faça na mão.
- **Se um `pararepo` acusar conflito**, ele não escreve nada. Leia as duas versões que ele
  mostra, proponha uma combinação que preserve as duas intenções e **pergunte ao usuário**
  antes de aplicar. Nunca descarte a edição local para "resolver logo".

### Primeira vez no projeto

`ponte init` pareia o repositório com o projeto do workspace. Ele pergunta onde há mais de
uma opção e resolve sozinho onde há uma só. Sem terminal interativo, o erro lista as opções
e a flag correspondente (`--api`, `--raml`, `--studio-api`, `--studio-raml`).
