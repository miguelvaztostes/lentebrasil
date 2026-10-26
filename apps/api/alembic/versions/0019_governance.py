"""Add secure source contribution and governance workflow.

Revision ID: 0019
Revises: 0018
"""

import sqlalchemy as sa

from alembic import op

revision = "0019"
down_revision = "0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("legal_identifier_hash", sa.String(64), unique=True),
        sa.Column("official_domain", sa.String(200)),
        sa.Column("verification_status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("verification_evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("verified_by_subject", sa.String(240)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "verification_status IN ('pending','verified','rejected')",
            name="ck_organizations_verification_status",
        ),
    )
    op.create_index("ix_organizations_name", "organizations", ["name"])
    op.create_index("ix_organizations_created_at", "organizations", ["created_at"])
    op.create_index(
        "ix_organizations_verification_status", "organizations", ["verification_status"]
    )
    op.create_table(
        "organization_representatives",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("subject", sa.String(240), nullable=False),
        sa.Column("status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("evidence_storage_key", sa.Text()),
        sa.Column("evidence_sha256", sa.String(64)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("verified_by_subject", sa.String(240)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('pending','verified','revoked')",
            name="ck_organization_representatives_status",
        ),
        sa.UniqueConstraint("organization_id", "subject", name="uq_organization_representative"),
    )
    op.create_index(
        "ix_organization_representatives_subject", "organization_representatives", ["subject"]
    )
    op.create_index(
        "ix_organization_representatives_organization_id",
        "organization_representatives",
        ["organization_id"],
    )
    op.create_index(
        "ix_organization_representatives_status", "organization_representatives", ["status"]
    )
    op.create_index(
        "ix_organization_representatives_created_at",
        "organization_representatives",
        ["created_at"],
    )
    op.create_table(
        "source_submissions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("public_name", sa.String(160), nullable=False),
        sa.Column("organization_name", sa.String(240), nullable=False),
        sa.Column("proposed_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("contact_ciphertext", sa.Text()),
        sa.Column("notification_opt_in", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("submitter_fingerprint", sa.String(64), nullable=False),
        sa.Column("submitted_by_subject", sa.String(240)),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id")),
        sa.Column("challenge_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(40), nullable=False, server_default="received"),
        sa.Column(
            "source_origin", sa.String(40), nullable=False, server_default="third_party_submission"
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('received','triage','verified','quarantined',"
            "'approved','rejected','published')",
            name="ck_source_submissions_status",
        ),
    )
    op.create_index("ix_source_submissions_status", "source_submissions", ["status"])
    op.create_index("ix_source_submissions_created_at", "source_submissions", ["created_at"])
    op.create_index("ix_source_submissions_updated_at", "source_submissions", ["updated_at"])
    op.create_index(
        "ix_source_submissions_submitted_by_subject",
        "source_submissions",
        ["submitted_by_subject"],
    )
    op.create_index(
        "ix_source_submissions_organization_id", "source_submissions", ["organization_id"]
    )
    op.create_index(
        "ix_source_submissions_fingerprint", "source_submissions", ["submitter_fingerprint"]
    )
    op.create_table(
        "submission_reviews",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "submission_id", sa.Uuid(), sa.ForeignKey("source_submissions.id"), nullable=False
        ),
        sa.Column("from_status", sa.String(40), nullable=False),
        sa.Column("to_status", sa.String(40), nullable=False),
        sa.Column("reviewer_subject", sa.String(240), nullable=False),
        sa.Column("reviewer_role", sa.String(40), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_submission_reviews_submission_id", "submission_reviews", ["submission_id"])
    op.create_index("ix_submission_reviews_to_status", "submission_reviews", ["to_status"])
    op.create_index(
        "ix_submission_reviews_reviewer_subject", "submission_reviews", ["reviewer_subject"]
    )
    op.create_index("ix_submission_reviews_created_at", "submission_reviews", ["created_at"])
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("sequence", sa.Integer(), nullable=False, unique=True),
        sa.Column("actor_subject", sa.String(240), nullable=False),
        sa.Column("actor_role", sa.String(40), nullable=False),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(80), nullable=False),
        sa.Column("resource_id", sa.String(120), nullable=False),
        sa.Column("reason", sa.Text()),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("previous_hash", sa.String(64)),
        sa.Column("event_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    for column in (
        "sequence",
        "actor_subject",
        "action",
        "resource_type",
        "resource_id",
        "created_at",
    ):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])
    op.execute(
        "CREATE FUNCTION deny_audit_event_mutation() RETURNS trigger AS $$ "
        "BEGIN RAISE EXCEPTION 'audit_events are append-only'; END; $$ LANGUAGE plpgsql"
    )
    op.execute(
        "CREATE TRIGGER audit_events_immutable BEFORE UPDATE OR DELETE ON audit_events "
        "FOR EACH ROW EXECUTE FUNCTION deny_audit_event_mutation()"
    )
    op.create_table(
        "source_discoveries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("registry", sa.String(120), nullable=False),
        sa.Column("external_id", sa.String(240), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("license", sa.String(240)),
        sa.Column("canonical_url", sa.Text(), nullable=False),
        sa.Column("etag", sa.String(240)),
        sa.Column("schema_hash", sa.String(64)),
        sa.Column("metadata_hash", sa.String(64), nullable=False),
        sa.Column("metadata_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("diff_json", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(40), nullable=False, server_default="review_pending"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "status IN ('review_pending','reviewed','rejected','missing_review')",
            name="ck_source_discoveries_status",
        ),
        sa.UniqueConstraint("registry", "external_id", name="uq_source_discovery_external"),
    )
    op.create_index("ix_source_discoveries_status", "source_discoveries", ["status"])
    op.create_index("ix_source_discoveries_registry", "source_discoveries", ["registry"])
    op.create_index("ix_source_discoveries_external_id", "source_discoveries", ["external_id"])
    op.create_index("ix_source_discoveries_first_seen_at", "source_discoveries", ["first_seen_at"])
    op.create_index("ix_source_discoveries_last_seen_at", "source_discoveries", ["last_seen_at"])
    op.create_table(
        "quarantined_uploads",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "submission_id", sa.Uuid(), sa.ForeignKey("source_submissions.id"), nullable=False
        ),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id")),
        sa.Column("uploaded_by_subject", sa.String(240), nullable=False),
        sa.Column("original_filename", sa.String(260), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False, unique=True),
        sa.Column("media_type", sa.String(120), nullable=False),
        sa.Column("byte_count", sa.Integer(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("scan_status", sa.String(40), nullable=False, server_default="pending"),
        sa.Column("scan_details", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scanned_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint(
            "scan_status IN ('pending','clean','infected','scan_failed')",
            name="ck_quarantined_uploads_scan_status",
        ),
    )
    op.create_index("ix_quarantined_uploads_scan_status", "quarantined_uploads", ["scan_status"])
    for column in (
        "submission_id",
        "organization_id",
        "uploaded_by_subject",
        "sha256",
        "created_at",
    ):
        op.create_index(f"ix_quarantined_uploads_{column}", "quarantined_uploads", [column])


def downgrade() -> None:
    op.drop_table("quarantined_uploads")
    op.drop_table("source_discoveries")
    op.execute("DROP TRIGGER audit_events_immutable ON audit_events")
    op.execute("DROP FUNCTION deny_audit_event_mutation")
    op.drop_table("audit_events")
    op.drop_table("submission_reviews")
    op.drop_table("source_submissions")
    op.drop_table("organization_representatives")
    op.drop_table("organizations")
