---
name: ponte
description: "parastudio | pararepo | status | init — sincroniza um projeto Mule entre o repositorio onde voce edita e o workspace do Anypoint Studio. Use quando o usuario pedir para mandar as alteracoes para o Studio, trazer de volta o que o Studio alterou (scaffold, application.xml, pom.xml), parear o projeto com o workspace, ou digitar /ponte com ou sem argumento."
---

# ponte

Camada fina sobre a CLI `mule-bridge`. **Nao reimplemente nada aqui** — toda a logica
(descoberta, sync, reescrita do `pom.xml`) vive na CLI. Esta skill so escolhe o comando
certo e reporta o resultado.

## Argumentos

| O usuario digita | Comando |
|---|---|
| `parastudio` | `ponte parastudio` |
| `pararepo` | `ponte pararepo` (previa) / `ponte pararepo force` (grava) |
| `status` | `ponte status` |
| `init`, `parear`, `configurar` | ver **init** abaixo |

Cada direcao aceita uma parte opcional, quando o usuario quer mover so um lado:

| O usuario digita | Comando |
|---|---|
| `parastudio raml` | `ponte parastudio raml` — aponta o pom.xml do Studio para a pasta local do RAML, ou copia se houver pasta no workspace |
| `parastudio api` | `ponte parastudio api` |
| `pararepo raml`, `atualizar o raml`, `trazer o raml novo` | `ponte pararepo raml` — ver abaixo |
| `pararepo api` | `ponte pararepo api` |
| `pararepo force`, `pararepo raml force` | o mesmo, gravando de verdade |

Sem a parte, vao os dois — que e o caso normal, porque uma mudanca no RAML costuma
implicar mudanca na API.

### Sem argumento nenhum

`/ponte` sozinho e o caso mais comum — o usuario pode nem saber quais argumentos
existem. **Nunca sincronize por conta propria aqui.** Rode `ponte status` e decida
pelo resultado:

- **Deu erro de config ausente** — o projeto ainda nao foi pareado. Nao peca para o usuario
  digitar outro comando: conduza o **init** (abaixo) na hora, ja mostrando as opcoes.
- **Mostrou o pareamento** — apresente a tabela e diga, em uma linha, o que ele pode fazer
  em seguida: `/ponte parastudio` para mandar pro Studio, `/ponte pararepo` para
  trazer de volta.

## Antes de sincronizar

1. Rode a partir da **raiz do repositorio** (onde fica o `.mule-bridge.toml`), nao de dentro
   da pasta da API. Se o comando falhar dizendo que nao ha config, suba um nivel ou passe
   `-w <raiz>`.
2. Se o usuario nao rodou `init` ainda, o comando falha pedindo isso. Nao invente a config
   nem escreva o `.mule-bridge.toml` na mao.

## Executando

Rode o comando direto no terminal e mostre a tabela de resultado ao usuario:

```bash
ponte parastudio        # o que voce editou -> workspace do Studio
ponte pararepo          # workspace do Studio -> seu repositorio (previa)
ponte pararepo force    # ... e grava
ponte status            # nao altera nada
```

## A palavra `force` e do usuario, nao sua

Nenhum `pararepo` grava sem a palavra `force`. **Nunca acrescente essa palavra por conta
propria.** Rode sem ela, mostre ao usuario o que aconteceria, e so repita com `force`
depois de ele confirmar — ou quando ele mesmo tiver digitado a palavra.

E de proposito que a protecao seja uma palavra e nao uma flag: e o comando que escreve no
repositorio do usuario, e uma palavra a mais no meio de uma conversa e deliberada de um
jeito que um `--aplicar` no fim da linha nao e. O `parastudio` nao exige nada disso — o
destino dele e o workspace do Studio, que se reconstroi reimportando o projeto.

Depois do `parastudio` **nao ha passo extra**: o Studio detecta a mudanca no disco e
redeploya sozinho. Nao sugira reimportar o projeto nem reiniciar o Studio.

## Quando usar --dry-run

Rode `--dry-run` antes do sync de verdade quando:

- for a primeira sincronizacao deste projeto na sessao;
- o usuario demonstrar duvida sobre o que vai mudar;
- for um `pararepo` (o destino sao os arquivos versionados do usuario).

Mostre o resultado e confirme antes de rodar sem a flag.

## --delete exige confirmacao

`--delete` apaga arquivos no destino. **Nunca** passe essa flag por conta propria — so
quando o usuario pedir explicitamente, e mesmo assim rode antes com `--dry-run` e mostre a
lista do que sera removido. No `pararepo`, o destino e o repositorio do usuario: apagar ali
pode destruir trabalho nao commitado.

## pararepo raml — juncao, nao copia

