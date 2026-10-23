from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from lente_api.database import SessionLocal
from lente_api.education_decisions import DECIDED_AT, EDUCATION_DECISIONS
from lente_api.health_decisions import DECIDED_AT as HEALTH_DECIDED_AT
from lente_api.health_decisions import HEALTH_DECISIONS
from lente_api.models import (
    CatalogEntry,
    CatalogImport,
    DataProvider,
    Dataset,
    Source,
    SourceResource,
)
from lente_api.transparency_decisions import (
    DECIDED_AT as TRANSPARENCY_DECIDED_AT,
)
from lente_api.transparency_decisions import (
    TRANSPARENCY_DECISIONS,
)

REFERENCE_RECORDS = 165
REFERENCE_AREAS = 16
REFERENCE_INDICATORS = 95
HOMOLOGATED_DATASET_LINKS = {
    "LNT-0003": "ibge_population",
    "LNT-0018": "cnes_establishments",
    "LNT-0020": "sim_mortality_municipal",
    "LNT-0093": "siconfi_rreo",
    "LNT-0007": "inep_censo_escolar",
    "LNT-0009": "inep_ideb_municipal",
    "LNT-0010": "inep_saeb_municipal",
    "LNT-0081": "fnde_pnae_municipal",
    "LNT-0038": "pncp_procurements",
    "LNT-0039": "tcesp_expenses",
    "LNT-0094": "siconfi_rgf",
    "LNT-0095": "siconfi_dca",
    "LNT-0099": "tcesp_revenues",
    "LNT-0100": "tcesp_expenses",
}
ALLOWED_FORMATS = {
    "api",
    "csv",
    "zip",
    "xlsx",
    "parquet",
    "portal",
    "manual",
    "json",
    "xml",
    "pdf",
}
ID_PATTERN = re.compile(r"^LNT-\d{4}$")
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
CODE_PATTERN = re.compile(r"^[a-z0-9]+(?:[._-][a-z0-9]+)*$")

ALIASES = {
    "external_id": ("id", "external_catalog_id", "catalog_id", "codigo", "código"),
    "area": ("area", "área", "domain", "dominio", "domínio", "tema", "setor"),
    "indicator": (
        "indicator",
        "indicador",
        "indicator_id",
        "indicador_id",
        "indicator_name",
        "nome_indicador",
    ),
    "provider": (
        "provider",
        "provedor",
        "provider_name",
        "source_provider",
        "orgao",
        "órgão",
        "instituicao",
        "instituição",
        "nome",
    ),
    "url": (
        "url",
        "source_url",
        "resource_url",
        "endpoint",
        "link",
        "download_url",
        "download",
        "api",
        "evidencia",
    ),
    "format": ("format", "formato", "resource_format", "formatos"),
    "provider_slug": ("provider_slug", "provedor_slug"),
    "resource_slug": ("resource_slug", "source_slug", "fonte_slug"),
    "dataset_code": ("dataset_code", "dataset_slug", "dataset", "conjunto_codigo"),
    "resource_title": ("resource_title", "source_name", "fonte", "recurso", "nome"),
    "description": ("description", "descricao", "descrição", "dados", "observacao"),
    "license": ("license", "licenca", "licença"),
    "terms": ("terms", "termos", "restricoes", "restrições"),
    "frequency": ("frequency", "frequencia", "frequência", "update_frequency", "freq"),
    "granularity": ("granularity", "granularidade", "recorte", "grao", "geografia"),
}

OFFICIAL_TOP_LEVEL_KEYS = {
    "projeto",
    "levantamento",
    "status",
    "fontes_count",
    "setores_count",
    "indicadores_count",
    "catalogo_descoberta",
    "fontes",
    "indicadores",
    "regras_etl",
    "roadmap",
}
OFFICIAL_SOURCE_KEYS = {
    "id",
    "setor",
    "nome",
    "dados",
    "geografia",
    "grao",
    "modalidade",
    "formatos",
    "api",
    "download",
    "tipo_link",
    "auth",
    "freq",
    "etl",
    "prioridade",
    "status",
    "observacao",
    "evidencia",
}
OFFICIAL_INDICATOR_KEYS = {
    "setor",
    "indicador",
    "fonte_principal_id",
    "fonte_complementar_id",
    "grao",
    "cuidado",
}


