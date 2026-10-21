# Lente Ribeirão

Observatório público e independente de dados municipais de Ribeirão Preto/SP. O projeto publica somente observações provenientes de fontes oficiais verificadas, com período, unidade, metodologia, coleta e URL de origem.

Não é um sistema oficial da Prefeitura, da Câmara, do Instituto Ribeirão 2030 ou do Lente Brasil.

## O que já funciona

- API pública FastAPI em `/api/v1` e documentação OpenAPI em `/api/docs`.
- PostgreSQL com migrações, catálogo, snapshots, revisões e auditoria de ingestão.
- Fundação nacional aditiva para geografia, provedores, recursos, cobertura e releases, sem
  retirar os contratos municipais.
- Next.js responsivo com página inicial, catálogo, séries, tabelas, fontes, metodologia e dados abertos.
- Coleta real da população estimada pelo IBGE/SIDRA.
- Coleta real do RREO/Siconfi, preservando receita, empenho, liquidação e pagamento.
- Coleta real e agregada do CNES, sem copiar nomes, contatos, endereços ou CNPJs para a base analítica.
- CSV por indicador, status público dos pipelines, health/readiness e logs estruturados.
- Docker Compose, Caddy opcional, testes e CI.

O IDEB está marcado como importação supervisionada até que o arquivo estruturado e todas as dimensões sejam validados. A transparência municipal não revelou um download tabular na auditoria inicial; o primeiro recorte fiscal usa o Siconfi.

## Requisitos

- Docker 24+ com Docker Compose.
- 4 GB de RAM recomendados. A primeira carga do CNES baixa um ZIP de aproximadamente 56 MB e o processa em memória sem persistir o conteúdo sensível.

## Subir o ambiente

```bash
cp .env.example .env
docker compose up --build
```

Em desenvolvimento:

- Aplicação: `http://localhost:3000`
- API: `http://localhost:8000/api/v1/health`
- OpenAPI: `http://localhost:8000/api/docs`

As migrações rodam antes da API. O serviço `ingestion` espera a API ficar saudável, executa as fontes configuradas em `INGESTION_SOURCES` e repete no intervalo configurado, nunca inferior a uma hora.

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

Verificar disponibilidade dos endpoints:

```bash
docker compose run --rm ingestion python -m ingestion.cli health --source all
```

O Siconfi respeita uma requisição por segundo. Ajuste o recorte anual com `SICONFI_START_YEAR` e `SICONFI_END_YEAR`; por padrão são usados exercícios completos de 2022 a 2025.

## Catálogo nacional candidato

O inventário nacional, quando fornecido, é validado e importado somente como metadado. Uma
fonte `discovered` continua não integrada até haver verificação e conector ativo. Consulte
`docs/CATALOGO_NACIONAL.md` para o contrato e os comandos. Os arquivos nacionais de referência
não estavam presentes neste checkout e, por isso, não foram fabricados nem importados.

## API e exportação

Principais rotas:

- `GET /api/v1/municipalities`
- `GET /api/v1/sources`
- `GET /api/v1/datasets`
- `GET /api/v1/indicators`
- `GET /api/v1/indicators/{code}/observations?from=2020-01-01&to=2026-12-31&scope={}`
- `GET /api/v1/dashboard/summary`
- `GET /api/v1/exports/observations.csv?indicator=population_estimated`
- `GET /api/v1/pipelines/status`

Listagens têm limites validados. A exportação inclui hash e URL do snapshot. Ingestão não possui endpoint público.

## Testes

Com os containers em execução:

```bash
docker compose run --rm api ruff check /app/apps/api /app/workers/ingestion
docker compose run --rm api ruff format --check /app/apps/api /app/workers/ingestion
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
