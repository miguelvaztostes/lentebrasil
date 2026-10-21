# Inventário de fontes oficiais

> O inventário nacional candidato é um artefato distinto deste levantamento de fontes já
> auditadas. Registros importados como `discovered` não integram esta lista de recursos
> verificados e não autorizam coleta ou publicação.

## Revalidação multicípio — 20/10/2026

- IBGE Localidades respondeu com 27 UFs e 5.571 municípios atuais. A carga preserva unidades
  anteriores como inativas e registra mudanças de nome em `geo_unit_versions`.
- SIDRA 6579/9324 respondeu em um lote para Ribeirão Preto (`3543402`), Campinas (`3509502`) e
  São Paulo (`3550308`), nos anos 2024–2025: seis linhas aceitas, nenhuma rejeitada.
- Siconfi respondeu ao RREO Anexo 01, 6º bimestre de 2025, para os três entes: três chamadas sob
  limite de 1 req/s, doze fases aceitas e nenhuma rejeitada.
- O ZIP nacional CNES com referência de 20/10/2026 foi baixado uma vez, processado em streaming e
  produziu nove agregados. Uma segunda execução recebeu a mesma versão e não repetiu o download
  nem criou observações.
- O CNES continha 14 códigos `53xxxx` sem correspondência municipal atual. As linhas estavam fora
  do recorte selecionado, foram ignoradas e registradas como ocorrência de qualidade
  `unknown_cnes_geography`; não foram silenciosamente convertidas para municípios.

Auditoria realizada em 09/10/2026 a partir deste ambiente. `confirmed` significa que houve resposta de dados verificável; não significa endosso institucional ao Lente Ribeirão.

| Fonte/dataset | Status | Recurso verificado | Formato/licença | Evidência e decisão |
|---|---|---|---|---|
| IBGE Localidades | `confirmed` | `https://servicodados.ibge.gov.br/api/v1/localidades/municipios/3543402` | JSON; uso com atribuição ao IBGE, termos específicos a revisar | HTTP 200; retornou código `3543402`, Ribeirão Preto/SP. Usado para validar domínio geográfico. |
| IBGE SIDRA, tabela 6579, variável 9324 | `confirmed` | `https://apisidra.ibge.gov.br/values/t/6579/n6/3543402/v/9324/p/last%2010?formato=json` | JSON; uso com atribuição ao IBGE, termos específicos a revisar | HTTP 200; em 09/10/2026 retornou, entre outros, população residente estimada de `734538` pessoas para 2026. Primeira integração vertical. |
| Tesouro Nacional / Siconfi, RREO Anexo 01 | `confirmed` | `https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/rreo` | JSON; Apache 2.0; limite publicado de 1 requisição/s | Consulta 2025, 6º bimestre, ente `3543402` retornou 513 registros. Integração fiscal usa rubricas e colunas explicitamente selecionadas, sem somar fases. |
| Tesouro Nacional / documentação | `confirmed` | `https://apidatalake.tesouro.gov.br/docs/siconfi/` e `https://apidatalake.tesouro.gov.br/docs/siconfi.yaml` | OpenAPI/Swagger YAML; Apache 2.0 | Contrato e parâmetros obrigatórios confirmados. |
| INEP / IDEB 2005–2025 | `requires_manual_import` | `https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados` | Página oficial e planilhas oficiais | HTTP 200; a página registra a série 2005–2025 e arquivos municipais, mas o link direto do pacote não foi exposto no HTML estático consultado. Não automatizar até validar arquivo, abas e cabeçalhos. |
| Ministério da Saúde / CNES estabelecimentos | `confirmed` | `https://dadosabertos.saude.gov.br/dataset/cnes-cadastro-nacional-de-estabelecimentos-de-saude` e `https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_csv.zip` | ZIP/CSV, delimitador `;`, bytes Latin-1/Windows-1252 observados; licença do portal a confirmar por recurso | HTTP 200; `Last-Modified: 09/10/2026`, 56.460.257 bytes compactados. O CSV tem 4.350 linhas para código municipal CNES `354340`. O pipeline persiste apenas agregados e hash, não nomes/telefones/e-mails. |
| Prefeitura de Ribeirão Preto / orçamento | `requires_manual_import` | `https://www.ribeiraopreto.sp.gov.br/portal/transparencia/orcamento` | HTML e PDFs históricos; licença não declarada na página auditada | HTTP 200. Foram localizados PDFs de 2007–2021 e páginas de consulta, mas nenhum CSV/XLSX/JSON reutilizável na página inicial. O Siconfi cobre o primeiro recorte fiscal. |
| Câmara Municipal de Ribeirão Preto | `pending` | `https://www.camararibeiraopreto.sp.gov.br/` | HTML | HTTP 200. Nenhuma API ou exportação de votos nominais foi presumida; módulo legislativo permanece fora do MVP. |
| Instituto Ribeirão 2030 / Plano de Cidade | `confirmed` | `https://www.ribeirao2030.com.br/publicacoes/plano-de-cidade-2020-2030/` | HTML/publicação; uso apenas como referência | HTTP 200. Fonte contextual confirmada; catálogo e vínculos às metas exigem curadoria humana e pertencem à fase E. |
| Instituto Ribeirão 2030 / Carta de dados abertos | `confirmed` | `https://www.ribeirao2030.com.br/posicionamentos-publicos/carta-de-ribeirao-preto-pela-transparencia-e-dados-abertos/` | HTML | HTTP 200. Referência temática, não feed de dados nem comprovação de parceria. |
| MTE / CAGED–ISPER | `pending` | `https://www.gov.br/trabalho-e-emprego/pt-br/assuntos/estatisticas-trabalho/isper-dados-por-municipio` | A verificar | Adiado para depois do recorte inicial; nenhum endpoint é inferido. |

## Política de verificação

Uma fonte só muda para `confirmed` quando a URL canônica responde e o conteúdo é conferido contra município, período, unidade e schema esperados. Mudança de schema bloqueia publicação da nova carga, registra uma ocorrência de qualidade e preserva o último valor validado.

## Fontes efetivamente implementadas no MVP

- `ibge_population`: população residente estimada, pessoas, periodicidade anual.
- `siconfi_rreo`: receita realizada e fases independentes da despesa, BRL nominal, exercício/6º bimestre por padrão.
- `cnes_establishments`: contagens agregadas de cadastros do CNES, sem dados pessoais ou identificadores de estabelecimentos na base analítica.

