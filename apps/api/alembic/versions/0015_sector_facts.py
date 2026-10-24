"""Add economy, labor, social and infrastructure facts.

Revision ID: 0015
Revises: 0014
"""

# ruff: noqa: E501

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None

SOURCES = (
    (
        UUID("20000000-0000-4000-8000-000000000028"),
        "IBGE — PIB dos Municípios",
        "ibge-pib-municipal",
        "https://apisidra.ibge.gov.br/values/t/5938",
        "ibge_pib_municipal",
        "PIB e valor adicionado municipal — SIDRA 5938",
        "economia-e-trabalho",
        "LNT-0028",
        "anual",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000029"),
        "Ministério do Trabalho e Emprego — Novo CAGED",
        "mte-novo-caged",
        "ftp://ftp.mtps.gov.br/pdet/microdados/NOVO%20CAGED/",
        "novo_caged_movements",
        "Novo CAGED — movimentações formais por município e seção CNAE",
        "economia-e-trabalho",
        "LNT-0029",
        "mensal",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000030"),
        "SENATRAN — frota de veículos",
        "senatran-frota",
        "https://www.gov.br/transportes/pt-br/assuntos/transito/conteudo-Senatran/frota-de-veiculos-2026",
        "senatran_fleet",
        "Frota registrada por município e tipo",
        "infraestrutura-e-cidades",
        "LNT-0119",
        "mensal",
    ),
)


def upgrade() -> None:
    op.create_table(
        "economic_activities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("classification_system", sa.String(40), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("label", sa.String(240), nullable=False),
        sa.Column("level", sa.String(40), nullable=False),
        sa.UniqueConstraint("classification_system", "code", name="uq_economic_activity_code"),
    )
    op.create_index(
        "ix_economic_activities_classification_system",
        "economic_activities",
        ["classification_system"],
    )
    op.create_index("ix_economic_activities_code", "economic_activities", ["code"])
    op.create_table(
        "social_programs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("provider", sa.String(240), nullable=False),
    )
    op.create_index("ix_social_programs_code", "social_programs", ["code"])
    op.create_table(
        "infrastructure_services",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("code", sa.String(100), nullable=False, unique=True),
        sa.Column("label", sa.String(240), nullable=False),
        sa.Column("service_type", sa.String(60), nullable=False),
    )
    op.create_index("ix_infrastructure_services_code", "infrastructure_services", ["code"])
    op.create_index(
        "ix_infrastructure_services_service_type", "infrastructure_services", ["service_type"]
    )
    _fact_tables()
    now = datetime.now(UTC)
    for offset, (
        source_id,
        provider,
        slug,
        url,
        code,
        title,
        domain,
        inventory_id,
        frequency,
    ) in enumerate(SOURCES):
        dataset_id = UUID(f"21000000-0000-4000-8000-{28 + offset:012d}")
        op.execute(
            sa.text(
                """INSERT INTO sources (id, provider, slug, source_url, license, terms, expected_frequency, status, verified_at, source_status, connector_status, catalog_metadata) VALUES (:id,:provider,:slug,:url,'Dados públicos oficiais; atribuição obrigatória ao provedor','Publicação apenas de agregados municipais, sem microdados pessoais.',:frequency,'confirmed',:now,'verified','implemented',CAST(:metadata AS jsonb))"""
            ).bindparams(
                id=source_id,
                provider=provider,
                slug=slug,
                url=url,
                frequency=frequency,
                now=now,
                metadata=f'{{"inventory_id":"{inventory_id}"}}',
            )
        )
        op.execute(
            sa.text(
                """INSERT INTO datasets (id, source_id, code, title, description, domain, granularity, update_policy, status, connector_status, publication_status, catalog_metadata) VALUES (:id,:source,:code,:title,:description,:domain,:granularity,:frequency,'confirmed','implemented','not_published',CAST(:metadata AS jsonb))"""
            ).bindparams(
                id=dataset_id,
                source=source_id,
                code=code,
                title=title,
                description="Recurso oficial homologado, versionado por hash e publicado somente após validação de schema.",
                domain=domain,
                granularity="município/período/métrica/categoria",
                frequency=frequency,
                metadata='{"raw_retention":false}',
            )
        )
        op.execute(
            sa.text(
                """UPDATE catalog_entries SET dataset_id=:dataset, integration_decision='integrate', decision_reason='Recurso oficial verificado e conector homologado', decided_at=now() WHERE external_catalog_id=:inventory"""
            ).bindparams(dataset=dataset_id, inventory=inventory_id)
        )


