"""Add political accountability and public works foundations.

Revision ID: 0021
Revises: 0020
"""

# ruff: noqa: E501

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None

SOURCES = (
    (
        UUID("20000000-0000-4000-8000-000000000050"),
        UUID("21000000-0000-4000-8000-000000000050"),
        "Tribunal Superior Eleitoral — Dados Abertos",
        "tse-dados-abertos-candidaturas",
        "https://dadosabertos.tse.jus.br/pt_BR/dataset/?groups=candidatos",
        "tse_candidacies",
        "Candidaturas e eleitos — TSE",
        "participacao-e-democracia",
        "planned",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000051"),
        UUID("21000000-0000-4000-8000-000000000051"),
        "Câmara dos Deputados — Dados Abertos",
        "camara-dados-abertos",
        "https://dadosabertos.camara.leg.br/swagger/api.html",
        "camara_legislative_activity",
        "Atuação e despesas parlamentares — Câmara",
        "participacao-e-democracia",
        "planned",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000052"),
        UUID("21000000-0000-4000-8000-000000000052"),
        "Senado Federal — Dados Abertos",
        "senado-dados-abertos",
        "https://legis.senado.leg.br/dadosabertos/api-docs/swagger-ui/index.html",
        "senado_legislative_activity",
        "Atuação e despesas parlamentares — Senado",
        "participacao-e-democracia",
        "planned",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000053"),
        UUID("21000000-0000-4000-8000-000000000053"),
        "Obrasgov.br — Dados Abertos",
        "obrasgov-dados-abertos",
        "https://api-publica.obrasgov.gestao.gov.br/obras/docs",
        "obrasgov_public_works",
        "Obras públicas financiadas com recursos federais",
        "infraestrutura-e-cidades",
        "planned",
    ),
)


def _revision_columns(*, municipality: bool = False) -> list[sa.Column]:
    columns = [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("source_system", sa.String(40), nullable=False),
        sa.Column("source_key", sa.String(240), nullable=False),
    ]
    if municipality:
        columns.append(
            sa.Column(
                "municipality_ibge_code",
                sa.String(7),
                sa.ForeignKey("municipalities.ibge_code"),
            )
        )
    return columns


