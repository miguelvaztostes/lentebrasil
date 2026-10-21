# Relatório de entrega e validação

Data da validação: 09/10/2026  
Município: Ribeirão Preto/SP (`3543402`)  
Escopo: MVP funcional, com fontes reais e sem dados simulados

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
