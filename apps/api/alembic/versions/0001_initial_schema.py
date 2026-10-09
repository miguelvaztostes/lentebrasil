"""Initial catalog, provenance and observation schema.

Revision ID: 0001
Revises: None
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

IBGE_SOURCE = "00000000-0000-4000-8000-000000000001"
SICONFI_SOURCE = "00000000-0000-4000-8000-000000000002"
CNES_SOURCE = "00000000-0000-4000-8000-000000000003"
INEP_SOURCE = "00000000-0000-4000-8000-000000000004"
PMRP_SOURCE = "00000000-0000-4000-8000-000000000005"
CAMARA_SOURCE = "00000000-0000-4000-8000-000000000006"
IR2030_SOURCE = "00000000-0000-4000-8000-000000000007"

IBGE_DATASET = "10000000-0000-4000-8000-000000000001"
SICONFI_DATASET = "10000000-0000-4000-8000-000000000002"
CNES_DATASET = "10000000-0000-4000-8000-000000000003"


def upgrade() -> None:
    op.create_table(
        "municipalities",
        sa.Column("ibge_code", sa.String(length=7), primary_key=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("state", sa.String(length=2), nullable=False),
    )
    op.create_table(
        "sources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False, unique=True),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("license", sa.String(length=200)),
        sa.Column("terms", sa.Text()),
        sa.Column("expected_frequency", sa.String(length=120)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("failure_reason", sa.Text()),
    )
    op.create_index("ix_sources_status", "sources", ["status"])
    op.create_table(
        "datasets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_id", sa.Uuid(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("code", sa.String(length=100), nullable=False, unique=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("granularity", sa.String(length=160), nullable=False),
        sa.Column("update_policy", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_datasets_source_id", "datasets", ["source_id"])
    op.create_index("ix_datasets_domain", "datasets", ["domain"])
    op.create_index("ix_datasets_status", "datasets", ["status"])
    op.create_table(
        "source_snapshots",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=False),
        sa.Column("storage_path", sa.Text()),
        sa.Column("original_format", sa.String(length=40), nullable=False),
        sa.Column("response_headers", sa.JSON(), nullable=False),
    )
    op.create_index("ix_snapshots_dataset", "source_snapshots", ["dataset_id"])
    op.create_index("ix_snapshots_fetched", "source_snapshots", ["fetched_at"])
    op.create_index("ix_snapshots_sha", "source_snapshots", ["sha256"])
    op.create_table(
        "indicators",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(length=120), nullable=False, unique=True),
        sa.Column("label", sa.String(length=240), nullable=False),
        sa.Column("definition", sa.Text(), nullable=False),
        sa.Column("unit", sa.String(length=80), nullable=False),
        sa.Column("periodicity", sa.String(length=80), nullable=False),
        sa.Column("methodology", sa.Text(), nullable=False),
        sa.Column("disaggregation_schema", sa.JSON(), nullable=False),
        sa.Column("limitations", sa.Text(), nullable=False),
        sa.Column("domain", sa.String(length=80), nullable=False),
        sa.Column("direction", sa.String(length=40)),
    )
    op.create_index("ix_indicators_code", "indicators", ["code"])
    op.create_index("ix_indicators_domain", "indicators", ["domain"])
    op.create_table(
        "observations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "municipality_ibge_code",
            sa.String(length=7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("indicator_id", sa.Uuid(), sa.ForeignKey("indicators.id"), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("scope_key", sa.String(length=64), nullable=False),
        sa.Column("value", sa.Numeric(24, 6)),
        sa.Column("availability_status", sa.String(length=40), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("source_reference_at", sa.DateTime(timezone=True)),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "municipality_ibge_code",
            "indicator_id",
            "period_start",
            "period_end",
            "scope_key",
            "revision",
            name="uq_observation_logical_revision",
        ),
    )
    op.create_index("ix_observations_municipality", "observations", ["municipality_ibge_code"])
    op.create_index("ix_observations_indicator", "observations", ["indicator_id"])
    op.create_index("ix_observations_period_start", "observations", ["period_start"])
    op.create_index("ix_observations_period_end", "observations", ["period_end"])
    op.create_index("ix_observations_scope_key", "observations", ["scope_key"])
    op.create_index("ix_observations_status", "observations", ["availability_status"])
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("items_received", sa.Integer(), nullable=False),
        sa.Column("items_accepted", sa.Integer(), nullable=False),
        sa.Column("items_rejected", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64)),
        sa.Column("error_details", sa.Text()),
    )
    op.create_index("ix_runs_dataset", "ingestion_runs", ["dataset_id"])
    op.create_index("ix_runs_started", "ingestion_runs", ["started_at"])
    op.create_index("ix_runs_status", "ingestion_runs", ["status"])
    op.create_table(
        "data_quality_issues",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("run_id", sa.Uuid(), sa.ForeignKey("ingestion_runs.id"), nullable=False),
        sa.Column("issue_code", sa.String(length=120), nullable=False),
        sa.Column("severity", sa.String(length=40), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
    )
    op.create_index("ix_quality_run", "data_quality_issues", ["run_id"])

    now = datetime(2026, 10, 9, tzinfo=UTC)
    municipalities = sa.table(
        "municipalities", sa.column("ibge_code"), sa.column("name"), sa.column("state")
    )
    op.bulk_insert(
        municipalities,
        [{"ibge_code": "3543402", "name": "Ribeirão Preto", "state": "SP"}],
    )

    sources = sa.table(
        "sources",
        sa.column("id", sa.Uuid()),
        sa.column("provider"),
        sa.column("slug"),
        sa.column("source_url"),
        sa.column("license"),
        sa.column("terms"),
        sa.column("expected_frequency"),
        sa.column("status"),
        sa.column("verified_at", sa.DateTime(timezone=True)),
        sa.column("failure_reason"),
    )
    op.bulk_insert(
        sources,
        [
            {
                "id": IBGE_SOURCE,
                "provider": "IBGE",
                "slug": "ibge",
                "source_url": "https://apisidra.ibge.gov.br/values/t/6579/n6/3543402/v/9324/p/last%2010?formato=json",
                "license": "Uso com atribuição; termos específicos a confirmar",
                "terms": (
                    "Fonte oficial. Preservar referência ao IBGE e não alterar a semântica "
                    "da tabela/variável."
                ),
                "expected_frequency": "Anual, conforme publicação do IBGE",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
            },
            {
                "id": SICONFI_SOURCE,
                "provider": "Secretaria do Tesouro Nacional — Siconfi",
                "slug": "siconfi",
                "source_url": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
                "license": "Apache 2.0",
                "terms": "API limita consultas a uma requisição por segundo.",
                "expected_frequency": "Bimestral para RREO",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
            },
            {
                "id": CNES_SOURCE,
                "provider": "Ministério da Saúde — CNES",
                "slug": "cnes",
                "source_url": "https://dadosabertos.saude.gov.br/dataset/cnes-cadastro-nacional-de-estabelecimentos-de-saude",
                "license": "A confirmar por recurso",
                "terms": (
                    "Persistir apenas agregados; não copiar contatos ou identificadores "
                    "de estabelecimentos."
                ),
                "expected_frequency": "Conforme publicação do arquivo corrente",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
            },
            {
                "id": INEP_SOURCE,
                "provider": "INEP — IDEB",
                "slug": "inep-ideb",
                "source_url": "https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados",
                "license": "A confirmar por arquivo",
                "terms": "Importação somente após validar arquivo, abas, redes e etapas.",
                "expected_frequency": "Bienal, conforme publicação",
                "status": "requires_manual_import",
                "verified_at": now,
                "failure_reason": (
                    "Link direto do arquivo municipal não exposto no HTML estático auditado."
                ),
            },
            {
                "id": PMRP_SOURCE,
                "provider": "Prefeitura Municipal de Ribeirão Preto",
                "slug": "pmrp-transparencia",
                "source_url": "https://www.ribeiraopreto.sp.gov.br/portal/transparencia/orcamento",
                "license": "Não declarada na página auditada",
                "terms": (
                    "Não realizar scraping frágil; usar exportação oficial ou importação "
                    "supervisionada."
                ),
                "expected_frequency": "A confirmar",
                "status": "requires_manual_import",
                "verified_at": now,
                "failure_reason": (
                    "Página oferece PDFs e consultas, mas nenhum download tabular foi confirmado."
                ),
            },
            {
                "id": CAMARA_SOURCE,
                "provider": "Câmara Municipal de Ribeirão Preto",
                "slug": "camara-ribeirao",
                "source_url": "https://www.camararibeiraopreto.sp.gov.br/",
                "license": None,
                "terms": "Não presumir API ou votos nominais estruturados.",
                "expected_frequency": "A confirmar",
                "status": "pending",
                "verified_at": now,
                "failure_reason": "Discovery estruturado pendente.",
            },
            {
                "id": IR2030_SOURCE,
                "provider": "Instituto Ribeirão 2030",
                "slug": "ribeirao-2030",
                "source_url": "https://www.ribeirao2030.com.br/publicacoes/plano-de-cidade-2020-2030/",
                "license": "Uso como referência, com atribuição",
                "terms": "Referência contextual; não implica parceria ou adoção oficial.",
                "expected_frequency": "Curadoria manual",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
            },
        ],
    )

    datasets = sa.table(
        "datasets",
        sa.column("id", sa.Uuid()),
        sa.column("source_id", sa.Uuid()),
        sa.column("code"),
        sa.column("title"),
        sa.column("description"),
        sa.column("domain"),
        sa.column("granularity"),
        sa.column("update_policy"),
        sa.column("status"),
    )
    op.bulk_insert(
        datasets,
        [
            {
                "id": IBGE_DATASET,
                "source_id": IBGE_SOURCE,
                "code": "ibge_population",
                "title": "Estimativas da população residente",
                "description": "Tabela SIDRA 6579, variável 9324, para o município.",
                "domain": "desenvolvimento",
                "granularity": "Município/ano",
                "update_policy": "Atualizar após nova publicação anual",
                "status": "confirmed",
            },
            {
                "id": SICONFI_DATASET,
                "source_id": SICONFI_SOURCE,
                "code": "siconfi_rreo",
                "title": "RREO — Anexo 01",
                "description": (
                    "Receitas e despesas orçamentárias municipais com fases preservadas."
                ),
                "domain": "transparencia",
                "granularity": "Município/exercício/bimestre/conta/coluna",
                "update_policy": "Atualizar bimestralmente após homologação",
                "status": "confirmed",
            },
            {
                "id": CNES_DATASET,
                "source_id": CNES_SOURCE,
                "code": "cnes_establishments",
                "title": "Cadastro Nacional de Estabelecimentos de Saúde",
                "description": "Contagens agregadas do arquivo corrente de estabelecimentos.",
                "domain": "saude",
                "granularity": "Município/data do arquivo",
                "update_policy": "Atualizar quando ETag ou Last-Modified mudar",
                "status": "confirmed",
            },
        ],
    )

    indicators = sa.table(
        "indicators",
        sa.column("id", sa.Uuid()),
        sa.column("code"),
        sa.column("label"),
        sa.column("definition"),
        sa.column("unit"),
        sa.column("periodicity"),
        sa.column("methodology"),
        sa.column("disaggregation_schema", sa.JSON()),
        sa.column("limitations"),
        sa.column("domain"),
        sa.column("direction"),
    )
    rows = [
        (
            "20000000-0000-4000-8000-000000000001",
            "population_estimated",
            "População estimada",
            "População residente estimada pelo IBGE para o ano de referência.",
            "pessoas",
            "anual",
            "SIDRA tabela 6579, variável 9324, nível município 3543402.",
            {},
            "Estimativa anual; não equivale ao Censo nem é uma projeção produzida pela plataforma.",
            "desenvolvimento",
        ),
        (
            "20000000-0000-4000-8000-000000000002",
            "revenue_realized",
            "Receita realizada",
            "Receitas, exceto intraorçamentárias, realizadas até o 6º bimestre.",
            "BRL nominal",
            "anual",
            "RREO Anexo 01, conta ReceitasExcetoIntraOrcamentarias, coluna Até o Bimestre (c).",
            {"required": ["demonstrativo", "anexo", "periodo", "conta", "coluna"]},
            "Valor nominal informado pelo ente ao Siconfi; sujeito a retificações.",
            "transparencia",
        ),
        (
            "20000000-0000-4000-8000-000000000003",
            "expense_committed",
            "Despesa empenhada",
            "Despesas, exceto intraorçamentárias, empenhadas até o 6º bimestre.",
            "BRL nominal",
            "anual",
            "RREO Anexo 01, coluna DESPESAS EMPENHADAS ATÉ O BIMESTRE (f).",
            {"required": ["demonstrativo", "anexo", "periodo", "conta", "coluna"]},
            "Não somar com liquidação ou pagamento; fases representam estágios distintos.",
            "transparencia",
        ),
        (
            "20000000-0000-4000-8000-000000000004",
            "expense_liquidated",
            "Despesa liquidada",
            "Despesas, exceto intraorçamentárias, liquidadas até o 6º bimestre.",
            "BRL nominal",
            "anual",
            "RREO Anexo 01, coluna DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h).",
            {"required": ["demonstrativo", "anexo", "periodo", "conta", "coluna"]},
            "Não somar com empenho ou pagamento; fases representam estágios distintos.",
            "transparencia",
        ),
        (
            "20000000-0000-4000-8000-000000000005",
            "expense_paid",
            "Despesa paga",
            "Despesas, exceto intraorçamentárias, pagas até o 6º bimestre.",
            "BRL nominal",
            "anual",
            "RREO Anexo 01, coluna DESPESAS PAGAS ATÉ O BIMESTRE (j).",
            {"required": ["demonstrativo", "anexo", "periodo", "conta", "coluna"]},
            "Não somar com empenho ou liquidação; fases representam estágios distintos.",
            "transparencia",
        ),
        (
            "20000000-0000-4000-8000-000000000006",
            "cnes_establishments_registered",
            "Estabelecimentos cadastrados no CNES",
            "Linhas do arquivo corrente do CNES associadas ao município.",
            "estabelecimentos",
            "conforme publicação",
            "Contagem de CO_IBGE=354340 no CSV oficial corrente.",
            {"required": ["record_status"]},
            "Cadastro não mede atendimento, capacidade efetiva, qualidade ou tempo de espera.",
            "saude",
        ),
        (
            "20000000-0000-4000-8000-000000000007",
            "cnes_establishments_without_disable_reason",
            "Cadastros sem motivo de desabilitação",
            "Registros do município cujo campo CO_MOTIVO_DESAB está vazio.",
            "estabelecimentos",
            "conforme publicação",
            "Filtro CO_IBGE=354340 e CO_MOTIVO_DESAB vazio.",
            {"required": ["record_status"]},
            "Ausência do código não substitui auditoria de funcionamento do estabelecimento.",
            "saude",
        ),
        (
            "20000000-0000-4000-8000-000000000008",
            "cnes_establishments_sus_ambulatory",
            "Cadastros com atendimento ambulatorial SUS",
            "Registros cujo campo CO_AMBULATORIAL_SUS informa SIM.",
            "estabelecimentos",
            "conforme publicação",
            "Filtro CO_IBGE=354340 e CO_AMBULATORIAL_SUS=SIM.",
            {"required": ["sus_ambulatory"]},
            "Cadastro declarado; não mede produção, acesso ou qualidade do atendimento.",
            "saude",
        ),
    ]
    op.bulk_insert(
        indicators,
        [
            {
                "id": row[0],
                "code": row[1],
                "label": row[2],
                "definition": row[3],
                "unit": row[4],
                "periodicity": row[5],
                "methodology": row[6],
                "disaggregation_schema": row[7],
                "limitations": row[8],
                "domain": row[9],
                "direction": None,
            }
            for row in rows
        ],
    )


def downgrade() -> None:
    op.drop_table("data_quality_issues")
    op.drop_table("ingestion_runs")
    op.drop_table("observations")
    op.drop_table("indicators")
    op.drop_table("source_snapshots")
    op.drop_table("datasets")
    op.drop_table("sources")
    op.drop_table("municipalities")