class CatalogValidationError(ValueError):
    def __init__(self, report: CatalogValidationReport):
        super().__init__("Catálogo candidato inválido; nenhuma alteração foi persistida")
        self.report = report


@dataclass(slots=True)
class CatalogExpectations:
    record_count: int = REFERENCE_RECORDS
    area_count: int = REFERENCE_AREAS
    indicator_count: int = REFERENCE_INDICATORS
    require_sequential_ids: bool = True


@dataclass(slots=True)
class CatalogValidationReport:
    valid: bool
    catalog_name: str | None
    catalog_version: str | None
    schema_version: str | None
    record_count: int
    area_count: int
    indicator_count: int
    duplicate_ids: list[str] = field(default_factory=list)
    missing_ids: list[str] = field(default_factory=list)
    unexpected_ids: list[str] = field(default_factory=list)
    invalid_ids: list[dict[str, Any]] = field(default_factory=list)
    missing_fields: list[dict[str, Any]] = field(default_factory=list)
    invalid_urls: list[dict[str, Any]] = field(default_factory=list)
    unsupported_urls: list[dict[str, Any]] = field(default_factory=list)
    invalid_formats: list[dict[str, Any]] = field(default_factory=list)
    invalid_indicator_links: list[dict[str, Any]] = field(default_factory=list)
    count_mismatches: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CatalogImportSummary:
    catalog_import_id: str
    sha256: str
    already_imported: bool
    records: int
    providers: int
    resources: int
    datasets: int
    entries: int
    discrepancies: list[dict[str, Any]]


def _first(record: dict[str, Any], field_name: str) -> Any:
    for key in ALIASES[field_name]:
        value = record.get(key)
        if value is not None and str(value).strip():
            return value
    return None


def _document_value(document: dict[str, Any], *keys: str) -> str | None:
    metadata = document.get("metadata") if isinstance(document.get("metadata"), dict) else {}
    for key in keys:
        value = document.get(key, metadata.get(key))
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def extract_records(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        return []
    for key in ("records", "registros", "items", "fontes", "sources"):
        records = document.get(key)
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def extract_indicator_records(document: Any) -> list[dict[str, Any]]:
    if not isinstance(document, dict):
        return []
    records = document.get("indicadores")
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]


def is_official_inventory(document: Any) -> bool:
    return isinstance(document, dict) and isinstance(document.get("fontes"), list)


def _record_urls(record: dict[str, Any]) -> list[tuple[str, str]]:
    fields = ("url", "source_url", "resource_url", "endpoint", "link", "download_url")
    if "fontes" not in record:
        fields += ("download", "api", "evidencia")
    seen: set[str] = set()
    values: list[tuple[str, str]] = []
    for field_name in fields:
        value = record.get(field_name)
        if value is None or not str(value).strip():
            continue
        normalized = str(value).strip()
        if normalized not in seen:
            values.append((field_name, normalized))
            seen.add(normalized)
    return values


def normalize_resource_format(value: Any) -> str | None:
    if value is None or not str(value).strip():
        return None
    normalized = slugify(str(value))
    if normalized in ALLOWED_FORMATS:
        return normalized
    if "api" in normalized or "swagger" in normalized or "wfs" in normalized or "wms" in normalized:
        return "api"
    if "zip" in normalized or "compactado" in normalized or "shapefile" in normalized:
        return "zip"
    if "parquet" in normalized:
        return "parquet"
    if "xlsx" in normalized or "excel" in normalized or "planilha" in normalized:
        return "xlsx"
    if "csv" in normalized:
        return "csv"
    if "json" in normalized:
        return "json"
    if "xml" in normalized:
        return "xml"
    if "pdf" in normalized:
        return "pdf"
    if any(
        marker in normalized
        for marker in (
            "portal",
            "painel",
            "paineis",
            "catalogo",
            "documentacao",
            "download",
            "tabela",
            "tabnet",
            "consulta",
        )
    ):
        return "portal"
    if any(
        marker in normalized
        for marker in ("arquivo", "etl", "microdados", "txt", "rdata", "aberto")
    ):
        return "manual"
    return None


