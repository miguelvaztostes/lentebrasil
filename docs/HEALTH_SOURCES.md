# Auditoria de fontes oficiais de saúde

Verificação realizada em 22/10/2026. O inventário é uma lista de candidatos; somente uma linha marcada como **integrada** possui conector e dados aptos à publicação. Uma página encontrada ou um endpoint documentado não equivale a dado validado.

| Conjunto | Canal oficial observado | Direito/status | Situação operacional |
|---|---|---|---|
| CNES estabelecimentos | API Dados Abertos MS / cadastro CNES | dados públicos; evitar campos pessoais | integração agregada anterior mantida; expansão de estabelecimentos, leitos e serviços modelada, mas respostas do Swagger não foram homologadas nesta execução |
| CNES leitos e serviços | endpoints documentados no Swagger DEMAS | cadastro público | recurso descoberto; sem resposta/schema validado neste ambiente; não publicado |
| SIH/SUS | endpoint documentado no Swagger DEMAS e arquivos DATASUS/TabNet | agregado público conforme recurso | descoberto; não presumido como API estável; sem conector homologado |
| SIA/SUS | endpoint documentado no Swagger DEMAS e arquivos DATASUS/TabNet | agregado público conforme recurso | descoberto; sem conector homologado |
| SIM | [dataset oficial](https://dadosabertos.saude.gov.br/dataset/sim) e ZIP anual | dados abertos anonimizados; atribuição ao MS | **integrada** para mortalidade não fetal agregada por município de residência, capítulo CID-10 ou faixa etária ampla |
| SINASC | portal/arquivos DATASUS | dados anonimizados conforme recurso | candidato auditado; não integrado |
| SISAB | portal e relatórios e-Gestor APS | acesso e granularidade variam | restrito/relatório; não integrado |
| SIOPS | portal e arquivos/consultas oficiais | dados fiscais públicos | candidato auditado; schema de extração não homologado; gasto em saúde permanece indisponível |
| ANS | [diretório DBC de beneficiários municipais](https://dadosabertos.ans.gov.br/FTP/Base_de_dados/Microdados/dados_dbc/beneficiarios/municipios/) | dados abertos conforme metadados ANS | arquivos mensais verificados no índice, sem parser DBC homologado |
| Epidemiologia (arboviroses e outros) | endpoints documentados no Swagger e conjuntos OpenDataSUS | depende do conjunto | candidatos; não publicados sem validar definição (notificado/confirmado), período, revisão e risco de reidentificação |

## Recurso SIM homologado

- Catálogo: `https://dadosabertos.saude.gov.br/dataset/sim`
- Artefato: `https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SIM/csv/DO24OPEN_csv.zip`
- Referência: 2024; óbitos não fetais (`TIPOBITO=2`), município de residência (`CODMUNRES`).
- Tamanho comprimido observado: 98.076.266 bytes; CSV descompactado: 550.842.628 bytes.
- SHA-256 observado: `13db250c90908e85d1ef9fb9cd7caa08583fb1912108b0f3260605aca0e9b787`.
- Cabeçalho mínimo validado: `TIPOBITO`, `DTOBITO`, `IDADE`, `CODMUNRES`, `CAUSABAS`.
- O conector baixa para área temporária, agrega em streaming e remove o microdado. O snapshot mantém URL, datas, cabeçalhos selecionados e hash, sem armazenar linhas individuais.
- Privacidade: células de 1 a 4 tornam-se `NULL` com status `suppressed`. Causa e faixa etária são publicadas separadamente para reduzir risco de reidentificação.

## Reconciliação manual do SIM 2024

Contagens reproduzidas diretamente do ZIP, sempre por residência. Cada total foi reconciliado tanto com a soma dos capítulos CID-10 quanto com a soma das faixas etárias.

| Município | Total | Circulatórias (I) | Neoplasias (C/D00-D48) | Respiratórias (J) |
|---|---:|---:|---:|---:|
| Ribeirão Preto/SP (3543402) | 5.272 | 1.358 | 958 | 705 |
| Campinas/SP (3509502) | 8.972 | 2.399 | 1.708 | 1.245 |
| São Paulo/SP (3550308) | 87.438 | 25.872 | 15.861 | 13.323 |

Não se calculam taxas padronizadas por população nesta etapa: denominador, ano e metodologia ainda não foram homologados em conjunto. SIM mede óbitos registrados, não notificações, confirmações de casos ou prevalência.

## Limitações verificadas

O host da API Dados Abertos do Ministério da Saúde apresentou reset/erro de gateway para chamadas diretas a partir do ambiente de execução. A documentação indexada permitiu descobrir recursos, mas nenhuma resposta foi usada como se tivesse sido validada. Assim, SIA/SUS, SIH/SUS, expansão CNES, SIOPS, SINASC e conjuntos epidemiológicos adicionais ficam explicitamente indisponíveis na interface, nunca com valor zero.
