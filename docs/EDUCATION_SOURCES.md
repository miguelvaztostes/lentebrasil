# Fontes de educação — auditoria e integrações homologadas

Auditoria executada em 21/10/2026. “Verificado” significa que a página oficial e o artefato
concreto responderam e que seu formato foi inspecionado; não significa que todos os recursos do
mesmo portal foram homologados. Decisões também ficam em `catalog_entries` com justificativa e
data. Requests públicos da API consultam somente PostgreSQL e nunca acionam o Inep/FNDE.

## Recursos homologados

| ID | Decisão | Recurso oficial | Evidência técnica | Cobertura implementada |
|---|---|---|---|---|
| LNT-0007 | `integrate` | [Censo Escolar](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar), arquivo `microdados_censo_escolar_2024.zip` | ZIP/CSV Windows-1252, `;`, 426 colunas; 33.829.396 bytes; SHA-256 `ae29d81d45ddecef59e11eda39788cbfd30dfa1cc71be9d29f23051fc2d640db` | Ano 2024, lote municipal/UF; escola, dependência, situação, infraestrutura publicável e matrículas agregadas por etapa. |
| LNT-0009 | `integrate` | [Ideb 2005–2025](https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados/2005-2025), arquivo `divulgacao_anos_iniciais_municipios_2025.zip` | ZIP/XLSX, cabeçalho máquina na linha 10, 14.547 linhas e 133 colunas; 25.308.289 bytes; SHA-256 `89100286327ab07a4b1318ba51974d62da90af334f663bedf6374cb67298a3e7` | Ano 2025, anos iniciais, município/rede; Ideb, rendimento e componentes Saeb. `-`, `...`, `NA` e vazio permanecem suprimidos. |
| LNT-0010 | `integrate` | [Saeb 2023](https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/saeb/resultados/2023), arquivo `planilha_de_resultados_2023.rar` | RAR com XLSB municipal, 69.053 linhas e 113 colunas; 8.413.247 bytes; SHA-256 `acf3066b192298574a4a7ceaacd83b46d05193062077dcc66ffdb0da6f61b113` | Ano 2023; médias agregadas de Língua Portuguesa e Matemática no 5º ano, 9º ano e 3ª/4ª série do ensino médio, por rede. Somente localização total evita dupla contagem de urbano/rural. |
| LNT-0081 | `integrate` | [PNAE — repasses por entidade executora](https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/programas/pnae/consultas/repasses-financeiros-por-entidade-executora), planilha municipal/estadual de 2024 | XLSX, cabeçalho na linha 5, 26.300 linhas; 920.689 bytes; SHA-256 `fc5eecb6d23bddf186301105a66c1f134c9892150e2889641f8f9a41ff194c5c` | Ano 2024; quantidade de alunos considerada e valor previsto por ação para prefeituras. Não equivale a pagamento nem despesa executada. |

URLs diretas executadas pelos conectores são constantes versionadas sob
`https://download.inep.gov.br/` e `https://www.gov.br/fnde/`. Redirecionamento para host não
permitido é bloqueado, o download tem limite de tamanho, usa arquivo de staging e valida
caminhos e tamanho descompactado antes do parse. O RAR do Saeb exige `libarchive` na imagem; o
parser lê o XLSB em streaming e não carrega microdados individuais.

## Decisões do inventário educacional

| IDs | Decisão | Justificativa resumida |
|---|---|---|
| LNT-0008 | `metadata_only` | Catálogo de Escolas localizado, mas exportação oficial estável ainda não homologada; o Censo fornece o cadastro escolar desta onda. |
| LNT-0011, LNT-0075–LNT-0080 | `manual_review` | Indicadores educacionais, rendimento, distorção, INSE, docentes, turma/horas e sinopses exigem validação por edição e dicionário. |
| LNT-0012 | `metadata_only` | Entrada geral do FNDE preservada como catálogo; cada programa recebe decisão própria. |
| LNT-0082–LNT-0084 | `manual_review` | PDDE, PNATE e Obras permanecem separados e ainda exigem recurso estruturado, grão e licença homologados. |
| LNT-0013, LNT-0014, LNT-0085 | `manual_review` | Educação superior/Enade ficam no backlog até confirmar granularidade municipal e dimensões publicáveis. |
| LNT-0015 | `restricted` | Enem exige avaliação LGPD; não haverá publicação individual. |
| LNT-0016 | `metadata_only` | QEdu é terceiro; autenticação e licença de redistribuição não foram homologadas. |

As razões completas e individuais estão versionadas em
`apps/api/src/lente_api/education_decisions.py`. Nenhum ID pendente exibe números.

## Privacidade, reconciliação e publicação

- O parser do Censo usa lista positiva de campos. Telefone, endereço, e-mail, CNPJ e qualquer
  dimensão individual de aluno/profissional não entram no objeto normalizado nem no banco.
- Código Inep tem oito dígitos e é reconciliado ao código IBGE municipal de sete dígitos já
  cadastrado. Escola e seus atributos são historizados por ano e release.
- Um release só se torna público depois de parse e validação. A troca de release e a gravação dos
  fatos ocorrem na mesma transação; falha preserva o release anterior. O rollback explícito restaura
  o último release retirado.
- Reexecução do mesmo SHA-256 reutiliza snapshot/release e não duplica fatos.
- O Saeb usa apenas resultados já agregados por município; microdados de estudantes, professores
  e diretores não são ingeridos. Supressão e ausência permanecem `NULL`.
- O PNAE reconcilia `UF + nome da prefeitura` com o cadastro IBGE. Ações como AEE podem se
  sobrepor a outras etapas, portanto o portal não soma categorias como se fossem pessoas únicas.
- Totais devem ser confrontados com as sinopses oficiais antes de ampliar um lote para publicação
  nacional. Nesta onda, nenhum total do banco de produção é presumido ou embarcado no Git.

## Evidência da execução descartável

O parser leu os artefatos oficiais completos e selecionou: Campinas, 741 escolas/248.732
matrículas; Ribeirão Preto, 464/141.415; São Paulo, 8.023/2.633.934. O pacote Ideb produziu 15
registros por município. A carga de Ribeirão Preto foi repetida e manteve 464 versões escolares,
4.176 fatos escola/etapa e 15 métricas, demonstrando idempotência por hash/release.

Na extensão Saeb/FNDE, o parser real selecionou 60 métricas Saeb para Campinas, Ribeirão Preto e
São Paulo e 36 métricas PNAE para os mesmos municípios. A publicação descartável de Ribeirão
Preto materializou 18 métricas Saeb e 12 métricas PNAE; a repetição do mesmo snapshot manteve as
contagens. Para o PNAE, os seis valores previstos municipais somam R$ 7.680.903,13, sem inferir
pagamento ou execução.

O download direto do PNAE respondeu no container. O endpoint do Inep continuou indisponível ali
por erro de cadeia de certificado (`CERTIFICATE_VERIFY_FAILED`), inclusive para Saeb. A validação
TLS permaneceu habilitada; nenhuma opção insegura foi adicionada. O RAR oficial foi baixado no
host, verificado por SHA-256 e processado integralmente pelo mesmo parser dentro do container.
