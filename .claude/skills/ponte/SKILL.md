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
| `pararepo` | `ponte pararepo` |
| `status` | `ponte status` |
| `init`, `parear`, `configurar` | ver **init** abaixo |

Cada direcao aceita uma parte opcional, quando o usuario quer mover so um lado:

| O usuario digita | Comando |
|---|---|
| `parastudio raml` | `ponte parastudio raml` |
| `parastudio api` | `ponte parastudio api` |
| `pararepo raml`, `atualizar o raml`, `trazer o raml novo` | `ponte pararepo raml` — ver abaixo |
| `pararepo api` | `ponte pararepo api` |

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
ponte parastudio     # o que voce editou -> workspace do Studio
ponte pararepo       # workspace do Studio -> seu repositorio
ponte status         # nao altera nada
```

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

Rode primeiro sem `--aplicar`, que so mostra o que aconteceria:

```bash
ponte pararepo raml
```

**Se nao houver conflito**, mostre a tabela ao usuario e pergunte se aplica. So entao:

```bash
ponte pararepo raml --aplicar
```

Lembre o usuario de apontar o `pom.xml` para a versao nova quando for commitar — o comando
mexe so na pasta do RAML.

### Quando houver conflito

O comando lista os arquivos em conflito com os dois lados e **nao escreve nada**. E aqui
que voce entra. Para cada conflito:

1. Leia as duas versoes que o comando mostrou (a do usuario e a do Exchange).
2. **Se as duas intencoes cabem juntas** — ex: um escreveu "Placa no padrao Mercosul" e o
   outro "Placa (obrigatorio)" — proponha um texto que preserve as duas, e **pergunte ao
   usuario** se pode aplicar. Nao aplique calado.
3. **Se sao incompativeis** — ex: `type: string` contra `type: number` — nao invente uma
   combinacao. Mostre os dois lados e pergunte qual vale.
4. Depois de o usuario decidir, edite o arquivo na pasta do RAML com o conteudo acordado e
   rode `ponte pararepo raml --aplicar` de novo.

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

2. **Mostre as opcoes ao usuario e pergunte qual e a correta.** A escolha do par de pastas
   e dele por design — a ferramenta nunca adivinha, e voce tambem nao deve.

3. Rode de novo com a escolha dele:

   ```bash
   ponte init --api pedidos-api --raml pedidos-raml \
     --studio-api minha-api --studio-raml minha-api-raml
   ```

Flags: `--api` e `--studio-api` (obrigatorias no modo sem prompt), `--raml` e
`--studio-raml` (use `--raml nenhuma` para nao sincronizar RAML), `--studio-root` quando o
workspace nao esta num caminho padrao, e `--force` para refazer uma config existente.

Rode `init` uma vez por repositorio: o resultado fica no `.mule-bridge.toml`.

## Erros comuns

| Mensagem | O que fazer |
|---|---|
| `Nenhuma config encontrada` | O usuario precisa rodar o `init` na raiz do repo. |
| `Origem nao existe` | O caminho no `.mule-bridge.toml` mudou de lugar; rode `init` de novo com `--force`. |
| `Este projeto nao tem pasta de RAML configurada` | Pediram `raml` mas o `init` foi feito sem RAML. Refaca com `--force`. |
| `command not found` | A CLI nao esta instalada ou nao esta no PATH. Ver o README para instalar. |
