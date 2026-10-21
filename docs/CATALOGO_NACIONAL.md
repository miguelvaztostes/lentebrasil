# Contrato do catálogo nacional

O catálogo nacional é um inventário versionado de candidatos. A presença de uma URL no JSON
não comprova disponibilidade, licença, implementação, qualidade, publicação ou cobertura.

## Fluxo e estados independentes

| Dimensão | Estados | Significado inicial do importador |
|---|---|---|
| Fonte/provedor/recurso | `discovered`, `pending_review`, `verified`, `unavailable`, `restricted` | `discovered`; URL ainda não homologada |
| Conector | `not_implemented`, `planned`, `implemented`, `active`, `degraded`, `failed`, `disabled` | `not_implemented`; não há coleta |
| Publicação/release | `not_published`, `draft`, `validated`, `published`, `withdrawn`, `failed` | dataset `not_published`; nenhuma observação pública |
| Cobertura | `unknown`, `partial`, `complete`, `unavailable`, `not_applicable` | só é criada após aferição; ausência não implica cobertura |
| Licença do recurso | `unknown`, `pending_review`, `confirmed`, `restricted` | `pending_review` quando há texto candidato; caso contrário `unknown` |

Somente uma verificação explícita pode promover um recurso para `verified`. Somente um conector
implementado, testado e monitorado pode chegar a `active`. Somente dados validados, com
proveniência e período, podem gerar release `published`.

## Arquivo e validação

O JSON deve ser um objeto com nome, versão do catálogo, versão do schema e uma lista em
`records` (aliases documentados em `lente_api.catalog`). Cada registro requer:

- ID único e sequencial `LNT-0001` a `LNT-0165`;
- área, indicador e provedor;
- URL `http`/`https` pública, quando fornecida, sem credenciais, host local ou IP privado;
- formato, quando fornecido, dentro de `api`, `csv`, `zip`, `xlsx`, `parquet`, `portal`,
  `manual`, `json`, `xml` ou `pdf`.

O contrato de referência exige exatamente 165 registros, 16 áreas e 95 indicadores distintos.
O validador é somente leitura e relata lacunas, IDs duplicados, campos, URLs e formatos
inconsistentes sem reescrever o original.

```bash
PYTHONPATH=apps/api/src python scripts/validate_national_catalog.py validate \
  docs/catalog/input/lente_inventario_nacional_fontes_2026.json
```

Após validação, a importação de metadados usa:

```bash
PYTHONPATH=apps/api/src python -m lente_api.catalog import \
  docs/catalog/input/lente_inventario_nacional_fontes_2026.json
```

O SHA-256 do arquivo identifica a importação. Repetir o mesmo arquivo não cria registros. Uma
nova versão preserva a importação e o registro bruto mais recente por `external_catalog_id`;
conflitos ficam em `catalog_imports.discrepancies`.

## Proveniência, nulo e zero

- Cada importação guarda versão, schema, caminho de origem, SHA-256, instante e contagens.
- Cada entrada guarda o objeto JSON recebido, vínculo ao provedor, recurso e dataset.
- Cada observação publicada continua exigindo snapshot, URL, hash, captura, período e revisão.
- `NULL` significa ausente, inaplicável ou não informado conforme o status; zero é um valor
  observado e nunca é usado para preencher ausência.
- URL descoberta sem conector não cria observação nem release publicada.

## Privacidade e segurança

O catálogo aceita apenas URLs públicas bem formadas, mas o importador não as acessa. Coletores
devem repetir a validação, resolver DNS com defesa contra SSRF e obedecer limites, licença e
termos do provedor. Segredos não pertencem ao JSON nem ao Git. Dados pessoais não são copiados
para a camada analítica; no CNES, por exemplo, só permanecem agregados municipais.

## Migração do MVP

A revisão `0002` cria `geo_units`, `geo_code_mappings`, `data_providers`, `source_resources`,
`dataset_coverage`, `publication_releases`, `catalog_imports` e `catalog_entries`. Também adiciona
chaves e estados às tabelas `sources` e `datasets`.

Os objetos do Lente Ribeirão são ligados às novas entidades com IDs determinísticos. IBGE,
Siconfi e CNES mantêm conectores `active` e releases de compatibilidade `published`; fontes ainda
manuais não são promovidas. `municipalities`, `sources`, `datasets`, `observations`, URLs, slugs e
histórico permanecem. O downgrade remove apenas a fundação nova.

## Manutenção

1. Versionar o arquivo recebido sem corrigir silenciosamente seu conteúdo.
2. Rodar validação e revisar todas as discrepâncias.
3. Importar em banco de homologação duas vezes e comparar contagens.
4. Verificar recurso/licença e implementar conector em mudança separada.
5. Publicar apenas após validação, cobertura e proveniência explícitas.
6. Monitorar mudança de schema e preservar o último release válido em falhas.
