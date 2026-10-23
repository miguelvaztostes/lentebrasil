# Lente Ribeirão — plano de implementação

Atualizado em 09/10/2026. Município inicial: Ribeirão Preto/SP (`3543402`).

> Em 20/10/2026 foi adicionada uma fundação nacional compatível, descrita em
> `NACIONALIZACAO_BASELINE.md` e `CATALOGO_NACIONAL.md`. O MVP municipal e seus coletores
> continuam operacionais; candidatos nacionais não são tratados como integrações homologadas.

## Objetivo e limites

O Lente Ribeirão é um observatório cívico independente. Não é um sistema oficial da Prefeitura, da Câmara, do Instituto Ribeirão 2030 ou do Lente Brasil. O MVP publica apenas dados agregados obtidos de fontes oficiais verificadas, sempre com período, unidade, método, data de coleta e ligação para a fonte.

Não fazem parte desta entrega: notas ou rankings de agentes públicos, notícias/NLP, votações legislativas, associação automática às metas 2030 e comparações entre municípios. Esses módulos permanecem explicitamente em preparação.

## Auditoria do repositório

O diretório de trabalho estava vazio em 09/10/2026, contendo apenas as pastas geradas `work/` e `outputs/`. Não havia código nem repositório Git a preservar. A implementação parte, portanto, de um monorepo novo e usa os SVGs fornecidos pelo usuário como identidade visual.

## Arquitetura do MVP

```text
Fontes oficiais (IBGE, Siconfi, CNES)
        │
        ▼
adaptadores Python → validação → snapshot ou hash/URL → upsert idempotente
        │
        ▼
PostgreSQL 16 → FastAPI /api/v1 → Next.js responsivo
        ▲                 │
scheduler                 └── JSON, CSV, OpenAPI, health/readiness
```

- `apps/api`: FastAPI, Pydantic 2, SQLAlchemy 2 e Alembic.
- `apps/web`: Next.js, TypeScript, Tailwind e Recharts.
- `workers/ingestion`: contrato `SourceAdapter`, CLI e agendador.
- `infra`: Caddy de produção e scripts de backup/restauração.
- `data/raw`: volume para snapshots permitidos; o conteúdo bruto não entra no Git.
- `docs`: inventário, dicionário e decisões operacionais.

O banco armazena timestamps em UTC. A apresentação usa `pt-BR` e `America/Sao_Paulo`. O PostgreSQL não é publicado externamente por padrão na composição de produção.

## Fases

### Fase A — inventário e blueprint

1. Verificar URL, status HTTP, formato, licença/termos e evidência de cada fonte.
2. Registrar `confirmed`, `pending`, `unavailable`, `requires_manual_import` ou `restricted` em `SOURCES.md`.
3. Congelar o contrato de dados mínimo em `DATA_DICTIONARY.md`.

Critério de saída: três documentos criados e pelo menos uma fonte com resposta de dados reais comprovada.

### Fase B — vertical completa

1. Subir PostgreSQL, API, web e worker com Docker Compose.
2. Aplicar migrações e catálogo inicial.
3. Ingerir a série de população estimada do IBGE/SIDRA para `3543402`.
4. Expor o resultado em JSON/CSV e apresentá-lo na página inicial e na página do indicador.

Critério de saída: um valor visível pode ser rastreado até URL, snapshot/hash, período, unidade e execução de ingestão.

### Fase C — expansão de dados

1. Integrar RREO/Siconfi mantendo receita, dotação, empenho, liquidação e pagamento como indicadores distintos.
2. Integrar agregados atuais do CNES sem armazenar dados pessoais ou contatos do arquivo de origem.
3. Manter IDEB e portal municipal em importação supervisionada até que o arquivo estruturado e seu contrato sejam comprovados.

Critério de saída: falhas de uma fonte não derrubam a API ou o frontend; o último dado validado é servido com estado de atualização.

### Fase D — confiabilidade e operação

1. Testar parsers, zero versus nulo, idempotência, revisões e separação das fases fiscais.
2. Executar lint, typecheck, build e testes de integração no PostgreSQL.
3. Documentar backup/restauração, deploy e troubleshooting.
4. Configurar CI e healthchecks.

## Decisões e riscos

- O snapshot IBGE/Siconfi é persistido porque contém somente dados agregados. Para CNES, o MVP mantém hash, cabeçalhos e URL canônica e persiste somente contagens agregadas, pois o arquivo contém dados de contato de estabelecimentos.
- O Siconfi declara limite de uma requisição por segundo; o adaptador respeita esse limite e usa apenas o Anexo 01 do RREO.
- O ano da população do cadastro de entes do Siconfi não deve substituir o indicador populacional do IBGE; o campo é apenas metadado da entrega fiscal.
- Um valor alterado para a mesma chave lógica cria nova revisão; uma repetição idêntica não cria duplicata.
- Ausência de dado é `NULL`/`unavailable`, nunca zero.
- O frontend deve tolerar API temporariamente indisponível com mensagem explícita e sem números de fallback.
- Censo Escolar 2024 e Ideb municipal 2025 foram homologados na Onda 3A; novas edições só entram após validação explícita de schema e reconciliação.

