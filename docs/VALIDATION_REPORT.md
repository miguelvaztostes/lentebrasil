# Relatório de entrega e validação

Data da validação: 09/10/2026  
Município: Ribeirão Preto/SP (`3543402`)  
Escopo: MVP funcional, com fontes reais e sem dados simulados

## Onda setorial — 24/10/2026

- SIDRA/PIB: 63 fatos validados para Ribeirão Preto, Campinas e São Paulo, 2021–2023; zero
  rejeições. PIB total 2023 foi conciliado nas três amostras e VAB indisponível em 2022/2023
  permaneceu nulo.
- Novo CAGED: arquivo 7z de 44.879.645 bytes e TXT de 382.538.259 bytes processado linha a linha;
  59 agregados município/seção, zero rejeições e saldo conciliado nas três amostras.
- SENATRAN: 66 fatos (22 por município), zero rejeições; cada total municipal confere com a soma
  dos tipos. Uma divergência de nome local em Campinas foi corrigida pela sincronização oficial
  do IBGE, sem fuzzy match.
- Testes cobrem schema, unidade monetária, ausência versus zero, descarte do 7z, conciliação
  CAGED/SENATRAN, rotas somente leitura, paginação e CSV.
- Validação final em PostgreSQL isolado e migrado do zero: `50 passed`, com uma advertência de
  depreciação Starlette/httpx já existente; testes de conteúdo e typecheck web aprovados, e build
  de produção Next.js concluído com todas as 18 rotas.

## Etapa A — auditoria e estrutura base

### Componentes concluídos

- Auditoria integral das especificações fornecidas e do diretório de trabalho, que não continha aplicação anterior.
- Monorepo organizado em `apps/api`, `apps/web`, `workers/ingestion`, `infra`, `docs` e `data/raw`.
- Inventário versionado de fontes, estados de disponibilidade, dicionário de dados e plano de implementação.
- Docker Compose para PostgreSQL 16, FastAPI, Next.js, coletor agendado e Caddy opcional.
- Identidade visual aplicada a partir dos dois SVGs fornecidos pelo usuário.

### Fontes verificadas

- IBGE Localidades e SIDRA: respostas JSON válidas para Ribeirão Preto.
- Tesouro Nacional/Siconfi: contrato Swagger e RREO Anexo 01 válidos.
- Ministério da Saúde/CNES: recurso ZIP/CSV oficial válido.
- INEP/IDEB, portal de transparência municipal, Câmara Municipal e Instituto Ribeirão 2030: páginas oficiais auditadas; os estados e limites estão em `docs/SOURCES.md`.

### Impedimentos registrados

- A página do IDEB confirma arquivos municipais da série 2005–2025, mas o link direto do pacote não apareceu no HTML estático auditado. O dataset permanece em `requires_manual_import`.
- A página inicial do orçamento municipal expôs PDFs e consultas, mas nenhum CSV/XLSX/JSON tabular confirmado. O recorte fiscal usa Siconfi.
- Nenhuma API estruturada de votações nominais da Câmara foi presumida. O módulo legislativo permanece pendente.

## Etapa B — primeira integração ponta a ponta

### Componentes concluídos

- Migração Alembic com catálogo, observações versionadas, snapshots, execuções e ocorrências de qualidade.
- Adaptador IBGE/SIDRA com validação geográfica, schema, unidade, período, hash e persistência do bruto agregado.
- Upsert idempotente: repetição idêntica não cria observação nova; mudança cria revisão histórica.
- API JSON, CSV e OpenAPI.
- Home e página do indicador com cartão, série, gráfico, tabela, metodologia, limitações, URL oficial, coleta e SHA-256.

### Evidência publicada

- População estimada de `734.538` pessoas, referência 2026, conforme SIDRA tabela 6579/variável 9324.
- A reexecução real do coletor manteve `10` observações antes e depois, confirmando idempotência.

## Etapa C — expansão das integrações

### Componentes concluídos

- Siconfi/RREO para 2022–2025, 6º bimestre: receita realizada, despesa empenhada, liquidada e paga mantidas como séries independentes.
- CNES agregado: três indicadores calculados para o código municipal `354340`, sem copiar nomes, endereços, telefones, e-mails, CNPJ ou identificadores de estabelecimentos para a base analítica.
- Execução por fonte isolada: uma falha não impede as demais; o último valor validado continua disponível.
- Agendador diário configurável, limite mínimo de uma hora, logs JSON e estado público dos pipelines.