def slugify(value: str, *, separator: str = "-") -> str:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", separator, normalized).strip(separator).lower()
    return slug or "sem-identificador"


def validate_public_url(value: str) -> str | None:
    try:
        parsed = urlparse(value)
    except ValueError:
        return "URL não pôde ser interpretada"
    if parsed.scheme not in {"http", "https"}:
        return "URL deve usar http ou https"
    if not parsed.hostname or parsed.username or parsed.password:
        return "URL deve ter host e não pode conter credenciais"
    hostname = parsed.hostname.rstrip(".").lower()
    if hostname == "localhost" or hostname.endswith(".localhost") or hostname.endswith(".local"):
        return "Host local não é permitido"
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        return None
    if not address.is_global:
        return "Endereço IP não público não é permitido"
    return None


def validate_catalog_document(
    document: Any,
    *,
    expectations: CatalogExpectations | None = None,
) -> CatalogValidationReport:
    expected = expectations or CatalogExpectations()
    errors: list[str] = []
    warnings: list[str] = []
    if not isinstance(document, dict):
        return CatalogValidationReport(
            valid=False,
            catalog_name=None,
            catalog_version=None,
            schema_version=None,
            record_count=0,
            area_count=0,
            indicator_count=0,
            errors=["A raiz deve ser um objeto JSON versionado"],
        )
    official_inventory = is_official_inventory(document)
    catalog_name = _document_value(document, "catalog_name", "nome", "name", "projeto")
    catalog_version = _document_value(
        document, "catalog_version", "version", "versao", "versão", "levantamento"
    )
    schema_version = _document_value(document, "schema_version", "versao_schema", "versão_schema")
    if official_inventory and not schema_version:
        schema_version = "lente-inventario-nacional-2026"
        warnings.append(
            "O arquivo não declara schema_version; aplicado o perfil de leitura "
            "lente-inventario-nacional-2026 sem alterar o original"
        )
    if not catalog_name:
        errors.append("Chave de nome do catálogo ausente")
    if not catalog_version:
        errors.append("Chave de versão do catálogo ausente")
    if not schema_version:
        errors.append("Chave de versão do schema ausente")
    records = extract_records(document)
    indicator_records = extract_indicator_records(document)
    if not records:
        errors.append("Lista de registros ausente ou vazia")

    ids: list[str] = []
    areas: set[str] = set()
    indicators: set[str] = set()
    invalid_ids: list[dict[str, Any]] = []
    missing_fields: list[dict[str, Any]] = []
    invalid_urls: list[dict[str, Any]] = []
    unsupported_urls: list[dict[str, Any]] = []
    invalid_formats: list[dict[str, Any]] = []
    invalid_indicator_links: list[dict[str, Any]] = []
    count_mismatches: list[dict[str, Any]] = []
    if official_inventory:
        missing_top_keys = sorted(OFFICIAL_TOP_LEVEL_KEYS - set(document))
        if missing_top_keys:
            errors.append(f"Chaves oficiais ausentes: {', '.join(missing_top_keys)}")
    for position, record in enumerate(records, start=1):
        external_id = str(_first(record, "external_id") or "").strip()
        if not ID_PATTERN.fullmatch(external_id):
            invalid_ids.append({"position": position, "value": external_id or None})
        else:
            ids.append(external_id)
        required_fields = (
            ("area", "provider") if indicator_records else ("area", "indicator", "provider")
        )
        for field_name in required_fields:
            value = _first(record, field_name)
            if value is None:
                missing_fields.append(
                    {"position": position, "id": external_id or None, "field": field_name}
                )
            elif field_name == "area":
                areas.add(str(value).strip().casefold())
            elif field_name == "indicator":
                indicators.add(str(value).strip().casefold())
        if official_inventory:
            missing_source_keys = sorted(OFFICIAL_SOURCE_KEYS - set(record))
            for field_name in missing_source_keys:
                missing_fields.append(
                    {
                        "position": position,
                        "id": external_id or None,
                        "field": field_name,
                    }
                )
        for url_field, url in _record_urls(record):
            parsed = urlparse(url)
            if (
                parsed.scheme == "ftp"
                and parsed.hostname
                and not parsed.username
                and not parsed.password
            ):
                unsupported_urls.append(
                    {
                        "position": position,
                        "id": external_id or None,
                        "field": url_field,
                        "value": url,
                        "reason": (
                            "FTP preservado como metadado; conectores aceitam somente HTTP/HTTPS"
                        ),
                    }
                )
                continue
            reason = validate_public_url(url)
            if reason:
                invalid_urls.append(
                    {
                        "position": position,
                        "id": external_id or None,
                        "field": url_field,
                        "value": url,
                        "reason": reason,
                    }
                )
        resource_format = _first(record, "format")
        if resource_format and normalize_resource_format(resource_format) is None:
            invalid_formats.append(
                {
                    "position": position,
                    "id": external_id or None,
                    "value": str(resource_format),
                }
            )

    valid_source_ids = set(ids)
    if indicator_records:
        for position, indicator_record in enumerate(indicator_records, start=1):
            if official_inventory:
                missing_indicator_keys = sorted(OFFICIAL_INDICATOR_KEYS - set(indicator_record))
                for field_name in missing_indicator_keys:
                    missing_fields.append(
                        {"position": position, "record": "indicator", "field": field_name}
                    )
            value = indicator_record.get("indicador")
            if value is None or not str(value).strip():
                missing_fields.append(
                    {"position": position, "record": "indicator", "field": "indicador"}
                )
            else:
                indicators.add(str(value).strip().casefold())
            area = indicator_record.get("setor")
            if area is None or not str(area).strip():
                missing_fields.append(
                    {"position": position, "record": "indicator", "field": "setor"}
                )
            for field_name in ("fonte_principal_id", "fonte_complementar_id"):
                source_id = indicator_record.get(field_name)
                if source_id and str(source_id).strip() not in valid_source_ids:
                    invalid_indicator_links.append(
                        {
                            "position": position,
                            "indicator": value,
                            "field": field_name,
                            "source_id": source_id,
                        }
                    )

    declared_counts = {
        "fontes_count": (len(records), expected.record_count),
        "setores_count": (len(areas), expected.area_count),
        "indicadores_count": (len(indicators), expected.indicator_count),
    }
    for field_name, (actual, expected_value) in declared_counts.items():
        if field_name not in document:
            continue
        declared = document[field_name]
        if declared != actual or declared != expected_value:
            count_mismatches.append(
                {
                    "field": field_name,
                    "declared": declared,
                    "actual": actual,
                    "expected": expected_value,
                }
            )

    duplicate_ids = sorted(item for item, count in Counter(ids).items() if count > 1)
    missing_ids: list[str] = []
    unexpected_ids: list[str] = []
    if expected.require_sequential_ids:
        expected_ids = {f"LNT-{index:04d}" for index in range(1, expected.record_count + 1)}
        actual_ids = set(ids)
        missing_ids = sorted(expected_ids - actual_ids)
        unexpected_ids = sorted(actual_ids - expected_ids)
    if len(records) != expected.record_count:
        errors.append(f"Esperados {expected.record_count} registros; recebidos {len(records)}")
    if len(areas) != expected.area_count:
        errors.append(f"Esperadas {expected.area_count} áreas; recebidas {len(areas)}")
    if len(indicators) != expected.indicator_count:
        errors.append(
            f"Esperados {expected.indicator_count} indicadores; recebidos {len(indicators)}"
        )
    if duplicate_ids:
        errors.append("Há IDs duplicados")
    if missing_ids:
        errors.append("A sequência LNT possui lacunas")
    if unexpected_ids:
        errors.append("Há IDs fora da sequência LNT esperada")
    if invalid_ids:
        errors.append("Há IDs fora do padrão LNT-0001")
    if missing_fields:
        errors.append("Há registros sem área, indicador ou provedor")
    if invalid_urls:
        errors.append("Há URLs inválidas ou não públicas")
    if invalid_formats:
        errors.append("Há formatos fora do vocabulário controlado")
    if unsupported_urls:
        warnings.append(
            f"{len(unsupported_urls)} URL(s) FTP foram preservadas apenas como metadado"
        )
    if invalid_indicator_links:
        errors.append("Há indicadores ligados a IDs de fonte inexistentes")
    if count_mismatches:
        errors.append("Há contagens declaradas inconsistentes")
    return CatalogValidationReport(
        valid=not errors,
        catalog_name=catalog_name,
        catalog_version=catalog_version,
        schema_version=schema_version,
        record_count=len(records),
        area_count=len(areas),
        indicator_count=len(indicators),
        duplicate_ids=duplicate_ids,
        missing_ids=missing_ids,
        unexpected_ids=unexpected_ids,
        invalid_ids=invalid_ids,
        missing_fields=missing_fields,
        invalid_urls=invalid_urls,
        unsupported_urls=unsupported_urls,
        invalid_formats=invalid_formats,
        invalid_indicator_links=invalid_indicator_links,
        count_mismatches=count_mismatches,
        warnings=warnings,
        errors=errors,
    )


