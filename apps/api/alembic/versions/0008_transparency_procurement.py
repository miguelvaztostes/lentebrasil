"""Add fiscal statements and public procurement facts.

Revision ID: 0008
Revises: 0007
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

SOURCE_IDS = {
    "pncp": "20000000-0000-4000-8000-000000000038",
    "tcesp": "20000000-0000-4000-8000-000000000099",
    "rgf": "20000000-0000-4000-8000-000000000094",
    "dca": "20000000-0000-4000-8000-000000000095",
}
DATASET_IDS = {
    "pncp": "21000000-0000-4000-8000-000000000038",
    "pncp_contracts": "21000000-0000-4000-8000-000000000039",
    "tcesp": "21000000-0000-4000-8000-000000000099",
    "rgf": "21000000-0000-4000-8000-000000000094",
    "dca": "21000000-0000-4000-8000-000000000095",
}


def upgrade() -> None:
    op.create_table(
        "agencies",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(160), nullable=False),
        sa.Column("name", sa.String(320), nullable=False),
        sa.Column("entity_identifier", sa.String(32)),
        sa.Column("unit_code", sa.String(80)),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
        ),
        sa.Column("state", sa.String(2)),
        sa.Column("power", sa.String(40)),
        sa.Column("sphere", sa.String(40)),
        sa.UniqueConstraint("source_system", "source_key", name="uq_agency_source_key"),
    )
    for column in ("source_system", "entity_identifier", "municipality_ibge_code", "state"):
        op.create_index(f"ix_agencies_{column}", "agencies", [column])

    op.create_table(
        "suppliers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(160), nullable=False),
        sa.Column("name", sa.String(320)),
        sa.Column("identifier_type", sa.String(20), nullable=False),
        sa.Column("identifier", sa.String(32)),
        sa.Column("public_identity", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("privacy_review", sa.String(80), nullable=False, server_default="pending"),
        sa.UniqueConstraint("source_system", "source_key", name="uq_supplier_source_key"),
    )
    op.create_index("ix_suppliers_source_system", "suppliers", ["source_system"])
    op.create_index("ix_suppliers_identifier", "suppliers", ["identifier"])

    op.create_table(
        "budget_accounts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("account_code", sa.String(120), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("account_type", sa.String(60)),
        sa.Column("hierarchy", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
        sa.UniqueConstraint("source_system", "account_code", name="uq_budget_account_source_code"),
    )
    op.create_index("ix_budget_accounts_source_system", "budget_accounts", ["source_system"])
    op.create_index("ix_budget_accounts_account_type", "budget_accounts", ["account_type"])

    op.create_table(
        "fiscal_statements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(240), nullable=False),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
            nullable=False,
        ),
        sa.Column("agency_id", sa.Uuid(), sa.ForeignKey("agencies.id")),
        sa.Column("budget_account_id", sa.Uuid(), sa.ForeignKey("budget_accounts.id")),
        sa.Column("statement_type", sa.String(60), nullable=False),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("reference_period", sa.Integer()),
        sa.Column("periodicity", sa.String(30)),
        sa.Column("annex", sa.String(100)),
        sa.Column("power", sa.String(20)),
        sa.Column("column_code", sa.String(120)),
        sa.Column("amount", sa.Numeric(24, 6)),
        sa.Column("availability_status", sa.String(40), nullable=False),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("source_published_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_fiscal_statement_revision"
        ),
    )
    for column in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "agency_id",
        "budget_account_id",
        "statement_type",
        "reference_year",
        "reference_period",
        "availability_status",
        "snapshot_id",
    ):
        op.create_index(f"ix_fiscal_statements_{column}", "fiscal_statements", [column])
    op.create_index(
        "ix_fiscal_statement_municipality_year_source",
        "fiscal_statements",
        ["municipality_ibge_code", "reference_year", "source_system"],
    )

    op.create_table(
        "procurements",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(180), nullable=False),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
        ),
        sa.Column("agency_id", sa.Uuid(), sa.ForeignKey("agencies.id"), nullable=False),
        sa.Column("procurement_year", sa.Integer(), nullable=False),
        sa.Column("procurement_number", sa.String(160)),
        sa.Column("process_number", sa.String(200)),
        sa.Column("object_description", sa.Text(), nullable=False),
        sa.Column("modality_code", sa.String(40)),
        sa.Column("modality_name", sa.String(160)),
        sa.Column("status", sa.String(160)),
        sa.Column("sector", sa.String(100)),
        sa.Column("estimated_amount", sa.Numeric(24, 6)),
        sa.Column("homologated_amount", sa.Numeric(24, 6)),
        sa.Column("proposal_start_at", sa.DateTime(timezone=True)),
        sa.Column("proposal_end_at", sa.DateTime(timezone=True)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_procurement_revision"
        ),
    )
    for column in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "agency_id",
        "procurement_year",
        "modality_code",
        "modality_name",
        "status",
        "sector",
        "published_at",
        "source_updated_at",
        "snapshot_id",
    ):
        op.create_index(f"ix_procurements_{column}", "procurements", [column])
    op.create_index(
        "ix_procurement_municipality_year_status",
        "procurements",
        ["municipality_ibge_code", "procurement_year", "status"],
    )

    op.create_table(
        "procurement_items",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("procurement_id", sa.Uuid(), sa.ForeignKey("procurements.id"), nullable=False),
        sa.Column("item_number", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("quantity", sa.Numeric(24, 6)),
        sa.Column("unit", sa.String(100)),
        sa.Column("estimated_unit_amount", sa.Numeric(24, 6)),
        sa.Column("estimated_total_amount", sa.Numeric(24, 6)),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.UniqueConstraint("procurement_id", "item_number", name="uq_procurement_item"),
    )
    op.create_index("ix_procurement_items_procurement_id", "procurement_items", ["procurement_id"])
    op.create_index("ix_procurement_items_snapshot_id", "procurement_items", ["snapshot_id"])

    op.create_table(
        "contracts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(180), nullable=False),
        sa.Column("procurement_source_key", sa.String(180)),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
        ),
        sa.Column("agency_id", sa.Uuid(), sa.ForeignKey("agencies.id"), nullable=False),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id")),
        sa.Column("contract_year", sa.Integer(), nullable=False),
        sa.Column("contract_number", sa.String(160)),
        sa.Column("object_description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(100)),
        sa.Column("initial_amount", sa.Numeric(24, 6)),
        sa.Column("global_amount", sa.Numeric(24, 6)),
        sa.Column("signed_at", sa.Date()),
        sa.Column("validity_start", sa.Date()),
        sa.Column("validity_end", sa.Date()),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("source_system", "source_key", "revision", name="uq_contract_revision"),
    )
    for column in (
        "source_system",
        "source_key",
        "procurement_source_key",
        "municipality_ibge_code",
        "agency_id",
        "supplier_id",
        "contract_year",
        "status",
        "snapshot_id",
    ):
        op.create_index(f"ix_contracts_{column}", "contracts", [column])

    op.create_table(
        "transfers",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(180), nullable=False),
        sa.Column(
            "municipality_ibge_code",
            sa.String(7),
            sa.ForeignKey("municipalities.ibge_code"),
        ),
        sa.Column("agency_id", sa.Uuid(), sa.ForeignKey("agencies.id")),
        sa.Column("program_code", sa.String(100)),
        sa.Column("program_name", sa.String(240)),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("transfer_type", sa.String(80), nullable=False),
        sa.Column("planned_amount", sa.Numeric(24, 6)),
        sa.Column("paid_amount", sa.Numeric(24, 6)),
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("source_system", "source_key", "revision", name="uq_transfer_revision"),
    )
    for column in (
        "source_system",
        "source_key",
        "municipality_ibge_code",
        "agency_id",
        "program_code",
        "reference_year",
        "transfer_type",
        "snapshot_id",
    ):
        op.create_index(f"ix_transfers_{column}", "transfers", [column])

    _seed_sources_and_datasets()


def _seed_sources_and_datasets() -> None:
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
                "id": SOURCE_IDS["pncp"],
                "provider": "Portal Nacional de Contratações Públicas",
                "slug": "pncp-consulta-publica",
                "source_url": "https://pncp.gov.br/api/consulta/swagger-ui/index.html",
                "license": "Dados abertos; condições do PNCP e LAI",
                "terms": (
                    "Consulta pública sem autenticação; origem permanece responsável pelos dados."
                ),
                "expected_frequency": "diária por atualização global",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {"inventory_ids": ["LNT-0038", "LNT-0104", "LNT-0105"]},
            },
            {
                "id": SOURCE_IDS["tcesp"],
                "provider": "Tribunal de Contas do Estado de São Paulo",
                "slug": "tcesp-receitas-csv",
                "source_url": "https://transparencia.tce.sp.gov.br/conjunto-de-dados",
                "license": "Reutilização específica não declarada na página auditada",
                "terms": "Dados declarados pelos municípios ao Audesp e sujeitos à fiscalização.",
                "expected_frequency": "semanal por exercício",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {"inventory_ids": ["LNT-0040", "LNT-0099"]},
            },
            {
                "id": SOURCE_IDS["rgf"],
                "provider": "Tesouro Nacional — Siconfi",
                "slug": "siconfi-rgf",
                "source_url": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
                "license": "Apache 2.0",
                "terms": "Limite oficial de uma requisição por segundo.",
                "expected_frequency": "quadrimestral ou semestral",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {"inventory_id": "LNT-0094"},
            },
            {
                "id": SOURCE_IDS["dca"],
                "provider": "Tesouro Nacional — Siconfi",
                "slug": "siconfi-dca",
                "source_url": "https://apidatalake.tesouro.gov.br/docs/siconfi/",
                "license": "Apache 2.0",
                "terms": "Limite oficial de uma requisição por segundo.",
                "expected_frequency": "anual",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {"inventory_id": "LNT-0095"},
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
                "id": DATASET_IDS["pncp"],
                "source_id": SOURCE_IDS["pncp"],
                "code": "pncp_procurements",
                "title": "Contratações publicadas no PNCP",
                "description": (
                    "Contratações por publicação/atualização, sem inferência de irregularidade."
                ),
                "domain": "financas-publicas",
                "granularity": "contratação/versão",
                "update_policy": "incremental por data de atualização e modalidade",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0038"},
            },
            {
                "id": DATASET_IDS["tcesp"],
                "source_id": SOURCE_IDS["tcesp"],
                "code": "tcesp_revenues",
                "title": "Receitas municipais TCE-SP/Audesp",
                "description": "Receitas mensais por rubrica e fonte declaradas ao Audesp.",
                "domain": "financas-publicas",
                "granularity": "município/mês/rubrica/fonte",
                "update_policy": "arquivo anual revalidado semanalmente",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0099"},
            },
            {
                "id": DATASET_IDS["pncp_contracts"],
                "source_id": SOURCE_IDS["pncp"],
                "code": "pncp_contracts",
                "title": "Contratos e empenhos publicados no PNCP",
                "description": (
                    "Contratos por publicação/atualização; fornecedor suprimido até revisão LGPD."
                ),
                "domain": "financas-publicas",
                "granularity": "contrato/versão",
                "update_policy": "incremental por data de atualização e CNPJ de órgão homologado",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0038"},
            },
            {
                "id": DATASET_IDS["rgf"],
                "source_id": SOURCE_IDS["rgf"],
                "code": "siconfi_rgf",
                "title": "Siconfi — Relatório de Gestão Fiscal",
                "description": "Linhas dos anexos RGF preservando conta, coluna, poder e período.",
                "domain": "financas-publicas",
                "granularity": "ente/período/anexo/conta/coluna",
                "update_policy": "quadrimestral ou semestral",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0094"},
            },
            {
                "id": DATASET_IDS["dca"],
                "source_id": SOURCE_IDS["dca"],
                "code": "siconfi_dca",
                "title": "Siconfi — Declaração de Contas Anuais",
                "description": "Linhas dos anexos DCA preservando conta e coluna original.",
                "domain": "financas-publicas",
                "granularity": "ente/ano/anexo/conta/coluna",
                "update_policy": "anual",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0095"},
            },
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    dataset_ids = tuple(DATASET_IDS.values())
    connection.execute(
        sa.text("UPDATE catalog_entries SET dataset_id=NULL WHERE dataset_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": dataset_ids},
    )
    connection.execute(
        sa.text(
            "DELETE FROM data_quality_issues WHERE run_id IN "
            "(SELECT id FROM ingestion_runs WHERE dataset_id IN :ids)"
        ).bindparams(sa.bindparam("ids", expanding=True)),
        {"ids": dataset_ids},
    )
    for table in ("ingestion_jobs", "ingestion_runs", "publication_releases"):
        connection.execute(
            sa.text(f"DELETE FROM {table} WHERE dataset_id IN :ids").bindparams(  # noqa: S608
                sa.bindparam("ids", expanding=True)
            ),
            {"ids": dataset_ids},
        )
    for table in (
        "transfers",
        "contracts",
        "procurement_items",
        "procurements",
        "fiscal_statements",
    ):
        op.drop_table(table)
    connection.execute(
        sa.text("DELETE FROM source_snapshots WHERE dataset_id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": dataset_ids},
    )
    connection.execute(
        sa.text("DELETE FROM datasets WHERE id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": dataset_ids},
    )
    source_ids = tuple(SOURCE_IDS.values())
    connection.execute(
        sa.text("DELETE FROM sources WHERE id IN :ids").bindparams(
            sa.bindparam("ids", expanding=True)
        ),
        {"ids": source_ids},
    )
    op.drop_table("budget_accounts")
    op.drop_table("suppliers")
    op.drop_table("agencies")
