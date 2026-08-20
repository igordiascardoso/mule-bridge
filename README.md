# mule-bridge

Mantém sincronizados os dois lugares onde um projeto Mule vive: a **pasta de trabalho**, onde
o código é editado e versionado no git, e o **workspace do Anypoint Studio**, de onde o Studio
roda a aplicação.

## O problema

Em muitos setups essas duas pastas são fisicamente separadas — o código fica num repositório
(`c:\projetos\minha-api`) e o Studio roda a partir do seu próprio workspace
(`~\AnypointStudio\studio-workspace\minha-api`). As duas não se falam: uma alteração feita
no repositório simplesmente não aparece no Studio, e a única forma de fazê-la aparecer é
excluir o projeto no Studio e reimportar do zero.

O tráfego também é de mão dupla. O Studio altera arquivos por conta própria: quando o contrato
RAML muda de versão, o scaffold regenera o `application.xml` e pode criar flows novos. Essas
mudanças precisam voltar para o repositório sem atropelar o que você editou lá.

## O que o mule-bridge faz

Um comando para cada sentido, rodados sob demanda — não há watcher em segundo plano:

- **`push`** leva o que você editou no repositório para o workspace do Studio. O Studio detecta
  a mudança no disco e redeploya sozinho, sem reimportação e sem nenhum passo manual.
- **`pull`** traz de volta o que o Studio alterou por conta própria.
- **`init`** descobre os projetos dos dois lados, mostra o que encontrou e deixa você parear —
  a ferramenta nunca adivinha qual pasta corresponde a qual.

O `pom.xml` recebe tratamento especial, para que o RAML editado localmente possa ser testado
no Studio sem que esse apontamento local jamais vaze para o commit (detalhes abaixo).

Funciona em qualquer projeto Mule. O caso previsto é o de uma pasta de API com a pasta do RAML
como irmã na raiz do repositório — quando os nomes seguem o padrão `*-api/` e `*-raml/`, o
pareamento é sugerido automaticamente, mas qualquer par de pastas pode ser escolhido.

## Instalação

```bash
pipx install git+https://github.com/igordiascardoso/mule-bridge
```

## Uso

```bash
cd /caminho/do/seu/repo     # raiz da pasta de trabalho

mule-bridge init            # pareia com um projeto do workspace do Studio
mule-bridge status          # mostra o pareamento e o que um push faria agora
mule-bridge push            # pasta de trabalho -> workspace do Studio
mule-bridge pull            # workspace do Studio -> pasta de trabalho
```

Os dois comandos aceitam `--dry-run`, que mostra o que seria feito sem alterar nada, e
`--delete`, que remove no lado de destino os arquivos que já não existem no lado de origem
(no `push` o destino é o workspace; no `pull`, a pasta de trabalho). Sem `--delete`, o sync
só copia — nada é apagado.

### `init`

Lista os projetos de API encontrados na raiz da pasta de trabalho, os workspaces do Studio
da máquina e os projetos dentro do workspace escolhido — e pede a escolha em cada passo. A
pasta de RAML irmã é sugerida pelo prefixo do nome, mas a decisão continua sendo sua. O
pareamento é gravado em `.mule-bridge.toml` na raiz da pasta de trabalho.

### `push` e o `pom.xml`

O `pom.xml` é o único caso especial. Na pasta de trabalho ele continua sempre apontando para
a dependência do RAML no Exchange, com a versão travada — é essa versão que vai para o git.
Só **no destino** (workspace do Studio) o `push` reescreve a dependência para apontar ao RAML
local, para que as edições locais do RAML possam ser testadas no Studio. A dependência
original fica preservada como comentário logo acima, e o `pull` ignora esse arquivo para que
o apontamento local nunca volte para a pasta de trabalho.

Depois do `push` não é preciso nenhum passo extra no Studio: ele detecta a mudança no disco
e redeploya sozinho.

### `pull`

Captura o que mudou do lado do Studio: o `application.xml` regenerado pelo scaffold, ou
arquivos que o próprio Studio ajustou ao resolver dependências. O `pom.xml` reescrito pelo
`push` é ignorado, para que o apontamento local nunca volte para o repositório.

## Desenvolvimento

```bash
git clone https://github.com/igordiascardoso/mule-bridge
cd mule-bridge
pip install -e ".[dev]"

pytest          # testes
ruff check .    # lint
```

## Estado

Estrutura base e sync bidirecional funcionando.

Ainda por implementar:

- **Reconciliação tipo `git rebase`** — hoje o sync é cópia direta: se os dois lados
  alterarem o mesmo arquivo, o último a sincronizar vence. O alvo é tratar a versão do
  Exchange como base limpa e reaplicar as edições locais por cima, para que nenhum dos
  lados se perca quando o scaffold do Studio e uma edição local acontecem em paralelo.
- **Skill do Claude Code e MCP server** — camadas finas que acionam os mesmos comandos
  desta CLI a partir de um agente, sem reimplementar lógica.
