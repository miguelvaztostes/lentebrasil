# Auditoria de transparência e contratações — 22/10/2026

Este relatório distingue descoberta, verificação, conector, validação e publicação. O inventário
nacional é uma lista de candidatos e não comprova integração.

## Recursos verificados

| Recurso | Evidência verificada | Estado |
|---|---|---|
| PNCP OpenAPI e modalidades | Contratos de `/v1/contratacoes/publicacao`, `/atualizacao`, `/v1/contratos` e `/atualizacao`; 19 modalidades ativas. Consulta pública sem autenticação. | Conector implementado. |
| PNCP, Ribeirão, modalidade 8, 01–22/10/2026 | 58 contratações em 2 páginas de 50; amostras `56024581000156-1-000424/2026` (R$ 950.000,00) e `63025530000104-1-003897/2026` (R$ 15.739,46). | Recurso validado; publicação depende da carga no banco-alvo. |
| Siconfi RGF 2025/3, Anexo 01 | 165 linhas oficiais para ente `3543402`. | Conector implementado por ente/exercício/período/anexo. |
| Siconfi DCA 2024, Anexo I-AB | 172 linhas oficiais para ente `3543402`. | Conector implementado por ente/exercício/anexo. |
| TCE-SP receitas 2025 | ZIP 35.462.775 bytes; SHA-256 `16df083d2088127108957a028f6c824265813c74542f528108526b44a392b84b`; CSV `;`/CP1252 com 18 campos. | Conector implementado em streaming para municípios selecionados. |
| TCE-SP despesas por município/mês | API oficial respondeu para Ribeirão Preto em janeiro/2025 com 7.559 linhas e cinco eventos. | Conector implementado com agregação em memória e descarte de fornecedor/identificador antes do snapshot. |

As amostras TCE-SP `43685502`, `43685503` e `43685504`, janeiro/2025, foram conferidas como
R$ 6.798.979,01, R$ 266.487,61 e R$ 29.021,88. Cada rubrica é preservada; TCE-SP não é somado ao
Siconfi e mês individual não é equiparado a período acumulado.

## Pendências verificáveis

- O ZIP nacional TCE-SP de despesas 2025 mede 2.104.704.991 bytes. Ele não é baixado pelo
  conector: a API oficial por município/mês reduz o recorte e permite separar as fases.
- O ZIP mensal TCE-SP de licitações contém participantes e identificadores. Não foi ingerido:
  PNCP cobre o primeiro recorte e não há regra homologada para deduplicar as fontes.
- O endpoint PNCP de atas por atualização respondeu com 39 registros para o CNPJ municipal de
  Ribeirão Preto entre 01–22/10/2026. O PCA respondeu `204` no mesmo recorte; ausência não foi
  convertida em zero. Ambos estão verificados, mas ainda não compõem os totais da visão geral.
- CGU exige token gov.br. Sem token autorizado, permanece `restricted`; nenhum segredo foi inventado.
- Fornecedores PNCP não são expostos. O modelo exige revisão de CPF, CNPJ de MEI e outros dados pessoais.
- PNAE/FNDE publica previsão educacional; não é tratado como pagamento ou somado às transferências.
- O portal municipal auditado não apresentou exportação estruturada estável e permitida.

## Controles

- URLs são constantes oficiais com HTTPS, whitelist de host, limite de tamanho e validação de schema/ZIP.
- PNCP usa janela, teto de requisições, paginação conferida e checkpoint por atualização.
- Quantias usam `Decimal`/`NUMERIC(24,6)`; vazio é `NULL`, nunca zero.
- Snapshots guardam URL, hash e horário. Mudança cria revisão; schema alterado bloqueia a carga.
- Exportações exigem recorte municipal e têm máximo de 10.000 linhas.
- A visão geral usa somente receita e despesa TCE-SP dentro do mesmo ano/mês; Siconfi aparece em
  demonstrativos separados. Reforço e anulação são exibidos, não compensados silenciosamente.
