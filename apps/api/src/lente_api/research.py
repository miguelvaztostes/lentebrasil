from __future__ import annotations

# ruff: noqa: E501, I001  # SQL permanece legível quando alinhado ao schema de origem.

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


@dataclass(frozen=True, slots=True)
class ResearchDefinition:
    code: str
    label: str
    domain: str
    unit: str
    periodicity: str
    methodology: str
    limitations: str
    denominator: str | None
    geography: str = "municipality"
    comparable: bool = True
    scope_required: bool = True


EDUCATION_METRIC_META: dict[str, tuple[str, str, str]] = {
    "approval_rate": (
        "Indicador de rendimento",
        "%",
        "Taxa convertida de proporção para percentual na consulta.",
    ),
    "ideb": ("Ideb", "índice", "Índice oficial por rede e etapa, sem combinar recortes."),
    "pnae_students_planned": (
        "Alunos considerados no PNAE",
        "alunos",
        "Previsão do FNDE por modalidade; categorias podem se sobrepor.",
    ),
    "pnae_transfer_planned_brl": (
        "Valor previsto do PNAE",
        "BRL nominal",
        "Previsão publicada pelo FNDE; não equivale a pagamento.",
    ),
    "saeb_mathematics": (
        "Proficiência Saeb em Matemática",
        "pontos",
        "Média oficial por rede e etapa.",
    ),
    "saeb_mean": ("Média padronizada Saeb", "pontos", "Média oficial por rede e etapa."),
    "saeb_portuguese": (
        "Proficiência Saeb em Língua Portuguesa",
        "pontos",
        "Média oficial por rede e etapa.",
    ),
}


STATIC_DEFINITIONS = {
    "education:enrollment_count": ResearchDefinition(
        "education:enrollment_count",
        "Matrículas declaradas",
        "educacao",
        "matrículas",
        "anual",
        "Soma das matrículas do Censo Escolar no mesmo ano, etapa e dependência.",
        "Categorias educacionais podem se sobrepor; não representam estudantes únicos.",
        None,
    ),
    "fiscal:amount": ResearchDefinition(
        "fiscal:amount",
        "Valor de demonstrativo fiscal",
        "transparencia",
        "BRL nominal",
        "anual/bimestral",
        "Valor da linha e coluna oficiais, sem somar fontes ou fases contábeis diferentes.",
        "Comparável somente com fonte, demonstrativo, fase, período e conta idênticos.",
        None,
    ),
    "procurement:count": ResearchDefinition(
        "procurement:count",
        "Contratações publicadas",
        "transparencia",
        "contratações",
        "anual",
        "Contagem de contratações na última revisão por modalidade, status e setor.",
        "Não é indicador automático de regularidade ou competição.",
        None,
    ),
    "procurement:estimated_amount": ResearchDefinition(
        "procurement:estimated_amount",
        "Valor estimado das contratações",
        "transparencia",
        "BRL nominal",
        "anual",
        "Soma de valores estimados dentro do mesmo recorte PNCP.",
        "Não equivale a valor contratado ou pago.",
        None,
    ),
    "procurement:homologated_amount": ResearchDefinition(
        "procurement:homologated_amount",
        "Valor homologado das contratações",
        "transparencia",
        "BRL nominal",
        "anual",
        "Soma de valores homologados dentro do mesmo recorte PNCP.",
        "Não equivale a pagamento ou execução orçamentária.",
        None,
    ),
    "contract:count": ResearchDefinition(
        "contract:count",
        "Contratos publicados",
        "transparencia",
        "contratos",
        "anual",
        "Contagem de contratos PNCP na última revisão e mesmo status.",
        "Cobertura depende dos órgãos publicadores no PNCP.",
        None,
    ),
    "contract:initial_amount": ResearchDefinition(
        "contract:initial_amount",
        "Valor inicial dos contratos",
        "transparencia",
        "BRL nominal",
        "anual",
        "Soma do valor inicial dos contratos no mesmo recorte.",
        "Não representa pagamento realizado.",
        None,
    ),
    "contract:global_amount": ResearchDefinition(
        "contract:global_amount",
        "Valor global dos contratos",
        "transparencia",
        "BRL nominal",
        "anual",
        "Soma do valor global informado no PNCP no mesmo recorte.",
        "Pode refletir atualizações contratuais; comparar somente mesma versão e status.",
        None,
    ),
    "transfer:planned_amount": ResearchDefinition(
        "transfer:planned_amount",
        "Valor previsto de transferências",
        "transparencia",
        "BRL nominal",
        "anual",
        "Soma do valor previsto dentro do mesmo programa, tipo e fonte oficial.",
        "Valor previsto não equivale a pagamento realizado.",
        None,
    ),
    "transfer:paid_amount": ResearchDefinition(
        "transfer:paid_amount",
        "Valor pago de transferências",
        "transparencia",
        "BRL nominal",
        "anual",
        "Soma do valor pago dentro do mesmo programa, tipo e fonte oficial.",
        "Não combinar com valor previsto nem atribuir transferências sem território definido.",
        None,
    ),
    "health:establishment_count": ResearchDefinition(
        "health:establishment_count",
        "Estabelecimentos de saúde cadastrados",
        "saude",
        "estabelecimentos",
        "conforme competência CNES",
        "Contagem de cadastros CNES por tipo, vínculo SUS e situação.",
        "Cadastro não comprova funcionamento ou atendimento em tempo real.",
        None,
    ),
    "health:bed_existing_count": ResearchDefinition(
        "health:bed_existing_count",
        "Leitos cadastrados existentes",
        "saude",
        "leitos",
        "conforme competência CNES",
        "Soma de leitos existentes no CNES por tipo.",
        "Capacidade cadastrada não é disponibilidade ou ocupação real.",
        None,
    ),
    "health:bed_sus_count": ResearchDefinition(
        "health:bed_sus_count",
        "Leitos cadastrados SUS",
        "saude",
        "leitos",
        "conforme competência CNES",
        "Soma de leitos SUS cadastrados no CNES por tipo.",
        "Capacidade cadastrada não é disponibilidade ou ocupação real.",
        None,
    ),
    "health:service_count": ResearchDefinition(
        "health:service_count",
        "Serviços de saúde cadastrados",
        "saude",
        "cadastros de serviço",
        "conforme competência CNES",
        "Contagem de cadastros estabelecimento/serviço/classificação do CNES.",
        "Não representa produção realizada nem pessoas atendidas.",
        None,
    ),
    "health:production_quantity": ResearchDefinition(
        "health:production_quantity",
        "Produção assistencial aprovada",
        "saude",
        "procedimentos/autorizações",
        "mensal",
        "Quantidade aprovada em SIA/SUS ou autorizações registradas em SIH/SUS.",
        "SIA e SIH são escopos diferentes e não são somados entre si.",
        None,
    ),
    "health:production_amount": ResearchDefinition(
        "health:production_amount",
        "Valor aprovado da produção assistencial",
        "saude",
        "BRL nominal",
        "mensal",
        "Valor aprovado em SIA/SUS ou valor total em SIH/SUS.",
        "Não equivale a custo total, pagamento final ou pessoas únicas.",
        None,
    ),
    "labor:admissions": ResearchDefinition(
        "labor:admissions",
        "Admissões formais",
        "economia-e-trabalho",
        "movimentações",
        "mensal",
        "Admissões do Novo CAGED por seção CNAE.",
        "Fluxo mensal; não é estoque de empregos nem informalidade.",
        None,
    ),
    "labor:dismissals": ResearchDefinition(
        "labor:dismissals",
        "Desligamentos formais",
        "economia-e-trabalho",
        "movimentações",
        "mensal",
        "Desligamentos do Novo CAGED por seção CNAE.",
        "Fluxo mensal; não é estoque de empregos nem informalidade.",
        None,
    ),
    "labor:balance": ResearchDefinition(
        "labor:balance",
        "Saldo de empregos formais",
        "economia-e-trabalho",
        "postos",
        "mensal",
        "Admissões menos desligamentos do Novo CAGED na mesma competência e seção CNAE.",
        "Fluxo mensal; não é estoque de empregos nem informalidade.",
        None,
    ),
    "social:beneficiary_count": ResearchDefinition(
        "social:beneficiary_count",
        "Beneficiários de programa social",
        "protecao-social",
        "beneficiários",
        "mensal",
        "Contagem agregada oficial por programa e período.",
        "Disponível somente quando o recurso agregado estiver homologado.",
        None,
    ),
    "social:family_count": ResearchDefinition(
        "social:family_count",
        "Famílias de programa social",
        "protecao-social",
        "famílias",
        "mensal",
        "Contagem agregada oficial por programa e período.",
        "Não equivale a pessoas únicas.",
        None,
    ),
    "social:amount": ResearchDefinition(
        "social:amount",
        "Valor de benefício social",
        "protecao-social",
        "BRL nominal",
        "mensal",
        "Valor agregado oficial por programa e período.",
        "Não combinar programas ou períodos incompatíveis.",
        None,
    ),
}