def _provenance_columns() -> list[sa.Column]:
    return [
        sa.Column("source_document_url", sa.Text(), nullable=False),
        sa.Column("snapshot_id", sa.Uuid(), sa.ForeignKey("source_snapshots.id"), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    ]


def upgrade() -> None:
    op.create_table(
        "political_people",
        *_revision_columns(),
        sa.Column("full_name", sa.String(260), nullable=False),
        sa.Column("ballot_name", sa.String(180)),
        sa.Column("slug", sa.String(220), nullable=False),
        sa.Column("photo_url", sa.Text()),
        *_provenance_columns(),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_political_person_revision"
        ),
    )
    op.create_table(
        "political_mandates",
        *_revision_columns(municipality=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("political_people.id"), nullable=False),
        sa.Column("election_year", sa.Integer(), nullable=False),
        sa.Column("office_code", sa.String(80), nullable=False),
        sa.Column("office_name", sa.String(160), nullable=False),
        sa.Column("government_level", sa.String(30), nullable=False),
        sa.Column("state", sa.String(2)),
        sa.Column("party_acronym", sa.String(30)),
        sa.Column("elected_status", sa.String(100), nullable=False),
        sa.Column("term_start", sa.Date()),
        sa.Column("term_end", sa.Date()),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        *_provenance_columns(),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_political_mandate_revision"
        ),
    )
    op.create_table(
        "political_candidacies",
        *_revision_columns(municipality=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("political_people.id"), nullable=False),
        sa.Column("election_year", sa.Integer(), nullable=False),
        sa.Column("election_type", sa.String(120), nullable=False),
        sa.Column("office_code", sa.String(80), nullable=False),
        sa.Column("office_name", sa.String(160), nullable=False),
        sa.Column("state", sa.String(2)),
        sa.Column("ballot_number", sa.String(20)),
        sa.Column("party_acronym", sa.String(30)),
        sa.Column("registration_status", sa.String(120)),
        sa.Column("election_result", sa.String(120)),
        sa.Column("vote_count", sa.Integer()),
        *_provenance_columns(),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_political_candidacy_revision"
        ),
    )
    op.create_table(
        "declared_asset_summaries",
        *_revision_columns(),
        sa.Column(
            "candidacy_id",
            sa.Uuid(),
            sa.ForeignKey("political_candidacies.id"),
            nullable=False,
        ),
        sa.Column("election_year", sa.Integer(), nullable=False),
        sa.Column("asset_type_code", sa.String(60), nullable=False),
        sa.Column("asset_type_name", sa.String(240), nullable=False),
        sa.Column("asset_count", sa.Integer(), nullable=False),
        sa.Column("total_amount", sa.Numeric(24, 6), nullable=False),
        *_provenance_columns(),
        sa.UniqueConstraint(
            "source_system",
            "source_key",
            "revision",
            name="uq_declared_asset_summary_revision",
        ),
    )
    op.create_table(
        "legislative_proposals",
        *_revision_columns(),
        sa.Column("chamber", sa.String(60), nullable=False),
        sa.Column("proposal_type", sa.String(80), nullable=False),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("summary", sa.Text()),
        sa.Column("themes", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(180)),
        sa.Column("presented_at", sa.DateTime(timezone=True)),
        sa.Column("updated_at_source", sa.DateTime(timezone=True)),
        *_provenance_columns(),
        sa.UniqueConstraint(
            "source_system",
            "source_key",
            "revision",
            name="uq_legislative_proposal_revision",
        ),
    )
    op.create_table(
        "proposal_authors",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "proposal_id",
            sa.Uuid(),
            sa.ForeignKey("legislative_proposals.id"),
            nullable=False,
        ),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("political_people.id")),
        sa.Column("author_name", sa.String(260), nullable=False),
        sa.Column("party_acronym", sa.String(30)),
        sa.UniqueConstraint("proposal_id", "person_id", "author_name", name="uq_proposal_author"),
    )
    op.create_table(
        "political_expenses",
        *_revision_columns(),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("political_people.id"), nullable=False),
        sa.Column("chamber", sa.String(60), nullable=False),
        sa.Column("reference_year", sa.Integer(), nullable=False),
        sa.Column("reference_month", sa.Integer()),
        sa.Column("category", sa.String(240), nullable=False),
        sa.Column("amount", sa.Numeric(24, 6), nullable=False),
        *_provenance_columns(),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_political_expense_revision"
        ),
    )
    op.create_table(
        "political_scores",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("person_id", sa.Uuid(), sa.ForeignKey("political_people.id"), nullable=False),
        sa.Column("peer_group", sa.String(180), nullable=False),
        sa.Column("reference_start", sa.Date(), nullable=False),
        sa.Column("reference_end", sa.Date(), nullable=False),
        sa.Column("methodology_version", sa.String(60), nullable=False),
        sa.Column("score", sa.Numeric(7, 4), nullable=False),
        sa.Column("rank", sa.Integer()),
        sa.Column("peer_count", sa.Integer()),
        sa.Column("coverage_ratio", sa.Numeric(7, 6), nullable=False),
        sa.Column("components", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("caveats", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("score >= 0 AND score <= 100", name="ck_political_score_range"),
        sa.CheckConstraint(
            "coverage_ratio >= 0 AND coverage_ratio <= 1",
            name="ck_political_score_coverage",
        ),
        sa.UniqueConstraint(
            "person_id",
            "peer_group",
            "reference_start",
            "reference_end",
            "methodology_version",
            name="uq_political_score_window",
        ),
    )
    op.create_table(
        "public_works",
        *_revision_columns(municipality=True),
        sa.Column("state", sa.String(2)),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("category", sa.String(160)),
        sa.Column("status", sa.String(120)),
        sa.Column("situation_detail", sa.Text()),
        sa.Column("executor_name", sa.String(320)),
        sa.Column("responsible_agency", sa.String(320)),
        sa.Column("planned_start", sa.Date()),
        sa.Column("planned_end", sa.Date()),
        sa.Column("actual_start", sa.Date()),
        sa.Column("actual_end", sa.Date()),
        sa.Column("estimated_amount", sa.Numeric(24, 6)),
        sa.Column("contracted_amount", sa.Numeric(24, 6)),
        sa.Column("paid_amount", sa.Numeric(24, 6)),
        sa.Column("physical_progress", sa.Numeric(7, 4)),
        sa.Column("latitude", sa.Numeric(10, 7)),
        sa.Column("longitude", sa.Numeric(10, 7)),
        sa.Column("source_updated_at", sa.DateTime(timezone=True)),
        *_provenance_columns(),
        sa.UniqueConstraint(
            "source_system", "source_key", "revision", name="uq_public_work_revision"
        ),
    )
    _create_indexes()
    _seed_sources()


def _create_indexes() -> None:
    indexed = {
        "political_people": (
            "source_system",
            "source_key",
            "full_name",
            "ballot_name",
            "slug",
            "snapshot_id",
        ),
        "political_mandates": (
            "source_system",
            "source_key",
            "person_id",
            "election_year",
            "office_code",
            "government_level",
            "state",
            "municipality_ibge_code",
            "party_acronym",
            "elected_status",
            "term_start",
            "term_end",
            "active",
            "snapshot_id",
        ),
        "political_candidacies": (
            "source_system",
            "source_key",
            "person_id",
            "election_year",
            "office_code",
            "state",
            "municipality_ibge_code",
            "party_acronym",
            "registration_status",
            "election_result",
            "snapshot_id",
        ),
        "declared_asset_summaries": (
            "source_system",
            "source_key",
            "candidacy_id",
            "election_year",
            "asset_type_code",
            "snapshot_id",
        ),
        "legislative_proposals": (
            "source_system",
            "source_key",
            "chamber",
            "proposal_type",
            "number",
            "year",
            "status",
            "snapshot_id",
        ),
        "proposal_authors": ("proposal_id", "person_id"),
        "political_expenses": (
            "source_system",
            "source_key",
            "person_id",
            "chamber",
            "reference_year",
            "reference_month",
            "category",
            "snapshot_id",
        ),
        "political_scores": (
            "person_id",
            "peer_group",
            "reference_start",
            "reference_end",
            "methodology_version",
            "calculated_at",
        ),
        "public_works": (
            "source_system",
            "source_key",
            "municipality_ibge_code",
            "state",
            "name",
            "category",
            "status",
            "snapshot_id",
        ),
    }
    for table, columns in indexed.items():
        for column in columns:
            op.create_index(f"ix_{table}_{column}", table, [column])


def _seed_sources() -> None:
    now = datetime.now(UTC)
    for source_id, dataset_id, provider, slug, url, code, title, domain, connector in SOURCES:
        op.execute(
            sa.text(
                """INSERT INTO sources
                (id,provider,slug,source_url,license,terms,expected_frequency,status,
                 verified_at,source_status,connector_status,catalog_metadata)
                VALUES (:id,:provider,:slug,:url,
                'Dados públicos oficiais; atribuição obrigatória ao provedor',
                'Publicação de dados funcionais e agregados; identificadores pessoais não necessários são descartados.',
                'conforme atualização oficial','confirmed',:now,'verified',:connector,CAST(:metadata AS jsonb))"""
            ).bindparams(
                id=source_id,
                provider=provider,
                slug=slug,
                url=url,
                now=now,
                connector=connector,
                metadata='{"audit_date":"2026-10-30"}',
            )
        )
        op.execute(
            sa.text(
                """INSERT INTO datasets
                (id,source_id,code,title,description,domain,granularity,update_policy,status,
                 connector_status,publication_status,catalog_metadata)
                VALUES (:id,:source,:code,:title,:description,:domain,:granularity,
                'incremental por atualização oficial','confirmed',:connector,'not_published',
                CAST(:metadata AS jsonb))"""
            ).bindparams(
                id=dataset_id,
                source=source_id,
                code=code,
                title=title,
                description="Recurso oficial versionado e publicável somente após validação e rastreabilidade.",
                domain=domain,
                granularity=(
                    "pessoa/candidatura/eleição"
                    if code == "tse_candidacies"
                    else "obra/município/atualização"
                    if code == "obrasgov_public_works"
                    else "pessoa/proposição/período"
                ),
                connector=connector,
                metadata='{"contains_personal_data":false,"publication_requires_validation":true}',
            )
        )


def downgrade() -> None:
    connection = op.get_bind()
    for _, dataset_id, *_ in reversed(SOURCES):
        connection.execute(
            sa.text("DELETE FROM source_snapshots WHERE dataset_id=:id"), {"id": dataset_id}
        )
        connection.execute(sa.text("DELETE FROM datasets WHERE id=:id"), {"id": dataset_id})
    for source_id, *_ in reversed(SOURCES):
        connection.execute(sa.text("DELETE FROM sources WHERE id=:id"), {"id": source_id})
    for table in (
        "public_works",
        "political_scores",
        "political_expenses",
        "proposal_authors",
        "legislative_proposals",
        "declared_asset_summaries",
        "political_candidacies",
        "political_mandates",
        "political_people",
    ):
        op.drop_table(table)
