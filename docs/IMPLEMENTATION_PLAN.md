# Lente Ribeirão — plano de implementação

Atualizado em 09/10/2026. Município inicial: Ribeirão Preto/SP (`3543402`).

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
- IDEB 2025 aparece no portal do Inep, mas o link direto do arquivo municipal é gerado na página e precisa de validação de parser antes da automação.

## Ordem de execução

```text
docs → migração/catálogo → API → adaptador IBGE → UI → Siconfi/CNES
     → testes → observabilidade → backup/restore → empacotamento
```

