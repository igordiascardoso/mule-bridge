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

### Os oito comandos

```
ponte parastudio raml      faz o Studio ler o RAML que eu edito
ponte parastudio api       copia a API daqui para o workspace
ponte parastudio force     copia tudo por cima do workspace
ponte parastudio           RECUSA: falta a palavra

ponte pararepo raml        junta a versão nova do RAML com as minhas edições, e grava
ponte pararepo api         junta o que o Studio mudou com o que eu mudei, e grava
ponte pararepo force       ⚠️  copia por cima daqui, SEM juntar
ponte pararepo             RECUSA: falta a palavra
```

`parastudio` escreve no workspace do Studio. `pararepo` escreve neste repositório.

Depois de um `parastudio` **não há passo extra**: o Studio detecta a mudança no disco e
redeploya sozinho. Não sugira reimportar o projeto nem reiniciar o Studio.

### Traduzindo o pedido

| Situação | Comando |
|---|---|
| Mexi em flow/service/java e quero testar no Studio | `ponte parastudio api` |
| Quero que o Studio leia o RAML que eu edito | `ponte parastudio raml` |
| Saiu versão nova do RAML no Exchange | `ponte pararepo raml` |
| O Studio gerou flows no scaffold, ou fiz um fix direto nele | `ponte pararepo api` |
| Quero ver o pareamento e o que está diferente | `ponte status` |

### Regras

- **Rode a partir da raiz do repositório**, onde fica o `.mule-bridge.toml`.
- **O vocabulário são três palavras:** `raml`, `api`, `force` — e uma delas é obrigatória.
  Não há flags a descobrir; uma palavra fora dessa lista é recusada de propósito.
- **`force` sobrescreve sem juntar, e é do usuário.** É a única palavra que pode fazer
  trabalho ser perdido. **Nunca a acrescente por conta própria** para "completar a tarefa" —
  só quando o usuário a tiver digitado. Para trazer algo do Studio, o comando certo é quase
  sempre `pararepo raml` ou `pararepo api`, que juntam e não perdem nada.
- **`force` não se combina com `raml`/`api`** — a CLI recusa `pararepo raml force`.
- **O `pom.xml` daqui nunca deve ser alterado para apontar ao RAML local.** Essa reescrita
  acontece só no workspace do Studio; aqui ele segue apontando para o Exchange com a versão
  travada, que é o que vai para o remoto. A ferramenta já cuida disso — não faça na mão.

### Quando um `pararepo` acusar conflito

Os dois lados mexeram nas mesmas linhas. A CLI imprime as duas versões e **não escreve
nada** — resolver é seu trabalho:

1. Leia as duas versões que o comando mostrou.
2. Se os dois só **acrescentaram** coisas diferentes no mesmo lugar, não há
   incompatibilidade: proponha manter as duas, uma depois da outra.
3. Se as duas intenções cabem juntas, proponha um texto que preserve as duas e **pergunte ao
   usuário** antes de aplicar.
4. Se são incompatíveis (`type: string` contra `type: number`), mostre os dois lados e
   pergunte qual vale — não invente uma combinação.
5. Com a decisão dele, edite o arquivo e rode o mesmo comando de novo.

**Nunca** descarte a edição local para "resolver logo", e **nunca** deixe marcador de merge
(`<<<<<<<`) no arquivo — o que você grava tem de ser o texto final, válido.

### Primeira vez no projeto

`ponte init` pareia o repositório com o projeto do workspace. Ele pergunta cada escolha
quando há terminal. Sem terminal interativo, o erro lista as opções e a flag correspondente
(`--api`, `--raml`, `--studio-api`, `--studio-raml`) — mostre as opções ao usuário e
pergunte, em vez de escolher por ele.
