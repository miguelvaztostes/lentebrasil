# Pesquisa pública avançada

As rotas `/pesquisa` e `/comparar` expõem, em uma interface única, os fatos municipais já publicados nas tabelas operacionais. Elas não transformam entradas do inventário de candidatos em dados disponíveis.

## Contrato de compatibilidade

Uma série só é desenhada quando o recorte usa o mesmo indicador, unidade e `scope_key`. O `scope_key` deriva das dimensões originais — por exemplo, atividade econômica, seção CNAE, produto agrícola, tipo de leito, procedimento, fase fiscal ou conta. O comparador também exige a mesma referência temporal. Não há soma automática entre fases contábeis, bases assistenciais ou categorias sobrepostas.

Os estados de cobertura são `published`, `suppressed`, `incompatible_period`, `outside_coverage` e `source_identified_no_connector`. Ausência e sigilo nunca são convertidos em zero.

## Famílias expostas

O dicionário `/api/v1/research/indicators` é gerado das tabelas `observations`, `economy_facts`, `labor_facts`, `infrastructure_facts`, `agriculture_facts`, `education_metrics`, `education_enrollments`, `health_establishments`, `health_beds`, `health_services`, `health_production`, `health_epidemiology`, `fiscal_statements`, `procurements`, `contracts`, `transfers` e `social_benefit_facts`.

Cada linha devolve período, território, valor/estado, unidade, escopo, dataset, provedor, licença, URL do documento, hash SHA-256, datas de publicação/coleta e revisão. Somente a revisão mais recente da chave lógica entra na consulta.

## API e exportações

- `GET /api/v1/research/indicators`: dicionário e contagens efetivas por domínio;
- `GET /api/v1/research/series`: série paginada, até oito municípios;
- `GET /api/v1/compare`: valida compatibilidade antes de retornar a comparação;
- `GET /api/v1/coverage`: explica cobertura e ausência por território;
- `GET /api/v1/research/export.csv` e `.json`: até 10 mil linhas;
- `POST /api/v1/export-jobs`, com `domain=research`: CSV ou Parquet assíncrono, com quota e limite de 250 mil linhas;
- `POST /api/v1/research/queries`: salva somente parâmetros canônicos anônimos e devolve URL reproduzível; novas combinações têm quota global de 120 por hora.

Não são armazenados nome, e-mail, IP bruto ou conta de usuário nas consultas salvas. Jobs de exportação usam hash do cliente para quota e autorização do download.

## Mapa

O mapa consulta `/api/v1/geo/boundaries/{codigo}` e desenha apenas a malha municipal oficial publicada. Município sem geometria homologada recebe aviso; não há contorno estimado.