## Etapa 3A — educação

- Modelo histórico separado para escola, matrículas e métricas; publicação por release atômico.
- Conectores versionados do Censo Escolar 2024, Ideb 2025, Saeb 2023 e PNAE 2024 com staging,
  hash, limites de arquivo compactado/descompactado, whitelist de host/schema e seleção municipal.
- API educacional não aciona provedores externos e preserva ausência/supressão.
- Dashboard municipal e detalhe público de escola não armazenam nem exibem dados pessoais.
- Saeb lê o XLSB municipal do RAR oficial em streaming e publica apenas médias agregadas;
  PNAE publica alunos considerados e valores previstos por ação, sem inferir pagamento.
- Próximo backlog verificável: PDDE, PNATE, Obras e indicadores anuais, cada qual como recurso
  independente; não ampliar antes de homologar grão, licença e reconciliação.

## Ordem de execução

## Etapa 3C — saúde municipal

- Modelo versionado para estabelecimentos, leitos, serviços, produção e epidemiologia, sempre
  ligado ao snapshot e ao documento oficial.
- SIM 2024 processado em streaming e publicado apenas como agregados por residência. Causa e
  idade não são cruzadas; células de 1 a 4 são suprimidas e o microdado temporário é removido.
- Hospitais/leitos CNES de setembro de 2026 e nascidos vivos SINASC 2024 foram homologados em
  arquivos oficiais, carregados com versão/hash e reconciliados em três municípios.
- API e página `/municipios/[ibgeCode]/saude` distinguem cadastro CNES, capacidade cadastrada,
  produção assistencial, mortalidade e gasto municipal; ausência nunca aparece como zero.
- SIA/SUS, SIH/SUS, serviços CNES, SISAB, SIOPS, ANS e epidemiologia adicional seguem
  como candidatos até que recurso, schema, direito, período e semântica sejam homologados.
- Próximo passo: homologar serviços CNES e somente depois SIA/SIH agregados,
  com três amostras por conjunto e reconciliação contra o portal oficial.

## Etapa 3B — transparência e contratações

- PNCP: janela máxima de 31 dias, paginação por modalidade/município para contratações e por CNPJ de órgão homologado para contratos; checkpoint guarda janela, atualização, chave e páginas.
- Siconfi: RREO existente preservado; RGF e DCA adicionados como linhas versionadas, respeitando 1 requisição/s e sem misturar fases, períodos ou fontes.
- TCE-SP: receitas 2025 são processadas em streaming de ZIP/CSV e por rubrica. Despesas usam a
  API oficial por município/mês, são agregadas por evento contábil antes do snapshot e descartam
  fornecedor/identificador em memória. Empenho, liquidação, pagamento, reforço e anulação não se
  compensam automaticamente. Licitações TCE-SP continuam fora até conciliação segura com PNCP.
- CGU permanece bloqueado sem token autorizado. FNDE/PNAE continua educacional e não vira transferência paga. Portais municipais sem exportação permanecem manuais.
- API e dashboard são consultivos; não produzem acusação ou escore de irregularidade.

```text
docs → migração/catálogo → API → adaptador IBGE → UI → Siconfi/CNES
     → testes → observabilidade → backup/restore → empacotamento
```

## Etapa 1 — fundação multicípio concluída em 20/10/2026

- A API de Localidades alimenta UFs, municípios atuais, versões de nomes e crosswalks explícitos.
- IBGE/SIDRA recebe lotes municipais, intervalo de anos e versão de recurso.
- Siconfi recebe município, exercício, período e anexo, com teto de chamadas e 1 req/s.
- CNES baixa o ZIP nacional uma vez por versão, processa o CSV em streaming e agrega somente os
  municípios selecionados; o arquivo temporário é removido após o parser.
- O scheduler usa jobs PostgreSQL com lock, checkpoint, último sucesso, retry e janela explícita.
- Filtros territoriais, período e escopo são executados em SQL, com contagem antes da paginação.
- O frontend continua em Ribeirão por padrão, mas seus componentes aceitam código municipal.

A busca territorial completa e as rotas públicas nacionais continuam reservadas para a etapa 2.

## Etapa 2 — catálogo público e busca territorial concluída em 21/10/2026

- O portal passa a se chamar Lente Brasil; Lente Ribeirão permanece como visão territorial de
  Ribeirão Preto e não como aplicação separada.
- As rotas `/brasil`, `/estados/[uf]`, `/municipios/[ibgeCode]`, visão setorial, `/buscar` e
  detalhes de fontes permitem navegação anônima e responsiva.
- O inventário de 165 candidatos é importado idempotentemente ao iniciar a API. Somente os IDs
  explicitamente reconciliados a SIDRA, CNES e Siconfi apontam para conectores homologados.
- Busca por texto usa normalização de acentos no PostgreSQL e índices GIN/trigrama; filtros,
  ordenação, contagem e paginação permanecem no banco.
- “Dados publicados” depende de observações existentes. Um dataset cadastrado ou uma fonte
  descoberta não produz gráfico, número ou cobertura presumida.
- Filtros do frontend são codificados na URL; estados de carregamento, erro e vazio mantêm a
  distinção entre ausência e zero.