### Evidência publicada

- Receita realizada 2025: `R$ 4.819.300.021,27`.
- Despesa paga 2025: `R$ 4.272.791.553,92`.
- Cadastros CNES sem motivo de desabilitação no arquivo de 09/10/2026: `2.257`.
- Última execução do agendador: IBGE `10/10`, Siconfi `16/16` e CNES `3/3`, todas com status `success` e nenhuma rejeição.

### Limitação técnica encontrada e tratada

O arquivo CNES observado contém bytes Latin-1/Windows-1252 sem charset declarado. A primeira leitura UTF-8 falhou de forma segura, sem publicar dados parciais. O parser passou a usar Latin-1 estrito e valida o cabeçalho antes de agregar.

## Etapa D — confiabilidade, operação e apresentação

### Componentes concluídos

- Healthcheck, readiness, rotação de logs, estado de integrações e mensagens explícitas para ausência de dados.
- Scripts de backup e restauração com checksum SHA-256.
- Workflow de CI com PostgreSQL, lint, testes, typecheck, build e imagens Docker.
- Frontend responsivo com dashboards de desenvolvimento, transparência e saúde; catálogo, fontes, metodologia, dados abertos, sobre e páginas de módulos futuros claramente sinalizadas.
- Proxy interno Next.js corrigido para usar o hostname Docker da API durante a construção da imagem.
- Dependências principais atualizadas e fixadas; instalação frontend reproduzível com `npm ci`.

### Testes executados

| Verificação | Resultado |
|---|---|
| `docker compose config --quiet` | aprovado |
| Pytest unitário/API/PostgreSQL | `6 passed`; um aviso de depreciação no adaptador de testes do Starlette |
| Ruff lint | aprovado |
| Ruff format check | `20 files already formatted` |
| Next.js produção + TypeScript | compilação aprovada, 16 rotas geradas |
| Teste de conteúdo frontend | `1 passed` |
| Auditoria npm de dependências de produção | 0 vulnerabilidades; 8 alertas permanecem apenas no ferramental de desenvolvimento do Tailwind 3 |
| Smoke test API | readiness `ready`, quatro cartões reais retornados |
| Smoke test visual | home e detalhe do indicador confirmados no navegador, sem erros de console |
| Backup/restauração | checksum válido; restauração isolada confirmou 29 observações, 12 snapshots e 8 execuções no instante do backup |

O banco temporário usado no teste de restauração foi removido após a conferência. O backup de teste permanece somente em `work/`, fora do Git e do pacote de entrega.

## Estado operacional ao encerrar

- `db`, `api`, `web` e `ingestion` estão em execução; `db`, `api` e `web` estão saudáveis.
- Aplicação: `http://localhost:3000`
- API: `http://localhost:8000/api/v1`
- OpenAPI: `http://localhost:8000/api/docs`
- O navegador da aplicação foi deixado aberto na home já carregada com os quatro indicadores reais.

## Próximos passos recomendados

1. Obter e validar, com revisão humana, o arquivo municipal do IDEB antes de automatizar a educação.
2. Formalizar os termos/licenças específicos do recurso CNES e das páginas municipais antes de publicação pública permanente.
3. Executar a restauração periodicamente em ambiente separado e enviar backups criptografados para armazenamento externo.
4. Configurar domínio, TLS, segredos e observabilidade externa antes do deploy público.
5. Tratar os módulos Legislativo, Metas 2030 e Notícias como novas etapas, sem misturá-los à confiabilidade do MVP atual.

## Fundação nacional — 20/10/2026

- Banco novo: `0001 → 0002` aprovado.
- Cópia descartável do banco legado: 32 observações antes e depois de `0001 → 0002`.
- Rollback seguro na cópia: `0002 → 0001 → 0002`, sempre com 32 observações.
- Importador candidato executado duas vezes em teste: 2 provedores, 2 recursos, 2 datasets e
  3 vínculos, sem duplicação; todos os recursos permaneceram `not_implemented` e os datasets
  `not_published`.
- API: health, municípios, fontes, datasets, indicadores e observações exercitados após a
  migração.
- Pytest: `10 passed`, com o mesmo aviso de depreciação do adaptador Starlette.
- Ruff lint e format check: aprovados, 23 arquivos formatados.
- Frontend: `npm test` (1 aprovado), typecheck e build de produção (16 rotas) aprovados.
- Compose validado; imagens `api` e `web` construídas.

