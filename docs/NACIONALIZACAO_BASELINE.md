# Baseline da nacionalização

Registro executado em 20/10/2026 antes das alterações desta etapa.

## Estado Git e referências

- Branch inicial: `main`.
- SHA inicial e `origin/main`: `e49ac2059431eeec760f97843e41b97adad4c388`.
- `git status --short`: limpo.
- Branch de trabalho criada de `origin/main`: `feat/lente-brasil-nacional`.
- `docs/PLANO_TECNICO_LENTE_BRASIL_V1.md`: não estava disponível no repositório,
  Downloads nem no pacote anexado.
- `docs/catalog/input/lente_inventario_nacional_fontes_2026.json`: não estava
  disponível nos mesmos locais. Portanto, nenhum dos 165 registros foi inventado ou importado.

## Arquitetura auditada

| Camada | Baseline observado |
|---|---|
| API | FastAPI, prefixo `/api/v1`, health/readiness, catálogos, observações, resumo, CSV e status de pipelines. |
| Banco | PostgreSQL 16 e Alembic `0001`; tabelas municipais, fontes, datasets, snapshots, indicadores, observações, execuções e ocorrências de qualidade. |
| Ingestão | Adaptadores reais separados para IBGE/SIDRA, Siconfi e CNES; CLI, scheduler, snapshots, hashes e revisões. |
| Web | Next.js com App Router; home, catálogo, indicadores, fontes, metodologia e dados abertos. |
| Infra | Compose para banco, API, ingestão e web; proxy Caddy no perfil de produção. |
| CI | Ruff, Alembic upgrade, Pytest, testes Node, typecheck, build Next.js e build das imagens. |

## Dados legados antes da alteração

Banco local em revisão `0001 (head)`:

- 1 município;
- 7 fontes;
- 3 datasets;
- 8 indicadores;
- 32 observações.

Essas contagens são uma fotografia do banco local, não estatísticas nacionais. A migração
`0002` é aditiva: não remove nem renomeia as tabelas legadas.

## Testes de baseline

| Comando | Resultado antes das alterações |
|---|---|
| `docker compose config --quiet` | aprovado |
| `ruff check apps/api workers/ingestion` | aprovado |
| `ruff format --check apps/api workers/ingestion` | 20 arquivos formatados |
| `pytest -q` | 6 aprovados; 1 aviso de depreciação do `httpx` via Starlette |
| `npm test` | 1 aprovado |
| `npm run typecheck` | aprovado |
| `docker compose build web` | aprovado |

Nenhum coletor externo foi disparado durante essa auditoria. O inventário e as evidências de
fontes previamente verificadas permanecem em `docs/SOURCES.md` e `docs/VALIDATION_REPORT.md`.

## Riscos encontrados e decisão

- O modelo `municipalities` é municipal e deve continuar atendendo os contratos existentes;
  a expansão usa `geo_units` em paralelo.
- `sources.status` mistura disponibilidade e implementação; novos campos separam estado da
  fonte, do conector e da publicação sem retirar o campo legado.
- Candidatos do inventário não podem ser confundidos com integrações. A importação grava
  apenas metadados como `discovered`/`not_implemented`/`not_published`.
- O arquivo nacional ausente impede comprovar suas contagens e conteúdo reais nesta etapa.
  O validador exige 165 registros, 16 áreas e 95 indicadores quando o arquivo for fornecido.