`pararepo raml` nao copia por cima: traz a versao nova do RAML preservando as edicoes
locais. A versao vem do `pom.xml` do lado do Studio, que registra o update feito la.

**Se a pasta do RAML nao existir** no repositorio, este comando a cria, extraindo a versao
que o projeto do Studio usa. Nao pergunte nada nesse caso — nao ha edicao local para
preservar, entao nao ha decisao a tomar.

Rode primeiro sem `force`, que so mostra o que aconteceria:

```bash
ponte pararepo raml
```

**Se nao houver conflito**, mostre a tabela ao usuario e pergunte se aplica. So entao:

```bash
ponte pararepo raml force
```

Lembre o usuario de apontar o `pom.xml` para a versao nova quando for commitar — o comando
mexe so na pasta do RAML.

### Quando houver conflito

O comando lista os arquivos em conflito com os dois lados e **nao escreve nada**. E aqui
que voce entra. Para cada conflito:

1. Leia as duas versoes que o comando mostrou (a do usuario e a do Exchange).
2. **Se os dois so ACRESCENTARAM coisas diferentes no mesmo lugar** — tipicamente o fim do
   arquivo, ou dentro do mesmo bloco — nao ha incompatibilidade nenhuma: o conflito existe
   so porque nao ha como saber a ordem. Proponha manter **os dois**, um depois do outro (o
   do Exchange primeiro, o do usuario em seguida), e confirme.
3. **Se as duas intencoes cabem juntas** — ex: um escreveu "Placa no padrao Mercosul" e o
   outro "Placa (obrigatorio)" — proponha um texto que preserve as duas, e **pergunte ao
   usuario** se pode aplicar. Nao aplique calado.
4. **Se sao incompativeis** — ex: `type: string` contra `type: number` — nao invente uma
   combinacao. Mostre os dois lados e pergunte qual vale.
5. Depois de o usuario decidir, edite o arquivo na pasta do RAML com o conteudo acordado e
   rode `ponte pararepo raml force --resolvido`.

O `--resolvido` e obrigatorio nesse segundo passo: sem ele o comando recusa de novo, porque
a base continua sendo a versao antiga e o texto combinado ainda diverge dos dois lados. A
flag diz "ja combinei, aceite o que esta na pasta" — entao **so use depois de o usuario
aprovar a combinacao**, nunca para contornar um conflito que voce nao resolveu.

Ao final, lembre o usuario de apontar o `pom.xml` para a versao nova: e isso que encerra o
aviso de conflito nas execucoes seguintes.

**Nunca** escolha um lado por conta propria nem descarte a edicao do usuario para "resolver
logo". Uma edicao perdida em silencio e o pior resultado possivel aqui.

## init

O `init` pareia o repositorio com um projeto do workspace. Ele pergunta interativamente
quando ha terminal, mas **dentro de uma sessao de agente nao ha** — entao conduza assim:

1. Rode sem flags para descobrir as opcoes. O comando falha de proposito, listando o que
   encontrou e a flag correspondente:

   ```bash
   ponte init
   ```

2. **Mostre as opcoes ao usuario e pergunte qual e a correta** — inclusive quando houver um
   candidato so. O `init` pergunta cada escolha de proposito: um pareamento errado nao da
   erro na hora, so aparece depois, quando um comando escreve no lugar indevido.

3. Rode de novo com a escolha dele:

   ```bash
   ponte init --api pedidos-api --raml pedidos-raml \
     --studio-api minha-api --studio-raml minha-api-raml
   ```

Flags: `--api` e `--studio-api` (obrigatorias no modo sem prompt), `--raml` e
`--studio-raml` (use `--raml nenhuma` para nao sincronizar RAML), `--studio-root` quando o
workspace nao esta num caminho padrao, e `--force` para refazer uma config existente.

Rode `init` uma vez por repositorio: o resultado fica no `.mule-bridge.toml`.

**Se ele avisar que nao ha pasta de RAML**, repasse a instrucao que ele mesmo deu:
`ponte pararepo raml force` cria a pasta com a especificacao que o Studio usa. Nao
diga ao usuario que o comando vai falhar — ele cria a pasta.

## Erros comuns

| Mensagem | O que fazer |
|---|---|
| `Nenhuma config encontrada` | O usuario precisa rodar o `init` na raiz do repo. |
| `Origem nao existe` | O caminho no `.mule-bridge.toml` mudou de lugar; rode `init` de novo com `--force`. |
| `Este projeto nao tem pasta de RAML configurada` | Pediram `raml` mas o `init` foi feito sem RAML. Refaca com `--force`. |
| `command not found` | A CLI nao esta instalada ou nao esta no PATH. Ver o README para instalar. |
