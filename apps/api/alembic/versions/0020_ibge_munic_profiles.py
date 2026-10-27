# ruff: noqa: E501
"""Publish selected municipal profile indicators from IBGE MUNIC.

Revision ID: 0020
Revises: 0019
"""

from datetime import UTC, datetime
from uuid import UUID

import sqlalchemy as sa

from alembic import op

revision = "0020"
down_revision = "0019"
branch_labels = None
depends_on = None

SOURCES = (
    (
        UUID("20000000-0000-4000-8000-000000000040"),
        "IBGE — MUNIC 2020",
        "ibge-munic-2020",
        "https://ftp.ibge.gov.br/Perfil_Municipios/2020/Base_de_Dados/Base_MUNIC_2020.xlsx",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000041"),
        "IBGE — MUNIC 2021",
        "ibge-munic-2021",
        "https://ftp.ibge.gov.br/Perfil_Municipios/2021/Base_de_Dados/Base_MUNIC_2021_20240425.xlsx",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000042"),
        "IBGE — MUNIC 2023",
        "ibge-munic-2023",
        "https://ftp.ibge.gov.br/Perfil_Municipios/2023/Base_de_Dados/Base_MUNIC_2023.xlsx",
    ),
    (
        UUID("20000000-0000-4000-8000-000000000043"),
        "IBGE — MUNIC 2024",
        "ibge-munic-2024",
        "https://ftp.ibge.gov.br/Perfil_Municipios/2024/Base_de_Dados/Base_MUNIC_2024_20251107.xlsx",
    ),
)

DATASETS = (
    (
        "21000000-0000-4000-8000-000000000040",
        SOURCES[3][0],
        "ibge_munic_2024_digital_government",
        "Governo digital municipal — MUNIC 2024",
        "ciencia-e-inovacao",
    ),
    (
        "21000000-0000-4000-8000-000000000041",
        SOURCES[3][0],
        "ibge_munic_2024_governance",
        "Governança municipal — MUNIC 2024",
        "gestao-publica",
    ),
    (
        "21000000-0000-4000-8000-000000000042",
        SOURCES[1][0],
        "ibge_munic_2021_culture",
        "Política e equipamentos culturais — MUNIC 2021",
        "cultura-e-turismo",
    ),
    (
        "21000000-0000-4000-8000-000000000043",
        SOURCES[1][0],
        "ibge_munic_2021_participation",
        "Participação social na política cultural — MUNIC 2021",
        "participacao-e-democracia",
    ),
    (
        "21000000-0000-4000-8000-000000000044",
        SOURCES[0][0],
        "ibge_munic_2020_environment",
        "Gestão ambiental municipal — MUNIC 2020",
        "meio-ambiente-e-riscos",
    ),
    (
        "21000000-0000-4000-8000-000000000045",
        SOURCES[0][0],
        "ibge_munic_2020_risk_management",
        "Riscos e desastres municipais — MUNIC 2020",
        "meio-ambiente-e-riscos",
    ),
    (
        "21000000-0000-4000-8000-000000000046",
        SOURCES[2][0],
        "ibge_munic_2023_social_assistance",
        "Gestão da assistência social — MUNIC 2023",
        "protecao-social",
    ),
    (
        "21000000-0000-4000-8000-000000000047",
        SOURCES[2][0],
        "ibge_munic_2023_public_security",
        "Estrutura municipal de segurança pública — MUNIC 2023",
        "seguranca-publica",
    ),
)

