from __future__ import annotations

from datetime import UTC, datetime

DECIDED_AT = datetime(2026, 10, 21, tzinfo=UTC)

# Decisions cover every education-related record in the 2026 national inventory.
# A manual-review decision is deliberately not evidence of an integration.
EDUCATION_DECISIONS: dict[str, tuple[str, str]] = {
    "LNT-0007": (
        "integrate",
        "Censo Escolar 2024: ZIP/CSV oficial verificado e conector implementado.",
    ),
    "LNT-0008": (
        "metadata_only",
        "Catálogo de Escolas localizado; exportação estável não homologada nesta onda.",
    ),
    "LNT-0009": (
        "integrate",
        "Ideb municipal 2025: ZIP/XLSX oficial verificado e conector implementado.",
    ),
    "LNT-0010": (
        "integrate",
        "Saeb 2023: RAR/XLSB municipal oficial verificado e conector implementado.",
    ),
    "LNT-0011": ("manual_review", "Indicadores educacionais exigem homologação recurso a recurso."),
    "LNT-0012": (
        "metadata_only",
        "Entrada guarda-chuva do FNDE; somente o recurso PNAE LNT-0081 foi homologado.",
    ),
    "LNT-0013": (
        "manual_review",
        "Censo da Educação Superior não integra o primeiro recorte municipal.",
    ),
    "LNT-0014": (
        "manual_review",
        "Indicadores de qualidade superior/Enade pendem de avaliação de granularidade.",
    ),
    "LNT-0015": (
        "restricted",
        "Microdados do Enem exigem avaliação LGPD e não serão publicados por pessoa.",
    ),
    "LNT-0016": (
        "metadata_only",
        "QEdu é fonte terceira; API/licença de redistribuição não foram homologadas.",
    ),
    "LNT-0075": ("manual_review", "Rendimento escolar será validado como recurso independente."),
    "LNT-0076": ("manual_review", "Distorção idade-série será validada como recurso independente."),
    "LNT-0077": (
        "manual_review",
        "INSE será integrado somente após confirmar edição, escopo e supressões.",
    ),
    "LNT-0078": ("manual_review", "Indicadores docentes serão validados por edição e dicionário."),
    "LNT-0079": ("manual_review", "Média de alunos/horas exige homologação do arquivo anual."),
    "LNT-0080": ("manual_review", "Sinopses são referência de reconciliação, não fato substituto."),
    "LNT-0081": (
        "integrate",
        "PNAE 2024: XLSX oficial por entidade executora verificado e conector implementado.",
    ),
    "LNT-0082": ("manual_review", "PDDE/FNDE requer endpoint, licença e grão verificados."),
    "LNT-0083": ("manual_review", "PNATE/FNDE requer endpoint, licença e grão verificados."),
    "LNT-0084": ("manual_review", "Obras/FNDE requer endpoint, licença e grão verificados."),
    "LNT-0085": (
        "manual_review",
        "Microdados Enade pendem de avaliação LGPD e granularidade publicável.",
    ),
}