def _row_definition(prefix: str, row: Any, **overrides: Any) -> ResearchDefinition:
    code = f"{prefix}:{row.code}"
    return ResearchDefinition(
        code=code,
        label=overrides.get("label", str(row.label)),
        domain=overrides.get("domain", str(row.domain)),
        unit=overrides.get("unit", str(row.unit)),
        periodicity=overrides.get("periodicity", str(row.periodicity)),
        methodology=overrides.get("methodology", str(row.methodology)),
        limitations=overrides.get("limitations", str(row.limitations)),
        denominator=overrides.get("denominator"),
        scope_required=overrides.get("scope_required", True),
    )


def research_definitions(db: Session) -> list[dict[str, Any]]:
    definitions = dict(STATIC_DEFINITIONS)
    for row in db.execute(
        text(
            """SELECT i.code, i.label, i.domain, i.unit, i.periodicity, i.methodology,
            i.limitations, count(o.id) AS rows
            FROM indicators i LEFT JOIN observations o ON o.indicator_id=i.id
            GROUP BY i.id ORDER BY i.domain, i.label"""
        )
    ):
        item = _row_definition("observation", row, scope_required=False)
        definitions[item.code] = item
    dynamic_queries = (
        (
            "economy",
            """SELECT DISTINCT metric_code AS code, metric_code AS label, 'economia-e-trabalho'
            AS domain, unit, 'anual' AS periodicity,
            'Fato econômico anual no recorte e atividade originais.' AS methodology,
            'Valores nominais não são corrigidos pela inflação.' AS limitations
            FROM economy_facts""",
        ),
        (
            "education",
            """SELECT DISTINCT metric_code AS code, metric_code AS label, 'educacao' AS domain,
            'conforme indicador' AS unit, 'conforme avaliação' AS periodicity,
            'Métrica educacional oficial por rede e etapa.' AS methodology,
            'Supressões e redes permanecem separadas.' AS limitations FROM education_metrics""",
        ),
        (
            "health_epidemiology",
            """SELECT DISTINCT indicator_code AS code, indicator_code AS label, 'saude' AS domain,
            'eventos' AS unit, 'anual' AS periodicity,
            'Evento agregado pela base territorial, categoria e faixa etária publicadas.'
            AS methodology, 'Células pequenas podem estar suprimidas.' AS limitations
            FROM health_epidemiology""",
        ),
        (
            "infrastructure",
            """SELECT DISTINCT metric_code AS code, metric_code AS label,
            'infraestrutura-e-cidades' AS domain, unit, 'conforme referência' AS periodicity,
            'Fato de infraestrutura por serviço e referência oficial.' AS methodology,
            'Cadastro não implica uso ou disponibilidade em tempo real.' AS limitations
            FROM infrastructure_facts""",
        ),
        (
            "agriculture",
            """SELECT DISTINCT metric_code AS code, metric_code AS label,
            'agropecuaria-e-rural' AS domain, unit, 'anual' AS periodicity,
            'Produção Agrícola Municipal do SIDRA por produto.' AS methodology,
            'Ausência ou sigilo permanece nulo; não há estimativa mensal.' AS limitations
            FROM agriculture_facts""",
        ),
    )
    for prefix, sql in dynamic_queries:
        for row in db.execute(text(sql)):
            overrides: dict[str, Any] = {}
            if prefix == "education" and str(row.code) in EDUCATION_METRIC_META:
                label, unit, methodology = EDUCATION_METRIC_META[str(row.code)]
                overrides = {"label": label, "unit": unit, "methodology": methodology}
            item = _row_definition(prefix, row, **overrides)
            definitions[item.code] = item
    counts = definition_counts(db)
    return [
        {
            **asdict(item),
            "row_count": counts.get(item.code, 0),
            "published": counts.get(item.code, 0) > 0,
        }
        for item in sorted(definitions.values(), key=lambda value: (value.domain, value.label))
    ]