INDICATORS = (
    (
        "municipal_tic_structure",
        "Estrutura municipal de TIC",
        "Existência de estrutura organizacional para tecnologia da informação e comunicação.",
        "sim/não",
        "ciencia-e-inovacao",
    ),
    (
        "municipal_data_center",
        "Centro de processamento de dados",
        "Existência de centro de processamento de dados na administração municipal.",
        "sim/não",
        "ciencia-e-inovacao",
    ),
    (
        "municipal_software_internal",
        "Software municipal para uso interno",
        "Desenvolvimento de software para funcionamento interno ou atendimento a servidores nos 12 meses anteriores.",
        "sim/não",
        "ciencia-e-inovacao",
    ),
    (
        "municipal_software_public",
        "Software municipal para a sociedade",
        "Desenvolvimento de software para atendimento à sociedade nos 12 meses anteriores.",
        "sim/não",
        "ciencia-e-inovacao",
    ),
    (
        "municipal_internal_control",
        "Estrutura de controle interno",
        "Existência de estrutura organizacional responsável pelo controle interno.",
        "sim/não",
        "gestao-publica",
    ),
    (
        "internal_control_online",
        "Controle interno com informação online",
        "Disponibilização de informação do controle interno na internet.",
        "sim/não",
        "gestao-publica",
    ),
    (
        "municipal_culture_plan",
        "Plano Municipal de Cultura",
        "Existência de Plano Municipal de Cultura.",
        "sim/não",
        "cultura-e-turismo",
    ),
    (
        "municipal_culture_council",
        "Conselho Municipal de Cultura",
        "Existência de Conselho Municipal de Cultura.",
        "sim/não",
        "cultura-e-turismo",
    ),
    (
        "municipal_culture_fund",
        "Fundo Municipal de Cultura",
        "Existência de Fundo Municipal de Cultura.",
        "sim/não",
        "cultura-e-turismo",
    ),
    (
        "public_library_exists",
        "Biblioteca pública",
        "Existência de biblioteca pública no município.",
        "sim/não",
        "cultura-e-turismo",
    ),
    ("museum_exists", "Museu", "Existência de museu no município.", "sim/não", "cultura-e-turismo"),
    (
        "theater_exists",
        "Teatro ou sala de espetáculos",
        "Existência de teatro ou sala de espetáculos no município.",
        "sim/não",
        "cultura-e-turismo",
    ),
    (
        "culture_plan_civic_participation",
        "Participação social no plano de cultura",
        "Plano Municipal de Cultura elaborado com participação da sociedade civil.",
        "sim/não",
        "participacao-e-democracia",
    ),
    (
        "municipal_environment_council",
        "Conselho Municipal de Meio Ambiente",
        "Existência de Conselho Municipal de Meio Ambiente.",
        "sim/não",
        "meio-ambiente-e-riscos",
    ),
    (
        "environment_council_meetings",
        "Reuniões do conselho ambiental",
        "Quantidade de reuniões realizadas pelo conselho nos 12 meses anteriores.",
        "reuniões",
        "meio-ambiente-e-riscos",
    ),
    (
        "environment_council_members",
        "Conselheiros de meio ambiente",
        "Número de conselheiros titulares e suplentes.",
        "conselheiros",
        "meio-ambiente-e-riscos",
    ),
    (
        "municipal_environment_fund",
        "Fundo Municipal de Meio Ambiente",
        "Existência de Fundo Municipal de Meio Ambiente ou similar.",
        "sim/não",
        "meio-ambiente-e-riscos",
    ),
    (
        "flooding_last_four_years",
        "Alagamento nos quatro anos anteriores",
        "Município atingido por alagamento nos quatro anos anteriores à pesquisa.",
        "sim/não",
        "meio-ambiente-e-riscos",
    ),
    (
        "gradual_flood_last_four_years",
        "Enchente gradual nos quatro anos anteriores",
        "Município atingido por enchente ou inundação gradual nos quatro anos anteriores.",
        "sim/não",
        "meio-ambiente-e-riscos",
    ),
    (
        "flash_flood_last_four_years",
        "Enxurrada nos quatro anos anteriores",
        "Município atingido por enxurrada ou inundação brusca nos quatro anos anteriores.",
        "sim/não",
        "meio-ambiente-e-riscos",
    ),
    (
        "landslide_last_four_years",
        "Deslizamento nos quatro anos anteriores",
        "Município atingido por escorregamento ou deslizamento nos quatro anos anteriores.",
        "sim/não",
        "meio-ambiente-e-riscos",
    ),
    (
        "municipal_risk_reduction_plan",
        "Plano Municipal de Redução de Riscos",
        "Existência de Plano Municipal de Redução de Riscos.",
        "sim/não",
        "meio-ambiente-e-riscos",
    ),
    (
        "municipal_social_assistance_plan",
        "Plano Municipal de Assistência Social",
        "Existência de Plano Municipal de Assistência Social.",
        "sim/não",
        "protecao-social",
    ),
    (
        "social_plan_council_approved",
        "Plano social aprovado pelo conselho",
        "Plano Municipal de Assistência Social aprovado pelo conselho municipal.",
        "sim/não",
        "protecao-social",
    ),
    (
        "municipal_social_assistance_council",
        "Conselho Municipal de Assistência Social",
        "Existência de Conselho Municipal de Assistência Social.",
        "sim/não",
        "protecao-social",
    ),
    (
        "municipal_social_assistance_fund",
        "Fundo Municipal de Assistência Social",
        "Existência de Fundo Municipal de Assistência Social.",
        "sim/não",
        "protecao-social",
    ),
    (
        "municipal_public_security_council",
        "Conselho Municipal de Segurança Pública",
        "Existência de Conselho Municipal de Segurança Pública.",
        "sim/não",
        "seguranca-publica",
    ),
    (
        "community_public_security_council",
        "Conselho Comunitário de Segurança",
        "Existência de conselho comunitário de segurança pública.",
        "sim/não",
        "seguranca-publica",
    ),
    (
        "municipal_public_security_fund",
        "Fundo Municipal de Segurança Pública",
        "Existência de Fundo Municipal de Segurança Pública.",
        "sim/não",
        "seguranca-publica",
    ),
    (
        "municipal_public_security_plan",
        "Plano Municipal de Segurança Pública",
        "Existência de Plano Municipal de Segurança Pública.",
        "sim/não",
        "seguranca-publica",
    ),
    (
        "municipal_guard",
        "Guarda municipal",
        "Existência de guarda municipal.",
        "sim/não",
        "seguranca-publica",
    ),
)


