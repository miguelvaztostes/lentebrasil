"""Add anonymous reproducible research queries.

Revision ID: 0018
Revises: 0017
"""

import sqlalchemy as sa

from alembic import op

revision = "0018"
down_revision = "0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_queries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(24), nullable=False),
        sa.Column("parameters_hash", sa.String(64), nullable=False),
        sa.Column("parameters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("access_count", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug"),
        sa.UniqueConstraint("parameters_hash"),
    )
    for column in ("slug", "parameters_hash", "created_at", "last_accessed_at"):
        op.create_index(f"ix_research_queries_{column}", "research_queries", [column])


def downgrade() -> None:
    op.drop_table("research_queries")
