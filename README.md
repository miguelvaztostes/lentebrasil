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
- Contratações e contratos PNCP com paginação, versões e checkpoints; RGF/DCA do Siconfi,
  receitas TCE-SP/Audesp por rubrica e despesas mensais agregadas por fase, sem consolidação
  indevida entre fontes e sem persistir dados de fornecedores da API de despesas.
- Coleta real e agregada do CNES, sem copiar nomes, contatos, endereços ou CNPJs para a base analítica.
- Saúde municipal com hospitais/leitos/serviços CNES, produção SIA/SUS e SIH/SUS, vínculos ANS,
  gastos SIOPS, mortalidade SIM e nascidos vivos SINASC, mantendo microdados fora da base
  publicada e distinguindo cadastro, capacidade, produção, gasto e eventos vitais.
- Educação municipal com Censo Escolar 2024, Ideb 2025, Saeb 2023 e previsão PNAE 2024,
  preservando supressões e distinguindo previsão de transferência de execução financeira.
- Pipeline multicípio para IBGE, Siconfi e CNES, com dimensão oficial de 27 UFs e 5.571
  municípios, crosswalks explícitos e histórico cadastral.
- Jobs persistidos no PostgreSQL com lock, checkpoint, retomada, retry e backfill por janela.
- CSV por indicador, status público dos pipelines, health/readiness e logs estruturados.
- Docker Compose, Caddy opcional, testes e CI.

A visão geral de transparência combina fontes supramunicipais oficiais verificadas. Ela não afirma
cobertura integral de todos os portais ou atos públicos; lacunas aparecem como indisponíveis.

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
docker compose run --rm ingestion python -m ingestion.cli ingest --source saeb --dry-run
docker compose run --rm ingestion python -m ingestion.cli ingest --source fnde_pnae --dry-run
docker compose run --rm ingestion python -m ingestion.cli ingest --source pncp --dry-run --municipalities 3543402 --start-date 2026-10-01 --end-date 2026-10-22 --modalities 8 --publication-mode
docker compose run --rm ingestion python -m ingestion.cli ingest --source siconfi_rgf --dry-run --municipalities 3543402 --start-year 2025 --periods 3 --annexes "RGF-Anexo 01"
docker compose run --rm ingestion python -m ingestion.cli ingest --source siconfi_dca --dry-run --municipalities 3543402 --start-year 2024 --annexes "DCA-Anexo I-AB"
docker compose run --rm ingestion python -m ingestion.cli ingest --source tcesp_revenues --dry-run --municipalities 3543402 --start-year 2025
docker compose run --rm ingestion python -m ingestion.cli ingest --source tcesp_expenses --dry-run --municipalities 3543402 --start-year 2025 --periods 1 --max-requests 1
docker compose run --rm ingestion python -m ingestion.cli ingest --source cnes_beds --dry-run --municipalities 3543402
docker compose run --rm ingestion python -m ingestion.cli ingest --source sinasc_births --dry-run --municipalities 3543402 --start-year 2024 --end-year 2024
docker compose run --rm ingestion python -m ingestion.cli ingest --source sih_production --dry-run --municipalities 3543402
docker compose run --rm ingestion python -m ingestion.cli ingest --source sia_production --dry-run --municipalities 3543402
docker compose run --rm ingestion python -m ingestion.cli ingest --source cnes_services --dry-run --municipalities 3543402
docker compose run --rm ingestion python -m ingestion.cli ingest --source ans_beneficiaries --dry-run --municipalities 3543402
```

Coletar e persistir:

```bash
docker compose run --rm ingestion python -m ingestion.cli ingest --source all
```

`--source all` inclui arquivos anuais volumosos de saúde e não é recomendado para uma carga
rápida de demonstração. Para a demo, execute somente as fontes necessárias e informe um recorte
municipal explícito; os conectores SIA/SIH/CNES/ANS acima usam dezembro/2025.

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
- `GET /api/v1/education/schools?municipality=3543402&network=municipal`
- `GET /api/v1/education/metrics?municipality=3543402&dataset=inep_saeb_municipal`
- `GET /api/v1/education/metrics?municipality=3543402&dataset=fnde_pnae_municipal`
- `GET /api/v1/education/municipalities/{ibge_code}`
- `GET /api/v1/transparency/fiscal-statements?municipality=3543402&year=2025`
- `GET /api/v1/transparency/overview?municipality=3543402&year=2025`
- `GET /api/v1/transparency/procurements?municipality=3543402&year=2026`
- `GET /api/v1/transparency/contracts?municipality=3543402`
- `GET /api/v1/transparency/transfers?municipality=3543402`
- `GET /api/v1/transparency/exports/fiscal-statements.csv?municipality=3543402`
- `GET /api/v1/transparency/exports/procurements.csv?municipality=3543402`
- `GET /api/v1/health/overview?municipality=3543402&year=2024`
- `GET /api/v1/health/epidemiology?municipality=3543402&year=2024`
- `GET /api/v1/health/establishments?municipality=3543402`
- `GET /api/v1/health/beds?municipality=3543402&active=true`
- `GET /api/v1/health/services?municipality=3543402`
- `GET /api/v1/health/production?municipality=3543402&year=2025`
- `GET /api/v1/health/exports/epidemiology.csv?municipality=3543402&year=2024`

Listagens têm limites validados. A exportação inclui hash e URL do snapshot. Ingestão não possui endpoint público.
O resumo legado `/dashboard/summary` permanece disponível e aceita `?municipality=`, usando
Ribeirão Preto quando o parâmetro é omitido.

Os conectores `sim_mortality` e `sinasc_births` publicam somente agregados municipais seguros e
não persistem microdados. Auditoria, direitos, cobertura e limitações estão em
`docs/HEALTH_SOURCES.md`. Eles não integram a carga padrão da demo porque os ZIPs anuais têm
cerca de 98 MB e 92 MB. A execução controlada usa o comando abaixo, trocando a fonte por
`sinasc_births` para nascidos vivos:

```bash
python -m ingestion.cli ingest --source sim_mortality --municipalities 3543402 \
  --start-year 2024 --end-year 2024
```

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
- **Dados educacionais não aparecem:** confira se os releases educacionais foram publicados pelo
  worker. Falha de certificado no container deve ser corrigida instalando a cadeia de CA do
  ambiente; nunca desabilite a validação TLS.

## Documentação

- `docs/IMPLEMENTATION_PLAN.md`: arquitetura, fases e riscos.
- `docs/SOURCES.md`: inventário e evidências de acesso.
- `docs/DATA_DICTIONARY.md`: modelo, indicadores e regras de qualidade.
- `docs/NACIONALIZACAO_BASELINE.md`: auditoria e baseline anteriores à fundação nacional.
- `docs/CATALOGO_NACIONAL.md`: schema, estados, importação, segurança e manutenção.
- `docs/EDUCATION_SOURCES.md`: artefatos homologados, decisões LNT, privacidade e evidências do módulo educacional.
