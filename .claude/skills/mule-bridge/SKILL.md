---
name: mule-bridge
description: Sincroniza um projeto Mule entre a pasta de trabalho (repositorio git) e o workspace do Anypoint Studio. Use quando o usuario pedir para sincronizar, mandar as alteracoes para o Studio, trazer de volta o que o Studio alterou (scaffold, application.xml, pom.xml), parear o projeto com o workspace, ou digitar /mule-bridge com push, pull, status ou init.
---

# mule-bridge

Camada fina sobre a CLI `mule-bridge`. **Nao reimplemente nada aqui** — toda a logica
(descoberta, sync, reescrita do `pom.xml`) vive na CLI. Esta skill so escolhe o comando
certo e reporta o resultado.

## Argumentos

O usuario escreve `/mule-bridge <acao>`. Mapeie assim:

| Argumento | Comando |
|---|---|
| `push`, ou nada dito sobre direcao mas o contexto e "mandar pro Studio" | `mule-bridge push` |
| `pull` | `mule-bridge pull` |
| `status`, `o que mudou`, vazio | `mule-bridge status` |
| `init`, `parear`, `configurar` | ver **init** abaixo |

Sem argumento nenhum, rode `mule-bridge status` — e nao um sync. Status nao altera nada,
entao e o default seguro.

## Antes de sincronizar

1. Rode a partir da **raiz da pasta de trabalho** (onde fica o `.mule-bridge.toml`), nao de
   dentro da pasta da API. Se o comando falhar dizendo que nao ha config, suba um nivel ou
   passe `-w <raiz>`.
2. Se o usuario nao rodou `init` ainda, o comando falha pedindo isso. Nao invente a config
   nem escreva o `.mule-bridge.toml` na mao.

## Executando

Rode o comando direto no terminal e mostre a tabela de resultado ao usuario:

```bash
mule-bridge push        # pasta de trabalho -> workspace do Studio
mule-bridge pull        # workspace do Studio -> pasta de trabalho
mule-bridge status      # nao altera nada; mostra o que um push faria
```

Depois do `push` **nao ha passo extra**: o Studio detecta a mudanca no disco e redeploya
sozinho. Nao sugira reimportar o projeto nem reiniciar o Studio.

## Quando usar --dry-run

Rode `--dry-run` antes do sync de verdade quando:

- for a primeira sincronizacao deste projeto na sessao;
- o usuario demonstrar duvida sobre o que vai mudar;
- for um `pull` (o destino sao os arquivos versionados do usuario).

Mostre o resultado e confirme antes de rodar sem a flag.

## --delete exige confirmacao

`--delete` apaga arquivos no destino. **Nunca** passe essa flag por conta propria — so
quando o usuario pedir explicitamente, e mesmo assim rode antes com `--dry-run` e mostre a
lista do que sera removido. No `pull`, o destino e o repositorio do usuario: apagar ali
pode destruir trabalho nao commitado.

## init

O `init` pareia o repositorio com um projeto do workspace. Ele pergunta interativamente
quando ha terminal, mas **dentro de uma sessao de agente nao ha** — entao conduza assim:

1. Rode sem flags para descobrir as opcoes. O comando falha de proposito, listando o que
   encontrou e a flag correspondente:

   ```bash
   mule-bridge init
   ```

2. **Mostre as opcoes ao usuario e pergunte qual e a correta.** A escolha do par de pastas
   e dele por design — a ferramenta nunca adivinha, e voce tambem nao deve.

3. Rode de novo com a escolha dele:

   ```bash
   mule-bridge init --api pedidos-api --raml pedidos-raml \
     --studio-api minha-api --studio-raml minha-api-raml
   ```

Flags: `--api` e `--studio-api` (obrigatorias no modo sem prompt), `--raml` e
`--studio-raml` (use `--raml nenhuma` para nao sincronizar RAML), `--studio-root` quando o
workspace nao esta num caminho padrao, e `--force` para refazer uma config existente.

Rode `init` uma vez por repositorio: o resultado fica no `.mule-bridge.toml`.

## Erros comuns

| Mensagem | O que fazer |
|---|---|
| `Nenhuma config encontrada` | O usuario precisa rodar `mule-bridge init` na raiz do repo. |
| `Origem nao existe` | O caminho no `.mule-bridge.toml` mudou de lugar; rode `init` de novo com `--force`. |
| `command not found` | A CLI nao esta instalada ou nao esta no PATH. Ver o README para instalar. |
