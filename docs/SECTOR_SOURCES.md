# Fontes setoriais — economia, trabalho, social e infraestrutura

Auditoria executada em 24/10/2026. O inventário nacional é uma lista de candidatos; somente os
recursos explicitamente marcados como `implemented` abaixo possuem conector e dados publicados.

## Recursos homologados

| Eixo | IDs | Recurso oficial | Resultado verificado | Decisão |
|---|---|---|---|---|
| Economia | LNT-0028 | SIDRA tabela 5938, variáveis 37, 498, 513, 517, 6575, 525 e 543 | JSON, sem autenticação. PIB total disponível até 2023; VAB setorial completo no recorte validado até 2021. | `implemented`; BRL nominal, anual, sem interpolação mensal. |
| Trabalho | LNT-0029 | FTP MTE `NOVO CAGED/2025/202512/CAGEDMOV202512.7z` | 44.879.645 bytes compactados, 382.538.259 bytes TXT UTF-8; SHA-256 `b6222e474ca881664903dc2ee3f6e6151a6a4b680e5dba08820cd9240c2036e2`. | `implemented`; fluxo mensal por seção CNAE, sem microdados persistidos. |
| Infraestrutura | LNT-0048 e LNT-0119 | SENATRAN, frota por município e tipo, setembro/2026 | XLSX de 737.420 bytes, 5.571 linhas municipais mais cabeçalhos; SHA-256 `889d133da1ee2c301ad9a3e6b41b24fbb94286b4ba483c15cb706775bef5e16a`. | `implemented`; frota registrada, não circulante. |

O CAGED é extraído em diretório temporário, lido linha a linha e removido. A base analítica guarda
somente admissões, desligamentos e saldo agregados por município, competência e seção CNAE. O
PIB em milhares de reais é convertido exatamente para reais com `Decimal`.

## Reconciliação de três municípios

| Município | PIB nominal 2023 | Admissões dez/2025 | Desligamentos dez/2025 | Saldo | Frota set/2026 |
|---|---:|---:|---:|---:|---:|
| Ribeirão Preto/SP | R$ 52.306.820.000 | 9.067 | 12.143 | -3.076 | 631.041 |
| Campinas/SP | R$ 91.968.328.000 | 14.578 | 20.682 | -6.104 | 1.037.057 |
| São Paulo/SP | R$ 1.066.825.105.000 | 177.541 | 238.865 | -61.324 | 10.165.045 |

As três amostras foram conferidas contra os próprios artefatos oficiais, em leitura independente da
API. Para cada município, o saldo CAGED confere com admissões menos desligamentos e o total da
SENATRAN confere com a soma dos tipos. Valores CAGED são movimentações do mês e podem sofrer
revisões; não são estoque de empregos.

## Auditoria dos demais IDs desta onda

| IDs | Situação comprovada em 24/10/2026 | Publicação |
|---|---|---|
| LNT-0030 | RAIS anual no FTP oficial; arquivo grande e schema ainda não homologados. | catálogo apenas |
| LNT-0031 | ISPER é consulta oficial; exportação estável não foi comprovada. | catálogo apenas |
| LNT-0032 | Comex Stat oferece arquivos oficiais; domicílio fiscal não prova origem física. | catálogo apenas |
| LNT-0033 | CNPJ aberto exige revisão de termos, MEI e dados pessoais. | bloqueada |
| LNT-0034, LNT-0155 | SGS/Olinda são índices nacionais; proibida atribuição municipal. | nacional, catálogo apenas |
| LNT-0035, LNT-0158 | PAM/PPM e Censo Agropecuário requerem seleção de tabelas municipais e sigilo estatístico. | catálogo apenas |
| LNT-0043, LNT-0044 | API CGU de Bolsa Família/BPC exige token gov.br não disponível no ambiente. | indisponível, nunca zero |
| LNT-0045, LNT-0110 | VIS DATA/CECAD agregado é público, mas o acesso testado redirecionou para manutenção e não forneceu API/artefato versionado. | indisponível, nunca zero |
| LNT-0046, LNT-0109, LNT-0111 | Censo SUAS exige escolha de edição, recurso e dicionário compatíveis. | catálogo apenas |
| LNT-0047, LNT-0112–LNT-0115 | SINISA 2025, referência 2024, publica planilhas por módulo; schemas e glossários ainda não foram homologados. | catálogo apenas |
| LNT-0049, LNT-0124, LNT-0125 | CKAN ANEEL respondeu; GD contém campos de titular que devem ser descartados e perdas podem não ter grão municipal. | bloqueada até revisão LGPD/grão |
| LNT-0050 | Blocos MUNIC de habitação e mobilidade variam por edição. | catálogo apenas |
| LNT-0116–LNT-0118 | MCMV possui candidatos de download, sem recurso municipal/schema homologado nesta etapa. | catálogo apenas |
| LNT-0120 | Sinistros SENATRAN não foram confundidos com frota; recurso municipal aguarda homologação. | catálogo apenas |
| LNT-0121–LNT-0123 | Anatel exige seleção de exportação, métrica e granularidade municipal compatíveis. | catálogo apenas |
| LNT-0156, LNT-0157 | Produção industrial e pesquisa de serviços não têm automaticamente grão municipal. | catálogo apenas |

Nenhuma consulta pública da API dispara coleta externa. Tokens não são aceitos por query string nem
armazenados no repositório. Arquivos candidatos não obtidos permanecem no catálogo e não aparecem
como cobertura efetiva.