def definition_counts(db: Session) -> dict[str, int]:
    counts: dict[str, int] = {}
    queries = (
        "SELECT 'observation:' || i.code, count(*) FROM observations o JOIN indicators i ON i.id=o.indicator_id GROUP BY i.code",
        "SELECT 'economy:' || metric_code, count(*) FROM economy_facts GROUP BY metric_code",
        "SELECT 'education:' || metric_code, count(*) FROM education_metrics GROUP BY metric_code",
        "SELECT 'health_epidemiology:' || indicator_code, count(*) FROM health_epidemiology GROUP BY indicator_code",
        "SELECT 'infrastructure:' || metric_code, count(*) FROM infrastructure_facts GROUP BY metric_code",
        "SELECT 'agriculture:' || metric_code, count(*) FROM agriculture_facts GROUP BY metric_code",
    )
    for sql in queries:
        counts.update({str(code): int(count) for code, count in db.execute(text(sql))})
    fixed_tables = {
        "education:enrollment_count": "education_enrollments",
        "fiscal:amount": "fiscal_statements",
        "procurement:count": "procurements",
        "procurement:estimated_amount": "procurements",
        "procurement:homologated_amount": "procurements",
        "contract:count": "contracts",
        "contract:initial_amount": "contracts",
        "contract:global_amount": "contracts",
        "transfer:planned_amount": "transfers",
        "transfer:paid_amount": "transfers",
        "health:establishment_count": "health_establishments",
        "health:bed_existing_count": "health_beds",
        "health:bed_sus_count": "health_beds",
        "health:service_count": "health_services",
        "health:production_quantity": "health_production",
        "health:production_amount": "health_production",
        "labor:admissions": "labor_facts",
        "labor:dismissals": "labor_facts",
        "labor:balance": "labor_facts",
        "social:beneficiary_count": "social_benefit_facts",
        "social:family_count": "social_benefit_facts",
        "social:amount": "social_benefit_facts",
    }
    for code, table in fixed_tables.items():
        counts[code] = int(db.scalar(text(f"SELECT count(*) FROM {table}")) or 0)
    return counts


