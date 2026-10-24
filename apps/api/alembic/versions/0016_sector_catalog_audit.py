"""Record integration decisions for the sector source wave.

Revision ID: 0016
Revises: 0015
"""

import sqlalchemy as sa

from alembic import op

revision = "0016"
down_revision = "0015"
branch_labels = None
depends_on = None

DECISIONS = {
    "LNT-0030": (
        "RAIS anual oficial acessível por FTP; arquivo volumoso e schema ainda não homologados."
    ),
    "LNT-0031": "ISPER é portal consultivo; exportação estável ainda não verificada.",
    "LNT-0032": (
        "Comex Stat possui arquivos oficiais; grão de domicílio fiscal ainda requer homologação."
    ),
    "LNT-0033": "CNPJ aberto exige revisão de termos, MEI e dados pessoais antes de publicação.",
    "LNT-0034": "Séries BCB são nacionais; não podem ser atribuídas a municípios.",
    "LNT-0035": "PAM/PPM e Censo Agropecuário permanecem para conector SIDRA próprio.",
    "LNT-0043": "API CGU requer token autorizado não presente no ambiente.",
    "LNT-0044": "API CGU requer token autorizado não presente no ambiente.",
    "LNT-0045": "VIS DATA/CECAD não expôs artefato versionado ou API estável homologável.",
    "LNT-0046": "Censo SUAS aguarda seleção de recurso, edição e dicionário compatíveis.",
    "LNT-0047": "SINISA 2025/ref. 2024 localizado; módulos e schemas aguardam homologação.",
    "LNT-0049": "ANEEL GD oferece recursos CKAN; campos de titular exigem descarte e revisão LGPD.",
    "LNT-0050": "Blocos MUNIC variam por edição; habitação/mobilidade aguardam schema escolhido.",
    "LNT-0109": "Microdados Censo SUAS não foram obtidos nesta etapa.",
    "LNT-0110": "Cadastro Único está em portal agregado sem exportação estável homologada.",
    "LNT-0111": "Indicadores Censo SUAS aguardam recurso e período definidos.",
    "LNT-0112": "SINISA Água aguarda homologação da planilha e glossário 2024.",
    "LNT-0113": "SINISA Esgoto aguarda homologação da planilha e glossário 2024.",
    "LNT-0114": "SINISA Resíduos aguarda homologação da planilha e glossário 2024.",
    "LNT-0115": "SINISA Drenagem aguarda homologação da planilha e glossário 2024.",
    "LNT-0116": "MCMV aguarda recurso municipal estruturado e revisão de granularidade.",
    "LNT-0117": "MCMV OGU possui ZIP candidato; arquivo não foi homologado.",
    "LNT-0118": "MCMV FGTS possui ZIP candidato; arquivo não foi homologado.",
    "LNT-0120": "Sinistros SENATRAN aguardam recurso municipal e dicionário versionados.",
    "LNT-0121": "Cobertura móvel Anatel é portal; exportação municipal ainda não homologada.",
    "LNT-0122": "Acessos Anatel aguardam definição de métrica e recurso municipal.",
    "LNT-0123": "Backhaul Anatel aguarda definição de grão e período.",
    "LNT-0124": "ANEEL GD Parquet aguarda pipeline com descarte comprovado de titulares.",
    "LNT-0125": "Perdas de energia não devem ser atribuídas ao município sem grão compatível.",
    "LNT-0155": "BCB Olinda publica índices nacionais, separados de fatos municipais.",
    "LNT-0156": "Produção industrial não possui automaticamente granularidade municipal.",
    "LNT-0157": "Pesquisa de serviços não possui automaticamente granularidade municipal.",
    "LNT-0158": "Censo Agropecuário requer seleção de tabela municipal e regras de sigilo.",
}


def upgrade() -> None:
    connection = op.get_bind()
    senatran_dataset = connection.execute(
        sa.text("SELECT id FROM datasets WHERE code='senatran_fleet'")
    ).scalar_one()
    connection.execute(
        sa.text(
            """UPDATE catalog_entries SET dataset_id=:dataset, integration_decision='integrate',
            decision_reason='Página e XLSX oficial 2026-09 verificados; conector homologado',
            decided_at=now() WHERE external_catalog_id='LNT-0048'"""
        ),
        {"dataset": senatran_dataset},
    )
    for external_id, reason in DECISIONS.items():
        connection.execute(
            sa.text(
                """UPDATE catalog_entries SET integration_decision='manual_review',
                decision_reason=:reason, decided_at=now()
                WHERE external_catalog_id=:external_id"""
            ),
            {"external_id": external_id, "reason": reason},
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            """UPDATE catalog_entries SET dataset_id=NULL, integration_decision='manual_review'
            WHERE external_catalog_id='LNT-0048'"""
        )
    )
    for external_id in DECISIONS:
        connection.execute(
            sa.text(
                """UPDATE catalog_entries SET integration_decision=NULL,
                decision_reason=NULL, decided_at=NULL WHERE external_catalog_id=:external_id"""
            ),
            {"external_id": external_id},
        )
