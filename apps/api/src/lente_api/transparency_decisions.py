from __future__ import annotations

from datetime import UTC, datetime

DECIDED_AT = datetime(2026, 10, 22, tzinfo=UTC)

TRANSPARENCY_DECISIONS: dict[str, tuple[str, str]] = {
    "LNT-0036": (
        "metadata_only",
        "Entrada guarda-chuva Siconfi; conectores são homologados por demonstrativo.",
    ),
    "LNT-0037": (
        "restricted",
        "API da CGU exige token; nenhum segredo foi fornecido ou persistido.",
    ),
    "LNT-0038": (
        "integrate",
        "OpenAPI oficial PNCP validada; paginação de contratações e contratos implementada.",
    ),
    "LNT-0039": (
        "integrate",
        (
            "API municipal TCE-SP validada também para 2025; despesas são agregadas por "
            "mês/fase e dados de fornecedor são descartados antes do snapshot."
        ),
    ),
    "LNT-0040": (
        "metadata_only",
        "Coleção TCE-SP auditada; receitas CSV e despesas via API possuem conectores próprios.",
    ),
    "LNT-0042": (
        "metadata_only",
        "FNDE é guarda-chuva; PNAE 2024 já é homologado separadamente em LNT-0081.",
    ),
    "LNT-0093": (
        "integrate",
        "RREO oficial Siconfi permanece no conector compatível já publicado.",
    ),
    "LNT-0094": (
        "integrate",
        (
            "RGF oficial Siconfi validado e conector por ente, exercício, período e "
            "anexo implementado."
        ),
    ),
    "LNT-0095": (
        "integrate",
        "DCA oficial Siconfi validada e conector anual por anexo implementado.",
    ),
    "LNT-0099": (
        "integrate",
        "ZIP/CSV oficial de receitas 2025 validado com rubricas preservadas.",
    ),
    "LNT-0100": (
        "integrate",
        (
            "API oficial por município/mês substitui o ZIP nacional de 2,10 GB; eventos "
            "permanecem separados e campos pessoais não são persistidos."
        ),
    ),
    "LNT-0101": ("restricted", "Convênios CGU exigem token autorizado não disponível."),
    "LNT-0102": ("restricted", "Emendas CGU exigem token autorizado não disponível."),
    "LNT-0103": (
        "restricted",
        "Sanções CGU exigem token e revisão LGPD antes de cruzamento com fornecedores.",
    ),
    "LNT-0104": (
        "manual_review",
        "Planos anuais PNCP ainda não possuem conector homologado nesta etapa.",
    ),
    "LNT-0105": ("manual_review", "Atas PNCP ainda não possuem conector homologado nesta etapa."),
}
