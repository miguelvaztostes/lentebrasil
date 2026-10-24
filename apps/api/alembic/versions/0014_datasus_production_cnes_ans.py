"""Register DATASUS production, CNES services and ANS municipal coverage.

Revision ID: 0014
Revises: 0013
"""

# ruff: noqa: E501

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None

SOURCES = (
    (
        UUID("20000000-0000-4000-8000-000000000024"),
        "DATASUS — SIH/SUS",
        "datasus-sih",
        "ftp://ftp.datasus.gov.br/dissemin/publicos/SIHSUS/200801_/Dados",
        "sih_production_municipal",
        "SIH/SUS — produção hospitalar municipal",
        "LNT-0022",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000025"),
        "DATASUS — SIA/SUS",
        "datasus-sia",
        "ftp://ftp.datasus.gov.br/dissemin/publicos/SIASUS/200801_/Dados",
        "sia_production_municipal",
        "SIA/SUS — produção ambulatorial municipal",
        "LNT-0023",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000026"),
        "DATASUS — CNES",
        "datasus-cnes-servicos",
        "ftp://ftp.datasus.gov.br/dissemin/publicos/CNES/200508_/Dados/SR",
        "cnes_services",
        "CNES — serviços especializados cadastrados",
        None,
    ),
    (
        UUID("20000000-0000-4000-8000-000000000027"),
        "Agência Nacional de Saúde Suplementar",
        "ans-beneficiarios-municipios",
        "https://dadosabertos.ans.gov.br/FTP/Base_de_dados/Microdados/dados_dbc/beneficiarios/municipios/",
        "ans_beneficiaries_municipal",
        "ANS — vínculos de beneficiários por município",
        "LNT-0026",
    ),
)


def upgrade() -> None:
    now = datetime.now(UTC)
    for index, (source_id, provider, slug, url, code, title, inventory_id) in enumerate(SOURCES):
        dataset_id = UUID(f"21000000-0000-4000-8000-{24 + index:012d}")
        op.execute(
            sa.text("""INSERT INTO sources (id, provider, slug, source_url, license, terms, expected_frequency, status, verified_at, source_status, connector_status, catalog_metadata)
            VALUES (:id, :provider, :slug, :url, :license, :terms, 'mensal', 'confirmed', :now, 'verified', 'implemented', CAST(:metadata AS jsonb))""").bindparams(
                id=source_id,
                provider=provider,
                slug=slug,
                url=url,
                license="Dados públicos oficiais; verificar atribuição e termos do provedor em cada redistribuição",
                terms="Publicação somente agregada. Identificadores pessoais e campos nominais do arquivo de origem são descartados.",
                now=now,
                metadata=(
                    f'{{"inventory_id":"{inventory_id}","reference_competence":"2025-12"}}'
                    if inventory_id
                    else '{"reference_competence":"2025-12"}'
                ),
            )
        )
        op.execute(
            sa.text("""INSERT INTO datasets (id, source_id, code, title, description, domain, granularity, update_policy, status, connector_status, publication_status, catalog_metadata)
            VALUES (:id, :source, :code, :title, :description, 'saude', :granularity, 'mensal após publicação oficial', 'confirmed', 'implemented', 'not_published', CAST(:metadata AS jsonb))""").bindparams(
                id=dataset_id,
                source=source_id,
                code=code,
                title=title,
                description=(
                    "Competência dezembro de 2025, convertida de DBC e agregada antes da persistência; "
                    "o arquivo bruto e campos individuais não são publicados."
                ),
                granularity=(
                    "município/competência/procedimento/tipo de unidade"
                    if code in {"sih_production_municipal", "sia_production_municipal"}
                    else "município/competência/serviço/classificação"
                    if code == "cnes_services"
                    else "município/competência/status"
                ),
                metadata='{"reference_year":2025,"reference_month":12,"raw_retention":false}',
            )
        )
        if inventory_id:
            op.execute(
                sa.text("""UPDATE catalog_entries SET dataset_id=:dataset, integration_decision='integrate',
                decision_reason='Recurso oficial 2025-12 verificado e conector DBC homologado', decided_at=now()
                WHERE external_catalog_id=:inventory""").bindparams(
                    dataset=dataset_id, inventory=inventory_id
                )
            )
    op.execute(
        sa.text("""INSERT INTO indicators (id, code, label, definition, unit, periodicity, methodology, disaggregation_schema, limitations, domain, direction)
        VALUES (:id, 'ans_health_plan_beneficiary_links', 'Vínculos de beneficiários de planos de saúde',
        'Quantidade de vínculos de beneficiários informados pela ANS para o município na competência.', 'vínculos', 'trimestral',
        'Soma das células municipais do arquivo DBC oficial; TP_VIGENCI distingue planos anteriores e posteriores à Lei 9.656/1998 e não é filtro de situação ativa.',
        CAST(:schema AS jsonb), 'Uma pessoa pode possuir mais de um vínculo; não mede acesso efetivo nem qualidade.', 'saude', NULL)""").bindparams(
            id=UUID("30000000-0000-4000-8000-000000000024"),
            schema='{"coverage":"all","counting_unit":"beneficiary_links"}',
        )
    )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text("DELETE FROM observations WHERE indicator_id=:id"),
        {"id": UUID("30000000-0000-4000-8000-000000000024")},
    )
    connection.execute(
        sa.text("DELETE FROM indicators WHERE id=:id"),
        {"id": UUID("30000000-0000-4000-8000-000000000024")},
    )
    for index, (source_id, _, _, _, code, _, _) in reversed(tuple(enumerate(SOURCES))):
        dataset_id = UUID(f"21000000-0000-4000-8000-{24 + index:012d}")
        if code in {"sih_production_municipal", "sia_production_municipal"}:
            connection.execute(
                sa.text(
                    "DELETE FROM health_production WHERE snapshot_id IN "
                    "(SELECT id FROM source_snapshots WHERE dataset_id=:id)"
                ),
                {"id": dataset_id},
            )
        elif code == "cnes_services":
            connection.execute(
                sa.text(
                    "DELETE FROM health_services WHERE snapshot_id IN "
                    "(SELECT id FROM source_snapshots WHERE dataset_id=:id)"
                ),
                {"id": dataset_id},
            )
            connection.execute(
                sa.text(
                    "DELETE FROM health_establishments WHERE snapshot_id IN "
                    "(SELECT id FROM source_snapshots WHERE dataset_id=:id)"
                ),
                {"id": dataset_id},
            )
        connection.execute(
            sa.text(
                "UPDATE catalog_entries SET dataset_id=NULL, integration_decision='manual_review' WHERE dataset_id=:id"
            ),
            {"id": dataset_id},
        )
        connection.execute(
            sa.text("DELETE FROM source_snapshots WHERE dataset_id=:id"), {"id": dataset_id}
        )
        connection.execute(sa.text("DELETE FROM datasets WHERE id=:id"), {"id": dataset_id})
        connection.execute(sa.text("DELETE FROM sources WHERE id=:id"), {"id": source_id})
