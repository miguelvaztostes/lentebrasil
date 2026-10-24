"""Register SIOPS 2025 municipal health expenses.

Revision ID: 0013
Revises: 0012
"""

# ruff: noqa: E501

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None

SOURCE_ID = UUID("20000000-0000-4000-8000-000000000023")
DATASET_ID = UUID("21000000-0000-4000-8000-000000000023")


def upgrade() -> None:
    now = datetime.now(UTC)
    op.execute(
        sa.text("""INSERT INTO sources (id, provider, slug, source_url, license, terms, expected_frequency, status, verified_at, source_status, connector_status, catalog_metadata)
        VALUES (:id, :provider, :slug, :url, :license, :terms, 'bimestral', 'confirmed', :now, 'verified', 'implemented', CAST(:metadata AS jsonb))""").bindparams(
            id=SOURCE_ID,
            provider="Ministério da Saúde/Fundo Nacional de Saúde — SIOPS",
            slug="siops-despesas-saude-municipais",
            url="https://portalfns.saude.gov.br/siops/siops-downloads/",
            license="Dados públicos oficiais; atribuição ao Ministério da Saúde/FNS",
            terms="Publicar valores agregados por município, fonte, subfunção, natureza e fase contábil, preservando a proveniência e sem somar fases.",
            now=now,
            metadata='{"inventory_ids":["LNT-0025"],"resource_year":2025,"period":6,"scope":"municipal"}',
        )
    )
    op.execute(
        sa.text("""INSERT INTO datasets (id, source_id, code, title, description, domain, granularity, update_policy, status, connector_status, publication_status, catalog_metadata)
        VALUES (:id, :source, 'siops_health_expenses', :title, :description, 'saude', 'município/ano/fonte/subfunção/natureza/fase', 'após publicação oficial de cada bimestre', 'confirmed', 'implemented', 'not_published', CAST(:metadata AS jsonb))""").bindparams(
            id=DATASET_ID,
            source=SOURCE_ID,
            title="SIOPS — despesas municipais em saúde",
            description="Despesas municipais declaradas ao SIOPS no fechamento do 6º bimestre de 2025, com fases contábeis separadas.",
            metadata='{"reference_resource":"SIOPS Despesas por Fonte/Subfuncao/Natureza Municipais 2025 6o Bimestre","monetary_type":"Decimal","cumulative":true,"no_phase_summing":true}',
        )
    )
    op.execute(
        sa.text(
            "UPDATE catalog_entries SET dataset_id=:dataset, integration_decision='integrate', decision_reason='ZIP/CSV oficial municipal SIOPS 2025, 6º bimestre, homologado com fases contábeis separadas', decided_at=now() WHERE external_catalog_id='LNT-0025'"
        ).bindparams(dataset=DATASET_ID)
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE catalog_entries SET dataset_id=NULL, integration_decision='manual_review' WHERE dataset_id=:id"
        ),
        {"id": DATASET_ID},
    )
    connection.execute(
        sa.text(
            "DELETE FROM fiscal_statements WHERE snapshot_id IN (SELECT id FROM source_snapshots WHERE dataset_id=:id)"
        ),
        {"id": DATASET_ID},
    )
    connection.execute(sa.text("DELETE FROM budget_accounts WHERE source_system='siops'"))
    connection.execute(
        sa.text("DELETE FROM source_snapshots WHERE dataset_id=:id"),
        {"id": DATASET_ID},
    )
    connection.execute(sa.text("DELETE FROM datasets WHERE id=:id"), {"id": DATASET_ID})
    connection.execute(sa.text("DELETE FROM sources WHERE id=:id"), {"id": SOURCE_ID})