def load_and_validate_catalog(
    path: Path,
    *,
    expectations: CatalogExpectations | None = None,
) -> tuple[dict[str, Any], bytes, CatalogValidationReport]:
    raw = path.read_bytes()
    try:
        document = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        report = CatalogValidationReport(
            valid=False,
            catalog_name=None,
            catalog_version=None,
            schema_version=None,
            record_count=0,
            area_count=0,
            indicator_count=0,
            errors=[f"JSON inválido: {exc}"],
        )
        raise CatalogValidationError(report) from exc
    report = validate_catalog_document(document, expectations=expectations)
    return document, raw, report


def _validated_slug(record: dict[str, Any], field_name: str, fallback: str) -> str:
    supplied = _first(record, field_name)
    if supplied is None:
        return slugify(fallback)[:100]
    value = str(supplied).strip()
    if not SLUG_PATTERN.fullmatch(value):
        raise ValueError(f"{field_name} inválido: {value}")
    return value


def _dataset_code(record: dict[str, Any], provider_slug: str, indicator: str) -> str:
    supplied = _first(record, "dataset_code")
    if supplied is not None:
        value = str(supplied).strip()
        if not CODE_PATTERN.fullmatch(value):
            raise ValueError(f"dataset_code inválido: {value}")
        return value[:100]
    external_id = str(_first(record, "external_id") or "").strip()
    if external_id:
        return slugify(f"catalog-{external_id}", separator="_")[:100]
    return slugify(f"catalog-{provider_slug}-{indicator}", separator="_")[:100]


