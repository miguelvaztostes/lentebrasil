"""Add multicity geography history, query index and persistent ingestion jobs.

Revision ID: 0004
Revises: 0003
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    connection = op.get_bind()
    methodologies = {
        "population_estimated": (
            "SIDRA tabela 6579, variável 9324, nível município; a identidade IBGE é "
            "validada em cada linha."
        ),
        "cnes_establishments_registered": (
            "Contagem por código municipal do CNES reconciliado ao código IBGE canônico."
        ),
        "cnes_establishments_without_disable_reason": (
            "Filtro municipal reconciliado e CO_MOTIVO_DESAB vazio no CSV oficial corrente."
        ),
        "cnes_establishments_sus_ambulatory": (
            "Filtro municipal reconciliado e CO_AMBULATORIAL_SUS=SIM no CSV oficial corrente."
        ),
    }
    for code, methodology in methodologies.items():
        connection.execute(
            sa.text("UPDATE indicators SET methodology=:methodology WHERE code=:code"),
            {"code": code, "methodology": methodology},
        )
    op.create_table(
        "geo_unit_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("geo_unit_id", sa.Uuid(), sa.ForeignKey("geo_units.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("state", sa.String(2)),
        sa.Column("effective_from", sa.Date(), nullable=False),
        sa.Column("effective_to", sa.Date()),
        sa.Column("source_hash", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.UniqueConstraint("geo_unit_id", "effective_from", name="uq_geo_unit_version_date"),
    )
    op.create_index("ix_geo_unit_versions_geo", "geo_unit_versions", ["geo_unit_id"])
    op.create_index("ix_geo_unit_versions_effective", "geo_unit_versions", ["effective_from"])
    op.create_index(
        "ix_observations_municipality_indicator_period",
        "observations",
        ["municipality_ibge_code", "indicator_id", "period_start", "period_end"],
    )
    op.create_table(
        "ingestion_jobs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("job_key", sa.String(240), nullable=False, unique=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("checkpoint", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("locked_at", sa.DateTime(timezone=True)),
        sa.Column("lock_token", sa.Uuid()),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("last_error", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'retry', 'success', 'failed', 'disabled')",
            name="ck_ingestion_jobs_status",
        ),
    )
    for name, column in (
        ("ix_ingestion_jobs_job_key", "job_key"),
        ("ix_ingestion_jobs_dataset", "dataset_id"),
        ("ix_ingestion_jobs_status", "status"),
        ("ix_ingestion_jobs_scheduled", "scheduled_for"),
        ("ix_ingestion_jobs_locked", "locked_at"),
        ("ix_ingestion_jobs_lock_token", "lock_token"),
    ):
        op.create_index(name, "ingestion_jobs", [column])


def downgrade() -> None:
    op.drop_table("ingestion_jobs")
    op.drop_index("ix_observations_municipality_indicator_period", table_name="observations")
    op.drop_table("geo_unit_versions")
    connection = op.get_bind()
    legacy_methodologies = {
        "population_estimated": "SIDRA tabela 6579, variável 9324, nível município 3543402.",
        "cnes_establishments_registered": "Contagem de CO_IBGE=354340 no CSV oficial corrente.",
        "cnes_establishments_without_disable_reason": (
            "Filtro CO_IBGE=354340 e CO_MOTIVO_DESAB vazio."
        ),
        "cnes_establishments_sus_ambulatory": ("Filtro CO_IBGE=354340 e CO_AMBULATORIAL_SUS=SIM."),
    }
    for code, methodology in legacy_methodologies.items():
        connection.execute(
            sa.text("UPDATE indicators SET methodology=:methodology WHERE code=:code"),
            {"code": code, "methodology": methodology},
        )