def definition_by_code(db: Session, code: str) -> dict[str, Any] | None:
    fixed_tables = {
        "education:enrollment_count": "education_enrollments",
        "fiscal:amount": "fiscal_statements",
        "procurement:count": "procurements",
        "procurement:estimated_amount": "procurements",
        "procurement:homologated_amount": "procurements",
        "contract:count": "contracts",
        "contract:initial_amount": "contracts",
        "contract:global_amount": "contracts",
        "transfer:planned_amount": "transfers",
        "transfer:paid_amount": "transfers",
        "health:establishment_count": "health_establishments",
        "health:bed_existing_count": "health_beds",
        "health:bed_sus_count": "health_beds",
        "health:service_count": "health_services",
        "health:production_quantity": "health_production",
        "health:production_amount": "health_production",
        "labor:admissions": "labor_facts",
        "labor:dismissals": "labor_facts",
        "labor:balance": "labor_facts",
        "social:beneficiary_count": "social_benefit_facts",
        "social:family_count": "social_benefit_facts",
        "social:amount": "social_benefit_facts",
    }
    if code in STATIC_DEFINITIONS:
        count = int(db.scalar(text(f"SELECT count(*) FROM {fixed_tables[code]}")) or 0)
        return {**asdict(STATIC_DEFINITIONS[code]), "row_count": count, "published": count > 0}
    prefix, _, metric = code.partition(":")
    if prefix == "observation":
        row = db.execute(
            text(
                """SELECT i.code,i.label,i.domain,i.unit,i.periodicity,i.methodology,i.limitations,
                count(o.id) rows FROM indicators i LEFT JOIN observations o ON o.indicator_id=i.id
                WHERE i.code=:metric GROUP BY i.id"""
            ),
            {"metric": metric},
        ).one_or_none()
        if row is None:
            return None
        definition = _row_definition("observation", row, scope_required=False)
        count = int(row.rows)
        return {**asdict(definition), "row_count": count, "published": count > 0}
    dynamic = {
        "economy": (
            "economy_facts",
            "metric_code",
            "economia-e-trabalho",
            "anual",
            "Fato econômico anual no recorte e atividade originais.",
            "Valores nominais não são corrigidos pela inflação.",
            None,
        ),
        "education": (
            "education_metrics",
            "metric_code",
            "educacao",
            "conforme avaliação",
            "Métrica educacional oficial por rede e etapa.",
            "Supressões e redes permanecem separadas.",
            "conforme indicador",
        ),
        "health_epidemiology": (
            "health_epidemiology",
            "indicator_code",
            "saude",
            "anual",
            "Evento agregado pela base territorial, categoria e faixa etária publicadas.",
            "Células pequenas podem estar suprimidas.",
            "eventos",
        ),
        "infrastructure": (
            "infrastructure_facts",
            "metric_code",
            "infraestrutura-e-cidades",
            "conforme referência",
            "Fato de infraestrutura por serviço e referência oficial.",
            "Cadastro não implica uso ou disponibilidade em tempo real.",
            None,
        ),
        "agriculture": (
            "agriculture_facts",
            "metric_code",
            "agropecuaria-e-rural",
            "anual",
            "Produção Agrícola Municipal do SIDRA por produto.",
            "Ausência ou sigilo permanece nulo; não há estimativa mensal.",
            None,
        ),
    }
    config = dynamic.get(prefix)
    if config is None:
        return None
    table, metric_column, domain, periodicity, methodology, limitations, fixed_unit = config
    unit_expression = ":fixed_unit" if fixed_unit else "min(unit)"
    row = db.execute(
        text(
            f"""SELECT :metric code,:metric label,:domain domain,{unit_expression} unit,
            :periodicity periodicity,:methodology methodology,:limitations limitations,count(*) rows
            FROM {table} WHERE {metric_column}=:metric HAVING count(*) > 0"""
        ),
        {
            "metric": metric,
            "domain": domain,
            "fixed_unit": fixed_unit,
            "periodicity": periodicity,
            "methodology": methodology,
            "limitations": limitations,
        },
    ).one_or_none()
    if row is None:
        return None
    overrides: dict[str, Any] = {}
    if prefix == "education" and metric in EDUCATION_METRIC_META:
        label, unit, methodology = EDUCATION_METRIC_META[metric]
        overrides = {"label": label, "unit": unit, "methodology": methodology}
    definition = _row_definition(prefix, row, **overrides)
    count = int(row.rows)
    return {**asdict(definition), "row_count": count, "published": True}


