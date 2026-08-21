"""Massa de codigo realista compartilhada pelos testes.

Um RAML com types aninhados, patterns, enums, traits e `!include`, e um XML Mule com
processadores encadeados, DataWeave em CDATA, error-handler e entidades escapadas. Vive
separado porque `test_codigo_real` e `test_estresse` usam a mesma massa, e porque manter
codigo realista num lugar so evita que os dois divirjam.
"""

from __future__ import annotations

RAML_BASE = """#%RAML 1.0
title: Catalogo de Produtos
version: v1
baseUri: https://api.exemplo.com/catalogo/{version}
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
  Produto:
    type: object
    properties:
      id:
        type: integer
        required: true
      sku:
        type: string
        pattern: "^[A-Z]{3}-[0-9]{4}$"
        description: Codigo interno do produto
      ean:
        type: string
        minLength: 17
        maxLength: 17
      situacao:
        type: string
        enum: [ATIVO, ESGOTADO, DESCONTINUADO]
  Pedido:
    type: object
    properties:
      produtoId: integer
      valor:
        type: number
        minimum: 0
      dataHora: datetime

/produtos:
  securedBy: [jwt]
  get:
    is: [paginado]
    responses:
      200:
        body:
          type: Produto[]
  /{id}:
    uriParameters:
      id: integer
    get:
      responses:
        200:
          body:
            type: Produto
        404:
          description: Produto nao encontrado

/pedidos:
  securedBy: [jwt]
  post:
    body:
      type: Pedido
    responses:
      201:
        body:
          type: Pedido
      409:
        description: Quantidade indisponivel
"""

# --- Massa: um XML Mule com processadores de verdade -----------------------------

MULE_BASE = """<?xml version="1.0" encoding="UTF-8"?>
<mule xmlns="http://www.mulesoft.org/schema/mule/core"
      xmlns:ee="http://www.mulesoft.org/schema/mule/ee/core"
      xmlns:http="http://www.mulesoft.org/schema/mule/http"
      xmlns:db="http://www.mulesoft.org/schema/mule/db">

    <flow name="get-produtos">
        <http:listener config-ref="api-httpListenerConfig" path="/produtos"/>
        <db:select config-ref="postgres-config">
            <db:sql>SELECT id, sku, ean, situacao FROM produto</db:sql>
        </db:select>
        <ee:transform>
            <ee:message>
                <ee:set-payload><![CDATA[%dw 2.0
output application/json
---
payload map (v) -> {
    id: v.id,
    sku: v.sku,
    ean: v.ean,
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

    <flow name="post-pedidos">
        <http:listener config-ref="api-httpListenerConfig" path="/pedidos"/>
        <flow-ref name="valida-pedido"/>
        <db:insert config-ref="postgres-config">
            <db:sql>INSERT INTO pedido (produto_id, valor) VALUES (:p, :val)</db:sql>
        </db:insert>
    </flow>

    <sub-flow name="valida-pedido">
        <choice>
            <when expression="#[payload.valor &lt;= 0]">
                <raise-error type="APP:PEDIDO_INVALIDO"/>
            </when>
        </choice>
    </sub-flow>
</mule>
"""
