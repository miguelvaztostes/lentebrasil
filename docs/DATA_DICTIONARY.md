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
| `geo_units` | `unit_type`, `code`, `parent_id` | Hierarquia nacional aditiva; não substitui `municipalities`. |
| `geo_code_mappings` | `code_system`, `external_code` | Tradução explícita de códigos externos, com vigência. |
| `geo_unit_versions` | nome, UF, vigência e hash | Histórico aditivo das identidades territoriais recebidas do IBGE. |
| `data_providers` | `source_status`, `connector_status` | Organização e estados independentes de descoberta e automação. |
| `source_resources` | URL, formato, licença e estados | Recurso concreto; pode existir sem conector e sem dados. |
| `catalog_imports` | versão, SHA-256 e discrepâncias | Execução idempotente de um arquivo candidato. |
| `catalog_entries` | `external_catalog_id`, `raw_record` | Registro original e vínculos sem perda do metadado recebido. |
|  | `integration_decision`, `decision_reason`, `decided_at` | Decisão auditável por ID do inventário; não equivale a publicação. |
| `dataset_coverage` | geografia, escopo, período e status | Cobertura aferida; nunca inferida pela presença do dataset. |
| `publication_releases` | chave, período, estado e proveniência | Unidade explícita de validação/publicação. |

## Transparência e contratações

| Tabela | Grão e regra publicável |
|---|---|
| `agencies` | Órgão/unidade conforme a fonte, com município anulável para não atribuir contratação intermunicipal por inferência. |
| `suppliers` | Identidade separada e bloqueada por padrão (`public_identity=false`, `privacy_review=pending`); CPF e CNPJ de MEI não são publicados sem revisão. |
| `budget_accounts` | Conta/rubrica por sistema de origem; hierarquia original em JSON. |
| `fiscal_statements` | Fonte/chave/versão, município, demonstrativo, exercício, período, anexo, poder, coluna e conta. `amount` é `NUMERIC(24,6)` anulável. Inclui despesas TCE-SP agregadas por município/mês/evento antes da persistência. |
| `procurements` | Contratação PNCP/versão com órgão, município informado, modalidade, situação, valores e datas. |
| `procurement_items` | Item da contratação; estrutura criada para expansão, sem publicação simulada. |
| `contracts` | Contrato/versão com vínculo opcional à contratação; fornecedor permanece anulável. |
| `transfers` | Programa/tipo/exercício/versão; previsão PNAE não é convertida em pagamento fiscal. |

Chaves lógicas usam `(source_system, source_key, revision)`. Repetição idêntica é idempotente;
republicação cria revisão e alerta `source_republication`. A API seleciona a última revisão e
devolve URL, hash, coleta, licença/status e documento de origem.

## Educação

| Tabela | Grão | Conteúdo publicável |
|---|---|---|
| `schools` | escola Inep | Identidade estável e município atual observado. |
| `school_versions` | escola/ano/release | Nome, município, situação, dependência, localização e infraestrutura declarada; histórico não é sobrescrito. |
| `education_enrollments` | escola/ano/etapa/release | Total agregado ou `NULL` com estado de disponibilidade. |
| `education_metrics` | município/ano/indicador/rede/etapa/release | Ideb, rendimento e componentes Saeb; médias agregadas Saeb 2023; alunos considerados e valores previstos PNAE 2024, exatamente como publicados, inclusive supressão. |
| `education_networks`, `education_dependencies`, `education_stages` | dimensão | Vocabulários explícitos; rede pública agregada não é confundida com dependência administrativa. |

Os fatos educacionais só são consultados quando seu `publication_releases.status` é `published`.
Não há tabela de aluno ou profissional, nem armazenamento de contatos/endereço/CNPJ escolar.
As métricas PNAE usam os códigos de ação como etapa técnica. Categorias podem se sobrepor (por
exemplo, AEE), portanto quantidades de alunos não devem ser somadas como pessoas únicas. Valores
financeiros são previsão de repasse, não pagamento nem despesa executada.

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

## Saúde municipal

| Tabela | Grão e campos centrais | Semântica pública |
|---|---|---|
| `health_establishments` | versão do estabelecimento CNES, município, tipo, vínculo SUS, situação e referência | cadastro administrativo; não prova atendimento ou operação em tempo real |
| `health_beds` | versão por estabelecimento/tipo de leito/referência, leitos existentes e SUS | o recurso homologado publica o total por hospital; capacidade cadastrada não é disponibilidade ou ocupação |
| `health_services` | versão por estabelecimento/serviço/classificação/referência | serviço cadastrado; não é produção realizada |
| `health_production` | município/período/tipo assistencial/procedimento/tipo de estabelecimento/setor SUS | quantidade e valor aprovado agregados; não representa pessoas únicas |
| `health_epidemiology` | município/período/indicador/base territorial/categoria ou faixa etária | contagem agregada; `NULL` com `suppressed` para células 1–4 |