BASE_SELECTS: dict[str, str] = {
    "observation": """
        WITH current AS (SELECT o.*,row_number() OVER (PARTITION BY indicator_id,
        municipality_ibge_code,period_start,period_end,scope_key ORDER BY revision DESC) rn
        FROM observations o)
        SELECT 'observation:' || i.code indicator_code, o.municipality_ibge_code geo_id,
        m.name geo_name, m.state, o.period_start, o.period_end, o.scope_json::jsonb scope,
        o.scope_key, o.value, o.availability_status, i.unit, i.periodicity,
        d.code dataset, s.provider, s.license, ss.url source_url, ss.sha256,
        ss.fetched_at retrieved_at, ss.published_at, o.revision
        FROM current o JOIN indicators i ON i.id=o.indicator_id
        JOIN municipalities m ON m.ibge_code=o.municipality_ibge_code
        JOIN source_snapshots ss ON ss.id=o.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
        JOIN sources s ON s.id=d.source_id WHERE o.rn=1 AND i.code=:metric
    """,
    "economy": """
        WITH current AS (SELECT f.*, row_number() OVER
        (PARTITION BY source_system,source_key ORDER BY revision DESC) rn FROM economy_facts f)
        SELECT 'economy:' || f.metric_code indicator_code, f.municipality_ibge_code geo_id,
        m.name geo_name,m.state,make_date(f.reference_year,1,1) period_start,
        make_date(f.reference_year,12,31) period_end,
        jsonb_build_object('activity',coalesce(a.code,'all'),'activity_label',coalesce(a.label,'Total'),
        'price_basis',coalesce(f.price_basis,'not_informed')) scope,
        md5(jsonb_build_object('activity',coalesce(a.code,'all'),'price_basis',
        coalesce(f.price_basis,'not_informed'))::text) scope_key,
        f.value,f.availability_status,f.unit,'anual' periodicity,d.code dataset,s.provider,s.license,
        ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,f.revision
        FROM current f LEFT JOIN economic_activities a ON a.id=f.activity_id
        JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
        JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
        JOIN sources s ON s.id=d.source_id WHERE f.rn=1 AND f.metric_code=:metric
    """,
    "education": """
        SELECT 'education:' || f.metric_code indicator_code,f.municipality_ibge_code geo_id,
        m.name geo_name,m.state,make_date(f.reference_year,1,1) period_start,
        make_date(f.reference_year,12,31) period_end,
        jsonb_build_object('dataset',d.code,'dataset_label',d.title,'network',f.network_code,
        'network_label',n.name,'stage',f.stage_code,'stage_label',es.name) scope,
        md5(jsonb_build_object('dataset',d.code,'network',f.network_code,'stage',f.stage_code)::text)
        scope_key,CASE WHEN f.metric_code='approval_rate' THEN f.value * 100 ELSE f.value END value,
        f.availability_status,CASE WHEN f.metric_code='approval_rate' THEN '%'
        WHEN f.metric_code='pnae_transfer_planned_brl' THEN 'BRL nominal'
        WHEN f.metric_code='pnae_students_planned' THEN 'alunos'
        WHEN f.metric_code='ideb' THEN 'índice' ELSE 'pontos' END unit,
        'conforme avaliação' periodicity,
        d.code dataset,s.provider,s.license,ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,
        ss.published_at,1 revision FROM education_metrics f
        JOIN publication_releases pr ON pr.id=f.release_id AND pr.status='published'
        JOIN education_networks n ON n.code=f.network_code
        JOIN education_stages es ON es.code=f.stage_code
        JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
        JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
        JOIN sources s ON s.id=d.source_id WHERE f.metric_code=:metric
    """,
    "health_epidemiology": """
        WITH current AS (SELECT f.*,row_number() OVER
        (PARTITION BY source_system,source_key ORDER BY revision DESC) rn FROM health_epidemiology f)
        SELECT 'health_epidemiology:' || f.indicator_code indicator_code,
        f.municipality_ibge_code geo_id,m.name geo_name,m.state,f.period_start,f.period_end,
        jsonb_build_object('geography_basis',f.geography_basis,'category',f.category_code,
        'category_label',f.category_name,'age_band',f.age_band) scope,
        md5(jsonb_build_object('geography_basis',f.geography_basis,'category',f.category_code,
        'age_band',f.age_band)::text) scope_key,f.count::numeric value,f.availability_status,
        'eventos' unit,'anual' periodicity,d.code dataset,s.provider,s.license,ss.url source_url,
        ss.sha256,ss.fetched_at retrieved_at,ss.published_at,f.revision
        FROM current f JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
        JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
        JOIN sources s ON s.id=d.source_id WHERE f.rn=1 AND f.indicator_code=:metric
    """,
    "infrastructure": """
        WITH current AS (SELECT f.*,row_number() OVER
        (PARTITION BY source_system,source_key ORDER BY revision DESC) rn FROM infrastructure_facts f)
        SELECT 'infrastructure:' || f.metric_code indicator_code,f.municipality_ibge_code geo_id,
        m.name geo_name,m.state,f.reference_date period_start,f.reference_date period_end,
        jsonb_build_object('service',sv.code,'service_label',sv.label,'service_type',sv.service_type)
        scope,md5(jsonb_build_object('service',sv.code,'service_type',sv.service_type)::text) scope_key,
        f.value,f.availability_status,f.unit,'conforme referência' periodicity,d.code dataset,
        s.provider,s.license,ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,
        f.revision FROM current f JOIN infrastructure_services sv ON sv.id=f.service_id
        JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
        JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
        JOIN sources s ON s.id=d.source_id WHERE f.rn=1 AND f.metric_code=:metric
    """,
    "agriculture": """
        WITH current AS (SELECT f.*,row_number() OVER
        (PARTITION BY source_system,source_key ORDER BY revision DESC) rn FROM agriculture_facts f)
        SELECT 'agriculture:' || f.metric_code indicator_code,f.municipality_ibge_code geo_id,
        m.name geo_name,m.state,make_date(f.reference_year,1,1) period_start,
        make_date(f.reference_year,12,31) period_end,
        jsonb_build_object('product',f.product_code,'product_label',f.product_name) scope,
        md5(jsonb_build_object('product',f.product_code)::text) scope_key,f.value,
        f.availability_status,f.unit,'anual' periodicity,d.code dataset,s.provider,s.license,
        ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,f.revision
        FROM current f JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
        JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
        JOIN sources s ON s.id=d.source_id WHERE f.rn=1 AND f.metric_code=:metric
    """,
}


