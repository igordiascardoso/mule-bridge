# Instruções para este projeto

## Regra master: documentar a feature do Design Center/Exchange

Este projeto está investigando uma feature nova do `ponte`: sincronizar RAML entre a pasta
local, o Anypoint Design Center e o Exchange (upload + publish via `anypoint-cli-v4`).

**Toda vez que algo for testado e confirmado (deu certo, deu errado, comportamento
descoberto, achado relevante) sobre essa feature, atualize
`docs/DESIGN-CENTER-CLI.md` na hora — não deixe para depois.**

O documento é o histórico de decisão da feature: o que a CLI faz de verdade (não o que a
documentação promete), os comandos que funcionam, os que não funcionam, os escopos
necessários, e os riscos encontrados (como publicação silenciosa de RAML mal formado).

Sem isso, a próxima sessão de trabalho reproduz testes já feitos.
