# Lente Brasil — plano técnico de evolução do observatório público nacional

Versão 1.0, de 20/10/2026. Documento de referência convertido e estruturado a partir do
[PDF original](reference/PLANO_TECNICO_LENTE_BRASIL_V1_2026-10-20.pdf), cujo SHA-256 é
`70e22ac1e1de1c0c4154969630f927d089f5640546583c66b452a0226f0f2976`.

O diagnóstico original usa como referência a branch `main` no commit
`e49ac2059431eeec760f97843e41b97adad4c388`. Ele não executou containers, consultou banco de
produção, testou os 165 candidatos nem alterou o GitHub.

## 1. Visão do produto e fronteiras

O Lente Brasil será o portal consultivo nacional. O Lente Ribeirão será uma visão territorial da
mesma infraestrutura e do mesmo catálogo, sem aplicação ou banco duplicado. A consulta pública
permanece independente, sem sugerir parceria ou endosso institucional.

O produto deve descobrir e catalogar fontes, importar conforme formato e licença, validar séries,
consultar por Brasil/UF/município/entidade, comparar somente recortes compatíveis e sempre expor
origem, referência, revisão e limitações. Fonte descoberta, conector executável, dado homologado e
cobertura são estados distintos.

## 2. Estado do repositório auditado

- Next.js, TypeScript, Tailwind e Recharts no frontend.
- FastAPI `/api/v1`, OpenAPI, séries, resumo, CSV e situação das pipelines.
- PostgreSQL com catálogo municipal, observações, snapshots, revisões e qualidade.
- `SourceAdapter` e conectores IBGE, Siconfi e CNES.
- Scheduler sequencial, Docker Compose, Caddy, backup/restauração e CI.
- Proveniência com SHA-256, coleta, período, licença, status e método.

Bloqueios identificados: município fixo nos conectores e dashboard; filtros de `scope` em memória;
modelo territorial insuficiente para outros níveis; scheduler único; frontend municipal; somente três
integrações; CSV síncrono limitado; e ausência de testes nacionais, concorrência e carga.

Devem ser preservados os contratos dos adaptadores, migrações, snapshots, revisões, semântica
`zero != ausência`, identidade visual, CI e Docker.

## 3. Arquitetura-alvo

Fluxo recomendado:

```text
fontes oficiais + catálogos + sugestões moderadas
                    ↓
registro de fontes e fila de homologação
                    ↓
agendamento por fonte + jobs/workers
                    ↓
download bruto → staging → validação → curated
                    ↓
PostgreSQL + armazenamento de objetos → FastAPI → Next.js
                    ↓
busca, filtros territoriais, séries, mapas, comparações e exportações
```

Reutilizar FastAPI, Next.js e PostgreSQL. Avaliar armazenamento S3, Redis/fila e Parquet com
DuckDB/Polars somente conforme a escala. Não adotar Kubernetes, Kafka, data warehouse externo ou
Elasticsearch sem necessidade medida. Visitas do usuário consultam dados processados e nunca
disparam coleta governamental.

## 4. Modelo de dados proposto

Catálogo e governança: `data_providers`, fontes, `source_resources`, `datasets`,
`dataset_coverage`, definições de indicadores, conectores, execuções, artefatos, regras de validação,
ocorrências de qualidade e `publication_releases`.

Território e instituições: `geo_units`, `geo_code_mappings`, escolas, estabelecimentos de saúde,
órgãos, contratos, fornecedores, contas orçamentárias, programas, eleições e estações ambientais.

Manter `observations` durante a migração e criar futuramente fatos adequados a agregados e dados
transacionais. JSON flexível não substitui colunas e índices para filtros recorrentes. Toda linha
publicada deve ligar snapshot, execução, versão, licença e transformação.

## 5. Inventário e conectores

O inventário contém 165 candidatos, 16 áreas, 95 indicadores propostos e 61 registros P0. Essas
contagens não representam conectores testados. A ordem indicada é:

1. Fundação: IBGE Localidades/malhas, SIDRA/Agregados, CNES e Siconfi.
2. Prioridade 1: Inep, TCE-SP, PNCP, Saúde/Dataseus, FNDE, MDS e SINISA.
3. Prioridade 2: CAGED/RAIS/PIB/Comex, SSP-SP, TSE, ANEEL, Senatran, INPE e catálogos locais.

Contrato futuro: `discover → fetch → stage → parse → validate → reconcile → publish`, com
geografias, período, versão, atualização incremental, dry-run, checkpoint, rate limit, retry, ETag,
logs e métricas. Página de conjunto, documentação, endpoint e download direto são recursos
diferentes. `validated` exige resposta, schema, amostra, licença, período e geografia conferidos.