def _fixed_select(code: str) -> tuple[str, dict[str, Any]]:
    if code == "education:enrollment_count":
        return (
            """SELECT :indicator indicator_code,f.municipality_ibge_code geo_id,m.name geo_name,
            m.state,make_date(f.census_year,1,1) period_start,make_date(f.census_year,12,31)
            period_end,jsonb_build_object('stage',f.stage_code,'stage_label',es.name,
            'dependency',f.dependency_code,'dependency_label',ed.name) scope,
            md5(jsonb_build_object('stage',f.stage_code,'dependency',f.dependency_code)::text)
            scope_key,sum(f.enrollment_count)::numeric value,
            CASE WHEN bool_and(f.availability_status='available') THEN 'available' ELSE 'unavailable'
            END availability_status,'matrículas' unit,'anual' periodicity,d.code dataset,s.provider,
            s.license,ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,1 revision
            FROM education_enrollments f JOIN publication_releases pr ON pr.id=f.release_id
            AND pr.status='published' JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
            JOIN education_stages es ON es.code=f.stage_code
            JOIN education_dependencies ed ON ed.code=f.dependency_code
            JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
            JOIN sources s ON s.id=d.source_id GROUP BY f.municipality_ibge_code,m.name,m.state,
            f.census_year,f.stage_code,es.name,f.dependency_code,ed.name,d.code,s.provider,s.license,ss.url,ss.sha256,
            ss.fetched_at,ss.published_at""",
            {"indicator": code},
        )
    if code.startswith("labor:"):
        field = {
            "labor:admissions": "admissions",
            "labor:dismissals": "dismissals",
            "labor:balance": "balance",
        }[code]
        return (
            f"""WITH current AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
            source_key ORDER BY revision DESC) rn FROM labor_facts f)
            SELECT :indicator indicator_code,f.municipality_ibge_code geo_id,m.name geo_name,m.state,
            f.period_start,f.period_end,jsonb_build_object('section',a.code,'section_label',a.label)
            scope,md5(jsonb_build_object('section',a.code)::text) scope_key,f.{field}::numeric value,
            f.availability_status,'movimentações' unit,'mensal' periodicity,d.code dataset,s.provider,
            s.license,ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,f.revision
            FROM current f JOIN economic_activities a ON a.id=f.activity_id
            JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
            JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
            JOIN sources s ON s.id=d.source_id WHERE f.rn=1""",
            {"indicator": code},
        )
    if code.startswith("health:production_"):
        field = "quantity" if code.endswith("quantity") else "approved_amount"
        unit = "procedimentos/autorizações" if field == "quantity" else "BRL nominal"
        return (
            f"""WITH current AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
            source_key ORDER BY revision DESC) rn FROM health_production f)
            SELECT :indicator indicator_code,f.municipality_ibge_code geo_id,m.name geo_name,m.state,
            f.period_start,f.period_end,jsonb_build_object('care_type',f.care_type,'procedure',
            coalesce(f.procedure_code,'all'),'procedure_label',coalesce(f.procedure_name,'Total'),
            'facility_type',coalesce(f.facility_type,'all'),'sus_sector',coalesce(f.sus_sector,'all'))
            scope,md5(jsonb_build_object('care_type',f.care_type,'procedure',
            coalesce(f.procedure_code,'all'),'facility_type',coalesce(f.facility_type,'all'),
            'sus_sector',coalesce(f.sus_sector,'all'))::text) scope_key,f.{field} value,
            f.availability_status,:unit unit,'mensal' periodicity,d.code dataset,s.provider,s.license,
            ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,f.revision
            FROM current f JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
            JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
            JOIN sources s ON s.id=d.source_id WHERE f.rn=1""",
            {"indicator": code, "unit": unit},
        )
    if code == "fiscal:amount":
        return (
            """WITH current AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
            source_key ORDER BY revision DESC) rn FROM fiscal_statements f)
            SELECT :indicator indicator_code,f.municipality_ibge_code geo_id,m.name geo_name,m.state,
            make_date(f.reference_year,1,1) period_start,make_date(f.reference_year,12,31) period_end,
            jsonb_build_object('source_system',f.source_system,'statement_type',f.statement_type,
            'reference_period',f.reference_period,'annex',f.annex,'power',f.power,'column',f.column_code,
            'account',coalesce(a.account_code,'none'),'account_label',coalesce(a.name,'Sem conta')) scope,
            md5(jsonb_build_object('source_system',f.source_system,'statement_type',f.statement_type,
            'reference_period',f.reference_period,'annex',f.annex,'power',f.power,'column',f.column_code,
            'account',coalesce(a.account_code,'none'))::text) scope_key,f.amount value,
            f.availability_status,'BRL nominal' unit,coalesce(f.periodicity,'anual') periodicity,
            d.code dataset,s.provider,s.license,ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,
            ss.published_at,f.revision FROM current f LEFT JOIN budget_accounts a ON a.id=f.budget_account_id
            JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
            JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
            JOIN sources s ON s.id=d.source_id WHERE f.rn=1""",
            {"indicator": code},
        )
    if code.startswith("social:"):
        field = code.split(":", 1)[1]
        return (
            f"""WITH current AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
            source_key ORDER BY revision DESC) rn FROM social_benefit_facts f)
            SELECT :indicator indicator_code,f.municipality_ibge_code geo_id,m.name geo_name,m.state,
            f.period_start,f.period_end,jsonb_build_object('program',p.code,'program_label',p.name)
            scope,md5(jsonb_build_object('program',p.code)::text) scope_key,f.{field}::numeric value,
            f.availability_status,CASE WHEN :indicator='social:amount' THEN 'BRL nominal'
            ELSE 'contagem' END unit,'mensal' periodicity,d.code dataset,s.provider,s.license,
            ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,f.revision
            FROM current f JOIN social_programs p ON p.id=f.program_id
            JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
            JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
            JOIN sources s ON s.id=d.source_id WHERE f.rn=1""",
            {"indicator": code},
        )
    if code.startswith("health:") and code in {
        "health:establishment_count",
        "health:bed_existing_count",
        "health:bed_sus_count",
        "health:service_count",
    }:
        return _health_registry_select(code)
    if code.startswith("procurement:") or code.startswith("contract:"):
        return _procurement_select(code)
    if code.startswith("transfer:"):
        field = code.split(":", 1)[1]
        return (
            f"""WITH current AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
            source_key ORDER BY revision DESC) rn FROM transfers f) SELECT :indicator indicator_code,
            f.municipality_ibge_code geo_id,m.name geo_name,m.state,
            make_date(f.reference_year,1,1) period_start,make_date(f.reference_year,12,31) period_end,
            jsonb_build_object('transfer_type',f.transfer_type,'program',coalesce(f.program_code,
            'unknown'),'program_label',coalesce(f.program_name,'Não informado')) scope,
            md5(jsonb_build_object('transfer_type',f.transfer_type,'program',coalesce(f.program_code,
            'unknown'))::text) scope_key,f.{field} value,'available' availability_status,
            'BRL nominal' unit,'anual' periodicity,d.code dataset,s.provider,s.license,ss.url source_url,
            ss.sha256,ss.fetched_at retrieved_at,ss.published_at,f.revision FROM current f
            JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code JOIN source_snapshots ss
            ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id JOIN sources s ON s.id=d.source_id
            WHERE f.rn=1 AND f.municipality_ibge_code IS NOT NULL""",
            {"indicator": code},
        )
    raise KeyError(code)


