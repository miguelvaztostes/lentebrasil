# Lente Brasil

Portal público e independente para pesquisa territorial e catálogo nacional de fontes. O projeto
publica somente observações provenientes de integrações oficiais verificadas, com período,
unidade, metodologia, coleta e URL de origem. O Lente Ribeirão permanece como a visão destacada
de Ribeirão Preto/SP na mesma infraestrutura.

Não é um sistema oficial da Prefeitura, da Câmara, do Instituto Ribeirão 2030 ou do Lente Brasil.

## O que já funciona

- API pública FastAPI em `/api/v1` e documentação OpenAPI em `/api/docs`.
- PostgreSQL com migrações, catálogo, snapshots, revisões e auditoria de ingestão.
- Fundação nacional aditiva para geografia, provedores, recursos, cobertura e releases, sem
  retirar os contratos municipais.
- Next.js responsivo com página inicial, catálogo, séries, tabelas, fontes, metodologia e dados abertos.
- Busca sem acentos por município, fonte e tema, filtros persistidos na URL e perfis para qualquer
  município presente no diretório IBGE.
- Catálogo público com os 165 candidatos e estados separados de descoberta, conector, licença,
  cobertura e publicação.
- Coleta real da população estimada pelo IBGE/SIDRA.
- Coleta real do RREO/Siconfi, preservando receita, empenho, liquidação e pagamento.
- Coleta real e agregada do CNES, sem copiar nomes, contatos, endereços ou CNPJs para a base analítica.
- Pipeline multicípio para IBGE, Siconfi e CNES, com dimensão oficial de 27 UFs e 5.571
  municípios, crosswalks explícitos e histórico cadastral.
- Jobs persistidos no PostgreSQL com lock, checkpoint, retomada, retry e backfill por janela.
- CSV por indicador, status público dos pipelines, health/readiness e logs estruturados.
- Docker Compose, Caddy opcional, testes e CI.

O IDEB está marcado como importação supervisionada até que o arquivo estruturado e todas as dimensões sejam validados. A transparência municipal não revelou um download tabular na auditoria inicial; o primeiro recorte fiscal usa o Siconfi.

## Requisitos

- Docker 24+ com Docker Compose.
- 4 GB de RAM recomendados. O CNES é baixado uma vez por versão para arquivo temporário,
  processado em streaming e removido sem persistir atributos pessoais na base analítica.

## Subir o ambiente

```bash
cp .env.example .env
docker compose up --build
```

Em desenvolvimento:

- Aplicação: `http://localhost:3000`
- API: `http://localhost:8000/api/v1/health`
- OpenAPI: `http://localhost:8000/api/docs`

As migrações rodam antes da API. O serviço `ingestion` registra jobs recorrentes, busca trabalhos
vencidos em intervalos curtos e usa lock no PostgreSQL. A recorrência nunca é inferior a uma hora;
uma falha isolada não apaga o último dado publicado nem bloqueia outros jobs.

## Executar coletores manualmente

Validar sem gravar:

```bash
docker compose run --rm ingestion python -m ingestion.cli ingest --source ibge --dry-run
docker compose run --rm ingestion python -m ingestion.cli ingest --source siconfi --dry-run
docker compose run --rm ingestion python -m ingestion.cli ingest --source cnes --dry-run
```

Coletar e persistir:

```bash
docker compose run --rm ingestion python -m ingestion.cli ingest --source all
```

Sincronizar a dimensão territorial oficial e coletar uma janela controlada para três municípios:

```bash
docker compose run --rm ingestion python -m ingestion.cli geo-sync
docker compose run --rm ingestion python -m ingestion.cli ingest --source ibge \
  --municipalities 3543402,3509502,3550308 --start-year 2024 --end-year 2025
docker compose run --rm ingestion python -m ingestion.cli ingest --source siconfi \
  --municipalities 3543402,3509502,3550308 --start-year 2025 --end-year 2025 \
  --periods 6 --max-requests 10
docker compose run --rm ingestion python -m ingestion.cli ingest --source cnes \
  --municipalities 3543402,3509502,3550308
```

Para backfill, prefira `ingestion.cli schedule` com município/UF, anos e limite total explícitos.
O comando antigo sem município continua usando Ribeirão Preto por compatibilidade. O Siconfi
recusa janelas acima de `--max-requests` e respeita uma requisição por segundo.

Verificar disponibilidade dos endpoints:

```bash
docker compose run --rm ingestion python -m ingestion.cli health --source all
```

O Siconfi respeita uma requisição por segundo. Ajuste o recorte anual com `SICONFI_START_YEAR` e `SICONFI_END_YEAR`; por padrão são usados exercícios completos de 2022 a 2025.

## Catálogo nacional candidato

