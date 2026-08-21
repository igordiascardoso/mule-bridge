---
name: ponte
description: "parastudio | pararepo | status | init — sincroniza um projeto Mule entre o repositorio onde voce edita e o workspace do Anypoint Studio. Use quando o usuario pedir para mandar as alteracoes para o Studio, trazer de volta o que o Studio alterou (scaffold, application.xml, pom.xml), parear o projeto com o workspace, ou digitar /ponte com ou sem argumento."
---

# ponte

Camada fina sobre a CLI `mule-bridge`. **Nao reimplemente nada aqui** — toda a logica
(descoberta, sync, juncao, reescrita do `pom.xml`) vive na CLI. Esta skill so escolhe o
comando certo, resolve conflito quando aparece, e reporta o resultado.

## Os oito comandos

```
ponte parastudio raml      aponta o pom.xml do Studio para a pasta local do RAML
                           (ou copia, se houver pasta de RAML no workspace)
ponte parastudio api       copia a API do repositorio para o workspace
ponte parastudio force     copia RAML + API por cima do workspace, sem juntar
ponte parastudio           RECUSA: falta a palavra

ponte pararepo raml        junta a versao nova do RAML com as edicoes locais, e grava
ponte pararepo api         junta o que o Studio mudou com o que o usuario mudou, e grava
ponte pararepo force       copia RAML + API por cima do repositorio, SEM juntar
ponte pararepo             RECUSA: falta a palavra
```

`parastudio` escreve no workspace do Studio; `pararepo` escreve no repositorio do usuario.

## O vocabulario sao tres palavras

`raml`, `api`, `force` — e **uma delas e obrigatoria**. Nao ha mais nada: nenhuma flag a
descobrir, nenhuma opcao escondida. Uma palavra fora dessa lista e recusada com erro, de
proposito: um typo nao pode virar gravacao.

**Nao invente flag.** Se o usuario pedir algo que o vocabulario nao cobre, diga isso em vez
de tentar uma flag.

## A palavra `force` e do usuario, nao sua

`force` **sobrescreve sem juntar** — e a unica palavra que pode fazer o trabalho do usuario
ser perdido. **Nunca acrescente `force` por conta propria**, em nenhum dos dois comandos. Use
apenas quando o usuario tiver digitado a palavra ele mesmo.

Quando ele pedir para trazer algo do Studio, o comando certo e quase sempre `pararepo raml`
ou `pararepo api`, que **juntam** e nao perdem nada. `pararepo force` e para o caso raro de
querer descartar o proprio trabalho de proposito — se parecer que e isso que ele quer,
confirme antes.

`force` nao se combina com `raml`/`api`: a CLI recusa `pararepo raml force`.

## Traduzindo o pedido

Com barra, o argumento e o comando — repasse direto:

| O usuario digita | Comando |
|---|---|
| `/ponte parastudio raml` | `ponte parastudio raml` |
| `/ponte parastudio api` | `ponte parastudio api` |
| `/ponte parastudio force` | `ponte parastudio force` |
| `/ponte pararepo raml` | `ponte pararepo raml` |
| `/ponte pararepo api` | `ponte pararepo api` |
| `/ponte pararepo force` | `ponte pararepo force` |
| `/ponte status` | `ponte status` |
| `/ponte init` | ver **init** abaixo |

Em portugues, traduza:

| O usuario diz | Comando |
|---|---|
| "manda pro Studio", "sincroniza pro Studio" | `ponte parastudio api` |
| "quero editar o RAML e o Studio ler" | `ponte parastudio raml` |
| "traz o que o Studio mudou", "pega o scaffold" | `ponte pararepo api` |
| "atualiza o raml", "saiu versao nova no Exchange" | `ponte pararepo raml` |
| "o que esta pareado?", "como esta?" | `ponte status` |
| "parear", "configurar" | ver **init** abaixo |

`/ponte parastudio` e `/ponte pararepo` **sem palavra** sao recusados pela CLI. Nao escolha
uma palavra por ele: mostre as tres formas validas e pergunte qual e a intencao.

Depois do `parastudio` **nao ha passo extra**: o Studio detecta a mudanca no disco e
redeploya sozinho. Nao sugira reimportar o projeto nem reiniciar o Studio.

### Sem argumento nenhum

