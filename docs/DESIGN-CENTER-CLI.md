# Subir o RAML para o Design Center pela CLI — investigação

Registro do que foi verificado, o que falta, e o que ainda não se sabe. Alimentado a cada
passo.

**Objetivo:** descobrir se o `ponte` pode ganhar uma feature que leve o RAML editado
localmente para o Design Center, deixando ele versionar como já faz — sem publicar por fora
no Exchange, que criaria divergência.

---

## O que já está resolvido

### A CLI existe e está instalada

| | |
|---|---|
| Pacote | `anypoint-cli-v4-public` |
| Instalação | `npm install -g anypoint-cli-v4-public` |
| Versão instalada | `1.6.26 win32-x64` |
| Node exigido | 22.0.0+ — a máquina tinha 20.18, atualizada para **v24.19.0** pelo .exe |
| Efeito colateral | traz `puppeteer` e `yarn` como dependências (pesado, mas é o pacote oficial) |

### Decisao: pre-requisito documentado, o `ponte` nao instala

O `ponte` **nao** vai chamar `npm install` por conta propria nem gerenciar Node. Seria assumir
uma responsabilidade nova (garantir Node 22+, resolver falha de instalacao global) que a
ferramenta nunca teve — hoje ela so depende de Python e `git`.

Quando a feature for implementada, isso entra no README como pre-requisito manual, do mesmo
jeito que hoje se pede para instalar o `git`. Ate la, o pre-requisito e este, valido para
quem for testar os comandos abaixo:

**Node 22+ e obrigatorio antes do `npm install`** — a `anypoint-cli-v4-public` nao roda em
versao mais antiga (testado: com Node 20.18 instalado, precisou atualizar para 24.19.0 para
funcionar).

```bash
# 1. Node 22+ (verificar com node -v; instalar/atualizar em nodejs.org se for menor que isso)
node -v

# 2. a CLI da Anypoint
npm install -g anypoint-cli-v4-public

# 3. a credencial, uma vez por maquina
anypoint-cli-v4 conf client_id SEU_ID
anypoint-cli-v4 conf client_secret SEU_SECRET
```

Os dois `conf` guardam a credencial cifrada na propria maquina (ver
[SEGURANCA.md](exchange-api/SEGURANCA.md)) — o `ponte` nunca guarda nem pede isso diretamente.
Se faltar, o comando do `ponte` vai falhar com o erro da propria `anypoint-cli-v4` — nao um
erro tratado pelo `ponte` — porque ele nao verifica a presenca dela de antemao.

### Os comandos que interessam

```
designcenter project list      lista os projetos da org
designcenter project create    cria projeto
designcenter project download  baixa o conteúdo
designcenter project upload    envia o conteúdo da pasta local  ← o que a feature usaria
designcenter project publish   publica no Exchange (opções não passadas vêm do exchange.json)
designcenter project delete    apaga projeto
```

**`upload` e `publish` são separados** — dá para levar a edição ao Design Center sem publicar
no Exchange. É essa separação que evita a divergência.

### Flags do `upload`

```
-b, --branch=<value>          escolhe o branch
-i, --include-dot-files       inclui arquivos que começam com ponto (excluídos por padrão)
```

Autenticação, por flag ou variável de ambiente:

| Flag | Variável |
|---|---|
| `--client_id` / `--client_secret` | `ANYPOINT_CLIENT_ID` / `ANYPOINT_CLIENT_SECRET` |
| `--username` / `--password` | `ANYPOINT_USERNAME` / `ANYPOINT_PASSWORD` |
| `--bearer` | `ANYPOINT_BEARER` |
| `--organization` | `ANYPOINT_ORG` |
| `--environment` | `ANYPOINT_ENV` |

---

## Como foi testado

**Conta:** nova, vazia, criada para isto. Não é a organização do projeto real.

**Material:** RAML **1.1.53** extraído do cache do Maven (versão real e antiga do projeto),
19 arquivos, em `scratchpad/dc-teste/`.

O `exchange.json` foi **removido de propósito**: ele carrega o `groupId` da organização real e o
`projectId` do Design Center de lá. Subi-lo faria a CLI falar com a org errada.

### Passos

| # | Passo | Resultado |
|---|---|---|
| 1 | Connected App na conta nova | 3 escopos de Design Center; depois **`Exchange Contributor`** para publicar |
| 2 | `project list` | tabela vazia — credencial e escopos ok |
| 3 | `project create teste-ponte` | criado, tipo `raml`, revisao 1 |
| 4 | `project upload` do RAML 1.1.53 | 19 arquivos; `Acquiring lock` → `Uploading` → `Releasing lock` |
| 5 | `project download` de volta | 22 arquivos: os 19 mais 3 que o Design Center criou |
| 6 | editar e subir de novo (2x) | revisao 3 → 4 → 5: **versiona a cada upload** |
| 7 | mudanca grande (15 endpoints, arquivo novo, 2 linhas) | revisao 12 → 13, e **so as 3 mudancas** no destino |
| 8 | `exchange asset upload` | `Publishing completed` — Exchange em `1.0.0`, depois `1.0.1` |

### Os comandos que interessam

```
designcenter project list      lista os projetos da org
designcenter project create    cria projeto
designcenter project download  baixa o conteúdo
designcenter project upload    envia o conteúdo da pasta local  ← o que a feature usaria
designcenter project publish   publica no Exchange (opções não passadas vêm do exchange.json)
designcenter project delete    apaga projeto
```

**`upload` e `publish` são separados** — dá para levar a edição ao Design Center sem publicar
no Exchange. É essa separação que evita a divergência.

### Flags do `upload`

```
-b, --branch=<value>          escolhe o branch
-i, --include-dot-files       inclui arquivos que começam com ponto (excluídos por padrão)
```

Autenticação, por flag ou variável de ambiente:

| Flag | Variável |
|---|---|
| `--client_id` / `--client_secret` | `ANYPOINT_CLIENT_ID` / `ANYPOINT_CLIENT_SECRET` |
| `--username` / `--password` | `ANYPOINT_USERNAME` / `ANYPOINT_PASSWORD` |
| `--bearer` | `ANYPOINT_BEARER` |
| `--organization` | `ANYPOINT_ORG` |
| `--environment` | `ANYPOINT_ENV` |



---

## Cuidados

- **Nunca usar a credencial da organização real** nestes testes. Só a conta nova.
- **Não subir o `exchange.json`** do projeto real: ele aponta para a org e o projeto de lá.
- A credencial passada por variável de ambiente não fica em arquivo nem no histórico do
  shell, mas **aparece na conversa** — motivo extra para ser a conta descartável.
---

## A resposta: o `upload` versiona, e nao apaga

Testado em conta propria e vazia, com o RAML 1.1.53 real do projeto (19 arquivos).

**Cada `upload` cria uma revisao nova.** O `project list` mostra o contador subindo:

| Operacao | Version |
|---|---|
| `project create` | 1 |
| 1o `upload` | 3 |
| 2o `upload`, com uma edicao | 4 |
| 3o `upload`, com outra | 5 |

