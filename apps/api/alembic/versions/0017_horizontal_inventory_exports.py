"""Close horizontal inventory decisions and add asynchronous exports.

Revision ID: 0017
Revises: 0016
"""

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0017"
down_revision = "0016"
branch_labels = None
depends_on = None

OWNER = "data-platform"
PAM_SOURCE = UUID("20000000-0000-4000-8000-000000000031")
PAM_DATASET = UUID("21000000-0000-4000-8000-000000000031")
BOUNDARY_SOURCE = UUID("20000000-0000-4000-8000-000000000032")
BOUNDARY_DATASET = UUID("21000000-0000-4000-8000-000000000032")


def upgrade() -> None:
    op.add_column(
        "catalog_entries",
        sa.Column("review_status", sa.String(40), nullable=False, server_default="under_review"),
    )
    op.add_column(
        "catalog_entries",
        sa.Column("technical_owner", sa.String(120), nullable=False, server_default=OWNER),
    )
    op.add_column(
        "catalog_entries", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_check_constraint(
        "ck_catalog_entries_review_status",
        "catalog_entries",
        "review_status IN ('validated_and_published', 'integrated_not_published', "
        "'under_review', 'restricted', 'portal_only', 'unavailable')",
    )
    op.create_index("ix_catalog_entries_review_status", "catalog_entries", ["review_status"])
    op.create_index("ix_catalog_entries_last_checked_at", "catalog_entries", ["last_checked_at"])

    _create_agriculture_facts()
    _create_geospatial_assets()
    _create_export_jobs()
    _register_sources()
    _classify_inventory()


def _create_agriculture_facts() -> None:
    op.create_table(
        "agriculture_facts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(240), nullable=False),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("product_code", sa.String(40), nullable=False),
        sa.Column("product_name", sa.String(240), nullable=False),
        sa.Column("metric_code", sa.String(100), nullable=False),
        sa.Column("value", sa.Numeric(24, 6)),
        sa.Column("unit", sa.String(80), nullable=False),
        sa.Column("availability_status", sa.String(40), nullable=False),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_agriculture_fact_revision"
        ),
    )
    for column in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "reference_year",
        "product_code",
        "metric_code",
        "availability_status",
        "snapshot_id",
    ):
        op.create_index(f"ix_agriculture_facts_{column}", "agriculture_facts", [column])
    op.create_index(
        "ix_agriculture_fact_municipality_year",
        "agriculture_facts",
        ["municipality_ibge_code", "reference_year"],
    )


def _create_geospatial_assets() -> None:
    op.create_table(
        "geospatial_assets",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(240), nullable=False),
        sa.Column("geo_type", sa.String(40), nullable=False),
        sa.Column("geo_code", sa.String(40), nullable=False),
        sa.Column("reference_date", sa.Date(), nullable=False),
        sa.Column("crs", sa.String(40), nullable=False),
        sa.Column("geometry", sa.JSON(), nullable=False),
        sa.Column("bbox", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_geospatial_asset_revision"
        ),
    )
    for column in (
        "source_system",
        "source_key",
        "geo_type",
        "geo_code",
        "reference_date",
        "snapshot_id",
    ):
        op.create_index(f"ix_geospatial_assets_{column}", "geospatial_assets", [column])


def _create_export_jobs() -> None:
    op.create_table(
        "export_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("requester_hash", sa.String(64), nullable=False),
        sa.Column("domain", sa.String(60), nullable=False),
        sa.Column("format", sa.String(20), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("row_limit", sa.Integer(), nullable=False),
        sa.Column("row_count", sa.Integer()),
        sa.Column("byte_count", sa.Integer()),
        sa.Column("sha256", sa.String(64)),
        sa.Column("storage_path", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("lock_token", sa.Uuid()),
        sa.Column("error_details", sa.Text()),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'expired')",
            name="ck_export_jobs_status",
        ),
        sa.CheckConstraint("format IN ('csv', 'parquet')", name="ck_export_jobs_format"),
    )
    for column in (
        "requester_hash",
        "domain",
        "status",
        "created_at",
        "expires_at",
        "locked_at",
        "lock_token",
    ):
        op.create_index(f"ix_export_jobs_{column}", "export_jobs", [column])