### Referências recebidas após a fundação

O PDF de 11 páginas, o XLSX de 9 abas e o JSON foram lidos integralmente. A comparação comprovou
165 fontes iguais entre a aba mestre e o JSON, 16 setores, 95 indicadores, IDs sequenciais sem
duplicatas e referências de indicadores válidas. O validador aceita o arquivo real sem modificar seu
conteúdo e emite dois avisos para URLs FTP, que permanecem metadados não executáveis. O importador
foi adaptado para preservar os vínculos propostos entre fontes e indicadores. Em banco descartável,
duas execuções mantiveram uma única importação: 68 provedores, 121 recursos, 165 datasets, 165
entradas e 99 vínculos. Os candidatos permaneceram `not_implemented`/`not_published`; quatro
variações nominais de provedor foram registradas como discrepâncias.
Também foi validado o ciclo `0003 → 0002 → 0003`; a reimportação do mesmo arquivo restaurou os
99 vínculos de forma idempotente, sem criar datasets nem observações adicionais.

## Etapa 1 multicípio — 20/10/2026

### Dados oficiais demonstrados em banco isolado

| Município | População 2025 | Receita realizada 2025 | Despesa paga 2025 | CNES cadastrados | CNES sem motivo de desabilitação |
|---|---:|---:|---:|---:|---:|
| Ribeirão Preto (`3543402`) | 731.639 | R$ 4.819.300.021,27 | R$ 4.272.791.553,92 | 4.362 | 2.250 |
| Campinas (`3509502`) | 1.187.974 | R$ 9.987.144.035,09 | R$ 9.051.973.374,98 | 5.073 | 3.798 |
| São Paulo (`3550308`) | 11.904.961 | R$ 112.335.533.909,13 | R$ 105.887.210.349,69 | 43.837 | 29.679 |

População: SIDRA 6579/9324. Valores fiscais: Siconfi RREO Anexo 01, 6º bimestre. CNES:
arquivo nacional com referência de 20/10/2026. Valores são evidência desta execução isolada e
continuam sujeitos a revisões das fontes.

### Verificações

- Geografia oficial: 27 UFs, 5.571 municípios e 11.136 novos mapeamentos nesta carga; o total de
  mapeamentos também inclui os dois vínculos legados já existentes.
- Coletores reais: IBGE `6/6`, Siconfi `12/12` e CNES `9/9`, sem rejeições.
- Reexecução CNES: mesma soma SHA-256, zero itens reprocessados e nenhuma nova observação. Um
  recorte posterior de Santos (`3548500`) gerou três indicadores a partir do agregado seguro da
  mesma versão, sem baixar novamente o ZIP nacional.
- CNES: 14 geografias `53xxxx` sem crosswalk municipal registradas como aviso de qualidade.
- API: busca `uf=SP&q=Campinas` e resumos de `3543402`, `3509502` e `3550308` responderam 200.
- Paginação SQL: fixture com 2.105 observações retornou contagem 2.105, página de 100 itens no
  offset 2.000 e cinco itens no offset 2.100.
- Migração: `0003 → 0004 → 0003 → 0004`; 27 observações reais permaneceram antes e depois.
- Pytest: 18 testes aprovados, com um aviso conhecido de depreciação do TestClient do Starlette.

O banco de comprovação é descartável e não faz parte da aplicação publicada. A busca nacional no
frontend permanece fora desta etapa; Ribeirão segue como padrão compatível.

## Etapa 2 — catálogo nacional e busca territorial — 21/10/2026

- Inventário publicado: 165 entradas, 68 provedores, 121 recursos deduplicados, 16 setores e 95
  indicadores propostos. Candidatos não geraram observações fictícias.
- Rotas territoriais: Brasil, 27 UFs, perfis municipais, setores, busca, catálogo e detalhe de
  fonte; Ribeirão Preto continua destacado em `/municipios/3543402`.
- API: busca facetada, municípios sem acentos, resumo municipal, detalhe de fonte e cobertura de
  dataset responderam 200 no banco descartável.
- PostgreSQL: migração `0004 → 0005 → 0004 → 0005` preservou as 165 entradas. `EXPLAIN` confirmou
  `Bitmap Index Scan` nos índices `ix_municipalities_name_search` e
  `ix_catalog_entries_indicator_search`.
