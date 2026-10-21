"""Add national catalog, geography, coverage and release foundations.

Revision ID: 0002
Revises: 0001
"""

from __future__ import annotations

import json
from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

NOW = datetime(2026, 10, 20, tzinfo=UTC)
BRAZIL = "40000000-0000-4000-8000-000000000001"
SAO_PAULO = "40000000-0000-4000-8000-000000000002"
RIBEIRAO_PRETO = "40000000-0000-4000-8000-000000000003"

LEGACY_SOURCES = [
    {
        "source_id": "00000000-0000-4000-8000-000000000001",
        "provider_id": "30000000-0000-4000-8000-000000000001",
        "resource_id": "31000000-0000-4000-8000-000000000001",
        "provider_slug": "ibge",
        "provider_name": "IBGE",
        "resource_slug": "ibge-sidra-populacao",
        "resource_title": "SIDRA — estimativas da população residente",
        "url": (
            "https://apisidra.ibge.gov.br/values/t/6579/n6/3543402/v/9324/p/last%2010?formato=json"
        ),
        "format": "api",
        "license": "Uso com atribuição; termos específicos a confirmar",
        "license_status": "pending_review",
        "source_status": "verified",
        "connector_status": "active",
    },
    {
        "source_id": "00000000-0000-4000-8000-000000000002",
        "provider_id": "30000000-0000-4000-8000-000000000002",
        "resource_id": "31000000-0000-4000-8000-000000000002",
        "provider_slug": "siconfi",
        "provider_name": "Secretaria do Tesouro Nacional — Siconfi",
        "resource_slug": "siconfi-rreo-anexo-01",
        "resource_title": "Siconfi — RREO Anexo 01",
        "url": "https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/rreo",
        "format": "api",
        "license": "Apache 2.0",
        "license_status": "confirmed",
        "source_status": "verified",
        "connector_status": "active",
    },
    {
        "source_id": "00000000-0000-4000-8000-000000000003",
        "provider_id": "30000000-0000-4000-8000-000000000003",
        "resource_id": "31000000-0000-4000-8000-000000000003",
        "provider_slug": "cnes",
        "provider_name": "Ministério da Saúde — CNES",
        "resource_slug": "cnes-estabelecimentos-csv",
        "resource_title": "CNES — estabelecimentos",
        "url": (
            "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/"
            "cnes_estabelecimentos_csv.zip"
        ),
        "format": "zip",
        "license": "A confirmar por recurso",
        "license_status": "pending_review",
        "source_status": "verified",
        "connector_status": "active",
    },
    {
        "source_id": "00000000-0000-4000-8000-000000000004",
        "provider_id": "30000000-0000-4000-8000-000000000004",
        "resource_id": "31000000-0000-4000-8000-000000000004",
        "provider_slug": "inep-ideb",
        "provider_name": "INEP — IDEB",
        "resource_slug": "inep-ideb-resultados",
        "resource_title": "INEP — resultados do IDEB",
        "url": (
            "https://www.gov.br/inep/pt-br/areas-de-atuacao/"
            "pesquisas-estatisticas-e-indicadores/ideb/resultados"
        ),
        "format": "portal",
        "license": "A confirmar por arquivo",
        "license_status": "pending_review",
        "source_status": "pending_review",
        "connector_status": "not_implemented",
    },
    {
        "source_id": "00000000-0000-4000-8000-000000000005",
        "provider_id": "30000000-0000-4000-8000-000000000005",
        "resource_id": "31000000-0000-4000-8000-000000000005",
        "provider_slug": "pmrp-transparencia",
        "provider_name": "Prefeitura Municipal de Ribeirão Preto",
        "resource_slug": "pmrp-orcamento",
        "resource_title": "Portal municipal — orçamento",
        "url": "https://www.ribeiraopreto.sp.gov.br/portal/transparencia/orcamento",
        "format": "portal",
        "license": "Não declarada na página auditada",
        "license_status": "pending_review",
        "source_status": "pending_review",
        "connector_status": "not_implemented",
    },
    {
        "source_id": "00000000-0000-4000-8000-000000000006",
        "provider_id": "30000000-0000-4000-8000-000000000006",
        "resource_id": "31000000-0000-4000-8000-000000000006",
        "provider_slug": "camara-ribeirao",
        "provider_name": "Câmara Municipal de Ribeirão Preto",
        "resource_slug": "camara-ribeirao-portal",
        "resource_title": "Portal da Câmara Municipal de Ribeirão Preto",
        "url": "https://www.camararibeiraopreto.sp.gov.br/",
        "format": "portal",
        "license": None,
        "license_status": "unknown",
        "source_status": "discovered",
        "connector_status": "not_implemented",
    },
    {
        "source_id": "00000000-0000-4000-8000-000000000007",
        "provider_id": "30000000-0000-4000-8000-000000000007",
        "resource_id": "31000000-0000-4000-8000-000000000007",
        "provider_slug": "ribeirao-2030",
        "provider_name": "Instituto Ribeirão 2030",
        "resource_slug": "ribeirao-2030-plano-cidade",
        "resource_title": "Plano de Cidade 2020–2030",
        "url": "https://www.ribeirao2030.com.br/publicacoes/plano-de-cidade-2020-2030/",
        "format": "portal",
        "license": "Uso como referência, com atribuição",
        "license_status": "pending_review",
        "source_status": "verified",
        "connector_status": "not_implemented",
    },
]