O proprio comando diz o que faz: `Acquiring lock` → `Uploading 19 files` → `Releasing lock`.
Ele trava o projeto durante a escrita, entao duas subidas nao se atropelam.

**Cuidado com a palavra "versao": sao duas escalas diferentes.**

| | O que e | Exemplo |
|---|---|---|
| `Version` do Design Center | contador de revisao do projeto | 1, 3, 4, 5 |
| `version` do Exchange | a versao do asset publicado | 1.1.54, 1.1.55 |

**Nao apaga o que existe la e nao existe local.** Na primeira subida o Design Center criou tres
arquivos por conta propria — `exchange.json`, `teste-ponte.raml` (o main) e `.gitignore`. As
subidas seguintes, com 19 arquivos, **nao os removeram**: o download continuou trazendo 22.
Nao e um `rsync --delete`; acrescenta e sobrescreve por nome, sem limpar o destino.

**A ida e volta preserva o conteudo.** O `download` trouxe os 19 identicos aos que subiram
(`diff` limpo), e as edicoes chegaram nas duas vezes.

### O `exchange.json` e da conta de destino, nao do repositorio

O Design Center gerou um com o `groupId` **da conta de teste** (`1b88a96a-...`), diferente do
`groupId` da organizacao real. Confirma o cuidado tomado: subir o do projeto real
levaria os identificadores de uma org para outra. Ele deve ficar de fora do que se envia.

### Publicar no Exchange: `exchange asset upload`, nao `designcenter project publish`

O `designcenter project publish` esta quebrado nesta versao da CLI (`1.6.26`):

```
$ anypoint-cli-v4 designcenter project publish teste-ponte --apiVersion v1
TypeError: Cannot read properties of undefined (reading 'data')
```

Nada e publicado — verificado no `exchange asset list`. Tentado tambem com `--version` e
`--status` explicitos, mesmo erro.

**Mas ha outro comando, e ele funciona:**

```
anypoint-cli-v4 exchange asset upload   --name "Nome do asset"   --type rest-api   --properties='{"mainFile":"api.raml","apiVersion":"v1"}'   --files='{"raml.zip":"C:/caminho/raml.zip"}'   meu-asset/1.0.0
```

Saida: `Publishing completed`. Confirmado no `exchange asset list`.

Ele recebe o RAML **zipado**, e nao a pasta — quem for usa-lo monta o zip antes. O
`assetIdentifier` no fim (`meu-asset/1.0.0`) e o par asset/versao; sem `group_id` na frente,
usa a org corrente.

**Exige o escopo `Exchange Contributor`** (ou `Exchange Administrator`) na Connected App. Sem
ele:

```
Error: Forbidden — status 403
You don't have permission to access url: /exchange/api/v2/organizations/.../assets/...
```

O erro engana: parece credencial invalida, e e permissao faltando. Os escopos de Design
Center nao cobrem publicar no Exchange — sao coisas separadas.

### A credencial nao precisa ser repassada

Ponto que vale para a feature: **os comandos acima rodaram sem nenhuma credencial na linha.**
Ela foi configurada uma vez com `anypoint-cli-v4 conf` e vive cifrada em `%APPDATA%` — 2865
bytes binarios, ilegiveis. Uma feature chamaria a CLI e herdaria isso, sem nunca ver, pedir
ou guardar segredo.

---

## Mudanca grande: sobe so o que mudou

Teste feito para responder se um `upload` grande mexe apenas no que foi alterado. Tres
mudancas de uma vez, sobre a revisao 12 do projeto:

| Mudanca | Tamanho |
|---|---|
| 15 endpoints novos no `api.raml` | 68 → 187 linhas |
| arquivo novo `types/tipos-do-teste.raml` | 164 linhas, 40 tipos |
| duas linhas alteradas no `types/types.raml` | `usage:` e um `example:` |

Depois do `upload`, baixei o projeto e comparei com o estado anterior:

```
$ diff -rq dc-antes dc-depois
Files dc-antes/api.raml and dc-depois/api.raml differ
Only in dc-depois/types: tipos-do-teste.raml
Files dc-antes/types/types.raml and dc-depois/types/types.raml differ
```

**Exatamente tres diferencas — as tres que subiram.** Os outros 18 arquivos ficaram
intactos. A revisao foi de 12 para 13.

### O Design Center normaliza o fim de linha

O `types.raml` aparecia como "arquivo inteiro diferente" no `diff`, e era CRLF. Ignorando
fim de linha, so as duas linhas editadas mudaram:

```
$ diff --strip-trailing-cr dc-antes/types/types.raml dc-depois/types/types.raml
2c2
< usage: Tipos de dados para a API de leilões
> usage: TIPOS REESCRITOS NO TESTE — todos os campos revisados
11c11
<     example: "ABC1D23"
>     example: "XYZ9A88"   # exemplo trocado no teste
```

Importa para uma feature: um `diff` ingenuo diria que tudo mudou. O merge do `ponte` ja trata
CRLF (testado em massa antes, reportou "sem mudanca"), entao nao e problema novo — mas quem
comparar o local com o do Design Center precisa ignorar fim de linha.

## O ciclo completo, comprovado

```
sua pasta ──[designcenter project upload]──▶ Design Center ──[exchange asset upload]──▶ Exchange
                  revisao 12 → 13                             1.0.0 → 1.0.1
```

Os dois passos foram executados e verificados baixando o resultado de cada lado.

**O `upload` para o Design Center nao toca no Exchange.** Depois das tres mudancas, a revisao
era 13 e o Exchange seguia em `1.0.0` — nada do que subiu apareceu la. E o correto: quem
consome o asset nao ve rascunho.

**Publicar leva o conteudo atual.** Depois do `exchange asset upload ... teste-ponte-cli/1.0.1`,
a `1.0.1` no Exchange tinha as tres mudancas: os 15 endpoints no `api.raml` (185 linhas), o
arquivo novo, e a edicao do `types.raml`. Verificado baixando o asset publicado e abrindo o
zip.

As duas versoes convivem no Exchange — `1.0.0` e `1.0.1` — porque cada publicacao e uma versao,
nao uma sobrescrita.

## O Exchange valida o RAML ao publicar

A primeira tentativa de publicar a `1.0.1` falhou:

```
Error: There was an error publishing the asset
  - message: The asset is invalid Cannot parse document with specified vendor.
    Cannot find any registered domain plugin for current document file://api.raml
```

Causa: linhas de marcacao de testes anteriores (`#TERCEIRA-EDICAO`) tinham sido inseridas
**antes** do `#%RAML 1.0`. Sem o cabecalho na primeira linha, o arquivo nao e RAML valido.

Duas licoes:

- **O Exchange valida** — RAML malformado e recusado, e nao publicado quebrado. Bom.
- **A mensagem nao diz a linha nem o problema real.** Uma feature que publique deveria checar
  o cabecalho `#%RAML` do `mainFile` antes de tentar, porque o erro da plataforma nao ajuda
  quem for depurar.

## Nomes que enganam nos dois lados

O Design Center cria um `<nome-do-projeto>.raml` de duas linhas como main padrao. No teste,
`teste-ponte.raml` — que conviveu com o `api.raml` de verdade.

