# Gerar o scaffold sem o Anypoint Studio — investigação

Registro do que foi verificado, o que falta, e o que ainda não se sabe. Alimentado a cada
passo.

**Objetivo:** descobrir se o `ponte` pode ganhar uma feature que gere o scaffold Mule (flows
XML a partir do RAML, o que hoje só acontece com o update de versão em
`Properties > Mule Project > APIs` dentro do Studio) sem precisar abrir a IDE.

---

## O que já está resolvido

### Não existe caminho oficial documentado pela MuleSoft

A documentação oficial da APIkit lista só três formas de gerar o scaffold, e todas dependem
da IDE:

1. New Mule Project wizard → "Scaffold Flows From These API Specifications"
2. Package Explorer → botão direito no arquivo da API → "Mule > Generate flows from Local
   REST API"
3. Package Explorer → botão direito na dependência da API → "Generate flows"

A doc é explícita: *"You must have access to Anypoint Studio or Anypoint Code Builder to
scaffold a supported API specification with APIkit."* Não há goal Maven oficial da MuleSoft
para isso — o "Maven" que aparece na doc é só sobre importar a API dentro do wizard do
Studio, não sobre gerar fora dele.

O `anypoint-cli-v4` (investigado em [DESIGN-CENTER-CLI.md](DESIGN-CENTER-CLI.md)) também não
cobre isso: seus comandos `designcenter` e `exchange` tratam só de Design Center/Exchange,
nada de scaffold de flows.

### Existe uma alternativa de comunidade, mas com limitação que provavelmente a descarta

`apikit-flow-generator-maven-plugin` (AVIO Consulting), goals `generateFlowRest` /
`generateFlowSoap`, roda via `mvn` sem abrir o Studio. Achados contra:

- Não é da MuleSoft — projeto de comunidade, manutenção incerta.
- **Não suporta MFA nem SSO** — inviável em org corporativa com autenticação moderna.
- Não há confirmação de que reproduz fielmente o que o Studio gera.

### Achado principal: a biblioteca real que o Studio usa é acessível diretamente

O Anypoint Studio é Eclipse RCP (`AnypointStudio.exe`, `AnypointStudio.ini`, `plugins/`,
`features/`, `p2/` — confirmado em `C:\.ferramentas\AnypointStudio`). Dentro dele:

```
plugins/org.mule.tooling.apikit.common_7.28.0.202608121221/lib/apikit-scaffolder-1.4.0.jar
```

Esse jar **não é plugin Eclipse-only** — é uma biblioteca Java pura, sem `Main-Class` no
manifesto (não tem CLI própria), mas com uma **API pública limpa** que o Studio chama
internamente para gerar o scaffold. Inspecionada com `javap` (usando o JDK embutido do
próprio Studio, em `plugins/org.mule.tooling.jdk.win32.x86_64_1.4.1/bin/javap.exe` — o
`javap` do sistema não estava no PATH):

```java
package org.mule.apikit.scaffolding.api;

public interface Scaffolder {
    ScaffoldingResult scaffold(ScaffoldingConfig config);
    ScaffoldingResult scaffoldMunitTestSuite(ScaffoldingConfig config);
}

public interface ScaffoldingConfig {
    String getApi();                                    // o RAML/main file
    String getBasePath();
    Set<String> getExistingConfigurations();             // evita duplicar flows já existentes
    Set<String> getExistingResources();
    Map<String, InputStream> getTemplates();
}

public interface ScaffoldingResult {
    boolean success();
    Map<String, InputStream> generatedMuleXmls();         // os flows XML prontos
    Map<String, InputStream> generatedPropertiesFiles();
    List<ScaffoldingError> errors();
    List<ScaffoldingDependency> dependencies();           // GAVs que entram no pom.xml
    Map<String, List<String>> additionalInformation();
}

public interface ScaffoldingDependency {
    String gavCoordinate();
    String classifier();
}

public interface ScaffoldingError {
    String cause();
    String stackTrace();
}
```