LEGACY_DATASETS = [
    (
        "10000000-0000-4000-8000-000000000001",
        "31000000-0000-4000-8000-000000000001",
        "50000000-0000-4000-8000-000000000001",
        "60000000-0000-4000-8000-000000000001",
        "legacy-ibge-population",
    ),
    (
        "10000000-0000-4000-8000-000000000002",
        "31000000-0000-4000-8000-000000000002",
        "50000000-0000-4000-8000-000000000002",
        "60000000-0000-4000-8000-000000000002",
        "legacy-siconfi-rreo",
    ),
    (
        "10000000-0000-4000-8000-000000000003",
        "31000000-0000-4000-8000-000000000003",
        "50000000-0000-4000-8000-000000000003",
        "60000000-0000-4000-8000-000000000003",
        "legacy-cnes-establishments",
    ),
]


def upgrade() -> None:
    op.create_table(
        "catalog_imports",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("catalog_name", sa.String(160), nullable=False),
        sa.Column("catalog_version", sa.String(80), nullable=False),
        sa.Column("schema_version", sa.String(40), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False, unique=True),
        sa.Column("source_path", sa.Text(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("record_count", sa.Integer(), nullable=False),
        sa.Column("area_count", sa.Integer(), nullable=False),
        sa.Column("indicator_count", sa.Integer(), nullable=False),
        sa.Column("discrepancies", sa.JSON(), nullable=False),
    )
    op.create_index("ix_catalog_imports_version", "catalog_imports", ["catalog_version"])
    op.create_index("ix_catalog_imports_imported", "catalog_imports", ["imported_at"])

    op.create_table(
        "geo_units",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("parent_id", sa.Uuid(), sa.ForeignKey("geo_units.id")),
        sa.Column("unit_type", sa.String(40), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("state", sa.String(2)),
        sa.Column("country_code", sa.String(2), nullable=False, server_default="BR"),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.CheckConstraint(
            "unit_type IN ('country', 'region', 'state', 'municipality')",
            name="ck_geo_units_type",
        ),
        sa.UniqueConstraint("unit_type", "code", name="uq_geo_units_type_code"),
    )
    op.create_index("ix_geo_units_parent", "geo_units", ["parent_id"])
    op.create_index("ix_geo_units_type", "geo_units", ["unit_type"])
    op.create_index("ix_geo_units_name", "geo_units", ["name"])
    op.create_table(
        "geo_code_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("geo_unit_id", sa.Uuid(), sa.ForeignKey("geo_units.id"), nullable=False),
        sa.Column("code_system", sa.String(60), nullable=False),
        sa.Column("external_code", sa.String(64), nullable=False),
        sa.Column("valid_from", sa.Date()),
        sa.Column("valid_to", sa.Date()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.UniqueConstraint(
            "code_system", "external_code", "valid_from", name="uq_geo_code_mapping"
        ),
    )
    op.create_index("ix_geo_mappings_unit", "geo_code_mappings", ["geo_unit_id"])
    op.create_index("ix_geo_mappings_system", "geo_code_mappings", ["code_system"])
    op.create_index("ix_geo_mappings_code", "geo_code_mappings", ["external_code"])

    op.create_table(
        "data_providers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("name", sa.String(240), nullable=False),
        sa.Column("external_catalog_id", sa.String(160), unique=True),
        sa.Column("source_status", sa.String(40), nullable=False),
        sa.Column("connector_status", sa.String(40), nullable=False),
        sa.Column("license", sa.String(200)),
        sa.Column("terms", sa.Text()),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "source_status IN ('discovered', 'pending_review', 'verified', 'unavailable', "
            "'restricted')",
            name="ck_data_providers_source_status",
        ),
        sa.CheckConstraint(
            "connector_status IN ('not_implemented', 'planned', 'implemented', 'active', "
            "'degraded', 'failed', 'disabled')",
            name="ck_data_providers_connector_status",
        ),
    )
    op.create_index("ix_data_providers_slug", "data_providers", ["slug"])
    op.create_index("ix_data_providers_source_status", "data_providers", ["source_status"])
    op.create_index("ix_data_providers_connector_status", "data_providers", ["connector_status"])
    op.create_table(
        "source_resources",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey("data_providers.id"), nullable=False),
        sa.Column("slug", sa.String(140), nullable=False, unique=True),
        sa.Column("title", sa.String(260), nullable=False),
        sa.Column("external_catalog_id", sa.String(180), unique=True),
        sa.Column("canonical_url", sa.Text()),
        sa.Column("format", sa.String(40), nullable=False),
        sa.Column("source_status", sa.String(40), nullable=False),
        sa.Column("connector_status", sa.String(40), nullable=False),
        sa.Column("license_status", sa.String(40), nullable=False),
        sa.Column("license", sa.String(200)),
        sa.Column("terms", sa.Text()),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.CheckConstraint(
            "format IN ('api', 'csv', 'zip', 'xlsx', 'parquet', 'portal', 'manual', "
            "'json', 'xml', 'pdf')",
            name="ck_source_resources_format",
        ),
        sa.CheckConstraint(
            "source_status IN ('discovered', 'pending_review', 'verified', 'unavailable', "
            "'restricted')",
            name="ck_source_resources_source_status",
        ),
        sa.CheckConstraint(
            "connector_status IN ('not_implemented', 'planned', 'implemented', 'active', "
            "'degraded', 'failed', 'disabled')",
            name="ck_source_resources_connector_status",
        ),
        sa.CheckConstraint(
            "license_status IN ('unknown', 'pending_review', 'confirmed', 'restricted')",
            name="ck_source_resources_license_status",
        ),
    )
    op.create_index("ix_source_resources_provider", "source_resources", ["provider_id"])
    op.create_index("ix_source_resources_slug", "source_resources", ["slug"])
    op.create_index("ix_source_resources_format", "source_resources", ["format"])
    op.create_index("ix_source_resources_source_status", "source_resources", ["source_status"])
    op.create_index(
        "ix_source_resources_connector_status", "source_resources", ["connector_status"]
    )
    op.create_index("ix_source_resources_license_status", "source_resources", ["license_status"])

    _add_legacy_catalog_columns()
    _create_release_tables()
    _seed_legacy_catalog()


def _add_legacy_catalog_columns() -> None:
    op.add_column("sources", sa.Column("data_provider_id", sa.Uuid()))
    op.add_column("sources", sa.Column("primary_resource_id", sa.Uuid()))
    op.add_column("sources", sa.Column("catalog_import_id", sa.Uuid()))
    op.add_column("sources", sa.Column("external_catalog_id", sa.String(180)))
    op.add_column(
        "sources",
        sa.Column("source_status", sa.String(40), nullable=False, server_default="discovered"),
    )
    op.add_column(
        "sources",
        sa.Column(
            "connector_status", sa.String(40), nullable=False, server_default="not_implemented"
        ),
    )
    op.add_column(
        "sources",
        sa.Column(
            "catalog_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
    )
    op.create_foreign_key(
        "fk_sources_data_provider", "sources", "data_providers", ["data_provider_id"], ["id"]
    )
    op.create_foreign_key(
        "fk_sources_primary_resource",
        "sources",
        "source_resources",
        ["primary_resource_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_sources_catalog_import",
        "sources",
        "catalog_imports",
        ["catalog_import_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_sources_external_catalog_id", "sources", ["external_catalog_id"]
    )
    op.create_check_constraint(
        "ck_sources_source_status",
        "sources",
        "source_status IN ('discovered', 'pending_review', 'verified', 'unavailable', "
        "'restricted')",
    )
    op.create_check_constraint(
        "ck_sources_connector_status",
        "sources",
        "connector_status IN ('not_implemented', 'planned', 'implemented', 'active', "
        "'degraded', 'failed', 'disabled')",
    )
    for name, column in (
        ("ix_sources_data_provider", "data_provider_id"),
        ("ix_sources_primary_resource", "primary_resource_id"),
        ("ix_sources_catalog_import", "catalog_import_id"),
        ("ix_sources_source_status", "source_status"),
        ("ix_sources_connector_status", "connector_status"),
    ):
        op.create_index(name, "sources", [column])

    op.add_column("datasets", sa.Column("source_resource_id", sa.Uuid()))
    op.add_column("datasets", sa.Column("catalog_import_id", sa.Uuid()))
    op.add_column("datasets", sa.Column("external_catalog_id", sa.String(180)))
    op.add_column(
        "datasets",
        sa.Column(
            "connector_status", sa.String(40), nullable=False, server_default="not_implemented"
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "publication_status", sa.String(40), nullable=False, server_default="not_published"
        ),
    )
    op.add_column(
        "datasets",
        sa.Column(
            "catalog_metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")
        ),
    )
    op.create_foreign_key(
        "fk_datasets_source_resource",
        "datasets",
        "source_resources",
        ["source_resource_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_datasets_catalog_import",
        "datasets",
        "catalog_imports",
        ["catalog_import_id"],
        ["id"],
    )
    op.create_unique_constraint(
        "uq_datasets_external_catalog_id", "datasets", ["external_catalog_id"]
    )
    op.create_check_constraint(
        "ck_datasets_connector_status",
        "datasets",
        "connector_status IN ('not_implemented', 'planned', 'implemented', 'active', "
        "'degraded', 'failed', 'disabled')",
    )
    op.create_check_constraint(
        "ck_datasets_publication_status",
        "datasets",
        "publication_status IN ('not_published', 'draft', 'validated', 'published', "
        "'withdrawn', 'failed')",
    )
    for name, column in (
        ("ix_datasets_source_resource", "source_resource_id"),
        ("ix_datasets_catalog_import", "catalog_import_id"),
        ("ix_datasets_connector_status", "connector_status"),
        ("ix_datasets_publication_status", "publication_status"),
    ):
        op.create_index(name, "datasets", [column])


def _create_release_tables() -> None:
    op.create_table(
        "dataset_coverage",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("geo_unit_id", sa.Uuid(), sa.ForeignKey("geo_units.id")),
        sa.Column("scope_json", sa.JSON(), nullable=False),
        sa.Column("scope_key", sa.String(64), nullable=False),
        sa.Column("coverage_status", sa.String(40), nullable=False),
        sa.Column("period_start", sa.Date()),
        sa.Column("period_end", sa.Date()),
        sa.Column("checked_at", sa.DateTime(timezone=True)),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "coverage_status IN ('unknown', 'partial', 'complete', 'unavailable', "
            "'not_applicable')",
            name="ck_dataset_coverage_status",
        ),
        sa.UniqueConstraint(
            "dataset_id", "geo_unit_id", "scope_key", name="uq_dataset_coverage_scope"
        ),
    )
    op.create_index("ix_dataset_coverage_dataset", "dataset_coverage", ["dataset_id"])
    op.create_index("ix_dataset_coverage_geo", "dataset_coverage", ["geo_unit_id"])
    op.create_index("ix_dataset_coverage_status", "dataset_coverage", ["coverage_status"])
    op.create_table(
        "publication_releases",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id"), nullable=False),
        sa.Column("source_resource_id", sa.Uuid(), sa.ForeignKey("source_resources.id")),
        sa.Column("release_key", sa.String(160), nullable=False),
        sa.Column("status", sa.String(40), nullable=False),
        sa.Column("reference_start", sa.Date()),
        sa.Column("reference_end", sa.Date()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("provenance", sa.JSON(), nullable=False),
        sa.Column("notes", sa.Text()),
        sa.CheckConstraint(
            "status IN ('draft', 'validated', 'published', 'withdrawn', 'failed')",
            name="ck_publication_releases_status",
        ),
        sa.UniqueConstraint("dataset_id", "release_key", name="uq_publication_release_key"),
    )
    op.create_index("ix_publication_releases_dataset", "publication_releases", ["dataset_id"])
    op.create_index(
        "ix_publication_releases_resource", "publication_releases", ["source_resource_id"]
    )
    op.create_index("ix_publication_releases_status", "publication_releases", ["status"])
    op.create_table(
        "catalog_entries",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("external_catalog_id", sa.String(20), nullable=False, unique=True),
        sa.Column(
            "catalog_import_id", sa.Uuid(), sa.ForeignKey("catalog_imports.id"), nullable=False
        ),
        sa.Column("provider_id", sa.Uuid(), sa.ForeignKey("data_providers.id"), nullable=False),
        sa.Column("source_resource_id", sa.Uuid(), sa.ForeignKey("source_resources.id")),
        sa.Column("dataset_id", sa.Uuid(), sa.ForeignKey("datasets.id")),
        sa.Column("area_slug", sa.String(120), nullable=False),
        sa.Column("indicator_ref", sa.String(180), nullable=False),
        sa.Column("raw_record", sa.JSON(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_catalog_entries_external", "catalog_entries", ["external_catalog_id"])
    op.create_index("ix_catalog_entries_import", "catalog_entries", ["catalog_import_id"])
    op.create_index("ix_catalog_entries_provider", "catalog_entries", ["provider_id"])
    op.create_index("ix_catalog_entries_resource", "catalog_entries", ["source_resource_id"])
    op.create_index("ix_catalog_entries_dataset", "catalog_entries", ["dataset_id"])
    op.create_index("ix_catalog_entries_area", "catalog_entries", ["area_slug"])
    op.create_index("ix_catalog_entries_indicator", "catalog_entries", ["indicator_ref"])


def _seed_legacy_catalog() -> None:
    geo_units = sa.table(
        "geo_units",
        sa.column("id", sa.Uuid()),
        sa.column("parent_id", sa.Uuid()),
        sa.column("unit_type"),
        sa.column("code"),
        sa.column("name"),
        sa.column("state"),
        sa.column("country_code"),
        sa.column("active"),
    )
    op.bulk_insert(
        geo_units,
        [
            {
                "id": BRAZIL,
                "parent_id": None,
                "unit_type": "country",
                "code": "BR",
                "name": "Brasil",
                "state": None,
                "country_code": "BR",
                "active": True,
            },
            {
                "id": SAO_PAULO,
                "parent_id": BRAZIL,
                "unit_type": "state",
                "code": "SP",
                "name": "São Paulo",
                "state": "SP",
                "country_code": "BR",
                "active": True,
            },
            {
                "id": RIBEIRAO_PRETO,
                "parent_id": SAO_PAULO,
                "unit_type": "municipality",
                "code": "3543402",
                "name": "Ribeirão Preto",
                "state": "SP",
                "country_code": "BR",
                "active": True,
            },
        ],
    )
    mappings = sa.table(
        "geo_code_mappings",
        sa.column("id", sa.Uuid()),
        sa.column("geo_unit_id", sa.Uuid()),
        sa.column("code_system"),
        sa.column("external_code"),
        sa.column("valid_from", sa.Date()),
        sa.column("valid_to", sa.Date()),
        sa.column("metadata_json", sa.JSON()),
    )
    op.bulk_insert(
        mappings,
        [
            {
                "id": "41000000-0000-4000-8000-000000000001",
                "geo_unit_id": RIBEIRAO_PRETO,
                "code_system": "IBGE_MUNICIPALITY",
                "external_code": "3543402",
                "valid_from": None,
                "valid_to": None,
                "metadata_json": {"origin": "legacy_mvp"},
            },
            {
                "id": "41000000-0000-4000-8000-000000000002",
                "geo_unit_id": RIBEIRAO_PRETO,
                "code_system": "CNES_MUNICIPALITY",
                "external_code": "354340",
                "valid_from": None,
                "valid_to": None,
                "metadata_json": {"origin": "legacy_mvp"},
            },
        ],
    )
    providers = sa.table(
        "data_providers",
        sa.column("id", sa.Uuid()),
        sa.column("slug"),
        sa.column("name"),
        sa.column("external_catalog_id"),
        sa.column("source_status"),
        sa.column("connector_status"),
        sa.column("license"),
        sa.column("terms"),
        sa.column("metadata_json", sa.JSON()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    resources = sa.table(
        "source_resources",
        sa.column("id", sa.Uuid()),
        sa.column("provider_id", sa.Uuid()),
        sa.column("slug"),
        sa.column("title"),
        sa.column("external_catalog_id"),
        sa.column("canonical_url"),
        sa.column("format"),
        sa.column("source_status"),
        sa.column("connector_status"),
        sa.column("license_status"),
        sa.column("license"),
        sa.column("terms"),
        sa.column("last_verified_at", sa.DateTime(timezone=True)),
        sa.column("metadata_json", sa.JSON()),
    )
    op.bulk_insert(
        providers,
        [
            {
                "id": item["provider_id"],
                "slug": item["provider_slug"],
                "name": item["provider_name"],
                "external_catalog_id": None,
                "source_status": item["source_status"],
                "connector_status": item["connector_status"],
                "license": item["license"],
                "terms": "Migrado do catálogo municipal sem alterar a evidência original.",
                "metadata_json": {"origin": "legacy_mvp"},
                "created_at": NOW,
                "updated_at": NOW,
            }
            for item in LEGACY_SOURCES
        ],
    )
    op.bulk_insert(
        resources,
        [
            {
                "id": item["resource_id"],
                "provider_id": item["provider_id"],
                "slug": item["resource_slug"],
                "title": item["resource_title"],
                "external_catalog_id": None,
                "canonical_url": item["url"],
                "format": item["format"],
                "source_status": item["source_status"],
                "connector_status": item["connector_status"],
                "license_status": item["license_status"],
                "license": item["license"],
                "terms": "Metadado migrado; consultar a fonte e o registro legado para limitações.",
                "last_verified_at": NOW,
                "metadata_json": {"origin": "legacy_mvp"},
            }
            for item in LEGACY_SOURCES
        ],
    )
    connection = op.get_bind()
    for item in LEGACY_SOURCES:
        connection.execute(
            sa.text(
                "UPDATE sources SET data_provider_id=:provider_id, "
                "primary_resource_id=:resource_id, source_status=:source_status, "
                "connector_status=:connector_status, "
                "catalog_metadata=CAST(:metadata AS json) "
                "WHERE id=:source_id"
            ),
            {
                "provider_id": item["provider_id"],
                "resource_id": item["resource_id"],
                "source_status": item["source_status"],
                "connector_status": item["connector_status"],
                "metadata": json.dumps({"origin": "legacy_mvp"}),
                "source_id": item["source_id"],
            },
        )
    for dataset_id, resource_id, _, _, _ in LEGACY_DATASETS:
        connection.execute(
            sa.text(
                "UPDATE datasets SET source_resource_id=:resource_id, "
                "connector_status='active', publication_status='published', "
                "catalog_metadata=CAST(:metadata AS json) WHERE id=:dataset_id"
            ),
            {
                "resource_id": resource_id,
                "metadata": json.dumps({"origin": "legacy_mvp"}),
                "dataset_id": dataset_id,
            },
        )
    coverage = sa.table(
        "dataset_coverage",
        sa.column("id", sa.Uuid()),
        sa.column("dataset_id", sa.Uuid()),
        sa.column("geo_unit_id", sa.Uuid()),
        sa.column("scope_json", sa.JSON()),
        sa.column("scope_key"),
        sa.column("coverage_status"),
        sa.column("period_start", sa.Date()),
        sa.column("period_end", sa.Date()),
        sa.column("checked_at", sa.DateTime(timezone=True)),
        sa.column("notes"),
    )
    releases = sa.table(
        "publication_releases",
        sa.column("id", sa.Uuid()),
        sa.column("dataset_id", sa.Uuid()),
        sa.column("source_resource_id", sa.Uuid()),
        sa.column("release_key"),
        sa.column("status"),
        sa.column("reference_start", sa.Date()),
        sa.column("reference_end", sa.Date()),
        sa.column("published_at", sa.DateTime(timezone=True)),
        sa.column("verified_at", sa.DateTime(timezone=True)),
        sa.column("provenance", sa.JSON()),
        sa.column("notes"),
    )
    op.bulk_insert(
        coverage,
        [
            {
                "id": coverage_id,
                "dataset_id": dataset_id,
                "geo_unit_id": RIBEIRAO_PRETO,
                "scope_json": {},
                "scope_key": "44136fa355b3678a1146ad16f7e8649e94fb4fc21fe77e8310c060f61caaff8a",
                "coverage_status": "complete",
                "period_start": None,
                "period_end": None,
                "checked_at": NOW,
                "notes": "Cobertura municipal migrada do MVP; não implica cobertura nacional.",
            }
            for dataset_id, _, coverage_id, _, _ in LEGACY_DATASETS
        ],
    )
    op.bulk_insert(
        releases,
        [
            {
                "id": release_id,
                "dataset_id": dataset_id,
                "source_resource_id": resource_id,
                "release_key": release_key,
                "status": "published",
                "reference_start": None,
                "reference_end": None,
                "published_at": NOW,
                "verified_at": NOW,
                "provenance": {"origin": "legacy_mvp", "migration": "0002"},
                "notes": "Registro de compatibilidade para dados já publicados pelo MVP.",
            }
            for dataset_id, resource_id, _, release_id, release_key in LEGACY_DATASETS
        ],
    )


def downgrade() -> None:
    op.drop_table("catalog_entries")
    op.drop_table("publication_releases")
    op.drop_table("dataset_coverage")

    for name in (
        "ix_datasets_publication_status",
        "ix_datasets_connector_status",
        "ix_datasets_catalog_import",
        "ix_datasets_source_resource",
    ):
        op.drop_index(name, table_name="datasets")
    op.drop_constraint("ck_datasets_publication_status", "datasets", type_="check")
    op.drop_constraint("ck_datasets_connector_status", "datasets", type_="check")
    op.drop_constraint("uq_datasets_external_catalog_id", "datasets", type_="unique")
    op.drop_constraint("fk_datasets_catalog_import", "datasets", type_="foreignkey")
    op.drop_constraint("fk_datasets_source_resource", "datasets", type_="foreignkey")
    for column in (
        "catalog_metadata",
        "publication_status",
        "connector_status",
        "external_catalog_id",
        "catalog_import_id",
        "source_resource_id",
    ):
        op.drop_column("datasets", column)

    for name in (
        "ix_sources_connector_status",
        "ix_sources_source_status",
        "ix_sources_catalog_import",
        "ix_sources_primary_resource",
        "ix_sources_data_provider",
    ):
        op.drop_index(name, table_name="sources")
    op.drop_constraint("ck_sources_connector_status", "sources", type_="check")
    op.drop_constraint("ck_sources_source_status", "sources", type_="check")
    op.drop_constraint("uq_sources_external_catalog_id", "sources", type_="unique")
    op.drop_constraint("fk_sources_catalog_import", "sources", type_="foreignkey")
    op.drop_constraint("fk_sources_primary_resource", "sources", type_="foreignkey")
    op.drop_constraint("fk_sources_data_provider", "sources", type_="foreignkey")
    for column in (
        "catalog_metadata",
        "connector_status",
        "source_status",
        "external_catalog_id",
        "catalog_import_id",
        "primary_resource_id",
        "data_provider_id",
    ):
        op.drop_column("sources", column)

    op.drop_table("source_resources")
    op.drop_table("data_providers")
    op.drop_table("geo_code_mappings")
    op.drop_table("geo_units")
    op.drop_table("catalog_imports")