def _resource_slug(record: dict[str, Any], provider_slug: str, url: str) -> str:
    supplied = _first(record, "resource_slug")
    if supplied is not None:
        value = str(supplied).strip()
        if not SLUG_PATTERN.fullmatch(value):
            raise ValueError(f"resource_slug inválido: {value}")
        base = value
    else:
        base = f"{provider_slug}-{hashlib.sha256(url.encode()).hexdigest()[:12]}"
    return base[:140]


def _legacy_source_slug(resource_slug: str, url: str) -> str:
    if len(resource_slug) <= 80:
        return resource_slug
    return f"{resource_slug[:67]}-{hashlib.sha256(url.encode()).hexdigest()[:12]}"


def _provider_identity(record: dict[str, Any]) -> tuple[str, str]:
    source_name = str(_first(record, "provider")).strip()
    if "nome" in record:
        provider_name = re.split(r"\s+[—–]\s+", source_name, maxsplit=1)[0].strip()
    else:
        provider_name = source_name
    provider_slug = _validated_slug(record, "provider_slug", provider_name)
    return provider_name, provider_slug


def _preferred_resource_url(record: dict[str, Any]) -> str | None:
    for field_name in ("download", "api", "url", "source_url", "resource_url", "evidencia"):
        value = record.get(field_name)
        if value is None or not str(value).strip():
            continue
        candidate = str(value).strip()
        if urlparse(candidate).scheme in {"http", "https"}:
            return candidate
    return None