As tabelas usam `(source_system, source_key, revision)` para histórico e `snapshot_id` para
rastreabilidade. `sim_deaths_residence` conta óbitos não fetais segundo residência; não equivale a
casos notificados, confirmados, incidência ou prevalência. Não há cruzamento publicado entre
capítulo CID-10 e faixa etária.

| Tabela | Campos | Semântica |
|---|---|---|
| `ingestion_runs` | início/fim, status, recebidos/aceitos/rejeitados, checksum, erro | Uma execução auditável por dataset. Erros são sanitizados antes da exposição pública. |
| `ingestion_jobs` | chave, parâmetros, checkpoint, lock, tentativas e último sucesso | Trabalho persistente por recurso/lote; suporta retomada e impede execução concorrente. |
| `data_quality_issues` | código, severidade, detalhes, status | Divergência de schema/domínio/valor ligada à execução. |

## Estados públicos do catálogo

| Estado | Regra pública |
|---|---|
| `discovered` | Fonte candidata registrada; recurso, licença e resposta ainda podem não ter sido verificados. |
| `pending_review` | Recurso ou conector em revisão explícita. |
| `integrated` | Conector implementado/ativo, mas sem observação publicada para o recorte consultado. |
| `published` | Há observação persistida com snapshot e proveniência; não decorre apenas de flag cadastral. |
| `stale` | Integração degradada ou publicação marcada como desatualizada. |
| `restricted` | Reuso ou acesso possui restrição registrada. |
| `unavailable` | Fonte ou conector está indisponível/falhou. |

A pesquisa normaliza acentos com `translate(lower(...))` no PostgreSQL e usa índices GIN com
`pg_trgm` para nomes municipais, títulos, provedores, indicadores e entradas do catálogo.

## Indicadores iniciais

| Código | Unidade | Escopo | Regra |
|---|---|---|---|
| `population_estimated` | pessoas | `{}` | Variável SIDRA `9324`, tabela `6579`; não é censo nem projeção própria. |
| `revenue_realized` | BRL nominal | demonstrativo, anexo, período bimestral, conta e coluna | RREO Anexo 01, `ReceitasExcetoIntraOrcamentarias`, coluna `Até o Bimestre (c)`. |
| `expense_committed` | BRL nominal | idem | `DespesasExcetoIntraOrcamentarias`, coluna `DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)`. |
| `expense_liquidated` | BRL nominal | idem | Coluna `DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)`. |
| `expense_paid` | BRL nominal | idem | Coluna `DESPESAS PAGAS ATÉ O BIMESTRE (j)`. |
| `cnes_establishments_registered` | estabelecimentos | município e status do cadastro | Quantidade de linhas do arquivo corrente para o código CNES reconciliado; não mede atendimentos ou qualidade. |
| `cnes_establishments_without_disable_reason` | estabelecimentos | `CO_MOTIVO_DESAB` vazio | Contagem descritiva do cadastro; o rótulo não equivale a auditoria operacional de atividade. |
| `cnes_establishments_sus_ambulatory` | estabelecimentos | `CO_AMBULATORIAL_SUS=SIM` | Cadastro informa atendimento ambulatorial SUS; não mede produção ou tempo de espera. |

## Regras obrigatórias

- `NULL != 0`: conversão vazia gera ausência/rejeição, nunca zero automático.
- Fases fiscais não são somadas nem apresentadas como intercambiáveis.
- Valores monetários usam `Decimal`/`NUMERIC(24, 6)` e são BRL nominais, sem correção inflacionária.
- O código CNES de município usa seis dígitos no arquivo; o armazenamento usa o código IBGE
  canônico de sete. A sincronização materializa um crosswalk explícito e verifica colisões; o parser
  nunca trunca códigos recebidos para inferir a identidade.
- O recurso CNES de 09/10/2026 contém bytes Latin-1/Windows-1252 e não declara charset no `Content-Type`; o parser usa Latin-1 estrito e valida o cabeçalho antes de agregar.
- Dados CNES do MVP são agregados antes da persistência; nomes, endereços, telefones, e-mails e CNPJs não são copiados para o banco.
- SIA/SUS usa `PA_QTDAPR` e `PA_VALAPR` por município do estabelecimento executor; SIH/SUS
  conta linhas de AIH e soma `VAL_TOT` por município do atendimento. A competência homologada é
  dezembro de 2025 e não deve ser interpretada como acumulado anual.
- `ans_health_plan_beneficiary_links` soma vínculos no arquivo municipal ANS;
  vínculo não equivale a pessoa única, atendimento ou cobertura efetiva.
- Datas de referência, captura e publicação são campos separados.
