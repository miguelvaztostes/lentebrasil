# Dicionário de dados

## Entidades de catálogo e proveniência

| Tabela | Campo principal | Tipo/semântica |
|---|---|---|
| `municipalities` | `ibge_code` | Texto de 7 dígitos. Chave do município em toda observação. |
|  | `name`, `state` | Nome e UF validados na API de Localidades do IBGE. |
| `sources` | `provider`, `source_url` | Instituição e URL oficial canônica. |
|  | `license`, `terms` | Licença conhecida e restrições/notas de uso; podem permanecer explicitamente pendentes. |
|  | `status`, `verified_at` | `confirmed`, `pending`, `unavailable`, `requires_manual_import` ou `restricted`; instante UTC da verificação. |
| `datasets` | `code` | Identificador estável do coletor/dataset. |
|  | `domain`, `granularity` | Tema e nível de agregação. |
|  | `update_policy`, `status` | Frequência real de atualização e estado público. |
| `source_snapshots` | `sha256` | Hash SHA-256 do corpo recebido. |
|  | `url`, `fetched_at`, `published_at` | Origem, captura UTC e publicação original, quando informada. |
|  | `storage_path` | Caminho do bruto somente quando o conteúdo pode ser retido; pode ser `NULL`. |
|  | `original_format`, `response_headers` | Tipo do artefato e metadados HTTP permitidos. |

## Indicadores e observações

| Tabela | Campo principal | Tipo/semântica |
|---|---|---|
| `indicators` | `code`, `label` | Código estável e rótulo público. |
|  | `definition`, `unit`, `periodicity` | Definição exata, unidade e frequência. |
|  | `methodology`, `limitations` | Como foi obtido e o que não permite concluir. |
|  | `domain`, `direction` | Área temática e sentido apenas quando aplicável. |
| `observations` | `municipality_ibge_code` | FK do município; nunca inferido pelo nome. |
|  | `period_start`, `period_end` | Intervalo de referência do dado, diferente da data de coleta. |
|  | `scope_json`, `scope_key` | Desagregação original e hash canônico usado na identidade lógica. |
|  | `value` | `NUMERIC`, anulável. Zero é valor e não representa ausência. |
|  | `availability_status` | `available`, `preliminary`, `unavailable` ou `stale`. |
|  | `source_reference_at`, `retrieved_at` | Referência/publicação da fonte e momento UTC da coleta. |
|  | `revision` | Versão crescente para a mesma chave lógica quando o valor ou estado muda. Repetição idêntica é idempotente. |
|  | `snapshot_id` | FK obrigatória para a proveniência da observação. |

Chave lógica: `(municipality_ibge_code, indicator_id, period_start, period_end, scope_key)`. A restrição física inclui `revision` para preservar alterações históricas.

## Operação e qualidade

| Tabela | Campos | Semântica |
|---|---|---|
| `ingestion_runs` | início/fim, status, recebidos/aceitos/rejeitados, checksum, erro | Uma execução auditável por dataset. Erros são sanitizados antes da exposição pública. |
| `data_quality_issues` | código, severidade, detalhes, status | Divergência de schema/domínio/valor ligada à execução. |

## Indicadores iniciais

| Código | Unidade | Escopo | Regra |
|---|---|---|---|
| `population_estimated` | pessoas | `{}` | Variável SIDRA `9324`, tabela `6579`; não é censo nem projeção própria. |
| `revenue_realized` | BRL nominal | demonstrativo, anexo, período bimestral, conta e coluna | RREO Anexo 01, `ReceitasExcetoIntraOrcamentarias`, coluna `Até o Bimestre (c)`. |
| `expense_committed` | BRL nominal | idem | `DespesasExcetoIntraOrcamentarias`, coluna `DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)`. |
| `expense_liquidated` | BRL nominal | idem | Coluna `DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)`. |
| `expense_paid` | BRL nominal | idem | Coluna `DESPESAS PAGAS ATÉ O BIMESTRE (j)`. |
| `cnes_establishments_registered` | estabelecimentos | status do cadastro | Quantidade de linhas do arquivo corrente para `CO_IBGE=354340`; não mede atendimentos ou qualidade. |
| `cnes_establishments_without_disable_reason` | estabelecimentos | `CO_MOTIVO_DESAB` vazio | Contagem descritiva do cadastro; o rótulo não equivale a auditoria operacional de atividade. |
| `cnes_establishments_sus_ambulatory` | estabelecimentos | `CO_AMBULATORIAL_SUS=SIM` | Cadastro informa atendimento ambulatorial SUS; não mede produção ou tempo de espera. |

## Regras obrigatórias

- `NULL != 0`: conversão vazia gera ausência/rejeição, nunca zero automático.
- Fases fiscais não são somadas nem apresentadas como intercambiáveis.
- Valores monetários usam `Decimal`/`NUMERIC(24, 6)` e são BRL nominais, sem correção inflacionária.
- O código CNES de município usa seis dígitos (`354340`) no arquivo; o armazenamento usa o código IBGE completo (`3543402`). O mapeamento é explícito no adaptador.
- O recurso CNES de 09/10/2026 contém bytes Latin-1/Windows-1252 e não declara charset no `Content-Type`; o parser usa Latin-1 estrito e valida o cabeçalho antes de agregar.
- Dados CNES do MVP são agregados antes da persistência; nomes, endereços, telefones, e-mails e CNPJs não são copiados para o banco.
- Datas de referência, captura e publicação são campos separados.
