# Governança, contribuições e curadoria

## Limites do fluxo

`/contribuir/fonte` recebe uma indicação e devolve um protocolo. O request público valida apenas
a sintaxe HTTPS; não resolve DNS, não abre a URL, não executa código e não cria fonte, dataset,
conector, observação ou release. O estado `published` significa somente que o registro da
sugestão foi publicado no fluxo de governança. Publicar dados continua dependendo do pipeline
existente de fonte verificada, snapshot, testes de qualidade e `publication_releases`.

A pesquisa em `/pesquisa` continua gratuita e anônima. Não foi ativada conta de pesquisador,
porque consultas compartilháveis já funcionam por URL e não há, nesta etapa, coleção privada ou
alerta que justifique coletar identidade. `registered_researcher` não possui papel de curadoria.

## Estados e responsabilidades

| Estado | Significado | Papel mínimo para entrar |
|---|---|---|
| `received` | indicação recebida, não verificada | público ou representante verificado |
| `triage` | análise inicial | `curator` |
| `verified` | metadados/evidências conferidos | `curator` |
| `quarantined` | risco ou arquivo isolado | `curator` |
| `approved` | sugestão aprovada, ainda sem publicar dados | `data_steward` |
| `rejected` | indicação recusada com motivo | `curator` |
| `published` | registro da sugestão publicado | `admin` |

Quem submeteu com identidade institucional não pode revisar nem aprovar a própria submissão.
Toda mudança exige motivo, grava revisão e acrescenta evento à cadeia de hashes. O PostgreSQL
bloqueia `UPDATE` e `DELETE` de `audit_events`; retenção e restauração devem preservar a tabela.

## Identidade, RBAC e CSRF

O backoffice usa Bearer OAuth2 validado por introspecção no IdP. Produção deve configurar URL
HTTPS, cliente, segredo, emissor e audiência. O token precisa conter `sub`, expiração, papel e
evidência MFA em `amr` (`mfa`, `otp`, `hwk` ou `webauthn`). O frontend mantém o token somente em
memória. Não há autenticação por cookie; por isso requests sem `Authorization`, inclusive com
cookie forjado, são recusados e não criam superfície CSRF de sessão.

Papéis formam a ordem `curator < data_steward < admin`. O backend aplica o papel em cada
transição, não apenas na interface. Tokens e corpos de submissão não são incluídos nos logs.

## Descoberta e defesa SSRF

O worker consulta somente URLs CKAN previamente configuradas em `CKAN_DISCOVERY_URLS`, cujos
hosts precisam estar na `DISCOVERY_ALLOWED_HOSTS`. Ele exige HTTPS/443, bloqueia credenciais,
loopback, RFC1918, link-local, endereços reservados e redirects fora da allowlist. DNS é conferido
antes e depois da resposta; mudança de conjunto de IPs bloqueia a execução. Respostas têm timeout,
limite de 5 MiB e content type JSON. A defesa de rede deve ser completada em produção por egress
allowlist no runtime: validação em aplicação não substitui isolamento de rede.

Título, licença, URL, ETag, estrutura de recursos e ausência em varredura completa geram diffs na
fila `source_discoveries`. Descoberta nova ou alterada nunca habilita ingestão ou publicação.
O intervalo padrão é diário; `/api/v1/curation/metrics` relata itens pendentes e defasados.

## Organizações e arquivos

Um `data_steward` cadastra a organização. Apenas `admin`, após validação humana de documentação
institucional, verifica organização e representante. Identificador legal é armazenado somente
como HMAC-SHA-256 com segredo do servidor; evidência privada é referenciada por chave e hash. O representante verificado pode
indicar uma API e anexar arquivo apenas à própria submissão.

Uploads aceitos: CSV, JSON, ZIP e XLSX, até 10 MiB por padrão. Nome é normalizado, destino recebe
identificador aleatório e permissões privadas; ZIP traversal, quantidade, tamanho expandido e
taxa de compressão são verificados. O arquivo permanece em `data/quarantine` e nunca é servido.
ClamAV via INSTREAM marca `clean`, `infected` ou `scan_failed`; ausência/falha do scanner mantém
o arquivo sem publicação. Uma submissão com arquivo diferente de `clean` não pode ser aprovada
ou publicada. Mesmo `clean` requer revisão humana de licença, schema, qualidade e
privacidade.

## Privacidade e retenção

Contato é opcional e só é aceito quando `CONTACT_ENCRYPTION_KEY` (Fernet) está configurada.
Opt-in de notificação não envia mensagem nesta versão; falta integrar provedor transacional. O
limitador guarda HMAC de IP e user-agent, nunca IP bruto. Segredos de captcha e fingerprint
default fazem a configuração de produção falhar.

Meta operacional, não garantia contratual: triagem inicial em até cinco dias úteis. Contato de
submissão rejeitada deve ser apagado após 90 dias; eventos de auditoria preservam apenas sujeito
técnico, ação, motivo e hash. Solicitação de acesso, correção, retirada ou relato de dado pessoal
indevido deve registrar protocolo, isolar o recurso, avaliar em curadoria e, se procedente,
retirar o release pelo processo existente antes de responder. O responsável operacional deve
publicar no deploy um canal de privacidade; este repositório não inventa endereço institucional.

## Runbook

1. Verificar `/api/v1/health`, logs `source_discovery_*`, `quarantine_scan_*` e métricas protegidas.
2. Em falha CKAN, manter último metadado e revisar DNS, certificado, allowlist e content type.
3. Em `scan_failed`, não mover nem abrir o arquivo; restaurar ClamAV e reprocessar no worker.
4. Em malware, restringir acesso, preservar hash/evidência e eliminar conforme política interna.
5. Em suspeita de token, revogar no IdP; não há credencial persistida no frontend.
6. Em retirada, registrar motivo e evidência. Rollback do registro retorna `published` para
   `approved`; retirada de dados usa `publication_releases` e nunca apaga a auditoria.
7. Backup deve incluir banco e storage de quarentena separadamente e cifrados. Para restaurar,
   recuperar ambos no mesmo ponto, validar contagem/sequência/hash dos eventos, permissões 0600,
   hashes dos uploads e executar migrações/testes antes de liberar o backoffice.

## Configuração mínima

- `SUBMISSION_CAPTCHA_SECRET`, `SUBMISSION_FINGERPRINT_SECRET` aleatórios;
- `CONTACT_ENCRYPTION_KEY` para aceitar contato opcional;
- `OIDC_INTROSPECTION_URL`, cliente/segredo, emissor e audiência com MFA obrigatório;
- `CKAN_DISCOVERY_URLS` e `DISCOVERY_ALLOWED_HOSTS` exclusivamente oficiais;
- `CLAMAV_HOST`, `CLAMAV_PORT` e volume privado `QUARANTINE_DIR`;
- egress de produção limitado aos hosts oficiais e ao IdP.

Endpoints de curadoria estão no OpenAPI, exigem Bearer e incluem fila, revisões, rollback,
organizações, upload, revisão de descobertas, auditoria e métricas. Nenhum deles é necessário para os GETs
públicos existentes.
