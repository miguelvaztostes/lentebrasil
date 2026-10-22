"""Add privacy-minimized TCE-SP monthly expense phases.

Revision ID: 0009
Revises: 0008
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

DATASET_ID = "21000000-0000-4000-8000-000000000100"
SOURCE_ID = "20000000-0000-4000-8000-000000000099"


def upgrade() -> None:
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
                "id": DATASET_ID,
                "source_id": SOURCE_ID,
                "code": "tcesp_expenses",
                "title": "Despesas municipais TCE-SP/Audesp por fase",
                "description": (
                    "Totais mensais por evento contábil, agregados antes da persistência; "
                    "fornecedores e identificadores são descartados."
                ),
                "domain": "financas-publicas",
                "granularity": "município/mês/fase contábil",
                "update_policy": "mensal com revalidação da resposta oficial",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {
                    "inventory_ids": ["LNT-0039", "LNT-0040", "LNT-0100"],
                    "privacy": "supplier fields discarded before snapshot",
                },
            }
        ],
    )
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE catalog_entries SET dataset_id=:dataset_id, "
            "integration_decision='integrate', "
            "decision_reason=:reason, decided_at=now() "
            "WHERE external_catalog_id IN ('LNT-0039', 'LNT-0100')"
        ),
        {
            "dataset_id": DATASET_ID,
            "reason": (
                "API municipal TCE-SP validada para agregação mensal por fase; "
                "fornecedor e identificador são descartados antes do snapshot."
            ),
        },
    )


def downgrade() -> None:
    connection = op.get_bind()
    params = {"dataset_id": DATASET_ID}
    connection.execute(
        sa.text(
            "UPDATE catalog_entries entry SET "
            "dataset_id=(SELECT candidate.id FROM datasets candidate "
            "WHERE candidate.external_catalog_id=entry.external_catalog_id "
            "AND candidate.id<>:dataset_id LIMIT 1), "
            "integration_decision='manual_review', "
            "decision_reason='Integração de despesas TCE-SP removida no downgrade', "
            "decided_at=now() WHERE entry.dataset_id=:dataset_id"
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
    connection.execute(
        sa.text(
            "DELETE FROM fiscal_statements WHERE snapshot_id IN "
            "(SELECT id FROM source_snapshots WHERE dataset_id=:dataset_id)"
        ),
        params,
    )
    connection.execute(sa.text("DELETE FROM source_snapshots WHERE dataset_id=:dataset_id"), params)
    connection.execute(sa.text("DELETE FROM datasets WHERE id=:dataset_id"), params)
    connection.execute(sa.text("DELETE FROM budget_accounts WHERE source_system='tcesp_expense'"))
    connection.execute(sa.text("DELETE FROM agencies WHERE source_system='tcesp_expense'"))
