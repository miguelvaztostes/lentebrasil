"""Register the official SINASC 2024 municipal aggregate.

Revision ID: 0012
Revises: 0011
"""

# ruff: noqa: E501

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

SOURCE_ID = UUID("20000000-0000-4000-8000-000000000022")
DATASET_ID = UUID("21000000-0000-4000-8000-000000000022")


def upgrade() -> None:
    now = datetime.now(UTC)
    op.execute(
        sa.text("""INSERT INTO sources (id, provider, slug, source_url, license, terms, expected_frequency, status, verified_at, source_status, connector_status, catalog_metadata)
        VALUES (:id, :provider, :slug, :url, :license, :terms, 'anual', 'confirmed', :now, 'verified', 'implemented', CAST(:metadata AS jsonb))""").bindparams(
            id=SOURCE_ID,
            provider="Ministério da Saúde — SINASC",
            slug="sinasc-nascidos-vivos",
            url="https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc",
            license="Dados abertos do SUS; atribuição ao Ministério da Saúde",
            terms="Publicar somente agregados municipais; remover o microdado após o processamento e suprimir células pequenas.",
            now=now,
            metadata='{"inventory_ids":["LNT-0021"]}',
        )
    )
    op.execute(
        sa.text("""INSERT INTO datasets (id, source_id, code, title, description, domain, granularity, update_policy, status, connector_status, publication_status, catalog_metadata)
        VALUES (:id, :source, 'sinasc_births_municipal', :title, :description, 'saude', 'município/ano', 'anual após homologação', 'confirmed', 'implemented', 'not_published', CAST(:metadata AS jsonb))""").bindparams(
            id=DATASET_ID,
            source=SOURCE_ID,
            title="SINASC — nascidos vivos por município de residência",
            description="Nascidos vivos registrados em 2024, agregados por município de residência.",
            metadata='{"reference_resource":"SINASC_2024_csv.zip","privacy":"microdata discarded; small cells suppressed"}',
        )
    )
    op.execute(
        sa.text(
            "UPDATE catalog_entries SET dataset_id=:dataset, integration_decision='integrate', decision_reason='CSV oficial definitivo SINASC 2024 homologado e agregado por residência', decided_at=now() WHERE external_catalog_id='LNT-0021'"
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
            "DELETE FROM health_epidemiology WHERE snapshot_id IN (SELECT id FROM source_snapshots WHERE dataset_id=:id)"
        ),
        {"id": DATASET_ID},
    )
    connection.execute(
        sa.text("DELETE FROM source_snapshots WHERE dataset_id=:id"),
        {"id": DATASET_ID},
    )
    connection.execute(sa.text("DELETE FROM datasets WHERE id=:id"), {"id": DATASET_ID})
    connection.execute(sa.text("DELETE FROM sources WHERE id=:id"), {"id": SOURCE_ID})