O inventário nacional versionado é validado e importado automaticamente, de forma idempotente,
na inicialização da API e somente como metadado. Uma
fonte `discovered` continua não integrada até haver verificação e conector ativo. Consulte
`docs/CATALOGO_NACIONAL.md` para o contrato e os comandos. O JSON original, a planilha mestre e o
plano técnico original estão preservados em `docs/catalog/input` e `docs/reference`.

## API e exportação

Principais rotas:

- `GET /api/v1/municipalities`
- `GET /api/v1/search?q=saude&uf=SP&sector=saude&status=discovered`
- `GET /api/v1/geo/municipios?uf=SP&q=Campinas&limit=50&offset=0`
- `GET /api/v1/municipios/{ibge_code}/summary`
- `GET /api/v1/datasets/{id-ou-code}/coverage`
- `GET /api/v1/sources/{slug-ou-LNT-id}`
- `GET /api/v1/sources`
- `GET /api/v1/datasets`
- `GET /api/v1/indicators`
- `GET /api/v1/indicators/{code}/observations?from=2020-01-01&to=2026-12-31&scope={}`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/exports/observations.csv?indicator=population_estimated`
- `GET /api/v1/pipelines/status`

Listagens têm limites validados. A exportação inclui hash e URL do snapshot. Ingestão não possui endpoint público.
O resumo legado `/dashboard/summary` permanece disponível e aceita `?municipality=`, usando
Ribeirão Preto quando o parâmetro é omitido.

## Testes

Com os containers em execução:

```bash
docker compose run --rm -w /app api ruff check apps/api workers/ingestion --ignore EXE002
docker compose run --rm -w /app api ruff format --check apps/api workers/ingestion
docker compose run --rm \
  -e TEST_DATABASE_URL=postgresql+psycopg://lente:lente-local@db:5432/lente \
  api pytest -q
docker run --rm -v "$PWD/apps/web:/app" -w /app node:22-alpine \
  node --test tests/content.test.mjs
docker compose build web
```

A construção da imagem `web` executa o typecheck e o build de produção do Next.js. A suíte completa também roda automaticamente no GitHub Actions.

O teste de integração do repositório exige `TEST_DATABASE_URL`; a CI aponta essa variável para PostgreSQL 16 e executa a migração antes do `pytest`.

## Backup e restauração

Em produção, monte um diretório externo criptografado em `/backups`. Exemplo de backup usando um container PostgreSQL temporário:

```bash
docker run --rm --network lente-ribeirao_default \
  -e DATABASE_URL=postgresql://lente:SENHA@db:5432/lente \
  -e BACKUP_DIR=/backups -v "$PWD/backups:/backups" \
  -v "$PWD/infra:/scripts:ro" postgres:16-alpine /scripts/backup.sh
```

Restauração destrutiva do banco de destino — use apenas em banco vazio ou ambiente de recuperação:

```bash
docker run --rm --network lente-ribeirao_default \
  -e DATABASE_URL=postgresql://lente:SENHA@db:5432/lente \
  -v "$PWD/backups:/backups" -v "$PWD/infra:/scripts:ro" \
  postgres:16-alpine /scripts/restore.sh /backups/lente-AAAAMMDDTHHMMSSZ.dump
```

O restore verifica primeiro o SHA-256. Teste periodicamente em um banco separado.

## Produção em VM Linux

1. Configure DNS e `SITE_ADDRESS` no `.env`.
2. Use senha forte e mantenha `DATABASE_URL` somente no servidor.
3. Inicie com `docker compose --profile production up -d --build`.
4. O Caddy obtém e renova TLS para um domínio público válido.
5. Não publique a porta do PostgreSQL. Os binds de API/web em `127.0.0.1` são apenas para diagnóstico local.
6. Configure backup externo, atualização de imagens e monitoramento do endpoint `/api/v1/ready`.

Uma VM com 2 vCPU, 4 GB de RAM e SSD é o ponto de partida recomendado; medir antes de definir SLA.

## Troubleshooting

- **A home não mostra números:** confira `/api/v1/pipelines/status` e os logs de `docker compose logs ingestion`.
- **Fonte caiu:** o job registra falha sem apagar o último dado validado; a API e o frontend continuam disponíveis.
- **CNES mudou o cabeçalho:** a carga é bloqueada como `schema_drift`; revise o adaptador antes de aceitar a nova versão.
- **Siconfi retorna vazio:** confirme exercício, 6º bimestre e homologação. Não troque automaticamente por outro período.
- **IDEb não aparece:** é intencional nesta etapa; use somente o fluxo de importação supervisionada depois de validar o arquivo oficial.

## Documentação

- `docs/IMPLEMENTATION_PLAN.md`: arquitetura, fases e riscos.
- `docs/SOURCES.md`: inventário e evidências de acesso.
- `docs/DATA_DICTIONARY.md`: modelo, indicadores e regras de qualidade.
- `docs/NACIONALIZACAO_BASELINE.md`: auditoria e baseline anteriores à fundação nacional.
- `docs/CATALOGO_NACIONAL.md`: schema, estados, importação, segurança e manutenção.