- Backend: 21 testes aprovados; permanece um aviso de depreciação do TestClient do Starlette.
- Frontend: teste de conteúdo, typecheck, build de produção com 22 rotas e smoke E2E das rotas de
  Ribeirão Preto, Campinas, São Paulo, busca compartilhável e detalhe de fonte aprovados.
- O banco e os dados usados na comprovação são descartáveis e não entram no Git.

## Etapa 3A — educação — 21/10/2026

- Artefatos oficiais verificados: Censo Escolar 2024 ZIP/CSV e Ideb municipal 2025 ZIP/XLSX.
- Schemas observados: 426 colunas no Censo; 14.547 linhas e 133 colunas no Ideb municipal de anos
  iniciais. Os hashes completos constam em `EDUCATION_SOURCES.md`.
- O conector rejeita mudança de cabeçalho, identidade inválida, ZIP inseguro, host/redirecionamento
  não permitido e lote vazio; marcadores de supressão não viram zero.
- Testes unitários cobrem CP1252/CSV, identificadores, whitelist de campos, total de matrículas,
  XLSX, rede e supressão. O teste PostgreSQL cobre rollback de release.
- Banco descartável limpo: 25 testes aprovados. Ciclo Alembic
  `0001 → 0006 → 0001 → 0006` aprovado e 21/21 entradas educacionais receberam decisão.
- Leitura real para Ribeirão Preto, Campinas e São Paulo: 9.228 escolas e 45 registros de métricas.
  Para Ribeirão Preto, a publicação descartável materializou 464 versões de escola, 4.176 fatos de
  matrícula/etapa e 15 métricas; a segunda carga do mesmo hash não aumentou nenhuma contagem.
- API no banco descartável: resumo municipal, escolas filtradas por rede e métricas Ideb responderam
  200, sempre com dataset, release, período, URL e licença/status na proveniência.
- Frontend: teste de conteúdo e typecheck aprovados; build de produção aprovado com 23 rotas,
  incluindo `/escolas/[inepCode]` e a visão `/municipios/[ibgeCode]/educacao`.
- Limitação ambiental: o download direto dentro do container encerrou o TLS por cadeia de
  certificado local (`CERTIFICATE_VERIFY_FAILED`). Os mesmos artefatos oficiais, baixados e
  conferidos fora do container, foram processados integralmente. O conector não desabilita a
  validação TLS; a imagem de implantação precisa receber a cadeia de CA compatível.

## Extensão da Etapa 3A — Saeb e FNDE/PNAE — 21/10/2026

- Saeb 2023: RAR oficial de 8.413.247 bytes, SHA-256
  `acf3066b192298574a4a7ceaacd83b46d05193062077dcc66ffdb0da6f61b113`; o XLSB municipal possui
  69.053 registros e 113 colunas. Foram selecionadas 60 métricas reais para Campinas, Ribeirão
  Preto e São Paulo.
- PNAE 2024: XLSX oficial de 920.689 bytes, SHA-256
  `fc5eecb6d23bddf186301105a66c1f134c9892150e2889641f8f9a41ff194c5c`; foram selecionadas 36
  métricas reais para os três municípios. Em Ribeirão Preto, os seis valores previstos somam
  R$ 7.680.903,13; o portal não os apresenta como pagamentos ou execução.
- Banco descartável: migração `0001 → 0007`, ciclo `0007 → 0006 → 0007` e importação do catálogo
  aprovados. Saeb publicou 18 métricas e PNAE 12 para Ribeirão Preto; repetir cada snapshot não
  alterou as contagens.
- API: os filtros por dataset de Saeb e PNAE e o resumo educacional combinado responderam 200,
  sempre com release, URL e proveniência. O dashboard separa Censo, Ideb, Saeb e PNAE e exibe as
  ressalvas metodológicas.
- Validação final: 28 testes backend aprovados em PostgreSQL limpo, Ruff aprovado em 39 arquivos,
  teste de conteúdo aprovado e build de produção Next.js concluído com 23 rotas.
- PDDE, PNATE e Obras permanecem em revisão manual; nenhum endpoint ou número foi presumido.
- Limitação ambiental preservada: PNAE respondeu no container, mas o host do INEP falhou por
  cadeia de certificado local. O RAR verificado no host foi processado pelo mesmo parser no
  container, com TLS obrigatório no conector.

## Etapa 3B — transparência e contratações — 22/10/2026

