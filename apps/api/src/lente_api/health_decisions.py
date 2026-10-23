from __future__ import annotations

from datetime import UTC, datetime

DECIDED_AT = datetime(2026, 10, 22, tzinfo=UTC)

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
        "manual_review",
        "Rota DEMAS de leitos documentada, porém resposta e schema não puderam ser "
        "validados neste ambiente.",
    ),
    "LNT-0020": (
        "integrate",
        "CSV oficial SIM 2024 homologado com agregação municipal por residência e "
        "limiar de divulgação.",
    ),
    "LNT-0021": (
        "manual_review",
        "SINASC possui arquivos oficiais, mas artefato e schema ainda não foram "
        "homologados nesta etapa.",
    ),
    "LNT-0022": (
        "manual_review",
        "SIH/SUS é arquivo/TABNET; a rota DEMAS documentada ainda não teve resposta validada.",
    ),
    "LNT-0023": (
        "manual_review",
        "SIA/SUS é arquivo/TABNET; a rota DEMAS documentada ainda não teve resposta validada.",
    ),
    "LNT-0024": (
        "restricted",
        "SISAB não teve API pública confirmada; endpoints internos ou autenticados não "
        "serão utilizados.",
    ),
    "LNT-0025": (
        "manual_review",
        "SIOPS foi confirmado como portal/TABNET, sem exportação estruturada "
        "homologada nesta etapa.",
    ),
    "LNT-0026": (
        "manual_review",
        "ANS publica arquivos DBC municipais; conversão e reconciliação ainda não "
        "foram homologadas.",
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