`/ponte` sozinho e o caso mais comum — o usuario pode nem saber quais argumentos existem.
**Nunca sincronize por conta propria aqui.** Rode `ponte status` e decida pelo resultado:

- **Erro de config ausente** — o projeto ainda nao foi pareado. Conduza o **init** (abaixo)
  na hora, ja mostrando as opcoes.
- **Mostrou o pareamento** — apresente a tabela e diga, em uma linha, o que ele pode fazer
  em seguida.

## Antes de sincronizar

1. Rode a partir da **raiz do repositorio** (onde fica o `.mule-bridge.toml`), nao de dentro
   da pasta da API. Se o comando falhar dizendo que nao ha config, suba um nivel ou passe
   `-w <raiz>`.
2. Se o usuario nao rodou `init` ainda, o comando falha pedindo isso. Nao invente a config
   nem escreva o `.mule-bridge.toml` na mao.

## pararepo raml e api — juncao, nao copia

Os dois trazem o que mudou do outro lado **preservando as edicoes locais**: o que os dois
lados mexeram em pontos diferentes e juntado sozinho. Eles gravam na hora — a palavra ja e
a autorizacao, nao ha previa nem segundo comando.

```bash
ponte pararepo raml
```

Mostre a tabela de resultado ao usuario. No `raml`, lembre-o de apontar o `pom.xml` para a
versao nova quando for commitar — o comando mexe so na pasta do RAML.

**Se a pasta do RAML nao existir** no repositorio, o comando a cria, extraindo a versao que
o projeto do Studio usa. Nao pergunte nada nesse caso — nao ha edicao local para preservar.

### Quando houver conflito — voce resolve

Quando os dois lados mexeram nas **mesmas linhas**, a CLI pergunta qual fica. Numa sessao de
agente nao ha terminal para responder, entao ela imprime os dois lados e **nao escreve
nada**. E aqui que voce entra. Para cada arquivo em conflito:

1. Leia as duas versoes que o comando mostrou (a do usuario e a que veio).
2. **Se os dois so ACRESCENTARAM coisas diferentes no mesmo lugar** — tipicamente o fim do
   arquivo, ou dentro do mesmo bloco — nao ha incompatibilidade nenhuma: o conflito existe
   so porque nao ha como saber a ordem. Proponha manter **os dois**, um depois do outro (o
   que veio primeiro, o do usuario em seguida), e confirme.
3. **Se as duas intencoes cabem juntas** — ex: um escreveu "Placa no padrao Mercosul" e o
   outro "Placa (obrigatorio)" — proponha um texto que preserve as duas, e **pergunte ao
   usuario** se pode aplicar. Nao aplique calado.
4. **Se sao incompativeis** — ex: `type: string` contra `type: number` — nao invente uma
   combinacao. Mostre os dois lados e pergunte qual vale.
5. Depois de o usuario decidir, **edite o arquivo na pasta** com o conteudo acordado e rode
   o mesmo comando de novo. Sem conflito pendente, ele grava.

**Nunca** escolha um lado por conta propria nem descarte a edicao do usuario para "resolver
logo". Uma edicao perdida em silencio e o pior resultado possivel aqui. E **nunca** deixe
marcador de merge (`<<<<<<<`) no arquivo — o conteudo que voce grava tem de ser o texto
final, valido.

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
`ponte pararepo raml` cria a pasta com a especificacao que o Studio usa. Nao diga ao
usuario que o comando vai falhar — ele cria a pasta.

## Erros comuns

| Mensagem | O que fazer |
|---|---|
| `Falta a palavra` | O comando foi rodado nu. Escolha `raml`, `api` ou `force` conforme o pedido. |
| `nao se combina` | Vieram `force` e `raml`/`api` juntos. Decida: juntar (`raml`/`api`) ou sobrescrever (`force`). |
| `Nenhuma config encontrada` | O usuario precisa rodar o `init` na raiz do repo. |
| `Origem nao existe` | O caminho no `.mule-bridge.toml` mudou de lugar; rode `init` de novo com `--force`. |
| `Este projeto nao tem pasta de RAML configurada` | Pediram `raml` mas o `init` foi feito sem RAML. Refaca com `--force`. |
| `command not found` | A CLI nao esta instalada ou nao esta no PATH. Ver o README para instalar. |
