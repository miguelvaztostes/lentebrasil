"""Register the official CNES hospitals and beds resource.

Revision ID: 0011
Revises: 0010
"""

# ruff: noqa: E501

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None

SOURCE_ID = UUID("20000000-0000-4000-8000-000000000021")
DATASET_ID = UUID("21000000-0000-4000-8000-000000000021")


def upgrade() -> None:
    now = datetime.now(UTC)
    op.execute(
        sa.text("""INSERT INTO sources (id, provider, slug, source_url, license, terms, expected_frequency, status, verified_at, source_status, connector_status, catalog_metadata)
        VALUES (:id, :provider, :slug, :url, :license, :terms, :frequency, 'confirmed', :now, 'verified', 'implemented', CAST(:metadata AS jsonb))""").bindparams(
            id=SOURCE_ID,
            provider="Ministério da Saúde — Hospitais e Leitos/CNES",
            slug="cnes-hospitais-leitos",
            url="https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos",
            license="Creative Commons Atribuição-SemDerivações 3.0 (portal)",
            terms="Publicar somente campos institucionais e capacidades agregadas; descartar contatos e endereços.",
            frequency="mensal",
            now=now,
            metadata='{"inventory_ids":["LNT-0019"]}',
        )
    )
    op.execute(
        sa.text("""INSERT INTO datasets (id, source_id, code, title, description, domain, granularity, update_policy, status, connector_status, publication_status, catalog_metadata)
        VALUES (:id, :source, 'cnes_beds_establishments', :title, :description, 'saude', 'estabelecimento/competência', 'mensal após homologação', 'confirmed', 'implemented', 'not_published', CAST(:metadata AS jsonb))""").bindparams(
            id=DATASET_ID,
            source=SOURCE_ID,
            title="CNES — hospitais e leitos cadastrados",
            description="Estabelecimentos hospitalares e totais de leitos existentes/SUS na competência mais recente do arquivo oficial.",
            metadata='{"reference_resource":"Leitos_csv_2026.zip","privacy":"contact fields discarded"}',
        )
    )
    op.execute(
        sa.text(
            "UPDATE catalog_entries SET dataset_id=:dataset, integration_decision='integrate', decision_reason='ZIP/CSV oficial de hospitais e leitos homologado com minimização LGPD', decided_at=now() WHERE external_catalog_id='LNT-0019'"
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
            "DELETE FROM health_beds WHERE snapshot_id IN (SELECT id FROM source_snapshots WHERE dataset_id=:id)"
        ),
        {"id": DATASET_ID},
    )
    connection.execute(
        sa.text(
            "DELETE FROM health_establishments WHERE snapshot_id IN (SELECT id FROM source_snapshots WHERE dataset_id=:id)"
        ),
        {"id": DATASET_ID},
    )
    connection.execute(
        sa.text("DELETE FROM source_snapshots WHERE dataset_id=:id"), {"id": DATASET_ID}
    )
    connection.execute(sa.text("DELETE FROM datasets WHERE id=:id"), {"id": DATASET_ID})
    connection.execute(sa.text("DELETE FROM sources WHERE id=:id"), {"id": SOURCE_ID})
