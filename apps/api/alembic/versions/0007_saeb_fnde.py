"""Add audited Saeb and FNDE/PNAE datasets.

Revision ID: 0007
Revises: 0006
"""

from __future__ import annotations

from datetime import UTC, datetime

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

SAEB_SOURCE = "10000000-0000-4000-8000-000000000010"
PNAE_SOURCE = "10000000-0000-4000-8000-000000000081"
SAEB_DATASET = "11000000-0000-4000-8000-000000000010"
PNAE_DATASET = "11000000-0000-4000-8000-000000000081"


def upgrade() -> None:
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
                "id": SAEB_SOURCE,
                "provider": "Inep",
                "slug": "inep-saeb-municipal",
                "source_url": (
                    "https://www.gov.br/inep/pt-br/areas-de-atuacao/"
                    "avaliacao-e-exames-educacionais/saeb/resultados/2023"
                ),
                "license": "Dados abertos; observar notas metodológicas do Inep",
                "terms": "Publicar somente resultados agregados e preservar supressões.",
                "expected_frequency": "bienal",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {"verified_artifact": "planilha_de_resultados_2023.rar"},
            },
            {
                "id": PNAE_SOURCE,
                "provider": "FNDE",
                "slug": "fnde-pnae-municipal",
                "source_url": (
                    "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/"
                    "programas/pnae/consultas/repasses-financeiros-por-entidade-executora"
                ),
                "license": (
                    "Portal gov.br sob CC BY-ND 3.0; licença específica do arquivo não indicada"
                ),
                "terms": "Valores são previsões de repasse, não pagamentos nem despesas.",
                "expected_frequency": "anual",
                "status": "confirmed",
                "verified_at": now,
                "failure_reason": None,
                "source_status": "verified",
                "connector_status": "implemented",
                "catalog_metadata": {
                    "verified_artifact": (
                        "DadosFinanceirosdoPNAE_RedesEstadual_Distrital_"
                        "Municipal_PorEntidadeExecutora_2024.xlsx"
                    )
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
                "id": SAEB_DATASET,
                "source_id": SAEB_SOURCE,
                "code": "inep_saeb_municipal",
                "title": "Saeb municipal 2023",
                "description": "Médias agregadas por município, rede e etapa avaliada.",
                "domain": "educacao",
                "granularity": "município/ano/rede/etapa",
                "update_policy": "bienal após validação",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0010"},
            },
            {
                "id": PNAE_DATASET,
                "source_id": PNAE_SOURCE,
                "code": "fnde_pnae_municipal",
                "title": "PNAE — previsão municipal de repasses",
                "description": "Alunos considerados e valores previstos por ação do PNAE.",
                "domain": "educacao",
                "granularity": "município/ano/ação",
                "update_policy": "anual após validação",
                "status": "confirmed",
                "connector_status": "implemented",
                "publication_status": "not_published",
                "catalog_metadata": {"inventory_id": "LNT-0081"},
            },
        ],
    )
    networks = sa.table("education_networks", sa.column("code"), sa.column("name"))
    op.bulk_insert(networks, [{"code": "all", "name": "Todas as redes"}])
    stages = sa.table(
        "education_stages",
        sa.column("code"),
        sa.column("name"),
        sa.column("display_order"),
    )
    op.bulk_insert(
        stages,
        [
            {
                "code": "fundamental_year_5",
                "name": "5º ano do ensino fundamental",
                "display_order": 25,
            },
            {
                "code": "fundamental_year_9",
                "name": "9º ano do ensino fundamental",
                "display_order": 29,
            },
            {
                "code": "secondary_year_3",
                "name": "3ª/4ª série do ensino médio",
                "display_order": 35,
            },
            {"code": "pnae_daycare", "name": "PNAE — creche", "display_order": 110},
            {"code": "pnae_pre_school", "name": "PNAE — pré-escola", "display_order": 111},
            {"code": "pnae_fundamental", "name": "PNAE — ensino fundamental", "display_order": 112},
            {"code": "pnae_secondary", "name": "PNAE — ensino médio", "display_order": 113},
            {"code": "pnae_special_education", "name": "PNAE — AEE", "display_order": 114},
            {"code": "pnae_youth_adult", "name": "PNAE — EJA", "display_order": 115},
            {"code": "pnae_indigenous", "name": "PNAE — indígena", "display_order": 116},
            {"code": "pnae_quilombola", "name": "PNAE — quilombola", "display_order": 117},
            {
                "code": "pnae_full_time_secondary",
                "name": "PNAE — ensino médio integral",
                "display_order": 118,
            },
        ],
    )


def downgrade() -> None:
    connection = op.get_bind()
    parameters = {"saeb": SAEB_DATASET, "pnae": PNAE_DATASET}
    connection.execute(
        sa.text(
            "DELETE FROM education_metrics WHERE release_id IN "
            "(SELECT id FROM publication_releases WHERE dataset_id IN (:saeb, :pnae))"
        ),
        parameters,
    )
    connection.execute(
        sa.text(
            "DELETE FROM data_quality_issues WHERE run_id IN "
            "(SELECT id FROM ingestion_runs WHERE dataset_id IN (:saeb, :pnae))"
        ),
        parameters,
    )
    for table in ("ingestion_jobs", "ingestion_runs", "publication_releases", "source_snapshots"):
        connection.execute(
            sa.text(f"DELETE FROM {table} WHERE dataset_id IN (:saeb, :pnae)"),  # noqa: S608
            parameters,
        )
    connection.execute(
        sa.text("UPDATE catalog_entries SET dataset_id=NULL WHERE dataset_id IN (:saeb, :pnae)"),
        parameters,
    )
    connection.execute(sa.text("DELETE FROM datasets WHERE id IN (:saeb, :pnae)"), parameters)
    connection.execute(
        sa.text("DELETE FROM sources WHERE id IN (:saeb, :pnae)"),
        {"saeb": SAEB_SOURCE, "pnae": PNAE_SOURCE},
    )
    stage_codes = (
        "fundamental_year_5",
        "fundamental_year_9",
        "secondary_year_3",
        "pnae_daycare",
        "pnae_pre_school",
        "pnae_fundamental",
        "pnae_secondary",
        "pnae_special_education",
        "pnae_youth_adult",
        "pnae_indigenous",
        "pnae_quilombola",
        "pnae_full_time_secondary",
    )
    stages = sa.table("education_stages", sa.column("code"))
    connection.execute(stages.delete().where(stages.c.code.in_(stage_codes)))
    connection.execute(sa.text("DELETE FROM education_networks WHERE code='all'"))