Ao verificar o que foi publicado, e facil ler o arquivo errado: o placeholder tem 2 linhas e
nenhum endpoint, e parece que a publicacao falhou. O `mainFile` informado no `upload` e quem
diz qual vale.

## Quem esta ligado a quem

Um projeto do Design Center publica em um asset do Exchange, dentro da mesma organizacao. O
`exchange.json` que vem dentro do RAML e o registro dessa ligacao:

| Campo | O que aponta |
|---|---|
| `metadata.projectId` | o projeto **no Design Center** |
| `groupId` | a **organizacao** — a mesma nos dois lados |
| `assetId` | o **asset no Exchange** |
| `version` | a versao publicada de onde aquele RAML veio |

No projeto real: um `projectId` (Design Center) publica em um `assetId`
correspondente (Exchange), ambos na mesma organizacao, e o RAML local veio de uma versao
publicada anterior.

**O nome do projeto pode ser descoberto.** O `upload` pede o nome, e o `exchange.json` guarda
o UUID. O `project list -o json` traz os dois:

```json
{ "id": "0ad41066-...", "name": "teste-ponte", "defaultBranch": "master" }
```

Entao uma feature casaria `metadata.projectId` com o `id` da lista e acharia o `name` sozinha
— sem pedir configuracao nova ao usuario.

---

## O fluxo que isto substitui

Como era feito a mao:

1. baixar o RAML mais atual para o PC
2. alterar o necessario — em geral aditivo, as vezes edicao
3. abrir o Design Center e **navegar** ate o arquivo alterado
4. **selecionar tudo, apagar, e colar** o conteudo local
5. repetir 3 e 4 para cada arquivo tocado
6. publicar

Os passos 3 a 5 sao o custo: manuais, arquivo por arquivo, e faceis de errar — colar no
arquivo errado, esquecer um dos arquivos, apagar e colar incompleto. E nao ha registro do que
foi feito.

Com o `upload`, os tres viram um comando:

```
anypoint-cli-v4 designcenter project upload <projeto> <pasta-local>
```

O que o teste provou sobre ele, e que importa para este fluxo:

- **sobe so o que mudou** — tres mudancas geraram exatamente tres diferencas no destino
- **nao apaga** o que existe la e nao existe local
- **versiona** a cada subida, sem numero a escolher
- **nao publica** — o passo 6 continua sendo seu, clicando

O fluxo passa a ser: alterar no PC, um comando, publicar.

## O publish funciona — faltava escopo, nao era bug

Testado de novo depois de acrescentar `Exchange Contributor` na Connected App:

```
anypoint-cli-v4 designcenter project publish teste-ponte --apiVersion v1 --version 1.1.0
...
Project published to Exchange
```

Confirmado no Exchange (`teste-ponte 1.1.0`), e o conteudo baixado de la tinha a edicao feita
antes do upload. O erro anterior (`TypeError: Cannot read properties of undefined`) so
aparecia sem esse escopo — nao e bug da CLI, e permissao faltando, mas a mensagem de erro
nao ajuda a descobrir isso.

Sequencia completa que funciona, do terminal, sem abrir navegador:

```
anypoint-cli-v4 designcenter project upload <projeto> <pasta-local>
anypoint-cli-v4 designcenter project publish <projeto> --apiVersion v1 --version X.Y.Z
```

**A versao no `publish` segue a regra do `apiVersion`.** Com `--apiVersion v1`, a versao
publicada tem que estar no formato `1.x.x` — tentar `2.0.0` da erro de validacao (esse sim
claro):

```
Error: Request failed with status code 400. The asset is invalid | Assets
with version group v1 should have version 1.x.x.
```

## Mudanca grande em varias pastas: testado e confirmado

Repeti o teste de "sobe so o que mudou" com um caso maior: 5 arquivos editados em 5 pastas
diferentes (`domain/`, `email/`, `excel/`, `security/`, `types/`), uma pasta nova
(`financeiro/` com 2 arquivos), e um arquivo removido so localmente.

Depois do `upload`, comparando com o estado anterior:

```
$ diff -rq base depois-grande
Files base/domain/api.raml and depois-grande/domain/api.raml differ
Files base/domain/veiculos.raml and depois-grande/domain/veiculos.raml differ
Files base/email/email.raml and depois-grande/email/email.raml differ
Files base/excel/excel.raml and depois-grande/excel/excel.raml differ
Only in depois-grande: financeiro
Files base/security/oauth2.raml and depois-grande/security/oauth2.raml differ
```

Exatamente as mudancas feitas — nada mais, nada menos. E o arquivo removido so localmente
**continuou existindo la** (upload nao apaga por padrao, confirmado outra vez).

Depois publiquei esse estado (`teste-ponte 1.2.0`) e baixei do Exchange para conferir: os 33
arquivos do asset publicado tinham as 5 edicoes e a pasta `financeiro/` completa. O ciclo
upload -> publish preserva mudancas espalhadas por muitas pastas sem perder nada.

## O connector "extension" que aparece sozinho

Ao publicar uma `rest-api`, o Exchange cria automaticamente um segundo asset do tipo
`extension` (aparece na lista de assets como "Connector"), com o mesmo nome prefixado por
`mule-plugin-`. No teste: publicar `teste-ponte` gerou tambem `mule-plugin-teste-ponte`.

