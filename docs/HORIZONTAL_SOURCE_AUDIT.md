# Auditoria horizontal de fontes

Auditoria executada em 24/10/2026. O inventário recebido contém 165 registros, 16 áreas e
95 indicadores candidatos. Ele é uma fila de descoberta: somente uma carga validada com
snapshot, hash, licença/status e período muda uma fonte para `validated_and_published`.

## Matriz completa

`GET /api/v1/catalog/matrix` é a matriz canônica paginada; aceita `area`, `review_status`,
`limit` e `offset`. `GET /api/v1/catalog/matrix.csv` entrega os 165 IDs. Cada linha contém
provedor, URL recebida, tipo/formato, autenticação, prioridade, última checagem, decisão,
bloqueio, responsável interno, dataset e estados do conector/publicação.

Estados permitidos:

- `validated_and_published`: conector homologado e ao menos uma carga publicada;
- `integrated_not_published`: conector existente sem carga publicada;
- `under_review`: recurso candidato ainda sem homologação suficiente;
- `restricted`: token, conta, termos ou privacidade impedem ativação automática;
- `portal_only`: consulta humana/portal sem recurso reproduzível homologado;
- `unavailable`: recurso verificado como indisponível, sem conversão para zero.

Todas as entradas têm `technical_owner=data-platform` e justificativa pública. A classificação
inicial usa apenas metadados do inventário; não transforma uma URL candidata em fonte validada.

## Recursos verificados nesta rodada

| Tema | Evidência oficial verificada | Decisão |
|---|---|---|
| Agricultura | SIDRA/PAM tabela 5457, variáveis 8331, 216, 214, 112 e 215, ano 2024 | Conector `ibge_pam` publicado. Área plantada/destinada, área colhida, quantidade, rendimento médio e valor por produto/município, `Decimal`, unidade e ausência preservados. |
| Território | API IBGE Malhas v3 em GeoJSON | Conector `ibge_boundaries` publicado com CRS EPSG:4674, bbox, hash e revisão. A geometria não produz indicador por interseção automaticamente. |
| Eleições | TSE Resultados 2024 oferece CSV de votação por município/zona sob CC BY | `under_review`: arquivo nacional volumoso e schema eleitoral ainda precisam de homologação e reconciliação de códigos. |
| Legislativo federal | Câmara respondeu na API v2/OpenAPI para proposições; Senado mantém catálogo próprio | `under_review`: dados são federais e não recebem código municipal. Assembleias permanecem separadas por provedor. |
| Segurança SP | SSP-SP publica séries mensais por município e informa a mudança de local de registro para local de ocorrência em julho/2001 | `under_review`: exportação/schema e revisões precisam ser versionados antes de publicar. Sinesp não foi presumido como API municipal aberta. |
| Meio ambiente | TerraBrasilis documenta WMS/WFS/WCS e GeoNetwork | `under_review`: camadas exigem homologação espacial; ponto/polígono não vira média municipal sem regra de interseção documentada. |
| Riscos | Cemaden disponibiliza download mensal por formulário/CAPTCHA/e-mail e dados brutos em UTC | `portal_only`: não há API reproduzível homologada; estação não é média municipal. |
| Defesa civil | MIDR/S2ID oferece consulta; Atlas Digital oferece base completa CSV/XLSX e metodologia | `under_review`: recurso do Atlas é promissor, mas versão, schema e atualização ainda não foram carregados. |
| Cultura | Mapas Culturais declara API para dados públicos; SALIC respondeu em HTTPS | `under_review`: campos de agentes/proponentes exigem revisão LGPD; textos integrais e pessoas não serão importados sem avaliação. |
| Turismo | Cadastur permanece como recurso candidato do portal | `portal_only`: nenhum download versionado foi homologado nesta rodada. |
| Ciência e inovação | MCTI publica indicadores anuais em XLSX, RData e JSON | `under_review`: grande parte é nacional/estadual; nenhuma atribuição municipal foi inferida. |

Câmara, TSE, SSP-SP, TerraBrasilis, Cemaden, S2ID/Atlas, Mapas Culturais/SALIC e MCTI foram
mantidos visíveis na matriz mesmo sem publicação. Não há alegação de cobertura integral.

## Carga real e reconciliação

O recorte controlado usa Ribeirão Preto (`3543402`), Campinas (`3509502`) e São Paulo
(`3550308`):

- PAM 2024: 258 linhas recebidas/aceitas, nenhuma rejeitada, checksum
  `e35fbf28dd5380e23917bd2bec6af979ffdd0d7a3e7847c996b27bd9efbead51`;
- malhas: três GeoJSON aceitos, checksum
  `c794003053cc2936263c848a437b29d41630e988d89a523ad302045ee585b11f`;
- Ribeirão Preto: 86 produtos PAM, dos quais ausência permanece `null`; abacate foi conferido
  como 168 toneladas na resposta oficial;
- malha de Ribeirão Preto: SHA-256
  `8e79a4980621fbee7474e3542d13221921f1871b67f93730a17e6824339a75d4`.

A repetição das duas cargas manteve 258 fatos PAM e três malhas, todos na revisão 1.

### Ampliação PAM para Ribeirão Preto — 27/10/2026

O mesmo recurso oficial SIDRA 5457 foi consultado sem criar nova fonte nem alterar a estrutura
de fatos. O dry-run e a carga publicada receberam 430 linhas (86 produtos × 5 métricas), sem
rejeições, com checksum
`a4b7877661d5c86d77f79f9b31743243cc002f3dc86ca193ea1bca01c6110763`.
As 86 linhas de quantidade já existentes permaneceram idempotentes; as quatro métricas novas
foram adicionadas com chave própria. Para cana-de-açúcar, a resposta oficial e a API local
coincidiram em 37.104 ha plantados, 37.104 ha colhidos, 3.002.604 t, rendimento de
80.924 kg/ha e valor de produção de R$ 405.352 mil. Somar métricas ou produtos distintos não é
usado como total municipal.

## Exportação assíncrona

`POST /api/v1/export-jobs` cria CSV ou Parquet para `observations`, `economy`, `labor`,
`infrastructure`, `agriculture` ou `catalog`. O worker faz streaming em lotes, limita a 250 mil
linhas, converte Parquet com DuckDB limitado a 128 MB, calcula SHA-256 e registra tamanho e
contagem. O solicitante acompanha `GET /api/v1/export-jobs/{id}` e baixa pelo endpoint retornado.

Há três jobs ativos e dez criações/hora por identidade, expiração padrão em 24 horas, recuperação
de lock após 30 minutos e limpeza de artefatos expirados. Os filtros são allowlisted por domínio;
nenhuma URL fornecida pelo usuário é buscada pelo worker.

## Pendências explícitas

- homologar TSE 2024 com processamento streaming e granularidade eleitoral correta;
- decidir recorte federal para Câmara/Senado sem atribuição municipal artificial;
- homologar exportação SSP-SP preservando a quebra metodológica de 2001;
- selecionar camadas TerraBrasilis e uma regra espacial auditável;
- homologar o CSV completo do Atlas de Desastres e sua versão;
- concluir avaliações LGPD/licença de cultura, turismo e CT&I;
- manter portais, recursos restritos e URLs não responsivas apenas no catálogo até evidência
  operacional.
