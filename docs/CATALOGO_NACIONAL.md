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

O arquivo oficial usa `projeto`, `levantamento`, contagens declaradas, `fontes`, `indicadores`,
`regras_etl` e `roadmap`. O leitor também aceita o schema canônico com nome, versão e `records`.
Cada fonte requer:

- ID único e sequencial `LNT-0001` a `LNT-0165`;
- setor e nome; os indicadores ficam em lista separada e apontam para fonte principal/complementar;
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

### Auditoria dos arquivos de 20/10/2026

- JSON: SHA-256 `07388429a64367e61f80beb4a371e988188ee7b8fc59d022134f9fd0fbb452de`.
- XLSX: SHA-256 `fa3466000d62ba7baf6b2073511538a00a2532dfbfff63ff806add37ccf81e78`.
- 165 IDs únicos e sequenciais; 16 setores; 95 indicadores; 61 fontes P0.
- Os 165 registros da aba `02 FONTES MESTRE` são iguais aos objetos `fontes` do JSON nos 18
  campos comparados.
- Todos os vínculos de indicador apontam para IDs existentes.
- Duas entradas (`LNT-0029` e `LNT-0030`) contêm o mesmo FTP oficial. O endereço é preservado no
  registro bruto e reportado como aviso, mas não é selecionado como URL de conector HTTP/HTTPS.
- O JSON não declara `schema_version`; o leitor registra o perfil
  `lente-inventario-nacional-2026` sem reescrever o arquivo.
- Em banco descartável, duas importações produziram o mesmo SHA/import ID, com 68 provedores,
  121 recursos agrupados, 165 datasets candidatos e 165 entradas. Todos os 121 recursos ficaram
  `not_implemented` e os 165 datasets `not_published`.
- Na publicação do portal, três vínculos explícitos reconciliam os candidatos `LNT-0003`,
  `LNT-0018` e `LNT-0093` aos datasets homologados SIDRA, CNES e Siconfi. Os demais candidatos
  não são promovidos. Mesmo nesses três casos, o estado público `published` exige observação real.
- Foram preservados 99 vínculos de 95 indicadores com 82 fontes. Quatro conflitos de grafia de
  provedor foram registrados, sem sobrescrever nomes: CNES, Inep/INEP e SENATRAN/Senatran.

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

A revisão `0005` adiciona `pg_trgm` e índices GIN de texto normalizado. O downgrade remove os
índices da busca, sem apagar catálogo, observações ou a extensão compartilhada.

## Manutenção

1. Versionar o arquivo recebido sem corrigir silenciosamente seu conteúdo.
2. Rodar validação e revisar todas as discrepâncias.
3. Importar em banco de homologação duas vezes e comparar contagens.
4. Verificar recurso/licença e implementar conector em mudança separada.
5. Publicar apenas após validação, cobertura e proveniência explícitas.
6. Monitorar mudança de schema e preservar o último release válido em falhas.