Isso e comportamento normal da plataforma (o "cliente Mule" gerado a partir da spec RAML,
para outros projetos importarem como dependencia) — nao e erro nem duplicacao acidental. A
feature deve avisar sobre isso quando publicar, para nao parecer bug ao usuario ("por que
apareceram dois assets?").

Confirmado tambem: apagar exige um escopo diferente de publicar. Com so
`Exchange Contributor`, o `exchange asset delete` da 403 — apagar pediu permissao maior (o
usuario apagou pela interface web, nao consegui confirmar qual escopo exato resolveria pela
CLI).

## O RAML mal formado nao sempre falha — as vezes publica quebrado, em silencio

Achado mais serio da rodada. Dois comportamentos diferentes pro mesmo tipo de erro:

**Primeira vez** (zip com `api.raml` comecando por linhas de comentario antes do
`#%RAML 1.0`): o publish falhou com erro claro:

```
Error: There was an error publishing the asset
  - message: The asset is invalid Cannot parse document with specified vendor.
    Cannot find any registered domain plugin for current document file://api.raml
```

**Segunda vez**, o mesmo tipo de defeito (linhas antes do cabecalho, reintroduzidas por um
`upload` que carregou um estado antigo do projeto) **nao gerou erro nenhum**. O `upload` e o
`publish` completaram normalmente (`Project published to Exchange`), mas a pagina do asset no
Exchange nao mostrou a secao de Endpoints/Summary que aparece quando a spec e reconhecida —
so "Conformance Status", vazio, sem nenhum recurso listado. Comparar com o asset real
asset real, que mostra a tabela completa de recursos.

**Isso e uma falha silenciosa que a feature tem que evitar.** Publicar "com sucesso" um RAML
que o parser nao consegue interpretar deixa o asset no Exchange sem a documentacao que o time
espera, e nada na saida do comando avisa disso.

**Validado agora, contra o projeto real (nao so com arquivos sinteticos):** a mitigacao de
"todo `.raml` tem que comecar com `#%RAML`" **da falso positivo** num projeto real de verdade.
Baixando o projeto de teste e rodando essa checagem ingenua contra ele, 13 arquivos foram
acusados de "problema" — mas eram fragmentos legitimos, incluidos via `!include` dentro de um
resource (ex: `!include domain/api.raml` referenciando um trecho que comeca com `post:`, nao
com `#%RAML`). Fragmento de include nao tem, e nao deve ter, esse cabecalho.

**A validacao correta precisa saber quais `.raml` sao includes antes de exigir o cabecalho:**

1. Percorrer todos os `.raml` do projeto e coletar os caminhos citados em `!include ...raml`
   dentro de qualquer um deles.
2. So exigir `#%RAML` na primeira linha nao-vazia dos arquivos que **nao** estao nessa lista
   de includes.

Testado nos dois sentidos: contra o projeto real (23 arquivos, 15 deles includes), a validacao
corrigida deu **zero falso positivo e zero problema real perdido**. Reintroduzindo de proposito
o mesmo defeito que causou o bug original (uma linha de comentario antes do `#%RAML` no
arquivo principal), a validacao **continuou detectando** — porque esse arquivo especifico nao
esta na lista de includes, e por isso precisa mesmo do cabecalho.

Essa logica (achar includes, validar so quem nao e include) e o que a feature deveria rodar
antes de qualquer `upload`/`publish`, recusando ou avisando antes de mandar algo que o
Exchange aceitaria em silencio.

## Implementado e testado ponta a ponta: os tres comandos, contra a conta de teste

Os tres comandos (`pararepo raml`, `paradesign raml`, `publicardesign`) foram implementados
em `src/mule_bridge/exchange.py` (as chamadas a `anypoint-cli-v4`) e `src/mule_bridge/cli.py`
(os comandos e os dois menus: projeto do Design Center, versao do Exchange). Testado o ciclo
completo contra a conta de teste, num repo isolado:

1. `pararepo raml` num repo sem pasta de RAML: menu de projeto, menu de versao, baixou a
   1.5.0 do Exchange, extraiu, gravou o pareamento, commitou a base — 24 arquivos.
2. Edicao local (`echo "..." >> <arquivo>`) seguida de `pararepo raml` de novo, sem versao
   nova disponivel: relatou "so seus, intocados: 1" e nao tocou no arquivo — confirmado que
   a edicao sobreviveu.
3. `paradesign raml`: upload da pasta (com a edicao local) para o Design Center — revisao
   subiu, confirmado com `designcenter project list`.
4. `publicardesign`: mostrou a versao publicada atual (1.5.0) antes de perguntar a nova,
   publicou a 1.6.0 usando o `main` correto (lido do `exchange.json`) —
   confirmado baixando o asset publicado e vendo a edicao local dentro do arquivo certo.

Achados de implementacao registrados nas secoes anteriores (nao repetidos aqui): o `.cmd` do
Windows precisa de `shutil.which`, `exchange asset list` exige `--organizationId` e filtro por
`assetId`+`type` no cliente, `exchange asset download` baixa zip (extraido pelo modulo), e a
mensagem "Could not determine raml's version" e mais uma variante do RAML mal formado.

## Testado tambem: pasta local numa versao antiga, trazendo uma versao muito mais nova, com
## edicao local pendente — o merge preserva as duas coisas

Cenario pedido explicitamente para confirmar, alem do "so avancar uma versao": e se a pasta
local estiver **varias versoes atras** da mais nova do Exchange, com uma edicao local ainda
nao publicada, e o `pararepo raml` trouxer a versao mais nova (nao a proxima)?

**Primeiro teste, com conteudo real do projeto de teste** (pasta na 1.3.0, Exchange na
1.6.0, edicao local numa linha de `domain/veiculos.raml`): o resultado classificou o arquivo
como "so seus, intocados", o que a princípio parecia suspeito — mas investigando, o
conteudo real desse arquivo especifico nao mudou de 1.3.0 para 1.6.0 (a diferenca era so
normalizacao de fim de linha, ja documentada na secao "O Design Center normaliza o fim de
linha"). Ou seja: o algoritmo classificou certo, so nao testava o caso de mudanca real dos
dois lados no mesmo arquivo.

**Segundo teste, sintetico e controlado**, para isolar exatamente esse caso: pasta local
na "1.0.0" com uma edicao numa linha (`id: integer  # MINHA EDICAO LOCAL`), Exchange com uma
"1.1.0" que edita outra linha do mesmo arquivo (`linha3: string  # MUDANCA DO EXCHANGE`).
Rodando `pararepo raml` e escolhendo a 1.1.0 direto (pulando qualquer intermediaria):

```
RAML 1.0.0 -> 1.1.0
merge (seu + o que veio): 1 arquivo
```

Conteudo final do arquivo, confirmado:
```
      id: integer  # MINHA EDICAO LOCAL
      linha2: string
      linha3: string  # MUDANCA DO EXCHANGE NA VERSAO NOVA
```

**As duas edicoes convivem no arquivo final.** Confirma que a base do merge de tres pontas
e sempre a versao real que a pasta local tem (lida do `exchange.json` dela via
`versao_da_pasta`, nunca do `pom.xml` ou de qual versao foi escolhida no menu) — e que isso
funciona corretamente mesmo pulando varias versoes de uma vez, nao so ao avancar uma.

## Validacao de RAML antes de subir/publicar: implementada e testada

A pendencia mais serio do desenho (secao "O RAML mal formado nao sempre falha — as vezes
publica quebrado, em silencio") foi implementada em `src/mule_bridge/ramlvalidate.py`: a
logica de "achar includes, validar so quem nao e include" que ja tinha sido validada
manualmente nesta investigacao agora roda automaticamente antes de `paradesign raml`
(contra a pasta local que vai subir) e `publicardesign` (contra o que esta de fato no
Design Center agora, baixado numa pasta temporaria — nao a pasta local, que pode ja ter
mudado desde o ultimo upload).

**Testado contra a conta real, com o defeito documentado reintroduzido de proposito**
(`# defeito antes do cabecalho` antes do `#%RAML 1.0` no `api.raml`): o `paradesign raml`
recusou antes de chamar `upload_design_center`, com a mensagem apontando o arquivo e a
primeira linha encontrada — nenhuma revisao nova subiu ao Design Center por essa tentativa
(confirmado com `designcenter project list` antes e depois). Corrigindo o cabecalho, o
mesmo comando completou o upload normalmente.

**Zero falso positivo confirmado de novo**, desta vez com a validacao de verdade (nao so o
algoritmo manual de antes): baixando o `teste-ponte` publicado (1.6.0, 24 arquivos, com
`!include` de verdade em varios subdiretorios) e rodando `ramlvalidate.validar` contra ele,
nenhum arquivo foi acusado.

## CORRECAO IMPORTANTE: a causa real da documentacao nao aparecer

As secoes anteriores ("RAML mal formado nao sempre falha", "Documentacao nao e algo que se
gera por comando") **diagnosticaram a causa errada**. Investigando de verdade — baixando o
zip publicado e olhando o `exchange.json` de dentro dele, em vez de confiar no que eu tinha
"corrigido" localmente — a causa real e outra:

**O `mainFile` publicado, num certo ponto, deixou de ser o `api.raml`.** O Design Center,
ao criar um projeto chamado `teste-ponte`, gera sozinho um arquivo placeholder
`teste-ponte.raml` com so duas linhas (`#%RAML 1.0` + `title: teste-ponte`) e configura o
`exchange.json` do projeto para apontar `"main": "teste-ponte.raml"` por padrao — nao para o
RAML real que foi subido depois.

Sao **dois achados distintos**, nao o mesmo: a secao anterior (linhas de comentario antes do
`#%RAML`) e um defeito real no conteudo do `api.raml`, que numa publicacao gerou erro claro de
parse. Este aqui e outro problema, no `exchange.json` do projeto, que faz o `publish` (quando
chamado sem `--main`) publicar **um arquivo diferente do que a pessoa pensa que esta
publicando** — o placeholder, nao o contrato real. Foi esse segundo problema que explicava por
que a documentacao continuava ausente mesmo depois de corrigir o primeiro.

Como a propria ajuda do `publish` avisa: *"Options that are not specified are extracted from
exchange.json"* — se o `main` la dentro esta errado, o comando publica o arquivo errado, sem
avisar.

Confirmado consultando `--help` do publish: existe a flag `--main`. Publicando de novo com
ela:

```
anypoint-cli-v4 designcenter project publish teste-ponte --apiVersion v1 --version 1.4.0 --main api.raml
...
Project published to Exchange
```

E baixando o asset publicado para confirmar o `exchange.json` de dentro do zip:

```
{"main":"api.raml", ...}
```

Agora sim aponta para o arquivo certo.

**Licao para a feature:** nao basta subir os arquivos certos — e preciso garantir que o
`exchange.json` (local ou via `--main` no publish) aponte para o RAML principal de verdade,
especialmente em projeto criado do zero pelo Design Center, que gera um placeholder por nome
do projeto e o deixa como main por padrao. Isso e silencioso: nao ha erro, nem aviso, so a
documentacao vazia.

## Documentacao (Summary/Endpoints) nao e algo que se "gera" por comando

O botao "Generate documentation" que aparece na tela do Exchange (visto no asset real
real) nao tem equivalente na CLI. Os comandos disponiveis (`exchange asset page list`,
`download`, `upload`, `modify`, `update`, `delete`) manipulam paginas de texto/Markdown — nao
disparam a analise do RAML que produz a tabela de recursos.

A tela de Endpoints/Summary parece ser gerada automaticamente pelo Exchange **quando a spec e
reconhecida como valida** (ver secao anterior) — nao pareceu depender de um clique manual,
mas nao foi possivel confirmar 100% via CLI, so pela inspecao visual da pagina.

**Pesquisado e confirmado com fonte oficial (nao so inferencia dos testes):** sao DUAS coisas
diferentes na pagina do asset, e so uma delas e automatica:

1. **A aba de Endpoints/tabela de recursos** (a que falta no `teste-ponte` quebrado, e existe
   real) — e gerada **automaticamente pelo parse do RAML**, sem clique nenhum,
   como parte da publicacao. Fonte:
   [busca sobre Exchange Asset Creation](https://docs.mulesoft.com/exchange/to-create-an-asset).
   E exatamente por isso que ela nao aparecia: o `mainFile` estava mal formado e o parser nao
   conseguia ler.

2. **O botao "Generate documentation"** — isso e outra funcionalidade, chamada **Einstein for
   Anypoint Exchange**: geracao de documentacao **por IA generativa** (nao e o parse simples
   do RAML). Segundo a
   [documentacao oficial](https://docs.mulesoft.com/exchange/generating-documentation-with-ai),
   o fluxo e: "Select the API from the catalog and click Generate documentation from the
   asset details page" — **manual, so pela interface**, sem API/CLI documentada para acionar
   programaticamente. Ela produz overview, autenticacao, base URL e documentacao detalhada de
   endpoints em formato de texto corrido — um "artigo" sobre a API, nao a tabela de recursos.

**Resposta direta:** a tabela de Endpoints deve aparecer sozinha, sem clique, se o RAML for
valido. O "Generate documentation" (texto gerado por IA) esse sim exige clique seu — nao ha
comando equivalente na CLI nem na API publica documentada.

**Consequencia pratica: a feature nao controla isso.** Se o `mainFile` for valido, a
documentacao deve aparecer sozinha; se nao aparecer, o problema mais provavel e o RAML mal
formado (secao anterior), nao falta de um passo extra de "gerar documentacao".

## Onde isso deixa a feature

O caminho funciona e cabe no desenho: um comando levaria a pasta de RAML editada ao Design
Center, ele versionaria sozinho, e a publicacao no Exchange continuaria sendo a decisao
manual que ja e hoje — no fluxo do projeto ela e feita clicando em "Publish to Exchange" no
Design Center. Nada de reimplementar: o `ponte` chamaria a `anypoint-cli-v4`, como hoje chama
o `git`.

**O `designcenter project publish` funciona** — nao e bug da CLI. O erro `TypeError` que
apareceu no inicio dos testes era falta do escopo `Exchange Contributor` na Connected App; com
ele, o publish funciona, versiona certo, e o conteudo chega integro no Exchange. Confirmado em
varios testes, inclusive com mudanca grande espalhada por 5 pastas (detalhes na secao
"O publish funciona — faltava escopo, nao era bug").

Publicar no Exchange pode entao ser feito por comando, sem abrir o navegador — e isso muda a
analise: nao e so o `upload` para o Design Center que a feature cobriria, mas o ciclo
completo: editar local -> upload -> publish, tudo por CLI.

O que pesa contra segue sendo de projeto, nao tecnico:

- **Dependencia externa nova.** A CLI exige Node 22+ e traz `puppeteer` e `yarn` a tiracolo.
  Hoje o `ponte` depende so de Python e do `git`, e a instalacao e um comando.
- **Credencial.** Exige Connected App com os escopos `Design Center Developer` e (para
  publicar) `Exchange Contributor`. O `ponte` nunca lidou com segredo. Ler de uma config feita
  por fora e melhor do que guardar, mas ainda e um pre-requisito novo — e a mensagem de erro
  de escopo faltando engana, parece credencial errada (da 403 "Forbidden", nao fala de
  escopo).
- **Um terceiro lado.** Hoje a ferramenta sincroniza duas pastas locais, e todo o cuidado dela
  (nunca apagar, sempre merge, nunca decidir sozinha) parte de que o dano e local e
  reversivel. Escrever no Design Center e no Exchange e escrever onde o time ve — e publicar
  no Exchange e uma operacao dificil de desfazer (versoes publicadas ficam la).
- **Publicacao silenciosa quando o `mainFile` esta errado ou o RAML e invalido.** Dois
  achados distintos, ambos silenciosos (ver secoes "O RAML mal formado nao sempre falha" e
  "CORRECAO IMPORTANTE: a causa real da documentacao nao aparecer") — juntos, sao o risco mais
  serio para a confiabilidade da feature.

## Puxar a versao mais nova publicada, sem depender do fluxo manual

Pergunta testada: e possivel a feature descobrir e baixar a versao mais recente publicada no
Exchange, sem alguem ter que acompanhar/lembrar qual foi a ultima publicacao?

**Sim, a CLI/API expoe o que e preciso, mas nao ha atalho de "latest" pronto.**

`exchange asset download <asset>/latest` **nao funciona** — testado, da erro:
```
Error: There was a problem looking for the specified asset.
```
A CLI exige o numero exato da versao no argumento (`<groupId>/<assetId>/<version>`).

O que funciona: `exchange asset list --output json` devolve todas as versoes publicadas de
um asset, e a lista ja vem **com a mais nova primeiro**:
```json
[
  {"assetId":"teste-ponte","version":"1.4.0", ...},
  {"assetId":"teste-ponte","version":"1.3.0", ...},
  ...
]
```
Extraindo o `version` do primeiro item com esse `assetId`, e possivel montar o
`exchange asset download <asset>/<versao-extraida>` e trazer o conteudo publicado mais recente
sem intervencao manual. Testado e confirmado: o download trouxe o zip da `1.4.0` (a mais nova
naquele momento) usando so essa logica.

**Para a feature:** e viavel automatizar "traga a versao mais atual do Exchange", mas isso e
codigo a escrever (listar + escolher o primeiro + baixar) — nao e um comando unico que a
plataforma ja oferece.

## `exchange asset list` sem `--organizationId` traz o catalogo publico inteiro, nao so a org

Testado ao implementar o cruzamento de menus: chamar `exchange asset list --output json` sem
filtro nenhum devolve o catalogo publico do Exchange (conectores de outras organizacoes, tipo
`mule-sap-s4hana-cloud-connector`), nao os assets da conta de teste. **`--organizationId` e
obrigatorio na pratica**, mesmo a API/CLI nao marcando como flag exigida.

Com `--organizationId <groupId>` funciona e traz certo, mas ainda faltam dois filtros que a
feature precisa aplicar no cliente, porque a CLI nao tem flag para eles:

- **Nao ha flag de `assetId` exato.** O unico filtro de texto e o argumento posicional
  `SEARCHTEXT` (ex: `exchange asset list "teste-ponte" --organizationId ...`), que e busca
  textual, nao igualdade — pode trazer nomes parecidos. A feature precisa filtrar de novo no
  resultado, comparando `assetId` exato.
- **`type` vem misturado.** Publicar um `rest-api` cria tambem o `extension` companheiro
  (`mule-plugin-<nome>`, ver secao "O connector 'extension' que aparece sozinho") e os dois
  aparecem juntos na mesma lista, intercalados por versao. A feature precisa filtrar
  `type == "rest-api"` antes de montar o menu de versoes — senao um `mule-plugin-*` aparece
  como se fosse uma versao do asset principal.

**`--limit` tem default 10** (visto no `--help`) — para nao truncar o historico de versoes de
um asset publicado mais de 10 vezes, a feature deve passar um `--limit` alto (ex: 100) ou
paginar com `--offset`.

**Campo de data no `designcenter project list`:** e `lastUpdatedDate`, nao `lastBackupDate`
(esse ultimo e sempre `null` nos testes, e parece ser so para backup manual do Design Center,
nao para "ultima edicao"). Confirmado com `-o json`:
```json
{"name": "teste-ponte", "lastUpdatedDate": "2026-08-22T16:40:27.181+00:00", "version": "29"}
```

## `exchange asset download` baixa um zip, nao a pasta extraida

Testado ao implementar: `exchange asset download teste-ponte/1.3.0 destino/` cria
`destino/<hash-sha256>.zip` — o nome do arquivo e um hash, imprevisivel, nao o nome do asset
nem da versao. A feature precisa descobrir o nome do arquivo criado (unico arquivo na pasta
apos o comando) e extrair o zip ela mesma com `zipfile`, do mesmo jeito que `reconcile.extrair`
ja faz para o cache do Maven — nao ha opcao de pedir para a CLI extrair.

## Um projeto do Design Center por par: precisa escolher qual, sim

Ate este ponto os testes tinham so 1 projeto na conta (`teste-ponte`), entao nunca foi
testado o cenario de **multiplos projetos na mesma organizacao** — que e o caso real: uma org
de qualquer cliente pode ter varios projetos no Design Center (um por API).

**Testado agora criando um segundo projeto** (`outro-projeto`) na mesma conta. Confirmado:

```
anypoint-cli-v4 designcenter project list

ID                                     Version   Name             Type
7cf23d17-99b9-42b0-8880-05ac667b631a   2         outro-projeto    raml
0ad41066-9545-46c0-b05f-9039408bef6d   29        teste-ponte      raml
```

E cada projeto baixado tem seu **proprio `exchange.json`**, com `assetId` diferente:

```json
// teste-ponte/exchange.json
{"assetId": "teste-ponte", "main": "api.raml", ...}

// outro-projeto/exchange.json
{"assetId": "outro-projeto", "main": "outro-projeto.raml", ...}
```

O `groupId` (organizacao) e igual porque e a mesma conta — mas o `assetId` distingue, e e por
projeto.

**Consequencia para a feature:** o `ponte` precisa perguntar **qual projeto do Design Center**
usar, do mesmo jeito que hoje ja pergunta qual pasta local pareia com qual projeto no
workspace do Studio. Nao ha atalho que dispense essa escolha quando existe mais de um projeto
na org — o que e o caso comum, nao a excecao.

O vinculo com o Exchange (`groupId`+`assetId`+`main`) vem de brinde **depois** dessa escolha,
lido do `exchange.json` do projeto selecionado — nao e uma segunda pergunta separada sobre
"qual Exchange". So se sobrescreve isso (via `--groupId`/`--assetId`/`--main` no `publish`) se
for um caso avancado de publicar num asset diferente do vinculado por padrao.

## Decisao de design: qual informacao mostrar no menu de projetos

Testado simulando o cenario real (varios projetos na org, nao so 1). Criados temporariamente
5 projetos com nomes variados para validar filtro por texto digitado, ordenacao, e o que
mostrar em cada linha.

**A `version` do `project list` do Design Center NAO e a versao publicada no Exchange —**
sao dois contadores completamente diferentes, confirmado com numeros reais lado a lado:

```
Design Center (project list):   teste-ponte   revisao 29
Exchange (asset list):          teste-ponte   1.4.0 (a mais recente publicada)
```

A revisao do Design Center sobe a cada `upload`, publicado ou nao — e um numero alto (29) que
nao significa nada para quem consome a API. Mostrar so essa `version` no menu enganaria o
usuario, fazendo parecer que e a versao "oficial".

**Cruzar automaticamente pelo nome do projeto e uma armadilha, testada e confirmada como
erro real:** publicar o projeto `outro-projeto` com `--assetId nome-totalmente-diferente`
funcionou normalmente (a flag existe e sobrescreve o vinculo padrao, como ja sabiamos do
`--main`). Resultado: o asset no Exchange se chama `nome-totalmente-diferente`, nao
`outro-projeto`. Uma logica que buscasse no Exchange "um asset com o mesmo nome do projeto"
concluiria, errado, que o projeto nunca foi publicado.

**A forma correta e ler o `exchange.json` de cada projeto** (que tem o `assetId` real,
gravado no momento da publicacao) e so entao consultar o Exchange por esse valor — nunca supor
que nome do projeto == assetId.

### Formato decidido para o menu, com dados reais confirmados

Cruzando corretamente (por `assetId` do `exchange.json`, nao por nome), o menu mostraria as
duas informacoes lado a lado, incluindo o caso "nunca publicado":

```
Qual projeto do Design Center?
  1. teste-ponte      (modificado 22/08 13:40)   versao no Exchange: 1.4.0 (latest, 22/08 13:40)
  2. outro-projeto    (modificado 22/08 14:17)   nunca publicado no Exchange
  3. outra opcao — eu digito para filtrar
```

**O rotulo e explicito: "versao no Exchange"**, nao so "publicado" — para nao deixar
ambiguo de onde vem esse numero, ja que a linha tambem mostra a data de modificacao do Design
Center ao lado. E sempre a **ultima** versao publicada (`latest`) que aparece aqui — esta
linha e so para ajudar a escolher o **projeto**; a escolha de qual versao trazer (a mais
atual ou uma anterior) e um passo separado, depois, descrito na secao "Decisao de design:
menu de versoes ao trazer do Exchange".

**A data de publicacao vem de novo, testado agora com os dados reais da conta de teste:**
o `exchange asset list --organizationId <org> --output json` traz `createdDate` por versao —
nao so o numero. Confirmado lado a lado:

```json
{ "assetId": "teste-ponte", "version": "1.4.0", "createdDate": "2026-08-22T16:40:21.232Z" }
{ "assetId": "teste-ponte", "version": "1.3.0", "createdDate": "2026-08-22T16:29:35.730Z" }
```

Por isso o menu mostra a data ao lado da versao publicada, nao so o numero — decisao tomada
porque a data de "modificado" (Design Center) e a data de "publicado" (Exchange) sao
independentes, e o fluxo manual antigo criava exatamente esse estado intermediario: alguem
cola uma mudanca no Design Center e esquece de publicar. Se o menu mostrasse so a versao sem
data, nao daria para notar que a modificacao e mais recente que a publicacao — ou seja, que
ha algo pendente. Com as duas datas visiveis, a divergencia fica clara sem precisar de um
aviso separado.

**Filtro por texto parcial** (o usuario digita um trecho do nome, nao o nome completo):
buscar `"pag"` entre 6 projetos trouxe so o que continha esse trecho; buscar algo sem
correspondencia (`"zzz"`) devolveu lista vazia — API nao erra, so nao sobra nada.

**Decisao: alem do filtro exato, sugerir por semelhanca quando nao achar nada.** Testado a
diferenca entre os dois tipos de busca com um typo real:

```
digitado "tset-ponte"           (erro de digitacao, faltou trocar duas letras)
  filtro por substring:  []                    -> nao acha nada
  busca por semelhanca:  ["teste-ponte"]        -> acha, tolera o typo
```

Um filtro por substring sozinho falha exatamente no caso mais comum de erro de digitacao
(letras trocadas), porque "contem o texto" e estrito. A decisao e: se a busca exata nao achar
nada, comparar por semelhanca (`difflib.get_close_matches` ou equivalente) e sugerir o mais
proximo, sempre com uma opcao de digitar de novo caso a sugestao esteja errada:

```
Nenhum projeto com "tset-ponte".

Voce quis dizer teste-ponte?  (modificado 22/08 13:40)   versao no Exchange: 1.4.0 (latest, 22/08 13:40)
  1. sim, e esse
  2. nao, deixa eu digitar de novo
```

Nunca autocompleta sozinho — a sugestao ainda pede confirmacao, pelo mesmo motivo de nunca
decidir por conjectura que vale para o resto do menu.

Nao ha campo de "quantidade de commits" na API — a `version` do Design Center (o contador que
sobe a cada `upload`) e o mais proximo disso, mas nao deveria ser chamado de "commits" no
menu, para nao confundir com o historico de versoes do Exchange, que e outra coisa.

## Decisao de design: menu de versoes ao trazer do Exchange

Para o cenario "trazer a versao publicada de volta para a pasta local", decidido apresentar
um menu de 4 opcoes em vez de assumir sempre a mais recente:

```
Qual versao do RAML trazer?
  1. mais atual — 1.4.0  (22/08 13:40)
  2. 1.3.0  (22/08 13:29)
  3. 1.2.0  (22/08 13:24)
  4. outra versao — eu digito
```

Motivo: o fluxo real as vezes precisa de uma versao especifica, nao so a ultima publicada
(comparar com uma anterior, retomar uma versao em teste, etc.). Formato de cada linha:
**numero da versao — data e hora**, para a data ajudar a lembrar qual e qual.

**As tres primeiras vem de `exchange asset list --output json`,** que devolve `version` e
`createdDate` por item (confirmado: `createdDate` e por versao, diferente de `updatedDate`
que e do asset inteiro). Ordenar por essa data resolve "quais sao as 3 mais recentes".

**A quarta opcao (campo livre) foi confirmada como viavel:** `exchange asset download
<asset>/<versao-qualquer>` funciona com qualquer versao existente, nao so a mais nova —
testado baixando uma versao antiga (`1.1.0`) depois de ja existirem versoes mais novas.

**Fuso horario: converter de UTC para Brasilia (UTC-3) antes de mostrar.** A API devolve tudo
em UTC (sufixo `Z` no `createdDate`, ex: `2026-08-22T16:40:21.232Z`) — sem converter, o menu
mostraria a hora errada (a diferenca e de 3h, o suficiente para confundir "antes/depois do
almoco"). Brasilia nao tem horario de verao desde 2019, entao a conversao e uma subtracao
fixa de 3 horas, sem tabela de regras sazonais para manter.

**Exemplo aprovado do formato final:**

```
Qual versao do RAML trazer?
  1. mais atual — 1.4.0  (22/08 13:40)
  2. 1.3.0  (22/08 13:29)
  3. 1.2.0  (22/08 13:24)
  4. outra versao — eu digito
>
```

Escolhendo `4`, pergunta o texto da versao em seguida e busca ela direto no Exchange.

## Decisao final: os tres comandos, e o que cada um faz

Fechado como a feature se encaixa no vocabulario que o `ponte` ja tem (`parastudio`/
`pararepo`, sempre `raml`/`api`/`force`). O ciclo completo, com direcao clara:

```
[editar local] --(pararepo raml, upload)--> [Design Center] --(publicar, exchange upload)--> [Exchange]
                                                                                                    |
      [de volta pro repo, com merge] <-------------------- pararepo raml (busca), agora direto -----
```

Sim, `pararepo raml` aparece nas duas pontas — **upload** (leva o local pro Design Center) e
**busca** (traz o publicado no Exchange pro repo) sao dois comandos separados, nao a mesma
chamada; ver abaixo por que nao virou duas palavras novas.

### `ponte pararepo raml` — comportamento mudado: busca do Exchange direto, sem depender do Studio

Ja existe, mas deixa de depender do usuario clicar "update" no Studio para descobrir versao
nova — passa a consultar o Exchange diretamente. Dois passos, nesta ordem, porque o segundo
depende do primeiro:

1. **Escolher o projeto do Design Center** — mesmo a origem final sendo o Exchange, e o
   projeto do Design Center que carrega o `exchange.json` com o `assetId` real (cruzar por
   nome e armadilha confirmada, ver secao "Um projeto do Design Center por par"). Menu com
   nome + data de modificacao (Design Center) + versao no Exchange, explicitamente rotulada
   e sempre a `latest` (ver "Formato decidido para o menu" acima). Se so houver um projeto na
   org, ainda pergunta e confirma — nunca assume.
2. **Escolher a versao do Exchange daquele projeto** — menu de 4 opcoes ja aprovado (mais
   atual + 2 anteriores + campo livre, ver "Decisao de design: menu de versoes"), usando o
   `assetId` descoberto no passo 1.

So depois desses dois passos o merge roda, preservando a edicao local — igual ao
comportamento de hoje.

**Pre-requisito novo:** exige a `anypoint-cli-v4` configurada (`client_id`/`client_secret`)
para rodar — os dois passos acima chamam `designcenter project list` e `exchange asset list`,
que exigem autenticacao. Antes, o `pararepo raml` funcionava sem credencial (lia o zip que o
Studio ja tinha baixado). Isso muda a partir de agora: quem usar `pararepo raml` precisa da
credencial configurada, mesmo que nunca vá usar upload/publish.

### `ponte paradesign raml` — comando novo, nome decidido

Sentido contrario ao `pararepo raml`: pega o RAML editado localmente no repo e faz **upload**
pro Design Center — sem publicar no Exchange. So versiona no Design Center (a revisao sobe),
do mesmo jeito que o `upload` testado nesta investigacao inteira.

Segue o padrao `para<destino>` que ja existe (`parastudio`, `pararepo`) — o destino aqui e o
Design Center, entao `paradesign`. Passa pelo mesmo passo 1 do `pararepo raml` (escolher o
projeto do Design Center) — nao passa pelo passo 2 (nao ha versao do Exchange a escolher, o
destino e o Design Center).

### `ponte publicardesign` — comando novo, nome decidido

Publica no Exchange o que esta no Design Center (a revisao atual), criando uma versao nova.
Antes de confirmar, mostra a versao atual publicada (se houver) para o usuario saber o que
esta prestes a virar historico — evita publicar por engano pensando que "sempre foi a
primeira vez".

Herda os riscos ja documentados: o Exchange valida o RAML e recusa cabecalho malformado, mas
**nao valida contra mainFile errado** (publicacao silenciosa, documentacao vazia) — a feature
deve checar o `mainFile` do `exchange.json` antes de chamar o `publish`, nao depois.

```
anypoint-cli-v4 designcenter project delete teste-ponte
anypoint-cli-v4 conf client_id -d
anypoint-cli-v4 conf client_secret -d
```

E revogar a Connected App em `Access Management > Connected Apps`. **Nao antes de terminar** —
sem ela nenhum comando roda.

## Implementacao: `subprocess.run` no Windows precisa resolver o `.cmd` via `shutil.which`

Testado ao escrever `src/mule_bridge/exchange.py`: chamar `subprocess.run(["anypoint-cli-v4",
...])` direto falha com `FileNotFoundError: [WinError 2] O sistema nao pode encontrar o
arquivo especificado`, mesmo com o comando funcionando normalmente no terminal e presente no
`PATH`.

**Causa:** no Windows, `anypoint-cli-v4` (instalado via `npm install -g`) e um script `.cmd`,
nao um `.exe` — `subprocess.run` sem `shell=True` nao aplica a resolucao de extensao do
`PATHEXT` que o `cmd.exe`/PowerShell fazem sozinhos. O `reconcile.py` nunca bateu nesse
problema porque so chama `git`, que tem `.exe` nativo.

**Correcao, sem usar `shell=True`** (que abriria brecha de injecao se algum argumento vier de
config/usuario): resolver o caminho completo com `shutil.which("anypoint-cli-v4")` antes de
montar a lista de argumentos do `subprocess.run`. `shutil.which` aplica o `PATHEXT` do
Windows e acha o `.cmd` corretamente. Testado contra a conta real: `designcenter project list`
funcionou depois da correcao.

## Mais uma mensagem de erro do `publish` com RAML mal formado: "Could not determine raml's version"

Testado com `src/mule_bridge/exchange.py` (`publicar_exchange`), contra um arquivo `main`
real que tinha as linhas extras antes do `#%RAML 1.0` (o mesmo defeito da secao "O RAML mal
formado nao sempre falha"). Erro obtido:

```
Error: ... | Could not determine raml's version.
```

Mensagem diferente da vista antes ("Cannot parse document with specified vendor") para a
mesma causa raiz — o parser da plataforma parece reagir de formas diferentes dependendo de
como o cabecalho esta corrompido. Confirma, mais uma vez, que a feature deve validar o
cabecalho `#%RAML` do `mainFile` antes de chamar `publish` (ver secao "O RAML mal formado nao
sempre falha as vezes publica quebrado, em silencio"), porque a mensagem de erro da CLI nao e
consistente nem clara sobre a causa.

## Filtro por texto e sugestao por semelhanca no menu de projeto: implementado

A pendencia identificada em code review (o design ja previa isso na secao "Filtro por texto
parcial", mas a primeira implementacao do menu mostrava a lista inteira sem filtro) foi
fechada em `_filtrar_e_escolher` (`src/mule_bridge/cli.py`), usada por
`_escolher_projeto_design_center`:

1. Pergunta um trecho do nome antes de mostrar a lista (`Digite um trecho do nome do
   projeto (ou Enter para ver todos)`) — Enter vazio preserva o comportamento antigo de
   mostrar tudo.
2. Filtro por substring, case-insensitive.
3. Se a busca exata nao achar nada, `difflib.get_close_matches` sugere o nome mais parecido
   e pede confirmacao explicita (`Voce quis dizer <nome>? 1. sim 2. nao, deixa eu digitar
   de novo`) — nunca autocompleta sozinho.
4. Recusando a sugestao, volta a pedir o filtro (recursao), nao aborta o comando.

**Testado contra a conta real** com o mesmo typo do design original (`tset-ponte`): a busca
por substring nao achou nada, a sugestao por semelhanca acertou `teste-ponte`, a confirmacao
funcionou, e o fluxo seguiu normalmente até criar a pasta do RAML. O filtro por substring
tambem foi testado (`outro` reduziu a lista para so `outro-projeto` antes do menu de
escolha).

Isso muda a sequencia de entrada esperada em qualquer teste que simule `pararepo raml`,
`paradesign raml` ou `publicardesign` via `CliRunner`: agora e preciso um `\n` extra
(Enter no filtro) antes do numero que escolhe o projeto — testes antigos que simulavam so
`"1\n1\n"` passaram a `"\n1\n1\n"`.