- Auditoria real: PNCP modalidade 8/Ribeirão retornou 58 contratações em duas páginas; RGF
  2025/3 retornou 165 linhas; DCA 2024 retornou 172; TCE-SP selecionou 3.286 linhas de receita.
- Três amostras TCE-SP foram reconciliadas por ID, rubrica e valor. O ZIP de 35.462.775 bytes
  reproduziu SHA-256 `16df083d2088127108957a028f6c824265813c74542f528108526b44a392b84b`.
- Carga descartável PostgreSQL: 58 contratações, 14 contratos (CNPJ municipal homologado), 165
  linhas RGF, 172 DCA e 3.286 receitas. Reexecutar PNCP manteve 58 fatos; snapshots preservaram
  respostas novas da fonte sem duplicar a entidade lógica.
- API demonstrada com HTTP 200 e paginação SQL: contratações `58`, contratos `14`, RGF `165`,
  receitas TCE-SP `3286`, transferências `0` (indisponível, não zero). CSV controlado respondeu
  com limite e proveniência.
- Alembic em PostgreSQL 16 limpo: `0001 → 0008 → 0007 → 0008` aprovado. O banco local existente
  foi atualizado de `0006 → 0008`, mantendo catálogo e dados anteriores.
- Backend: 31 testes aprovados no PostgreSQL limpo. Unidade cobre paginação/checkpoint PNCP,
  `Decimal`, schema, três amostras e ausência; integração cobre idempotência/revisões existentes.
- Frontend: teste de conteúdo, TypeScript e build Next.js 16.4.2 de produção aprovados; 23 rotas,
  incluindo `/transparencia` e a visão financeira municipal. A atualização corretiva de 16.4.0
  para 16.4.2 removeu o alerta de segurança da versão e o `npm audit --omit=dev` terminou sem
  vulnerabilidades de produção.
- Docker: imagens de API, worker e web construídas; serviços locais ficaram saudáveis após
  recriação. Ruff global e verificação de formatação dos arquivos alterados foram aprovados.
- CGU não foi executado porque nenhum token autorizado foi fornecido. Na conclusão original,
  despesas TCE-SP, atas/PCA PNCP e portais municipais ainda estavam sem aceite; a extensão abaixo
  substitui o estado das despesas após validar a API municipal.

## Extensão da Etapa 3B — visão geral e despesas TCE-SP — 22/10/2026

- A API municipal TCE-SP, embora documentada textualmente até 2019, respondeu HTTP 200 para
  Ribeirão Preto em janeiro/2025: 7.559 lançamentos e cinco eventos contábeis.
- A carga agregou antes da persistência 3.945 empenhos, 2.062 liquidações, 1.417 pagamentos,
  20 reforços e 115 anulações. Os cinco totais usam `Decimal` e permanecem separados.
- Nomes e identificadores de fornecedores foram descartados em memória. O snapshot contém cinco
  agregados, contagens e hash SHA-256 da resposta upstream; busca no volume confirmou ausência
  dos campos pessoais. Reexecução manteve cinco fatos, revisão 1 e um snapshot.
- A migração `0009` cadastra `tcesp_expenses`; o catálogo liga LNT-0039/LNT-0100 ao conector.
  A API `/transparency/overview` expõe receita, fases de despesa e contagens PNCP com ausência
  explícita e metodologia sem compensação automática.
- Backend: 33 testes aprovados no PostgreSQL limpo; os testes novos verificam agregação, precisão,
  ausência sem conversão em zero e descarte de fornecedor. A página pública passou a explicar
  sua cobertura e as limitações.
- Ruff aprovou todos os arquivos Python alterados nesta extensão. A varredura integral ainda aponta
  nove ocorrências preexistentes em `base.py`, educação, geografia e scheduler; elas não foram
  incluídas neste diff. O build de produção validou TypeScript e as 23 rotas Next.js, e o teste de
  conteúdo do frontend foi aprovado.
- Atas PNCP foram verificadas com 39 registros no recorte municipal de 01–22/10/2026; PCA
  respondeu 204. Permanecem complementos fora dos totais, assim como CGU sem token e portal
  municipal sem exportação homologada.

## Etapa 3C — saúde municipal — 22/10/2026

- O ZIP oficial definitivo do SIM 2024 foi validado com 98.076.266 bytes compactados,
  550.842.628 bytes descompactados e SHA-256
  `13db250c90908e85d1ef9fb9cd7caa08583fb1912108b0f3260605aca0e9b787`.
