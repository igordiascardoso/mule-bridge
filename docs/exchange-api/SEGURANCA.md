# Credencial: o `ponte` nao guarda nenhuma

Uma feature que fale com o Anypoint precisa de credencial. Este documento fixa como — e o
principio e o mesmo que o resto da ferramenta ja segue.

## O que existe hoje

Nenhum segredo. Zero mencoes a `password`, `secret` ou `token` no codigo, e o
`.mule-bridge.toml` guarda apenas caminhos:

```toml
[studio]
root = "C:\\Users\\voce\\AnypointStudio\\studio-workspace"

[api]
work = "pedidos-api"
studio = "pedidos-api"
```

Nada ali e sigiloso. O arquivo entra no `.gitignore` porque e o caminho *da sua maquina*, nao
porque seja segredo.

## A regra

**A credencial nunca passa pelo `ponte`, nem pelo repositorio.** Nem em arquivo, nem em flag,
nem em variavel que ele leia. Ele usa o que a maquina ja tem configurado — como o `git` faz
com as suas chaves SSH: nao as guarda, nao as pede, apenas as usa.

Na pratica, quem configura e o usuario, uma vez:

```
anypoint-cli-v4 conf client_id SEU_ID
anypoint-cli-v4 conf client_secret SEU_SECRET
```

A CLI grava **cifrado** em `%APPDATA%\anypoint-cli-v4-public-nodejs\Config\config.json`. Nao e
JSON legivel: uma leitura direta devolve bytes binarios. Fora do repositorio, fora do git.

Dai em diante os comandos rodam sem credencial nenhuma na linha:

```
anypoint-cli-v4 designcenter project upload <projeto> <pasta>
```

E e isso que uma feature chamaria.

## Por que nao um arquivo no projeto

Tentador, e errado por tres motivos:

**O `.gitignore` e uma rede, nao uma garantia.** Ele protege o caso comum e falha no `git add
-f`, no clone que copia o arquivo, no backup que sobe para outro lugar. Segredo que nao existe
no repositorio nao pode escapar dele.

**Um segredo em disco claro vaza por caminhos que ninguem lembra.** Um `grep` recursivo, um
log de build, um print de tela, uma pasta sincronizada. O `config.json` cifrado da CLI nao
resolve tudo, mas e melhor do que texto puro num `.env`.

**E muda o que a ferramenta e.** Hoje o pior que um `ponte` mal usado faz e sobrescrever
arquivo local, e isso se recupera. Uma ferramenta que guarda credencial de plataforma passa a
ser alvo — e o cuidado que ela exige e de outra ordem.

## Como verificar que nada escapou

```
grep -rin 'client_secret\|client_id\|password\|bearer' . --include='*.py' --include='*.toml' --include='*.md'
```

Deve devolver so *nomes* de flags e variaveis, em documentacao. Nunca um valor.

O `.gitignore` tambem cobre o arquivo criado por engano:

```
*.env
.env
anypoint*.json
```

## O que fica de fora, e por que

O `ponte` **nao** vai:

- pedir usuario e senha
- gravar `client_id`/`client_secret` em lugar nenhum
- ler um `.env` do projeto
- aceitar credencial por flag — a flag aparece no historico do shell e na lista de processos

Se a credencial nao estiver configurada, o comando **recusa e explica como configurar** — do
mesmo jeito que hoje recusa quando falta o `.mule-bridge.toml` e manda rodar o `init`.