def _fact_tables() -> None:
    def common() -> list[sa.Column]:
        return [
            sa.Column("id", sa.Uuid(), primary_key=True),
            sa.Column("source_system", sa.String(40), nullable=False),
            sa.Column("source_key", sa.String(240), nullable=False),
            sa.Column(
                "municipality_ibge_code",
                sa.String(7),
                sa.ForeignKey("municipalities.ibge_code"),
                nullable=False,
            ),
            sa.Column("availability_status", sa.String(40), nullable=False),
            sa.Column("source_document_url", sa.Text(), nullable=False),
            sa.Column(
                "snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False
            ),
            sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        ]

    op.create_table(
        "economy_facts",
        *common(),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(100), nullable=False),
        sa.Column("activity_id", sa.Uuid(), sa.ForeignKey("economic_activities.id")),
        sa.Column("value", sa.Numeric(24, 6)),
        sa.Column("unit", sa.String(80), nullable=False),
        sa.Column("price_basis", sa.String(80)),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_economy_fact_revision"
        ),
    )
    op.create_index(
        "ix_economy_fact_municipality_year",
        "economy_facts",
        ["municipality_ibge_code", "reference_year"],
    )
    for col in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "reference_year",
        "metric_code",
        "activity_id",
        "availability_status",
        "snapshot_id",
    ):
        op.create_index(f"ix_economy_facts_{col}", "economy_facts", [col])
    op.create_table(
        "labor_facts",
        *common(),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column(
            "activity_id", sa.Uuid(), sa.ForeignKey("economic_activities.id"), nullable=False
        ),
        sa.Column("admissions", sa.Integer(), nullable=False),
        sa.Column("dismissals", sa.Integer(), nullable=False),
        sa.Column("balance", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_labor_fact_revision"
        ),
    )
    op.create_index(
        "ix_labor_fact_municipality_period",
        "labor_facts",
        ["municipality_ibge_code", "period_start"],
    )
    for col in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "period_start",
        "period_end",
        "activity_id",
        "availability_status",
        "snapshot_id",
    ):
        op.create_index(f"ix_labor_facts_{col}", "labor_facts", [col])
    op.create_table(
        "social_benefit_facts",
        *common(),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("program_id", sa.Uuid(), sa.ForeignKey("social_programs.id"), nullable=False),
        sa.Column("beneficiary_count", sa.Integer()),
        sa.Column("family_count", sa.Integer()),
        sa.Column("amount", sa.Numeric(24, 6)),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_social_benefit_fact_revision"
        ),
    )
    op.create_table(
        "infrastructure_facts",
        *common(),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column(
            "service_id", sa.Uuid(), sa.ForeignKey("infrastructure_services.id"), nullable=False
        ),
        sa.Column("metric_code", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric(24, 6)),
        sa.Column("unit", sa.String(80), nullable=False),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_infrastructure_fact_revision"
        ),
    )
    op.create_index(
        "ix_infrastructure_fact_municipality_date",
        "infrastructure_facts",
        ["municipality_ibge_code", "reference_date"],
    )
    for table in ("social_benefit_facts", "infrastructure_facts"):
        for col in (
            "source_system",
            "source_key",
            "municipality_ibge_code",
            "availability_status",
            "snapshot_id",
        ):
            op.create_index(f"ix_{table}_{col}", table, [col])


def downgrade() -> None:
    connection = op.get_bind()
    for table in ("infrastructure_facts", "social_benefit_facts", "labor_facts", "economy_facts"):
        connection.execute(sa.text(f"DELETE FROM {table}"))
    for offset, (source_id, _, _, _, _, _, _, _, _) in reversed(tuple(enumerate(SOURCES))):
        dataset_id = UUID(f"21000000-0000-4000-8000-{28 + offset:012d}")
        connection.execute(
            sa.text(
                "UPDATE catalog_entries SET dataset_id=NULL, integration_decision='manual_review' WHERE dataset_id=:id"
            ),
            {"id": dataset_id},
        )
        connection.execute(
            sa.text("DELETE FROM source_snapshots WHERE dataset_id=:id"), {"id": dataset_id}
        )
        connection.execute(sa.text("DELETE FROM datasets WHERE id=:id"), {"id": dataset_id})
        connection.execute(sa.text("DELETE FROM sources WHERE id=:id"), {"id": source_id})
    for table in (
        "infrastructure_facts",
        "social_benefit_facts",
        "labor_facts",
        "economy_facts",
        "infrastructure_services",
        "social_programs",
        "economic_activities",
    ):
        op.drop_table(table)