Entrada e saída são tipos simples (String, Set, Map de InputStream) — nada pede workspace
Eclipse aberto, nada pede UI. Essa é a mesma peça que a `apikit-flow-generator-maven-plugin`
da AVIO usa por baixo dos panos, só que acessível direto do disco, sem depender do plugin de
terceiros nem da limitação de MFA/SSO dele.

**Onde encontrar de novo**, caso o Studio seja reinstalado ou a versão mude:

```powershell
Get-ChildItem "<pasta-do-studio>\plugins" -Filter "*apikit*"
```

O jar fica em `lib/apikit-scaffolder-<versão>.jar` dentro da pasta
`org.mule.tooling.apikit.common_<versão-do-studio>`.

---

## O que falta testar

- [ ] Montar um pequeno programa Java que implemente `ScaffoldingConfig` a partir de um
  `api.raml` real do projeto (lendo os arquivos existentes para preencher
  `getExistingConfigurations()`/`getExistingResources()` e não duplicar flows).
- [ ] Descobrir o classpath completo necessário (o `apikit-scaffolder-1.4.0.jar` sozinho tem
  dependências fortes em AMF/Scala — ver a pasta `lib/` inteira do plugin, listada na
  investigação: `amf-*`, `scala-library`, `wlang`, `parser`, etc. Provavelmente precisa do
  `lib/` inteiro no `-cp`).
- [ ] Chamar `scaffold(...)` de fato contra um RAML do projeto real (ou o de teste já usado
  em [DESIGN-CENTER-CLI.md](DESIGN-CENTER-CLI.md)) e comparar o XML gerado com o que o Studio
  geraria pela UI, arquivo por arquivo.
- [ ] Confirmar se `generatedMuleXmls()`/`generatedPropertiesFiles()` batem 1:1 com o que a
  ferramenta grava em disco quando gerada pela UI, ou se a UI faz pós-processamento adicional
  (formatação, ordenação de flows, etc.) que precisaria ser replicado.
- [ ] Verificar se as `dependencies()` retornadas cobrem tudo que o Studio adiciona no
  `pom.xml` do projeto (ou se falta algo que a UI resolve por fora, como o `mule-maven-plugin`
  em si).
- [ ] Testar `scaffoldMunitTestSuite(...)` também, já que existe e pode interessar para uma
  segunda feature (gerar testes MUnit sem Studio).
- [ ] Confirmar se essa API é estável entre versões do Studio (hoje testada contra
  `7.28.0.202608121221`) ou se o pacote `internal` por trás muda com frequência — o pacote
  `api` parece deliberadamente separado do `internal` para isso, mas não foi confirmado
  olhando changelogs.
- [ ] Decidir a forma de empacotar: chamar via `java -cp` de dentro do `ponte` (Python
  invocando um `.jar` fino que faz essa ponte), ou algo mais integrado.

## Onde isso deixa a feature

Ainda não é uma feature pronta — é a confirmação de que o caminho técnico existe e é viável:
a lógica de scaffold não é proprietária inacessível, é uma biblioteca Java com API pública
redistribuída dentro do próprio instalador do Studio. O gargalo deixa de ser "impossível sem
clicar na IDE" e passa a ser "escrever um pequeno adaptador Java que chama essa API com os
dados certos".

Isso muda a resposta dada antes (quando só se conhecia a via oficial e o plugin da AVIO): dá
sim para tirar o Studio do scaffold, sem depender de um projeto de comunidade com limitação
de MFA/SSO — usando a mesma peça que o Studio usa, direto.

## Cuidados

- Essa é uma peça interna do produto (pacote `org.mule.apikit.scaffolding.internal` ao lado
  do `api`), redistribuída dentro do instalador — não documentada publicamente como API para
  uso de terceiros. Não há garantia contratual de estabilidade entre versões do Studio.
- O jar tem dependências pesadas (AMF, Scala) — herdar isso no `ponte` é uma dependência nova
  significativa, do mesmo tipo de preocupação já registrada para a `anypoint-cli-v4` em
  [DESIGN-CENTER-CLI.md](DESIGN-CENTER-CLI.md) (hoje o `ponte` só depende de Python e `git`).
