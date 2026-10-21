# Operação multicípio

## Princípios

- Sincronize a geografia oficial antes de selecionar UFs ou novos municípios.
- Prefira jobs pequenos por fonte, UF/município, período e recurso.
- Nunca use uma visita ao frontend para iniciar coleta externa.
- Ausência continua `unavailable`; zero é persistido somente quando informado pela fonte.
- O inventário nacional candidato não concede automaticamente licença nem ativa conectores.

## Geografia e crosswalks

```bash
docker compose run --rm ingestion python -m ingestion.cli geo-sync
```

O comando busca os endpoints oficiais de UFs e municípios do IBGE, atualiza `municipalities` e
`geo_units`, registra versões cadastrais e cria mapeamentos `IBGE_MUNICIPALITY` e
`CNES_MUNICIPALITY`. O CNES usa o crosswalk persistido; o parser não transforma seis dígitos em
sete durante a leitura.

## Jobs controlados

Exemplo de backfill fiscal pequeno:

```bash
docker compose run --rm ingestion python -m ingestion.cli schedule \
  --source siconfi --uf SP --start-year 2025 --end-year 2025 \
  --periods 6 --max-requests 250
```

Divida uma UF em janelas que respeitem `--max-requests`. Cada combinação município/exercício/
período/anexo corresponde a uma chamada; o adaptador recusa a execução antes da rede quando o teto
for excedido. O worker recupera locks antigos, aplica backoff e mantém o último dado bem-sucedido.

## CNES

O download usa ETag ou `Last-Modified` quando disponível. A primeira resposta da versão é gravada
em arquivo temporário, calculada por SHA-256 e percorrida linha a linha. O arquivo é removido depois
do parser. Somente os agregados municipais não pessoais são mantidos por versão. Uma resposta
`304 Not Modified` encerra um recorte já processado sem recriar observações; um município novo é
materializado a partir desse agregado, sem baixar novamente o ZIP nacional.

Geografias desconhecidas fora do recorte são registradas como aviso de qualidade. Colunas de nome,
e-mail, telefone, endereço e CNPJ não são copiadas para observações nem logs.

## API

- `GET /api/v1/geo/municipios?uf=SP&q=Campinas&limit=50&offset=0`
- `GET /api/v1/municipios/3509502/summary`
- `GET /api/v1/indicators/population_estimated/observations?municipality=3509502`
- `GET /api/v1/dashboard/summary?municipality=3509502` — compatibilidade temporária

Filtros de município, período e objeto `scope` são aplicados no PostgreSQL antes da contagem e da
paginação. Município malformado retorna 400; município inexistente e indicador inexistente retornam
404.