def _health_registry_select(code: str) -> tuple[str, dict[str, Any]]:
    if code == "health:establishment_count":
        sql = """WITH current AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
        source_key ORDER BY revision DESC) rn FROM health_establishments f)
        SELECT :indicator indicator_code,f.municipality_ibge_code geo_id,m.name geo_name,m.state,
        f.reference_date period_start,f.reference_date period_end,jsonb_build_object('facility_type',
        coalesce(f.facility_type_code,'unknown'),'facility_type_label',coalesce(f.facility_type_name,
        'Não informado'),'sus_linked',f.sus_linked,'active',f.active) scope,
        md5(jsonb_build_object('facility_type',coalesce(f.facility_type_code,'unknown'),
        'sus_linked',f.sus_linked,'active',f.active)::text) scope_key,count(*)::numeric value,
        'available' availability_status,'estabelecimentos' unit,'conforme competência CNES'
        periodicity,d.code dataset,s.provider,s.license,ss.url source_url,ss.sha256,
        ss.fetched_at retrieved_at,ss.published_at,max(f.revision) revision FROM current f
        JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code JOIN source_snapshots ss
        ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id JOIN sources s ON s.id=d.source_id
        WHERE f.rn=1 GROUP BY f.municipality_ibge_code,m.name,m.state,f.reference_date,
        f.facility_type_code,f.facility_type_name,f.sus_linked,f.active,d.code,s.provider,s.license,
        ss.url,ss.sha256,ss.fetched_at,ss.published_at"""
    elif code.startswith("health:bed_"):
        field = "existing_count" if code.endswith("existing_count") else "sus_count"
        sql = f"""WITH beds AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
        source_key ORDER BY revision DESC) rn FROM health_beds f), establishments AS
        (SELECT f.*,row_number() OVER (PARTITION BY source_system,source_key ORDER BY revision DESC)
        rn FROM health_establishments f) SELECT :indicator indicator_code,e.municipality_ibge_code
        geo_id,m.name geo_name,m.state,b.reference_date period_start,b.reference_date period_end,
        jsonb_build_object('bed_type',b.bed_type_code,'bed_type_label',b.bed_type_name) scope,
        md5(jsonb_build_object('bed_type',b.bed_type_code)::text) scope_key,
        sum(b.{field})::numeric value,'available' availability_status,'leitos' unit,
        'conforme competência CNES' periodicity,d.code dataset,s.provider,s.license,ss.url source_url,
        ss.sha256,ss.fetched_at retrieved_at,ss.published_at,max(b.revision) revision FROM beds b
        JOIN establishments e ON e.id=b.establishment_id AND e.rn=1 JOIN municipalities m ON
        m.ibge_code=e.municipality_ibge_code JOIN source_snapshots ss ON ss.id=b.snapshot_id
        JOIN datasets d ON d.id=ss.dataset_id JOIN sources s ON s.id=d.source_id WHERE b.rn=1
        GROUP BY e.municipality_ibge_code,m.name,m.state,b.reference_date,b.bed_type_code,
        b.bed_type_name,d.code,s.provider,s.license,ss.url,ss.sha256,ss.fetched_at,ss.published_at"""
    else:
        sql = """WITH services AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
        source_key ORDER BY revision DESC) rn FROM health_services f), establishments AS
        (SELECT f.*,row_number() OVER (PARTITION BY source_system,source_key ORDER BY revision DESC)
        rn FROM health_establishments f) SELECT :indicator indicator_code,e.municipality_ibge_code
        geo_id,m.name geo_name,m.state,v.reference_date period_start,v.reference_date period_end,
        jsonb_build_object('service',v.service_code,'service_label',v.service_name,'classification',
        coalesce(v.classification_code,'all'),'classification_label',coalesce(v.classification_name,
        'Todas'),'sus_available',v.sus_available) scope,md5(jsonb_build_object('service',v.service_code,
        'classification',coalesce(v.classification_code,'all'),'sus_available',v.sus_available)::text)
        scope_key,count(*)::numeric value,'available' availability_status,'cadastros de serviço'
        unit,'conforme competência CNES' periodicity,d.code dataset,s.provider,s.license,ss.url
        source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,max(v.revision) revision
        FROM services v JOIN establishments e ON e.id=v.establishment_id AND e.rn=1
        JOIN municipalities m ON m.ibge_code=e.municipality_ibge_code JOIN source_snapshots ss
        ON ss.id=v.snapshot_id JOIN datasets d ON d.id=ss.dataset_id JOIN sources s ON s.id=d.source_id
        WHERE v.rn=1 GROUP BY e.municipality_ibge_code,m.name,m.state,v.reference_date,v.service_code,
        v.service_name,v.classification_code,v.classification_name,v.sus_available,d.code,s.provider,
        s.license,ss.url,ss.sha256,ss.fetched_at,ss.published_at"""
    return sql, {"indicator": code}