def upgrade() -> None:
    now = datetime.now(UTC)
    connection = op.get_bind()
    for source_id, provider, slug, url in SOURCES:
        connection.execute(
            sa.text(
                """INSERT INTO sources (id,provider,slug,source_url,license,terms,
                expected_frequency,status,verified_at,source_status,connector_status,
                catalog_metadata) VALUES (:id,:provider,:slug,:url,
                'Dados públicos oficiais; atribuição obrigatória ao IBGE',
                'Reutilização com identificação da pesquisa, edição e variável.',
                'por edição','confirmed',:now,'verified','implemented','{}'::jsonb)"""
            ),
            {"id": source_id, "provider": provider, "slug": slug, "url": url, "now": now},
        )
    for dataset_id, source_id, code, title, domain in DATASETS:
        connection.execute(
            sa.text(
                """INSERT INTO datasets (id,source_id,code,title,description,domain,
                granularity,update_policy,status,connector_status,publication_status,
                catalog_metadata) VALUES (:id,:source,:code,:title,
                'Recorte municipal oficial da pesquisa MUNIC com snapshot e revisão.',
                :domain,'município/edição/variável','por edição','confirmed','implemented',
                'not_published','{}'::jsonb)"""
            ),
            {
                "id": UUID(dataset_id),
                "source": source_id,
                "code": code,
                "title": title,
                "domain": domain,
            },
        )
    for code, label, definition, unit, domain in INDICATORS:
        connection.execute(
            sa.text(
                """INSERT INTO indicators (id,code,label,definition,unit,periodicity,
                methodology,disaggregation_schema,limitations,domain,direction)
                VALUES (gen_random_uuid(),:code,:label,:definition,:unit,'por edição',
                'Resposta municipal publicada na base completa da Pesquisa de Informações Básicas Municipais (MUNIC/IBGE).',
                '{"edition":"integer","variable":"string","response":"string"}'::jsonb,
                'Retrata a existência, quantidade ou ocorrência declarada na edição; não mede qualidade, capacidade ou desempenho.',
                :domain,NULL)"""
            ),
            {
                "code": code,
                "label": label,
                "definition": definition,
                "unit": unit,
                "domain": domain,
            },
        )


def downgrade() -> None:
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "DELETE FROM observations WHERE indicator_id IN (SELECT id FROM indicators WHERE code = ANY(:codes))"
        ),
        {"codes": [row[0] for row in INDICATORS]},
    )
    connection.execute(
        sa.text("DELETE FROM indicators WHERE code = ANY(:codes)"),
        {"codes": [row[0] for row in INDICATORS]},
    )
    connection.execute(
        sa.text("DELETE FROM source_snapshots WHERE dataset_id = ANY(:ids)"),
        {"ids": [UUID(row[0]) for row in DATASETS]},
    )
    connection.execute(
        sa.text("DELETE FROM datasets WHERE id = ANY(:ids)"),
        {"ids": [UUID(row[0]) for row in DATASETS]},
    )
    connection.execute(
        sa.text("DELETE FROM sources WHERE id = ANY(:ids)"), {"ids": [row[0] for row in SOURCES]}
    )
