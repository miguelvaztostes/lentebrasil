"""Add safe municipal health facts and audited SIM mortality.

Revision ID: 0010
Revises: 0009
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

SIM_SOURCE = "20000000-0000-4000-8000-000000000020"
SIM_DATASET = "21000000-0000-4000-8000-000000000020"
SIM_INDICATOR = "22000000-0000-4000-8000-000000000020"


def _fact_columns(*, establishment: bool = False) -> list[sa.Column]:
    columns = [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(240), nullable=False),
    ]
    if establishment:
        columns.append(
            sa.Column(
                "establishment_id",
                sa.Uuid(),
                sa.ForeignKey("health_establishments.id"),
                nullable=False,
            )
        )
    return columns


def upgrade() -> None:
    op.create_table(
        "health_establishments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(160), nullable=False),
        sa.Column("cnes_code", sa.String(7), nullable=False),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("name", sa.String(320), nullable=False),
        sa.Column("facility_type_code", sa.String(40)),
        sa.Column("facility_type_name", sa.String(240)),
        sa.Column("management_scope", sa.String(40)),
        sa.Column("sus_linked", sa.Boolean()),
        sa.Column("active", sa.Boolean()),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_establishment_revision"
        ),
    )
    for column in (
        "source_system",
        "source_key",
        "cnes_code",
        "municipality_ibge_code",
        "facility_type_code",
        "sus_linked",
        "active",
        "reference_date",
        "snapshot_id",
    ):
        op.create_index(f"ix_health_establishments_{column}", "health_establishments", [column])

    op.create_table(
        "health_beds",
        *_fact_columns(establishment=True),
        sa.Column("bed_type_code", sa.String(60), nullable=False),
        sa.Column("bed_type_name", sa.String(240), nullable=False),
        sa.Column("existing_count", sa.Integer()),
        sa.Column("sus_count", sa.Integer()),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_bed_revision"
        ),
    )
    op.create_table(
        "health_services",
        *_fact_columns(establishment=True),
        sa.Column("service_code", sa.String(60), nullable=False),
        sa.Column("service_name", sa.String(320), nullable=False),
        sa.Column("classification_code", sa.String(60)),
        sa.Column("classification_name", sa.String(320)),
        sa.Column("sus_available", sa.Boolean()),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_service_revision"
        ),
    )
    for table in ("health_beds", "health_services"):
        for column in ("source_system", "source_key", "establishment_id", "snapshot_id"):
            op.create_index(f"ix_{table}_{column}", table, [column])

    op.create_table(
        "health_production",
        *_fact_columns(),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("care_type", sa.String(60), nullable=False),
        sa.Column("procedure_code", sa.String(40)),
        sa.Column("procedure_name", sa.String(320)),
        sa.Column("facility_type", sa.String(160)),
        sa.Column("sus_sector", sa.String(80)),
        sa.Column("quantity", sa.Numeric(24, 6)),
        sa.Column("approved_amount", sa.Numeric(24, 6)),
        sa.Column("availability_status", sa.String(40), nullable=False),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_production_revision"
        ),
    )
    for column in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "period_start",
        "period_end",
        "care_type",
        "procedure_code",
        "facility_type",
        "sus_sector",
        "availability_status",
        "snapshot_id",
    ):
        op.create_index(f"ix_health_production_{column}", "health_production", [column])

    op.create_table(
        "health_epidemiology",
        *_fact_columns(),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("indicator_code", sa.String(120), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("geography_basis", sa.String(40), nullable=False),
        sa.Column("category_code", sa.String(80), nullable=False),
        sa.Column("category_name", sa.String(240), nullable=False),
        sa.Column("age_band", sa.String(40), nullable=False),
        sa.Column("count", sa.Integer()),
        sa.Column("availability_status", sa.String(40), nullable=False),
        sa.Column("disclosure_threshold", sa.Integer(), nullable=False),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_health_epidemiology_revision"
        ),
    )
    for column in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "indicator_code",
        "period_start",
        "period_end",
        "geography_basis",
        "category_code",
        "age_band",
        "availability_status",
        "snapshot_id",
    ):
        op.create_index(f"ix_health_epidemiology_{column}", "health_epidemiology", [column])
    op.create_index(
        "ix_health_epidemiology_municipality_period",
        "health_epidemiology",
        ["municipality_ibge_code", "period_start", "period_end"],
    )

    now = datetime.now(UTC)
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
        sa.column("verified_at"),
        sa.column("failure_reason"),
        sa.column("source_status"),
        sa.column("connector_status"),
        sa.column("catalog_metadata", sa.JSON()),
    )
    op.bulk_insert(
        sources,
        [
            {
                "id": SIM_SOURCE,
                "provider": "Ministério da Saúde — SIM",
                "slug": "datasus-sim-mortalidade",
                "source_url": "https://dadosabertos.saude.gov.br/dataset/sim",
                "license": "Dados abertos anonimizados; atribuição ao Ministério da Saúde",
                "terms": (
                    "Publicar somente agregados municipais por residência, com limiar de "
                    "divulgação; não persistir microdados do óbito."
                ),
                "expected_frequency": "anual, com versões preliminares e definitivas",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {
                    "inventory_ids": ["LNT-0020", "LNT-0087", "LNT-0088"],
                    "verified_artifact": "DO24OPEN_csv.zip",
                    "privacy": "municipal aggregates only; disclosure threshold 5",
                },
            }
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
        sa.column("connector_status"),
        sa.column("publication_status"),
        sa.column("catalog_metadata", sa.JSON()),
    )
    op.bulk_insert(
        datasets,
        [
            {
                "id": SIM_DATASET,
                "source_id": SIM_SOURCE,
                "code": "sim_mortality_municipal",
                "title": "SIM — mortalidade municipal por residência",
                "description": (
                    "Óbitos não fetais agregados por município de residência, capítulo CID-10 "
                    "ou faixa etária ampla; células pequenas são suprimidas."
                ),
                "domain": "saude",
                "granularity": "município/ano/categoria agregada",
                "update_policy": "anual após validação do artefato definitivo",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {
                    "inventory_id": "LNT-0020",
                    "reference_year": 2024,
                    "disclosure_threshold": 5,
                },
            }
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
    op.bulk_insert(
        indicators,
        [
            {
                "id": SIM_INDICATOR,
                "code": "sim_deaths_residence",
                "label": "Óbitos registrados no SIM por município de residência",
                "definition": "Óbitos não fetais no ano, segundo município de residência.",
                "unit": "óbitos",
                "periodicity": "anual",
                "methodology": (
                    "Contagem do CSV oficial do SIM, agregada antes da persistência por "
                    "capítulo CID-10 ou faixa etária ampla."
                ),
                "disaggregation_schema": {
                    "category_code": "capítulo CID-10 ou todas as causas",
                    "age_band": "faixa ampla ou todas as idades",
                    "geography_basis": "residência",
                },
                "limitations": (
                    "Registro de mortalidade sujeito a revisão; não é incidência de doença. "
                    "Células menores que cinco não são armazenadas nem publicadas."
                ),
                "domain": "saude",
                "direction": None,
            }
        ],
    )
    op.get_bind().execute(
        sa.text(
            "UPDATE catalog_entries SET dataset_id=:dataset_id, "
            "integration_decision='integrate', decision_reason=:reason, decided_at=now() "
            "WHERE external_catalog_id='LNT-0020'"
        ),
        {
            "dataset_id": SIM_DATASET,
            "reason": (
                "CSV anual oficial do SIM homologado; publicação somente em agregados "
                "municipais por residência com limiar de divulgação."
            ),
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    params = {"dataset_id": SIM_DATASET, "source_id": SIM_SOURCE}
    connection.execute(
        sa.text(
            "UPDATE catalog_entries SET dataset_id=NULL, integration_decision='manual_review', "
            "decision_reason='Integração SIM removida no downgrade', decided_at=now() "
            "WHERE dataset_id=:dataset_id"
        ),
        params,
    )
    connection.execute(
        sa.text(
            "DELETE FROM data_quality_issues WHERE run_id IN "
            "(SELECT id FROM ingestion_runs WHERE dataset_id=:dataset_id)"
        ),
        params,
    )
    for table in ("ingestion_jobs", "ingestion_runs", "publication_releases"):
        connection.execute(
            sa.text(f"DELETE FROM {table} WHERE dataset_id=:dataset_id"),  # noqa: S608
            params,
        )
    for table in (
        "health_epidemiology",
        "health_production",
        "health_services",
        "health_beds",
        "health_establishments",
    ):
        op.drop_table(table)
    connection.execute(sa.text("DELETE FROM source_snapshots WHERE dataset_id=:dataset_id"), params)
    connection.execute(sa.text("DELETE FROM datasets WHERE id=:dataset_id"), params)
    connection.execute(sa.text("DELETE FROM sources WHERE id=:source_id"), params)
    connection.execute(
        sa.text("DELETE FROM indicators WHERE id=:indicator_id"),
        {"indicator_id": SIM_INDICATOR},
    )
