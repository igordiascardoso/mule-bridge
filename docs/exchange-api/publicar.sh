#!/usr/bin/env bash
# Publica um RAML no Exchange pela Exchange API v2, contornando o `publish` da CLI.
#
# Uso:
#   ID=seu_client_id SECRET=seu_client_secret ZIP=/caminho/raml.zip bash publicar.sh
#
# Nao imprime a credencial nem o token.

set -euo pipefail

: "${ID:?defina ID=seu_client_id}"
: "${SECRET:?defina SECRET=seu_client_secret}"

ORG="${ORG:?defina ORG=id-da-sua-organizacao}"
ASSET="${ASSET:-teste-ponte}"
VERSAO="${VERSAO:-1.0.0}"
MAIN="${MAIN:-api.raml}"                       # o arquivo principal dentro do zip
ZIP="${ZIP:?defina ZIP=caminho/do/raml.zip}"   # o zip do RAML, montado por voce

echo "1) pegando o token"
TOKEN=$(curl -s -X POST \
  https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token \
  -H 'Content-Type: application/json' \
  -d "{\"grant_type\":\"client_credentials\",\"client_id\":\"$ID\",\"client_secret\":\"$SECRET\"}" \
  | python -c 'import json,sys; print(json.load(sys.stdin).get("access_token",""))')

if [ -z "$TOKEN" ]; then
  echo "   FALHOU: nao veio access_token — credencial ou escopo?"
  exit 1
fi
echo "   ok (token obtido, nao impresso)"

echo "2) publicando $ASSET $VERSAO no Exchange"
curl -s -o /tmp/resp.json -w '   HTTP %{http_code}\n' -X POST \
  "https://anypoint.mulesoft.com/exchange/api/v2/organizations/$ORG/assets/$ORG/$ASSET/$VERSAO" \
  -H "Authorization: bearer $TOKEN" \
  -H 'x-sync-publication: true' \
  -F "name=$ASSET" \
  -F "description=publicado pela Exchange API, sem a CLI" \
  -F "properties.mainFile=$MAIN" \
  -F 'properties.apiVersion=v1' \
  -F "files.raml.zip=@$ZIP"

echo "3) resposta:"
head -c 600 /tmp/resp.json; echo
