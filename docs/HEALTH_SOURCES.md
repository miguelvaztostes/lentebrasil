# Auditoria de fontes oficiais de saúde

Verificação realizada em 22/10/2026. O inventário é uma lista de candidatos; somente uma linha marcada como **integrada** possui conector e dados aptos à publicação. Uma página encontrada ou um endpoint documentado não equivale a dado validado.

| Conjunto | Canal oficial observado | Direito/status | Situação operacional |
|---|---|---|---|
| CNES estabelecimentos | API Dados Abertos MS / cadastro CNES | dados públicos; evitar campos pessoais | integração agregada anterior mantida; expansão de estabelecimentos, leitos e serviços modelada, mas respostas do Swagger não foram homologadas nesta execução |
| CNES leitos | [dataset Hospitais e Leitos](https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos), ZIP/CSV anual | cadastro público; licença CC BY-ND 3.0 informada pelo portal | **integrada** na competência mais recente, com campos de contato e endereço descartados |
| CNES serviços | endpoints documentados no Swagger DEMAS | cadastro público | recurso descoberto; sem resposta/schema validado neste ambiente; não publicado |
| SIH/SUS | endpoint documentado no Swagger DEMAS e arquivos DATASUS/TabNet | agregado público conforme recurso | descoberto; não presumido como API estável; sem conector homologado |
| SIA/SUS | endpoint documentado no Swagger DEMAS e arquivos DATASUS/TabNet | agregado público conforme recurso | descoberto; sem conector homologado |
| SIM | [dataset oficial](https://dadosabertos.saude.gov.br/dataset/sim) e ZIP anual | dados abertos anonimizados; atribuição ao MS | **integrada** para mortalidade não fetal agregada por município de residência, capítulo CID-10 ou faixa etária ampla |
| SINASC | [dataset oficial](https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc) e ZIP anual | dados abertos do SUS; atribuição ao MS | **integrada** para nascidos vivos de 2024 agregados por município de residência |
| SISAB | portal e relatórios e-Gestor APS | acesso e granularidade variam | restrito/relatório; não integrado |
| SIOPS | [downloads oficiais do FNS](https://portalfns.saude.gov.br/siops/siops-downloads/), ZIP/CSV municipal | dados fiscais públicos | **integrada** para o fechamento de 2025 (6º bimestre), preservando fonte, subfunção, natureza e fase contábil |
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

## CNES Hospitais e Leitos homologado

- Catálogo: `https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos`.
- Artefato: `https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2026.zip`.
- Observado em 22/10/2026: 4.914.199 bytes, CSV CP1252 de 21.631.614 bytes e SHA-256 `9e36112332b486a265890ad5327e0c7ba86a5d4ed000ece455f12838739d9157`.
- Competência publicada: setembro de 2026. O conector escolhe a maior `COMP`, valida o schema e publica somente CNES, nome institucional, tipo, gestão e totais existentes/SUS.
- E-mail, telefone, endereço e motivo textual de desabilitação não são persistidos. Leito cadastrado não significa vaga disponível ou ocupação em tempo real.

| Município | Estabelecimentos hospitalares | Leitos existentes | Leitos SUS |
|---|---:|---:|---:|
| Ribeirão Preto/SP (3543402) | 18 | 2.555 | 1.609 |
| Campinas/SP (3509502) | 26 | 3.473 | 1.638 |
| São Paulo/SP (3550308) | 233 | 37.437 | 18.069 |

## SINASC 2024 homologado

- Catálogo: `https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc`.
- Artefato: `https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINASC/csv/SINASC_2024_csv.zip`.
- Observado em 22/10/2026: 92.289.354 bytes, CSV Latin-1 de 561.812.933 bytes e SHA-256 `27e55de6359e1b1914301dc1d752d78e9535a7a52cc0640931dd94876aca6027`.
- O conector lê em streaming, conta por `CODMUNRES`, valida `DTNASC`, remove o arquivo temporário e nunca persiste registros individuais. Contagens de 1 a 4 são suprimidas; ausência permanece indisponível.

| Município | Nascidos vivos por residência, 2024 |
|---|---:|
| Ribeirão Preto/SP (3543402) | 7.020 |
| Campinas/SP (3509502) | 11.465 |
| São Paulo/SP (3550308) | 120.789 |

## Limitações verificadas

O host da API Dados Abertos do Ministério da Saúde apresentou reset/erro de gateway para chamadas diretas a partir do ambiente de execução. Arquivos oficiais estáveis permitiram homologar leitos, SINASC e SIOPS sem presumir que o Swagger é uma API operacional. SIA/SUS, SIH/SUS, serviços CNES, SISAB, ANS e conjuntos epidemiológicos adicionais ficam explicitamente indisponíveis na interface, nunca com valor zero.

Em 23/10/2026, tentativas `HEAD` e `GET` ao host oficial `ftp.datasus.gov.br`, inclusive para o caminho esperado `SIHSUS/200801_/Dados/RDSP2501.dbc`, expiraram por timeout de conexão neste ambiente. Sem baixar o DBC não foi possível validar hash, dicionário, período ou três amostras; por isso SIA/SIH não foram promovidos a integração apenas com base no padrão nominal dos arquivos.

## SIOPS municipal 2025 homologado

- Página oficial: `https://portalfns.saude.gov.br/siops/siops-downloads/`.
- Recurso: ZIP “Despesas por Fonte/Subfunção/Natureza Municipais 2025 — 6º Bimestre”, publicado pelo FNS em 21/07/2026.
- Observado em 23/10/2026: 64.105.064 bytes compactados, CSV UTF-8 de 1.878.084.870 bytes e SHA-256 `67723683052e6dca7b344c8b99c7243d3791829b550b8de3a534442dbaaa6c5d`.
- A carga controlada validou e publicou 6.013 linhas para Ribeirão Preto, Campinas e São Paulo. Valores usam `Decimal`; o ZIP temporário é removido após o processamento.
- O 6º bimestre é acumulado anual. Dotação inicial/atualizada, empenhada, liquidada, paga e restos a pagar são fases distintas e nunca são somadas entre si.

Reconciliação do nível total (`3.0.00.00.00.00` + `4.0.00.00.00.00`) diretamente no CSV:

| Município | Dotação atualizada | Empenhada | Liquidada | Paga |
|---|---:|---:|---:|---:|
| Ribeirão Preto/SP (3543402) | R$ 1.190.385.069,88 | R$ 1.125.539.705,55 | R$ 1.071.570.767,14 | R$ 1.031.794.155,24 |
| Campinas/SP (3509502) | R$ 2.564.706.611,08 | R$ 2.341.398.894,58 | R$ 2.286.956.653,97 | R$ 2.223.012.417,95 |
| São Paulo/SP (3550308) | R$ 25.625.569.084,01 | R$ 25.173.757.629,24 | R$ 24.099.774.787,65 | R$ 24.080.276.794,75 |
