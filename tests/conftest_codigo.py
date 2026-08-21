"""Massa de codigo realista compartilhada pelos testes.

Um RAML com types aninhados, patterns, enums, traits e `!include`, e um XML Mule com
processadores encadeados, DataWeave em CDATA, error-handler e entidades escapadas. Vive
separado porque `test_codigo_real` e `test_estresse` usam a mesma massa, e porque manter
codigo realista num lugar so evita que os dois divirjam.
"""

from __future__ import annotations

RAML_BASE = """#%RAML 1.0
title: Leilao de Veiculos
version: v1
baseUri: https://api.exemplo.com/leilao/{version}
mediaType: application/json

securitySchemes:
  jwt: !include security/jwt.raml

traits:
  paginado:
    queryParameters:
      pagina:
        type: integer
        default: 1
      tamanho:
        type: integer
        default: 20

types:
  Veiculo:
    type: object
    properties:
      id:
        type: integer
        required: true
      placa:
        type: string
        pattern: "^[A-Z]{3}[0-9][A-Z0-9][0-9]{2}$"
        description: Placa no padrao Mercosul
      chassi:
        type: string
        minLength: 17
        maxLength: 17
      situacao:
        type: string
        enum: [DISPONIVEL, ARREMATADO, RETIRADO]
  Lance:
    type: object
    properties:
      veiculoId: integer
      valor:
        type: number
        minimum: 0
      dataHora: datetime

/veiculos:
  securedBy: [jwt]
  get:
    is: [paginado]
    responses:
      200:
        body:
          type: Veiculo[]
  /{id}:
    uriParameters:
      id: integer
    get:
      responses:
        200:
          body:
            type: Veiculo
        404:
          description: Veiculo nao encontrado

/lances:
  securedBy: [jwt]
  post:
    body:
      type: Lance
    responses:
      201:
        body:
          type: Lance
      409:
        description: Lance menor que o atual
"""

# --- Massa: um XML Mule com processadores de verdade -----------------------------

MULE_BASE = """<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db">

    <flow name="get-veiculos">
        <http:listener config-ref="api-httpListenerConfig" path="/veiculos"/>
        <db:select config-ref="postgres-config">
            <db:sql>SELECT id, placa, chassi, situacao FROM veiculo</db:sql>
        </db:select>
        <ee:transform>
            <ee:message>
                <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload map (v) -> {
    id: v.id,
    placa: v.placa,
    chassi: v.chassi,
    situacao: v.situacao
}]]></ee:set-payload>
            </ee:message>
        </ee:transform>
        <error-handler>
            <on-error-propagate type="DB:CONNECTIVITY">
                <logger level="ERROR" message="banco indisponivel"/>
            </on-error-propagate>
        </error-handler>
    </flow>

    <flow name="post-lances">
        <http:listener config-ref="api-httpListenerConfig" path="/lances"/>
        <flow-ref name="valida-lance"/>
        <db:insert config-ref="postgres-config">
            <db:sql>INSERT INTO lance (veiculo_id, valor) VALUES (:v, :val)</db:sql>
        </db:insert>
    </flow>

    <sub-flow name="valida-lance">
        <choice>
            <when expression="#[payload.valor &lt;= 0]">
                <raise-error type="APP:LANCE_INVALIDO"/>
            </when>
        </choice>
    </sub-flow>
</mule>
"""
