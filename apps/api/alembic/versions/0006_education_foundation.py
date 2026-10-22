"""Add historical education facts and audited catalog decisions.

Revision ID: 0006
Revises: 0005
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

CENSO_SOURCE = "10000000-0000-4000-8000-000000000007"
IDEB_SOURCE = "10000000-0000-4000-8000-000000000009"
CENSO_DATASET = "11000000-0000-4000-8000-000000000007"
IDEB_DATASET = "11000000-0000-4000-8000-000000000009"


def upgrade() -> None:
    op.add_column("catalog_entries", sa.Column("integration_decision", sa.String(40)))
    op.add_column("catalog_entries", sa.Column("decision_reason", sa.Text()))
    op.add_column("catalog_entries", sa.Column("decided_at", sa.DateTime(timezone=True)))
    op.create_check_constraint(
        "ck_catalog_entries_integration_decision",
        "catalog_entries",
        "integration_decision IS NULL OR integration_decision IN "
        "('integrate', 'manual_review', 'restricted', 'metadata_only', 'unavailable')",
    )
    op.create_index(
        "ix_catalog_entries_integration_decision", "catalog_entries", ["integration_decision"]
    )

    op.create_table(
        "education_networks",
        sa.Column("code", sa.String(30), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
    )
    op.create_table(
        "education_stages",
        sa.Column("code", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("display_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "education_dependencies",
        sa.Column("code", sa.String(10), primary_key=True),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
        sa.Column(
            "network_code", sa.String(30), sa.ForeignKey("education_networks.code"), nullable=False
        ),
    )
    op.create_index("ix_education_dependencies_network", "education_dependencies", ["network_code"])
    op.create_table(
        "schools",
        sa.Column("inep_code", sa.String(8), primary_key=True),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_schools_municipality", "schools", ["municipality_ibge_code"])
    op.create_table(
        "school_versions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "school_inep_code", sa.String(8), sa.ForeignKey("schools.inep_code"), nullable=False
        ),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("census_year", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(260), nullable=False),
        sa.Column("state", sa.String(2), nullable=False),
        sa.Column(
            "dependency_code",
            sa.String(10),
            sa.ForeignKey("education_dependencies.code"),
            nullable=False,
        ),
        sa.Column("operating_status", sa.String(40), nullable=False),
        sa.Column("location_type", sa.String(30)),
        sa.Column(
            "infrastructure", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column(
            "release_id", sa.Uuid(), sa.ForeignKey("publication_releases.id"), nullable=False
        ),
        sa.UniqueConstraint(
            "school_inep_code", "census_year", "release_id", name="uq_school_version"
        ),
    )
    for name, column in (
        ("ix_school_versions_school", "school_inep_code"),
        ("ix_school_versions_municipality", "municipality_ibge_code"),
        ("ix_school_versions_year", "census_year"),
        ("ix_school_versions_state", "state"),
        ("ix_school_versions_dependency", "dependency_code"),
        ("ix_school_versions_operating", "operating_status"),
        ("ix_school_versions_release", "release_id"),
    ):
        op.create_index(name, "school_versions", [column])
    op.create_table(
        "education_enrollments",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "school_inep_code", sa.String(8), sa.ForeignKey("schools.inep_code"), nullable=False
        ),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("census_year", sa.Integer(), nullable=False),
        sa.Column(
            "stage_code", sa.String(50), sa.ForeignKey("education_stages.code"), nullable=False
        ),
        sa.Column(
            "dependency_code",
            sa.String(10),
            sa.ForeignKey("education_dependencies.code"),
            nullable=False,
        ),
        sa.Column("enrollment_count", sa.Integer()),
        sa.Column("availability_status", sa.String(40), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column(
            "release_id", sa.Uuid(), sa.ForeignKey("publication_releases.id"), nullable=False
        ),
        sa.UniqueConstraint(
            "school_inep_code",
            "census_year",
            "stage_code",
            "release_id",
            name="uq_education_enrollment_release",
        ),
    )
    for name, column in (
        ("ix_education_enrollments_school", "school_inep_code"),
        ("ix_education_enrollments_municipality", "municipality_ibge_code"),
        ("ix_education_enrollments_year", "census_year"),
        ("ix_education_enrollments_stage", "stage_code"),
        ("ix_education_enrollments_dependency", "dependency_code"),
        ("ix_education_enrollments_availability", "availability_status"),
        ("ix_education_enrollments_release", "release_id"),
    ):
        op.create_index(name, "education_enrollments", [column])
    op.create_table(
        "education_metrics",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("metric_code", sa.String(80), nullable=False),
        sa.Column(
            "network_code", sa.String(30), sa.ForeignKey("education_networks.code"), nullable=False
        ),
        sa.Column(
            "stage_code", sa.String(50), sa.ForeignKey("education_stages.code"), nullable=False
        ),
        sa.Column("value", sa.Numeric(16, 6)),
        sa.Column("availability_status", sa.String(40), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column(
            "release_id", sa.Uuid(), sa.ForeignKey("publication_releases.id"), nullable=False
        ),
        sa.UniqueConstraint(
            "municipality_ibge_code",
            "reference_year",
            "metric_code",
            "network_code",
            "stage_code",
            "release_id",
            name="uq_education_metric_release",
        ),
    )
    for name, column in (
        ("ix_education_metrics_municipality", "municipality_ibge_code"),
        ("ix_education_metrics_year", "reference_year"),
        ("ix_education_metrics_code", "metric_code"),
        ("ix_education_metrics_network", "network_code"),
        ("ix_education_metrics_stage", "stage_code"),
        ("ix_education_metrics_availability", "availability_status"),
        ("ix_education_metrics_release", "release_id"),
    ):
        op.create_index(name, "education_metrics", [column])

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
                "id": CENSO_SOURCE,
                "provider": "Inep",
                "slug": "inep-censo-escolar",
                "source_url": "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar",
                "license": "Dados abertos; observar termos e LGPD do Inep",
                "terms": "Publicar somente atributos escolares agregados e não sensíveis.",
                "expected_frequency": "anual",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {"verified_artifact": "microdados_censo_escolar_2024.zip"},
            },
            {
                "id": IDEB_SOURCE,
                "provider": "Inep",
                "slug": "inep-ideb-municipal",
                "source_url": "https://www.gov.br/inep/pt-br/areas-de-atuacao/pesquisas-estatisticas-e-indicadores/ideb/resultados/2005-2025",
                "license": "Dados abertos; observar notas metodológicas do Inep",
                "terms": "Preservar supressões e não inferir valores ausentes.",
                "expected_frequency": "bienal",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {
                    "verified_artifact": "divulgacao_anos_iniciais_municipios_2025.zip"
                },
            },
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
                "id": CENSO_DATASET,
                "source_id": CENSO_SOURCE,
                "code": "inep_censo_escolar",
                "title": "Censo Escolar — escolas e matrículas",
                "description": "Recorte publicável por escola, município, dependência e etapa.",
                "domain": "educacao",
                "granularity": "escola/ano/etapa",
                "update_policy": "anual após validação",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0007"},
            },
            {
                "id": IDEB_DATASET,
                "source_id": IDEB_SOURCE,
                "code": "inep_ideb_municipal",
                "title": "Ideb municipal",
                "description": (
                    "Indicadores municipais por rede e etapa, com supressões preservadas."
                ),
                "domain": "educacao",
                "granularity": "município/ano/rede/etapa",
                "update_policy": "bienal após validação",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0009"},
            },
        ],
    )
    networks = sa.table("education_networks", sa.column("code"), sa.column("name"))
    op.bulk_insert(
        networks,
        [
            {"code": "federal", "name": "Federal"},
            {"code": "state", "name": "Estadual"},
            {"code": "municipal", "name": "Municipal"},
            {"code": "private", "name": "Privada"},
            {"code": "public", "name": "Pública"},
        ],
    )
    dependencies = sa.table(
        "education_dependencies",
        sa.column("code"),
        sa.column("name"),
        sa.column("network_code"),
    )
    op.bulk_insert(
        dependencies,
        [
            {"code": "1", "name": "Federal", "network_code": "federal"},
            {"code": "2", "name": "Estadual", "network_code": "state"},
            {"code": "3", "name": "Municipal", "network_code": "municipal"},
            {"code": "4", "name": "Privada", "network_code": "private"},
        ],
    )
    stages = sa.table(
        "education_stages",
        sa.column("code"),
        sa.column("name"),
        sa.column("display_order"),
    )
    op.bulk_insert(
        stages,
        [
            {"code": "all_basic", "name": "Educação básica", "display_order": 0},
            {"code": "early_childhood", "name": "Educação infantil", "display_order": 10},
            {"code": "fundamental", "name": "Ensino fundamental", "display_order": 20},
            {
                "code": "fundamental_early",
                "name": "Anos iniciais do ensino fundamental",
                "display_order": 21,
            },
            {
                "code": "fundamental_late",
                "name": "Anos finais do ensino fundamental",
                "display_order": 22,
            },
            {"code": "secondary", "name": "Ensino médio", "display_order": 30},
            {
                "code": "technical",
                "name": "Educação profissional técnica",
                "display_order": 40,
            },
            {
                "code": "youth_adult",
                "name": "Educação de jovens e adultos",
                "display_order": 50,
            },
            {"code": "special", "name": "Educação especial", "display_order": 60},
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    op.drop_table("education_metrics")
    op.drop_table("education_enrollments")
    op.drop_table("school_versions")
    op.drop_table("schools")
    connection.execute(
        sa.text(
            "DELETE FROM data_quality_issues WHERE run_id IN "
            "(SELECT id FROM ingestion_runs WHERE dataset_id IN (:censo, :ideb))"
        ),
        {"censo": CENSO_DATASET, "ideb": IDEB_DATASET},
    )
    for table in ("ingestion_jobs", "ingestion_runs", "publication_releases", "source_snapshots"):
        connection.execute(
            sa.text(f"DELETE FROM {table} WHERE dataset_id IN (:censo, :ideb)"),  # noqa: S608
            {"censo": CENSO_DATASET, "ideb": IDEB_DATASET},
        )
    connection.execute(
        sa.text("UPDATE catalog_entries SET dataset_id=NULL WHERE dataset_id IN (:censo, :ideb)"),
        {"censo": CENSO_DATASET, "ideb": IDEB_DATASET},
    )
    connection.execute(
        sa.text("DELETE FROM datasets WHERE id IN (:censo, :ideb)"),
        {"censo": CENSO_DATASET, "ideb": IDEB_DATASET},
    )
    connection.execute(
        sa.text("DELETE FROM sources WHERE id IN (:censo, :ideb)"),
        {"censo": CENSO_SOURCE, "ideb": IDEB_SOURCE},
    )
    op.drop_table("education_dependencies")
    op.drop_table("education_stages")
    op.drop_table("education_networks")
    op.drop_index("ix_catalog_entries_integration_decision", table_name="catalog_entries")
    op.drop_constraint("ck_catalog_entries_integration_decision", "catalog_entries", type_="check")
    op.drop_column("catalog_entries", "decided_at")
    op.drop_column("catalog_entries", "decision_reason")
    op.drop_column("catalog_entries", "integration_decision")
