from __future__ import annotations

from datetime import UTC, datetime

DECIDED_AT = datetime(2026, 10, 23, tzinfo=UTC)

HEALTH_DECISIONS: dict[str, tuple[str, str]] = {
    "LNT-0017": (
        "manual_review",
        "Swagger DEMAS localizado, mas o host reiniciou conexões neste ambiente; rotas "
        "exigem homologação individual.",
    ),
    "LNT-0018": (
        "integrate",
        "CNES agregado existente permanece homologado; detalhes publicáveis terão "
        "conector separado.",
    ),
    "LNT-0019": (
        "integrate",
        "ZIP/CSV oficial de hospitais e leitos homologado com competência explícita, "
        "campos institucionais mínimos e descarte de contatos e endereços.",
    ),
    "LNT-0020": (
        "integrate",
        "CSV oficial SIM 2024 homologado com agregação municipal por residência e "
        "limiar de divulgação.",
    ),
    "LNT-0021": (
        "integrate",
        "CSV oficial definitivo SINASC 2024 homologado com agregação por município "
        "de residência e descarte dos microdados após o processamento.",
    ),
    "LNT-0022": (
        "integrate",
        "DBC oficial SIH/SUS de dezembro de 2025 validado por FTP passivo e "
        "agregado antes da persistência.",
    ),
    "LNT-0023": (
        "integrate",
        "Partes DBC oficiais SIA/SUS de dezembro de 2025 validadas por FTP passivo "
        "e agregadas antes da persistência.",
    ),
    "LNT-0024": (
        "manual_review",
        "Os relatórios públicos SISAB abrem sem autenticação, mas a exportação depende de "
        "estado JSF e não oferece contrato estável de API ou arquivo versionado homologado.",
    ),
    "LNT-0025": (
        "integrate",
        "ZIP/CSV oficial municipal SIOPS 2025, 6º bimestre, homologado com "
        "fases contábeis, fonte, subfunção e natureza preservadas.",
    ),
    "LNT-0026": (
        "integrate",
        "Arquivo DBC municipal ANS de dezembro de 2025 homologado para vínculos; "
        "a unidade de contagem não representa pessoas únicas.",
    ),
    "LNT-0027": (
        "metadata_only",
        "OpenDataSUS é catálogo; cada conjunto precisa de recurso, schema, licença e "
        "conector próprios.",
    ),
    "LNT-0086": (
        "manual_review",
        "Rotas DEMAS de arboviroses estão documentadas, mas notificações não são "
        "casos confirmados.",
    ),
    "LNT-0087": (
        "metadata_only",
        "TABNET é interface de tabulação e não foi tratado como API REST geral.",
    ),
    "LNT-0088": (
        "metadata_only",
        "Distribuição DBC exige conector e dicionário próprios por sistema; SIM usa "
        "seu CSV oficial.",
    ),
    "LNT-0089": (
        "manual_review",
        "Cadastro de operadoras ANS não mede rede ou cobertura assistencial municipal.",
    ),
    "LNT-0090": (
        "manual_review",
        "Cobertura vacinal depende de dataset e metodologia específicos ainda não homologados.",
    ),
    "LNT-0091": (
        "restricted",
        "Profissionais CNES exigem avaliação LGPD; nenhuma lista nominal será publicada.",
    ),
    "LNT-0092": (
        "metadata_only",
        "Portal SES-SP é referência institucional; nenhum conjunto estadual específico "
        "foi presumido.",
    ),
}