## 6. Área pública inicial

Rotas propostas: `/`, `/brasil`, `/estados/[uf]`, `/municipios/[ibgeCode]`, visões setoriais,
`/indicadores/[codigo]`, `/fontes`, `/comparar`, `/dados-abertos`, `/contribuir/fonte` e `/pesquisa`.
Filtros devem persistir na URL. Comparações e rankings dependem de conceito, denominador,
periodicidade e geografia compatíveis.

Endpoints propostos, ainda não implementados no plano original:

- `GET /api/v1/geo/municipios`
- `GET /api/v1/search`
- `GET /api/v1/municipios/{code}/summary`
- `GET /api/v1/municipios/{code}/indicators`
- observações com `geo_type` e `geo_id`
- `GET /api/v1/compare`
- cobertura de dataset e jobs de exportação
- `POST /api/v1/source-submissions`

O lançamento combina catálogo completo de candidatos com observatório restrito aos dados realmente
homologados. Ausência deve aparecer como “fonte identificada — ainda não integrada”.

## 7. Pesquisa e contas

Consulta, filtros, comparação e downloads públicos não exigem conta. Perfis entram somente para
salvar consultas, alertas, coleções, chaves com quota ou submissões identificadas. Papéis futuros:
leitor anônimo, pesquisador, contribuidor, organização verificada, curador, data steward e
administrador.

## 8. Descoberta e contribuição de fontes

Sugestões seguem triagem, verificação de legitimidade/licença, quarentena, testes, validação humana,
aprovação, agendamento e revalidação. Nenhuma sugestão escreve diretamente em dados oficiais.

URLs submetidas são metadados até aprovação. Antes de qualquer acesso: domínio oficial, defesa
SSRF, resolução DNS e redirects, bloqueio de IP privado/metadata, timeout, tamanho, MIME, antivírus,
proteção contra ZIP bomb, quarentena, privacidade e licença.

## 9. Segurança, privacidade, qualidade e governança

Dado público não significa reprodução irrestrita de dado pessoal. Avaliar base legal, finalidade,
minimização, agregação, reidentificação e retenção. Aplicar TLS, segredos protegidos, menor
privilégio, rotação, RBAC, MFA no backoffice, auditoria e backups cifrados testados.

Registrar hash, fonte, publicação, ingestão, período, parser, licença, transformação, cálculo,
geografia e release. Validar schema, tipos, vazios, duplicidade, tempo, extremos, limites, totais,
cardinalidade e divulgação indevida. Fontes contraditórias permanecem identificadas; fases fiscais
nunca são misturadas.

## 10. Observabilidade

Por fonte: duração, bytes, recebidos/válidos/rejeitados, data recente, defasagem, drift, HTTP,
retries, custo e publicação. Na API: p50/p95, 5xx, cache, consultas e downloads. Na infraestrutura:
PostgreSQL, conexões, objetos, backlog e jobs. Metas de serviço devem ser definidas após baseline.

## 11. Roadmap

- Etapa 0: segurança, compatibilidade, catálogo versionado e migrações aditivas.
- Etapa 1: nacionalizar IBGE, Siconfi e CNES, remover município fixo e corrigir consultas.
- Etapa 2: importar os 165 candidatos e publicar busca territorial e catálogo.
- Etapa 3: conectores prioritários e fatos especializados, com CSV/Parquet assíncrono.
- Etapa 4: comparações compatíveis, mapas, cobertura e pesquisa facetada.
- Etapa 5: contribuição, curadoria, organizações verificadas e perfis opcionais.

## 12. Tarefas técnicas em ordem

`NAT-001` baseline; `NAT-002` território; `NAT-003` IBGE multigeografia; `NAT-004` CNES nacional;
`NAT-005` Siconfi por ente/ano; `NAT-006` filtros e paginação SQL; `NAT-007` resumo municipal;
`NAT-008` UI territorial; `NAT-009` catálogo candidato; `NAT-010` busca facetada; `NAT-011` Inep;
`NAT-012` testes multicípio, regressão, desempenho e proveniência.

## 13. Aceite por dataset

Exigir URL/licença, formato, versão ou hash, schema, reconciliação territorial, período/unidade,
zero distinto de ausência, deduplicação, amostra oficial, cobertura, monitoramento, API/CSV,
tratamento LGPD e retirada/rollback possíveis.

## 14. Referências

O plano referencia o repositório Lente Brasil, CKAN, data.gov.uk, Zenodo e OWASP SSRF Prevention.
O XLSX e o JSON versionados neste repositório são o inventário de candidatos; sua enumeração não
equivale a homologação.