- Três amostras municipais foram reconciliadas: Ribeirão Preto 5.272 óbitos, Campinas 8.972 e
  São Paulo 87.438. As somas independentes por capítulo CID-10 e faixa etária coincidiram com o
  total de cada município.
- O conector não persiste o CSV: agrega em streaming por residência, remove o arquivo temporário,
  não transporta campos nominais e suprime contagens de 1 a 4.
- A API separa rede cadastrada, leitos cadastrados, produção, mortalidade e gastos. SIA/SIH
  permanecem explicitamente indisponíveis; a falha de acesso ao host DEMAS impediu validar
  respostas e schema, portanto a documentação Swagger foi tratada apenas como descoberta.
- Carga PostgreSQL descartável: 93 agregados, 31 por município; reexecução aceitou zero itens,
  manteve revisão 1, um snapshot e nenhum `storage_path` bruto. A API respondeu HTTP 200 para
  visão geral, paginação e CSV; Ribeirão Preto retornou o total reconciliado de 5.272.
- Migração limpa e ciclo `0010 → 0009 → 0010` aprovados. Backend: 36 testes aprovados; Ruff e
  formatação globais aprovados após normalizar nove arquivos legados exigidos pela CI.
- Frontend: teste de conteúdo, TypeScript e build de produção Next.js aprovados; a rota dinâmica
  `/municipios/[ibgeCode]/[setor]` renderiza o painel de saúde quando `setor=saude`.

### Complemento homologado — leitos CNES e SINASC

- Migrações `0011` e `0012` aplicadas do zero em PostgreSQL 16, registrando fontes, datasets e
  decisões do catálogo com UUID nativo.
- O arquivo Hospitais e Leitos 2026 teve 4.914.199 bytes, SHA-256
  `9e36112332b486a265890ad5327e0c7ba86a5d4ed000ece455f12838739d9157` e competência máxima
  `202609`. A carga aceitou 277 hospitais nos três municípios e nenhuma rejeição.
- Reconciliação direta do CSV e do banco: Ribeirão Preto 18 hospitais/2.555 leitos/1.609 SUS;
  Campinas 26/3.473/1.638; São Paulo 233/37.437/18.069.
- O SINASC 2024 teve 92.289.354 bytes compactados, 561.812.933 bytes descompactados e SHA-256
  `27e55de6359e1b1914301dc1d752d78e9535a7a52cc0640931dd94876aca6027`. As três contagens por
  residência foram 7.020, 11.465 e 120.789, respectivamente.
- A repetição de cada carga manteve 277 estabelecimentos/leitos, três fatos SINASC e um snapshot
  por dataset. Os arquivos temporários não foram persistidos.
- A API real respondeu HTTP 200: `/health/overview` retornou 18 estabelecimentos, 2.555 leitos,
  1.609 leitos SUS e 7.020 nascidos vivos para Ribeirão Preto; `/health/beds` retornou paginação
  SQL com 18 linhas. A ausência de SIM no banco descartável permaneceu `null`, nunca zero.
- SIA/SUS, SIH/SUS e serviços CNES continuam sem conector homologado. O material Swagger
  não foi promovido a fonte operacional sem resposta/schema verificáveis.
- O ciclo de migração `0012 → 0010 → 0012` foi aprovado. A suíte completa passou com 39 testes;
  Ruff e verificação de formatação passaram. O frontend passou no teste de conteúdo, TypeScript e
  build de produção com 23 rotas Next.js.

### Complemento homologado — SIOPS municipal 2025 — 23/10/2026

- O ZIP/CSV oficial do 6º bimestre de 2025 respondeu HTTP 200, com 64.105.064 bytes,
  1.878.084.870 bytes descompactados e SHA-256
  `67723683052e6dca7b344c8b99c7243d3791829b550b8de3a534442dbaaa6c5d`.
- A validação real aceitou 6.013 linhas e nenhuma rejeição para Ribeirão Preto, Campinas e São
  Paulo. O mesmo recorte foi carregado no PostgreSQL da demo.
- As fases inicial, atualizada, empenhada, liquidada, paga e restos a pagar permanecem em linhas
  distintas. O painel destaca somente a fase paga e o endpoint permite consultar cada rubrica.
