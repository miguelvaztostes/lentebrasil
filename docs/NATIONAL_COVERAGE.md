# Cobertura nacional e implantação controlada

Este documento separa capacidade do conector, validação local e publicação em
produção. Um conector aceitar `--national` não significa que seus dados já estejam
publicados para todos os municípios.

## Evidência local de 30/10/2026

| Tema | Fonte oficial | Capacidade nacional | Validação local |
| --- | --- | --- | --- |
| Desenvolvimento | IBGE SIDRA 6579 | lotes de até 100 municípios | 11.142 observações de 2024–2025; 5.571 municípios |
| Economia | IBGE SIDRA 5938 | lotes de até 100 municípios | PIB total 2023 para 5.570 municípios e indisponibilidade explícita para o município ausente na edição histórica |
| Ciência e inovação | IBGE MUNIC 2024 | arquivo nacional | 22.284 observações; 5.571 municípios |
| Gestão pública | IBGE MUNIC 2024 | arquivo nacional | 11.142 observações; 5.571 municípios |
| Cultura e turismo | IBGE MUNIC 2021 | arquivo nacional | 33.426 observações; 5.571 municípios |
| Participação e democracia | IBGE MUNIC 2021 | arquivo nacional | cobertura municipal validada; indicador compartilhado não é duplicado |
| Meio ambiente e riscos | IBGE MUNIC 2020 | arquivo nacional | 50.139 observações; 5.571 municípios |
| Proteção social | IBGE MUNIC 2023 | arquivo nacional | 22.284 observações; 5.571 municípios |
| Segurança pública | IBGE MUNIC 2023 | arquivo nacional | 27.855 observações; 5.571 municípios |
| Educação | Inep Censo Escolar 2024 | arquivo nacional | 215.545 escolas e 1.939.905 linhas agregadas de matrículas; 5.570 municípios presentes na edição |
| Representação política | TSE candidaturas e bens 2024 | conector nacional por arquivo oficial | carga controlada de Ribeirão Preto: 422 candidaturas, 23 mandatos eleitos e 805 agregados patrimoniais; segunda execução idempotente |
| Saúde — rede cadastrada | CNES estabelecimentos | arquivo nacional agregado antes da persistência | 16.713 observações; 5.571 municípios; cadastro não equivale a atendimento ou disponibilidade real |

As cargas acima foram executadas somente no Docker local. Elas não autorizam nem
comprovam publicação na VM. A promoção exige backup, teste de migração, health
check e consulta de amostras após o deploy.

### Limitação temporal do PIB

A tabela SIDRA 5938 publica PIB total para 2022 e 2023, mas retorna ausência
oficial (`...`) para as parcelas de valor adicionado nesses anos. A composição
setorial mais recente efetivamente disponível nessa tabela é 2021. A API deve
mostrar os períodos separadamente e nunca preencher a composição ausente com zero.

## Conectores nacionais ainda sem carga completa

| Tema | Conjuntos implementados | Estratégia de implantação |
| --- | --- | --- |
| Educação | Ideb, Saeb e PNAE | completar as cargas nacionais e reconciliar amostras; o Censo Escolar 2024 já foi carregado e medido localmente |
| Saúde | leitos, serviços, SIM, SINASC, SIA, SIH, SIOPS e ANS | processar um conjunto por vez e publicar somente após reconciliação das amostras; CNES agregado já possui carga local nacional |
| Finanças | Siconfi RREO/RGF/DCA | agendar um município/exercício/período/anexo por job; nunca executar milhares de chamadas em request web |
| Contratações | PNCP | janelas curtas por data de atualização, paginação e checkpoint; não atribuir contratação sem município comprovado |
| Trabalho | Novo CAGED | arquivo nacional mensal, streaming e recorte por código oficial |
| Agropecuária | PAM/SIDRA | lotes de até 100 municípios e indisponibilidade preservada |
| Infraestrutura | Senatran | arquivo nacional por competência; frota registrada não equivale a circulação |

## Sequência operacional

1. Executar e reconciliar uma fonte por vez no Docker local.
2. Conferir três amostras, incluindo uma capital, um município pequeno e um caso
   indisponível.
3. Medir tempo, memória, volume persistido e idempotência da segunda execução.
4. Fazer backup do PostgreSQL e dos volumes de dados brutos na VM.
5. Promover a imagem sem alterar o banco, executar migrações e health checks.
6. Rodar a carga como job separado, sem reiniciar o frontend ou bloquear a API.
7. Publicar cobertura somente após contagens e amostras pós-carga.

## Comandos de referência local

```bash
docker compose run --rm --no-deps ingestion python -m ingestion.cli ingest \
  --source ibge --national --start-year 2024 --end-year 2025 --batch-size 100

docker compose run --rm --no-deps ingestion python -m ingestion.cli ingest \
  --source ibge_pib --national --start-year 2021 --end-year 2023 --batch-size 100

docker compose run --rm --no-deps ingestion python -m ingestion.cli ingest \
  --source ibge_munic_culture --national
```

Para Siconfi, use `schedule --national` com um único exercício, período e anexo.
O CLI decompõe a seleção em jobs unitários retomáveis. A opção
`--source all --national` permanece bloqueada para evitar uma carga acidental e
não dimensionada.