def _indicator_links_by_source(document: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    links: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for indicator in extract_indicator_records(document):
        for role, field_name in (
            ("primary", "fonte_principal_id"),
            ("complementary", "fonte_complementar_id"),
        ):
            source_id = indicator.get(field_name)
            if not source_id:
                continue
            links[str(source_id)].append(
                {
                    "role": role,
                    "indicator": indicator.get("indicador"),
                    "area": indicator.get("setor"),
                    "grain": indicator.get("grao"),
                    "caution": indicator.get("cuidado"),
                }
            )
    return links


def import_candidate_catalog(
    db: Session,
    path: Path,
    *,
    expectations: CatalogExpectations | None = None,
) -> CatalogImportSummary:
    document, raw, report = load_and_validate_catalog(path, expectations=expectations)
    if not report.valid:
        raise CatalogValidationError(report)
    digest = hashlib.sha256(raw).hexdigest()
    existing_import = db.scalar(select(CatalogImport).where(CatalogImport.sha256 == digest))
    imported_at = datetime.now(UTC)
    already_imported = existing_import is not None
    if existing_import is None:
        catalog_import = CatalogImport(
            catalog_name=report.catalog_name or "",
            catalog_version=report.catalog_version or "",
            schema_version=report.schema_version or "",
            sha256=digest,
            source_path=str(path),
            imported_at=imported_at,
            record_count=report.record_count,
            area_count=report.area_count,
            indicator_count=report.indicator_count,
            discrepancies=[],
        )
        db.add(catalog_import)
        db.flush()
    else:
        catalog_import = existing_import
    discrepancies: list[dict[str, Any]] = []
    indicator_links = _indicator_links_by_source(document)
    try:
        for record in extract_records(document):
            external_id = str(_first(record, "external_id")).strip()
            _import_record(
                db,
                record,
                catalog_import,
                imported_at,
                discrepancies,
                indicator_links.get(external_id, []),
            )
        if report.record_count == REFERENCE_RECORDS:
            _link_homologated_datasets(db)
        combined_discrepancies = list(catalog_import.discrepancies or []) + discrepancies
        catalog_import.discrepancies = list(
            {
                json.dumps(item, ensure_ascii=False, sort_keys=True): item
                for item in combined_discrepancies
            }.values()
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return _summary(db, catalog_import, already_imported=already_imported)


def _link_homologated_datasets(db: Session) -> None:
    """Connect only explicitly homologated inventory entries to active datasets."""
    for external_id, dataset_code in HOMOLOGATED_DATASET_LINKS.items():
        entry = db.scalar(
            select(CatalogEntry).where(CatalogEntry.external_catalog_id == external_id)
        )
        dataset = db.scalar(select(Dataset).where(Dataset.code == dataset_code))
        if entry is None or dataset is None:
            continue
        entry.dataset_id = dataset.id
        if dataset.source_resource_id is not None:
            entry.source_resource_id = dataset.source_resource_id


def _import_record(
    db: Session,
    record: dict[str, Any],
    catalog_import: CatalogImport,
    imported_at: datetime,
    discrepancies: list[dict[str, Any]],
    indicator_refs: list[dict[str, Any]],
) -> None:
    external_id = str(_first(record, "external_id")).strip()
    source_name = str(_first(record, "provider")).strip()
    area = str(_first(record, "area")).strip()
    indicator = str(_first(record, "indicator") or source_name).strip()
    provider_name, provider_slug = _provider_identity(record)
    provider = db.scalar(select(DataProvider).where(DataProvider.slug == provider_slug))
    if provider is None:
        provider = DataProvider(
            slug=provider_slug,
            name=provider_name,
            external_catalog_id=f"national:provider:{provider_slug}",
            source_status="discovered",
            connector_status="not_implemented",
            license=str(_first(record, "license")) if _first(record, "license") else None,
            terms=str(_first(record, "terms")) if _first(record, "terms") else None,
            metadata_json={"catalog_candidate": True},
            created_at=imported_at,
            updated_at=imported_at,
        )
        db.add(provider)
        db.flush()
    elif provider.name != provider_name:
        discrepancies.append(
            {
                "id": external_id,
                "code": "provider_name_conflict",
                "kept": provider.name,
                "received": provider_name,
            }
        )

    resource: SourceResource | None = None
    dataset: Dataset | None = None
    url_value = _preferred_resource_url(record)
    if url_value:
        url = str(url_value).strip()
        resource = db.scalar(
            select(SourceResource).where(
                SourceResource.provider_id == provider.id,
                SourceResource.canonical_url == url,
            )
        )
        resource_slug = _resource_slug(record, provider_slug, url)
        resource_format = normalize_resource_format(_first(record, "format")) or "manual"
        if _first(record, "format") is None:
            discrepancies.append({"id": external_id, "code": "format_missing_defaulted_manual"})
        if resource is None:
            same_slug = db.scalar(
                select(SourceResource).where(SourceResource.slug == resource_slug)
            )
            if same_slug is not None and same_slug.canonical_url != url:
                resource_slug = (
                    f"{resource_slug[:127]}-{hashlib.sha256(url.encode()).hexdigest()[:12]}"
                )
                discrepancies.append({"id": external_id, "code": "resource_slug_collision"})
            resource = SourceResource(
                provider_id=provider.id,
                slug=resource_slug,
                title=str(_first(record, "resource_title") or source_name),
                external_catalog_id=f"national:resource:{resource_slug}",
                canonical_url=url,
                format=resource_format,
                source_status="discovered",
                connector_status="not_implemented",
                license_status="pending_review" if _first(record, "license") else "unknown",
                license=str(_first(record, "license")) if _first(record, "license") else None,
                terms=str(_first(record, "terms")) if _first(record, "terms") else None,
                last_verified_at=None,
                metadata_json={"catalog_candidate": True},
            )
            db.add(resource)
            db.flush()
        legacy_source = db.scalar(select(Source).where(Source.primary_resource_id == resource.id))
        legacy_source_slug = _legacy_source_slug(resource.slug, url)
        if legacy_source is None:
            legacy_source = db.scalar(select(Source).where(Source.slug == legacy_source_slug))
        if legacy_source is None:
            legacy_source = Source(
                provider=provider.name,
                slug=legacy_source_slug,
                source_url=url,
                license=resource.license,
                terms=resource.terms,
                expected_frequency=(
                    str(_first(record, "frequency")) if _first(record, "frequency") else None
                ),
                status="pending",
                verified_at=None,
                failure_reason="Recurso candidato; ainda não verificado nem integrado.",
                data_provider_id=provider.id,
                primary_resource_id=resource.id,
                catalog_import_id=catalog_import.id,
                external_catalog_id=f"national:source:{resource.slug}",
                source_status="discovered",
                connector_status="not_implemented",
                catalog_metadata={"catalog_candidate": True},
            )
            db.add(legacy_source)
            db.flush()
        dataset_code = _dataset_code(record, provider_slug, indicator)
        dataset = db.scalar(select(Dataset).where(Dataset.code == dataset_code))
        if dataset is None:
            dataset = Dataset(
                source_id=legacy_source.id,
                code=dataset_code,
                title=indicator,
                description=str(
                    _first(record, "description")
                    or "Metadado candidato; nenhuma observação foi coletada ou publicada."
                ),
                domain=slugify(area),
                granularity=str(_first(record, "granularity") or "a revisar"),
                update_policy=str(_first(record, "frequency") or "a revisar"),
                status="pending",
                source_resource_id=resource.id,
                catalog_import_id=catalog_import.id,
                external_catalog_id=f"national:dataset:{dataset_code}",
                connector_status="not_implemented",
                publication_status="not_published",
                catalog_metadata={"catalog_candidate": True},
            )
            db.add(dataset)
            db.flush()
        elif dataset.source_resource_id not in {None, resource.id}:
            discrepancies.append(
                {
                    "id": external_id,
                    "code": "dataset_resource_conflict",
                    "dataset": dataset.code,
                }
            )
    else:
        discrepancies.append(
            {
                "id": external_id,
                "code": "resource_url_missing",
                "message": "Metadado preservado sem criar source/dataset legado.",
            }
        )

    entry = db.scalar(select(CatalogEntry).where(CatalogEntry.external_catalog_id == external_id))
    if entry is None:
        entry = CatalogEntry(
            external_catalog_id=external_id,
            catalog_import_id=catalog_import.id,
            provider_id=provider.id,
            source_resource_id=resource.id if resource else None,
            dataset_id=dataset.id if dataset else None,
            area_slug=slugify(area),
            indicator_ref=indicator,
            indicator_refs=indicator_refs,
            raw_record=record,
            imported_at=imported_at,
        )
        db.add(entry)
    else:
        entry.catalog_import_id = catalog_import.id
        entry.provider_id = provider.id
        entry.source_resource_id = resource.id if resource else None
        entry.dataset_id = dataset.id if dataset else None
        entry.area_slug = slugify(area)
        entry.indicator_ref = indicator
        entry.indicator_refs = indicator_refs
        entry.raw_record = record
        entry.imported_at = imported_at
    decision = (
        EDUCATION_DECISIONS.get(external_id)
        or TRANSPARENCY_DECISIONS.get(external_id)
        or HEALTH_DECISIONS.get(external_id)
    )
    if decision:
        entry.integration_decision, entry.decision_reason = decision
        if external_id in EDUCATION_DECISIONS:
            entry.decided_at = DECIDED_AT
        elif external_id in TRANSPARENCY_DECISIONS:
            entry.decided_at = TRANSPARENCY_DECIDED_AT
        else:
            entry.decided_at = HEALTH_DECIDED_AT
        if decision[0] == "integrate" and resource is not None:
            resource.source_status = "verified"
            resource.connector_status = "implemented"
            resource.last_verified_at = entry.decided_at


def _summary(
    db: Session, catalog_import: CatalogImport, *, already_imported: bool
) -> CatalogImportSummary:
    entries = list(
        db.scalars(select(CatalogEntry).where(CatalogEntry.catalog_import_id == catalog_import.id))
    )
    return CatalogImportSummary(
        catalog_import_id=str(catalog_import.id),
        sha256=catalog_import.sha256,
        already_imported=already_imported,
        records=catalog_import.record_count,
        providers=len({entry.provider_id for entry in entries}),
        resources=len(
            {entry.source_resource_id for entry in entries if entry.source_resource_id is not None}
        ),
        datasets=len({entry.dataset_id for entry in entries if entry.dataset_id is not None}),
        entries=len(entries),
        discrepancies=list(catalog_import.discrepancies or []),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Valida e importa o catálogo nacional candidato")
    subparsers = parser.add_subparsers(dest="command", required=True)
    validate_parser = subparsers.add_parser("validate", help="Valida sem escrever no banco")
    validate_parser.add_argument("path", type=Path)
    import_parser = subparsers.add_parser("import", help="Valida e importa metadados")
    import_parser.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            _, _, report = load_and_validate_catalog(args.path)
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
            raise SystemExit(0 if report.valid else 1)
        with SessionLocal() as db:
            summary = import_candidate_catalog(db, args.path)
        print(json.dumps(asdict(summary), ensure_ascii=False, indent=2))
    except CatalogValidationError as exc:
        print(json.dumps(exc.report.to_dict(), ensure_ascii=False, indent=2))
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