def _procurement_select(code: str) -> tuple[str, dict[str, Any]]:
    family, measure = code.split(":", 1)
    table = "procurements" if family == "procurement" else "contracts"
    year = "procurement_year" if family == "procurement" else "contract_year"
    modality = "coalesce(f.modality_code,'unknown')" if family == "procurement" else "'contract'"
    sector = "coalesce(f.sector,'unknown')" if family == "procurement" else "'all'"
    value = {
        "count": "count(*)::numeric",
        "estimated_amount": "sum(f.estimated_amount)",
        "homologated_amount": "sum(f.homologated_amount)",
        "initial_amount": "sum(f.initial_amount)",
        "global_amount": "sum(f.global_amount)",
    }[measure]
    unit = "registros" if measure == "count" else "BRL nominal"
    sql = f"""WITH current AS (SELECT f.*,row_number() OVER (PARTITION BY source_system,
    source_key ORDER BY revision DESC) rn FROM {table} f) SELECT :indicator indicator_code,
    f.municipality_ibge_code geo_id,m.name geo_name,m.state,make_date(f.{year},1,1) period_start,
    make_date(f.{year},12,31) period_end,jsonb_build_object('status',coalesce(f.status,'unknown'),
    'modality',{modality},'sector',{sector}) scope,md5(jsonb_build_object('status',
    coalesce(f.status,'unknown'),'modality',{modality},'sector',{sector})::text) scope_key,
    {value} value,'available' availability_status,:unit unit,'anual' periodicity,d.code dataset,
    s.provider,s.license,ss.url source_url,ss.sha256,ss.fetched_at retrieved_at,ss.published_at,
    max(f.revision) revision FROM current f JOIN municipalities m ON m.ibge_code=f.municipality_ibge_code
    JOIN source_snapshots ss ON ss.id=f.snapshot_id JOIN datasets d ON d.id=ss.dataset_id
    JOIN sources s ON s.id=d.source_id WHERE f.rn=1 AND f.municipality_ibge_code IS NOT NULL
    GROUP BY f.municipality_ibge_code,m.name,m.state,f.{year},f.status,{modality},{sector},d.code,
    s.provider,s.license,ss.url,ss.sha256,ss.fetched_at,ss.published_at"""
    return sql, {"indicator": code, "unit": unit}


def _indicator_select(indicator: str) -> tuple[str, dict[str, Any]]:
    prefix, _, metric = indicator.partition(":")
    if indicator == "education:enrollment_count":
        return _fixed_select(indicator)
    if prefix in BASE_SELECTS:
        return BASE_SELECTS[prefix], {"metric": metric}
    return _fixed_select(indicator)


def research_points(
    db: Session,
    *,
    indicator: str,
    geo_ids: list[str],
    start_year: int | None,
    end_year: int | None,
    scope_key: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    definition = definition_by_code(db, indicator)
    if definition is None:
        raise KeyError(indicator)
    inner, params = _indicator_select(indicator)
    filters = ["q.geo_id IN :geo_ids"]
    params["geo_ids"] = geo_ids
    if start_year is not None:
        filters.append("q.period_end >= make_date(:start_year,1,1)")
        params["start_year"] = start_year
    if end_year is not None:
        filters.append("q.period_start <= make_date(:end_year,12,31)")
        params["end_year"] = end_year
    if scope_key:
        filters.append("q.scope_key=:scope_key")
        params["scope_key"] = scope_key
    where = " AND ".join(filters)
    base = f"SELECT * FROM ({inner}) q WHERE {where}"
    count = int(
        db.scalar(
            text(f"SELECT count(*) FROM ({base}) counted").bindparams(
                bindparam("geo_ids", expanding=True)
            ),
            params,
        )
        or 0
    )
    statement = text(
        f"{base} ORDER BY period_start,geo_name,scope_key LIMIT :limit OFFSET :offset"
    ).bindparams(bindparam("geo_ids", expanding=True))
    rows = db.execute(statement, {**params, "limit": limit, "offset": offset}).mappings()
    items = [
        {
            **{key: value for key, value in row.items() if key not in {"value"}},
            "value": format(row["value"], "f") if row["value"] is not None else None,
        }
        for row in rows
    ]
    scopes = [
        {"scope_key": key, "scope": scope, "rows": rows_count}
        for key, scope, rows_count in db.execute(
            text(
                f"SELECT scope_key,min(scope::text)::jsonb scope,count(*) rows FROM ({base}) scoped "
                "GROUP BY scope_key ORDER BY count(*) DESC,scope_key LIMIT 200"
            ).bindparams(bindparam("geo_ids", expanding=True)),
            params,
        )
    ]
    return {
        "definition": definition,
        "items": items,
        "count": count,
        "limit": limit,
        "offset": offset,
        "scopes": scopes,
    }