def _register_sources() -> None:
    now = datetime.now(UTC)
    records = (
        (
            PAM_SOURCE,
            PAM_DATASET,
            "IBGE — Produção Agrícola Municipal",
            "ibge-pam",
            "https://apisidra.ibge.gov.br/values/t/5457",
            "ibge_pam_production",
            "Produção agrícola municipal por produto — SIDRA 5457",
            "agropecuaria-e-rural",
            "LNT-0137",
            "anual",
        ),
        (
            BOUNDARY_SOURCE,
            BOUNDARY_DATASET,
            "IBGE — API de Malhas",
            "ibge-malhas-geojson",
            "https://servicodados.ibge.gov.br/api/v3/malhas",
            "ibge_municipality_boundaries",
            "Malha municipal simplificada GeoJSON",
            "territorio-e-demografia",
            "LNT-0069",
            "anual/edição",
        ),
    )
    connection = op.get_bind()
    for (
        source_id,
        dataset_id,
        provider,
        slug,
        url,
        code,
        title,
        domain,
        inventory_id,
        frequency,
    ) in records:
        connection.execute(
            sa.text(
                """INSERT INTO sources (id, provider, slug, source_url, license, terms,
                expected_frequency, status, verified_at, source_status, connector_status,
                catalog_metadata) VALUES (:id,:provider,:slug,:url,
                'Dados públicos oficiais; atribuição obrigatória ao IBGE',
                'Reutilização com identificação da fonte e do período.',:frequency,
                'confirmed',:now,'verified','implemented',CAST(:metadata AS jsonb))"""
            ),
            {
                "id": source_id,
                "provider": provider,
                "slug": slug,
                "url": url,
                "frequency": frequency,
                "now": now,
                "metadata": f'{{"inventory_id":"{inventory_id}"}}',
            },
        )
        connection.execute(
            sa.text(
                """INSERT INTO datasets (id, source_id, code, title, description, domain,
                granularity, update_policy, status, connector_status, publication_status,
                catalog_metadata) VALUES (:id,:source,:code,:title,
                'Recurso oficial homologado com snapshot, hash e revisão.',:domain,
                'município/período/categoria',:frequency,'confirmed','implemented',
                'not_published',CAST(:metadata AS jsonb))"""
            ),
            {
                "id": dataset_id,
                "source": source_id,
                "code": code,
                "title": title,
                "domain": domain,
                "frequency": frequency,
                "metadata": f'{{"inventory_id":"{inventory_id}"}}',
            },
        )
        connection.execute(
            sa.text(
                """UPDATE catalog_entries SET dataset_id=:dataset,
                integration_decision='integrate', review_status='integrated_not_published',
                decision_reason='Recurso oficial verificado e conector implementado; publicação
                depende de carga validada.', decided_at=:now, last_checked_at=:now,
                technical_owner=:owner WHERE external_catalog_id=:inventory"""
            ),
            {
                "dataset": dataset_id,
                "now": now,
                "owner": OWNER,
                "inventory": inventory_id,
            },
        )


def _classify_inventory() -> None:
    connection = op.get_bind()
    now = datetime.now(UTC)
    connection.execute(
        sa.text(
            """UPDATE catalog_entries SET technical_owner=:owner,
            last_checked_at=COALESCE(last_checked_at, :now),
            review_status=CASE
              WHEN dataset_id IS NOT NULL AND EXISTS (
                SELECT 1 FROM datasets d WHERE d.id=catalog_entries.dataset_id
                AND d.publication_status='published') THEN 'validated_and_published'
              WHEN integration_decision='integrate' THEN 'integrated_not_published'
              WHEN integration_decision='restricted'
                OR lower(COALESCE(raw_record->>'auth','')) LIKE '%token%'
                OR lower(COALESCE(raw_record->>'auth','')) LIKE '%conta%'
                THEN 'restricted'
              WHEN integration_decision='unavailable' THEN 'unavailable'
              WHEN lower(COALESCE(raw_record->>'modalidade','')) LIKE '%portal%'
                OR lower(COALESCE(raw_record->>'modalidade','')) LIKE '%catálogo%'
                THEN 'portal_only'
              ELSE 'under_review'
            END,
            decision_reason=COALESCE(decision_reason,
              NULLIF(raw_record->>'observacao',''), NULLIF(raw_record->>'status',''),
              'Recurso candidato aguarda homologação técnica.')"""
        ),
        {"owner": OWNER, "now": now},
    )


def downgrade() -> None:
    connection = op.get_bind()
    for dataset_id, source_id in (
        (BOUNDARY_DATASET, BOUNDARY_SOURCE),
        (PAM_DATASET, PAM_SOURCE),
    ):
        connection.execute(
            sa.text(
                "UPDATE catalog_entries SET dataset_id=NULL, integration_decision='manual_review' "
                "WHERE dataset_id=:id"
            ),
            {"id": dataset_id},
        )
        connection.execute(
            sa.text("DELETE FROM source_snapshots WHERE dataset_id=:id"), {"id": dataset_id}
        )
        connection.execute(sa.text("DELETE FROM datasets WHERE id=:id"), {"id": dataset_id})
        connection.execute(sa.text("DELETE FROM sources WHERE id=:id"), {"id": source_id})
    op.drop_table("export_jobs")
    op.drop_table("geospatial_assets")
    op.drop_table("agriculture_facts")
    op.drop_index("ix_catalog_entries_last_checked_at", table_name="catalog_entries")
    op.drop_index("ix_catalog_entries_review_status", table_name="catalog_entries")
    op.drop_constraint("ck_catalog_entries_review_status", "catalog_entries", type_="check")
    op.drop_column("catalog_entries", "last_checked_at")
    op.drop_column("catalog_entries", "technical_owner")
    op.drop_column("catalog_entries", "review_status")