- Três totais pagos foram reconciliados diretamente do CSV: R$ 1.031.794.155,24,
  R$ 2.223.012.417,95 e R$ 24.080.276.794,75, respectivamente.
- A primeira validação detectou corretamente que `Cod_IBGE` era UF e que o município estava em
  `Cód.Município`; o mapeamento foi corrigido antes de qualquer publicação.
- SIA/SUS, SIH/SUS, serviços CNES, SISAB e ANS continuam sem conector homologado. Os arquivos
  DBC e relatórios existentes exigem conversor/dicionário e reconciliação próprios; essa lacuna
  não é apresentada como zero nem como cobertura disponível.
- Migração limpa, ciclo `0013 → 0012 → 0013`, Ruff, formatação e 41 testes em PostgreSQL 16
  descartável foram aprovados. O frontend passou no teste de conteúdo, TypeScript e build Next.js.

### Complemento homologado — produção DATASUS, serviços CNES e ANS — 23/10/2026

- A indisponibilidade anterior foi localizada no transporte: o servidor DATASUS não entregou os
  DBCs por HTTP/HTTPS, mas respondeu por FTP nativo em modo passivo. Foram homologados
  `RDSP2512.dbc` (SIH), as quatro partes `PASP2512[a-d].dbc` (SIA) e `SRSP2512.dbc`
  (serviços CNES). A ANS foi obtida por HTTPS em `tb_bb_2025-12.dbc`.
- A competência é dezembro/2025 e representa um mês, não o total anual. SIA usa município do
  estabelecimento executor e soma procedimentos/valores aprovados; SIH usa município do
  atendimento, conta autorizações e soma `VAL_TOT`. As fases e unidades não são combinadas.
- Carga controlada real para Ribeirão Preto, Campinas e São Paulo: 10.127 agregados SIA, 3.028
  agregados SIH, 48.806 cadastros de serviço/classificação CNES e três totais municipais ANS,
  sem itens rejeitados. Todos os fatos permaneceram na revisão 1.
- As três amostras foram conferidas por soma dos fatos de revisão corrente e pela resposta da API:

| Município | SIA procedimentos | SIA valor aprovado | SIH autorizações | SIH valor aprovado | Serviços CNES | Vínculos ANS |
|---|---:|---:|---:|---:|---:|---:|
| Ribeirão Preto/SP (3543402) | 3.201.139 | R$ 20.382.557,14 | 8.074 | R$ 17.476.536,06 | 2.803 | 588.466 |
| Campinas/SP (3509502) | 4.529.200 | R$ 23.290.160,06 | 6.507 | R$ 17.380.522,24 | 5.356 | 1.047.329 |
| São Paulo/SP (3550308) | 33.764.121 | R$ 180.770.793,51 | 57.638 | R$ 137.216.142,98 | 40.647 | 10.131.751 |

- O arquivo ANS mede vínculos, não pessoas únicas. `TP_VIGENCI` classifica a época de contratação
  do plano e não foi tratado como estado ativo/inativo. CNES mede cadastro, não disponibilidade
  real; 1.334, 2.573 e 22.175 cadastros de serviço/classificação, respectivamente, indicaram
  atendimento SUS.
- Os DBC/DBF foram removidos da área temporária após a agregação. Os campos individuais de SIA,
  SIH e os campos fiscais do CNES não foram persistidos. Um arquivo temporário preexistente do
  FNDE permaneceu intacto por não pertencer a esta etapa.
- SISAB foi reclassificado de “restrito” para relatório público, porém segue sem conector: a
  exportação depende de estado JSF e não há API ou artefato versionado estável homologado. A
  ausência continua indisponível, nunca zero.
- Na retomada de 24/10/2026, um checkpoint SIM persistido no volume coexistia com um banco sem
  os fatos correspondentes. O conector passou a aceitar `304 Not Modified` somente quando todos
  os municípios pedidos já têm fatos no banco; sem essa cobertura, baixa e recompõe o agregado.
  A recomposição publicou 93 linhas SIM, além de três linhas SINASC e 277 registros de leitos.
- Validação final: 45 testes aprovados em PostgreSQL 16 descartável; migração limpa até `0014` e
  ciclo `0014 → 0013 → 0014` aprovados; Ruff, formatação e `git diff --check` aprovados. O
  frontend passou no teste de conteúdo, TypeScript e build Next.js com 23 rotas. O audit de
  dependências de produção (`npm audit --omit=dev`) não encontrou vulnerabilidades.
