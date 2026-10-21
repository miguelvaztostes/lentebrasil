"""Add accent-insensitive indexes for territorial and catalog search.

Revision ID: 0005
Revises: 0004
"""

from __future__ import annotations

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

ACCENTS = "áàâãäåéèêëíìîïóòôõöúùûüçñýÿ"
ASCII = "aaaaaaeeeeiiiiooooouuuucnyy"


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    expressions = {
        "ix_municipalities_name_search": (
            "municipalities",
            f"translate(lower(name), '{ACCENTS}', '{ASCII}') gin_trgm_ops",
        ),
        "ix_catalog_entries_indicator_search": (
            "catalog_entries",
            f"translate(lower(indicator_ref), '{ACCENTS}', '{ASCII}') gin_trgm_ops",
        ),
        "ix_data_providers_name_search": (
            "data_providers",
            f"translate(lower(name), '{ACCENTS}', '{ASCII}') gin_trgm_ops",
        ),
        "ix_source_resources_title_search": (
            "source_resources",
            f"translate(lower(title), '{ACCENTS}', '{ASCII}') gin_trgm_ops",
        ),
        "ix_datasets_title_search": (
            "datasets",
            f"translate(lower(title), '{ACCENTS}', '{ASCII}') gin_trgm_ops",
        ),
        "ix_indicators_label_search": (
            "indicators",
            f"translate(lower(label), '{ACCENTS}', '{ASCII}') gin_trgm_ops",
        ),
    }
    for name, (table, expression) in expressions.items():
        op.execute(f"CREATE INDEX {name} ON {table} USING gin ({expression})")


def downgrade() -> None:
    for name in (
        "ix_indicators_label_search",
        "ix_datasets_title_search",
        "ix_source_resources_title_search",
        "ix_data_providers_name_search",
        "ix_catalog_entries_indicator_search",
        "ix_municipalities_name_search",
    ):
        op.execute(f"DROP INDEX IF EXISTS {name}")
