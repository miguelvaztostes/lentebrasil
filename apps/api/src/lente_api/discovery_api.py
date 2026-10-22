from __future__ import annotations

import unicodedata
import uuid
from collections.abc import Iterable
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import Text, and_, case, cast, func, or_, select
from sqlalchemy.orm import Session, joinedload

from lente_api.database import get_db
from lente_api.models import (
    CatalogEntry,
    DataProvider,
    Dataset,
    DatasetCoverage,
    Municipality,
    Observation,
    Source,
    SourceResource,
    SourceSnapshot,
)

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_db)]

ACCENTS = "áàâãäåéèêëíìîïóòôõöúùûüçñýÿ"
ASCII = "aaaaaaeeeeiiiiooooouuuucnyy"


def normalize_text(value: str) -> str:
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", value.casefold())
        if not unicodedata.combining(character)
    )


def normalized_column(column: Any) -> Any:
    return func.translate(func.lower(column), ACCENTS, ASCII)


def public_status(
    *, source_status: str, connector_status: str, publication_status: str | None = None
) -> str:
    if source_status == "restricted":
        return "restricted"
    if source_status == "unavailable" or connector_status == "failed":
        return "unavailable"
    if publication_status == "stale" or connector_status == "degraded":
        return "stale"
    if publication_status == "published":
        return "published"
    if connector_status in {"implemented", "active"}:
        return "integrated"
    if source_status in {"pending_review", "pending"} or connector_status == "planned":
        return "pending_review"
    return "discovered"


def _status_condition(status: str) -> Any:
    published = (
        select(Observation.id)
        .join(SourceSnapshot, SourceSnapshot.id == Observation.snapshot_id)
        .where(SourceSnapshot.dataset_id == Dataset.id)
        .limit(1)
        .exists()
    )
    if status == "restricted":
        return SourceResource.source_status == "restricted"
    if status == "unavailable":
        return or_(
            SourceResource.source_status == "unavailable",
            SourceResource.connector_status == "failed",
        )
    if status == "stale":
        return or_(
            Dataset.publication_status == "stale",
            SourceResource.connector_status == "degraded",
        )
    if status == "published":
        return published
    if status == "integrated":
        return and_(
            SourceResource.connector_status.in_(["implemented", "active"]),
            ~published,
        )
    if status == "pending_review":
        return or_(
            SourceResource.source_status == "pending_review",
            SourceResource.connector_status == "planned",
        )
    return SourceResource.source_status == "discovered"


def _facet(rows: Iterable[tuple[str | None, int]]) -> list[dict[str, Any]]:
    return [
        {"value": value, "count": count}
        for value, count in rows
        if value is not None and str(value).strip()
    ]


def _catalog_base() -> Any:
    return (
        select(CatalogEntry)
        .join(DataProvider, DataProvider.id == CatalogEntry.provider_id)
        .outerjoin(SourceResource, SourceResource.id == CatalogEntry.source_resource_id)
        .outerjoin(Dataset, Dataset.id == CatalogEntry.dataset_id)
    )


def _catalog_item(
    entry: CatalogEntry, published_dataset_ids: set[uuid.UUID] | None = None
) -> dict[str, Any]:
    resource = entry.source_resource
    dataset = entry.dataset
    source_status = resource.source_status if resource else entry.provider.source_status
    connector_status = (
        dataset.connector_status
        if dataset
        else resource.connector_status
        if resource
        else entry.provider.connector_status
    )
    effectively_published = bool(
        dataset and published_dataset_ids and dataset.id in published_dataset_ids
    )
    publication_status = "published" if effectively_published else "not_published"
    raw = entry.raw_record or {}
    return {
        "id": entry.external_catalog_id,
        "title": entry.indicator_ref,
        "description": raw.get("dados") or (dataset.description if dataset else None),
        "area": entry.area_slug,
        "area_label": raw.get("setor") or entry.area_slug,
        "provider": {"slug": entry.provider.slug, "name": entry.provider.name},
        "resource": None
        if resource is None
        else {
            "slug": resource.slug,
            "title": resource.title,
            "url": resource.canonical_url,
            "format": resource.format,
            "source_status": resource.source_status,
            "connector_status": resource.connector_status,
            "license_status": resource.license_status,
            "license": resource.license,
            "last_verified_at": resource.last_verified_at,
        },
        "dataset": None
        if dataset is None
        else {
            "id": str(dataset.id),
            "code": dataset.code,
            "granularity": dataset.granularity,
            "update_policy": dataset.update_policy,
            "publication_status": dataset.publication_status,
        },
        "status": public_status(
            source_status=source_status,
            connector_status=connector_status,
            publication_status=publication_status,
        ),
        "source_status": source_status,
        "connector_status": connector_status,
        "publication_status": publication_status,
        "integration_decision": entry.integration_decision,
        "decision_reason": entry.decision_reason,
        "decided_at": entry.decided_at,
        "reference_period": None,
        "collected_at": None,
    }


@router.get("/search")
def search_catalog(
    db: DbSession,
    q: str | None = Query(None, max_length=120),
    uf: str | None = Query(None, min_length=2, max_length=2, pattern="^[A-Za-z]{2}$"),
    sector: str | None = Query(None, max_length=120),
    origin: str | None = Query(None, max_length=100),
    resource: str | None = Query(None, max_length=140),
    granularity: str | None = Query(None, max_length=160),
    resource_format: str | None = Query(None, alias="format", max_length=40),
    status: Literal[
        "discovered",
        "pending_review",
        "integrated",
        "published",
        "stale",
        "restricted",
        "unavailable",
    ]
    | None = None,
    availability: Literal["published", "not_published"] | None = None,
    license_status: Literal["unknown", "pending_review", "confirmed", "restricted"] | None = None,
    freshness: Literal["current", "stale", "unknown"] | None = None,
    from_year: int | None = Query(None, ge=1900, le=2100),
    to_year: int | None = Query(None, ge=1900, le=2100),
    sort: Literal["relevance", "title", "status"] = "relevance",
    limit: int = Query(24, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if from_year and to_year and from_year > to_year:
        raise HTTPException(status_code=400, detail="from_year deve preceder to_year")
    statement = _catalog_base()
    if q and q.strip():
        term = f"%{normalize_text(q.strip())}%"
        statement = statement.where(
            or_(
                normalized_column(CatalogEntry.external_catalog_id).like(term),
                normalized_column(CatalogEntry.indicator_ref).like(term),
                normalized_column(DataProvider.name).like(term),
                normalized_column(SourceResource.title).like(term),
                normalized_column(Dataset.title).like(term),
                normalized_column(CatalogEntry.area_slug).like(term),
                normalized_column(cast(CatalogEntry.raw_record, Text)).like(term),
                normalized_column(cast(CatalogEntry.indicator_refs, Text)).like(term),
            )
        )
    if sector:
        statement = statement.where(CatalogEntry.area_slug == sector)
    if origin:
        statement = statement.where(DataProvider.slug == origin)
    if resource:
        statement = statement.where(SourceResource.slug == resource)
    if granularity:
        statement = statement.where(Dataset.granularity == granularity)
    if resource_format:
        statement = statement.where(SourceResource.format == resource_format)
    if status:
        statement = statement.where(_status_condition(status))
    if availability:
        published = (
            select(Observation.id)
            .join(SourceSnapshot, SourceSnapshot.id == Observation.snapshot_id)
            .where(SourceSnapshot.dataset_id == Dataset.id)
            .limit(1)
            .exists()
        )
        statement = statement.where(published if availability == "published" else ~published)
    if license_status:
        statement = statement.where(SourceResource.license_status == license_status)
    freshness_cutoff = datetime.now(UTC) - timedelta(days=400)
    if freshness == "current":
        statement = statement.where(SourceResource.last_verified_at >= freshness_cutoff)
    elif freshness == "stale":
        statement = statement.where(
            SourceResource.last_verified_at.is_not(None),
            SourceResource.last_verified_at < freshness_cutoff,
        )
    elif freshness == "unknown":
        statement = statement.where(SourceResource.last_verified_at.is_(None))
    if from_year or to_year:
        coverage_filter = select(DatasetCoverage.id).where(DatasetCoverage.dataset_id == Dataset.id)
        if from_year:
            coverage_filter = coverage_filter.where(
                DatasetCoverage.period_end >= date(from_year, 1, 1)
            )
        if to_year:
            coverage_filter = coverage_filter.where(
                DatasetCoverage.period_start <= date(to_year, 12, 31)
            )
        statement = statement.where(coverage_filter.exists())

    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = db.scalar(count_statement) or 0
    if sort == "title":
        statement = statement.order_by(CatalogEntry.indicator_ref, CatalogEntry.external_catalog_id)
    elif sort == "status":
        statement = statement.order_by(
            case((_status_condition("published"), 0), else_=1),
            CatalogEntry.indicator_ref,
        )
    else:
        statement = statement.order_by(
            case((_status_condition("published"), 0), else_=1),
            CatalogEntry.external_catalog_id,
        )
    entries = list(
        db.scalars(
            statement.options(
                joinedload(CatalogEntry.provider),
                joinedload(CatalogEntry.source_resource),
                joinedload(CatalogEntry.dataset),
            )
            .limit(limit)
            .offset(offset)
        ).unique()
    )
    dataset_ids = {entry.dataset_id for entry in entries if entry.dataset_id is not None}
    published_dataset_ids = set()
    if dataset_ids:
        published_dataset_ids = set(
            db.scalars(
                select(SourceSnapshot.dataset_id)
                .join(Observation, Observation.snapshot_id == SourceSnapshot.id)
                .where(SourceSnapshot.dataset_id.in_(dataset_ids))
                .distinct()
            )
        )

    municipality_statement = select(Municipality)
    if uf:
        municipality_statement = municipality_statement.where(Municipality.state == uf.upper())
    if q and q.strip():
        municipality_statement = municipality_statement.where(
            normalized_column(Municipality.name).like(f"%{normalize_text(q.strip())}%")
        )
    municipalities = list(db.scalars(municipality_statement.order_by(Municipality.name).limit(8)))
    candidate_total = db.scalar(select(func.count(CatalogEntry.id))) or 0
    published_total = (
        db.scalar(
            select(func.count(func.distinct(SourceSnapshot.dataset_id))).join(
                Observation, Observation.snapshot_id == SourceSnapshot.id
            )
        )
        or 0
    )
    facets = {
        "sectors": _facet(
            db.execute(
                select(CatalogEntry.area_slug, func.count(CatalogEntry.id))
                .group_by(CatalogEntry.area_slug)
                .order_by(CatalogEntry.area_slug)
            )
        ),
        "providers": _facet(
            db.execute(
                select(DataProvider.slug, func.count(CatalogEntry.id))
                .join(CatalogEntry, CatalogEntry.provider_id == DataProvider.id)
                .group_by(DataProvider.slug)
                .order_by(DataProvider.slug)
            )
        ),
        "formats": _facet(
            db.execute(
                select(SourceResource.format, func.count(CatalogEntry.id))
                .join(CatalogEntry, CatalogEntry.source_resource_id == SourceResource.id)
                .group_by(SourceResource.format)
                .order_by(SourceResource.format)
            )
        ),
        "resources": _facet(
            db.execute(
                select(SourceResource.slug, func.count(CatalogEntry.id))
                .join(CatalogEntry, CatalogEntry.source_resource_id == SourceResource.id)
                .group_by(SourceResource.slug)
                .order_by(SourceResource.slug)
            )
        ),
        "license_statuses": _facet(
            db.execute(
                select(SourceResource.license_status, func.count(CatalogEntry.id))
                .join(CatalogEntry, CatalogEntry.source_resource_id == SourceResource.id)
                .group_by(SourceResource.license_status)
                .order_by(SourceResource.license_status)
            )
        ),
        "statuses": [
            {
                "value": value,
                "count": db.scalar(
                    select(func.count()).select_from(
                        _catalog_base().where(_status_condition(value)).order_by(None).subquery()
                    )
                )
                or 0,
            }
            for value in (
                "discovered",
                "pending_review",
                "integrated",
                "published",
                "stale",
                "restricted",
                "unavailable",
            )
        ],
        "freshness": [
            {
                "value": "current",
                "count": db.scalar(
                    select(func.count(CatalogEntry.id))
                    .join(SourceResource, CatalogEntry.source_resource_id == SourceResource.id)
                    .where(SourceResource.last_verified_at >= freshness_cutoff)
                )
                or 0,
            },
            {
                "value": "stale",
                "count": db.scalar(
                    select(func.count(CatalogEntry.id))
                    .join(SourceResource, CatalogEntry.source_resource_id == SourceResource.id)
                    .where(
                        SourceResource.last_verified_at.is_not(None),
                        SourceResource.last_verified_at < freshness_cutoff,
                    )
                )
                or 0,
            },
            {
                "value": "unknown",
                "count": db.scalar(
                    select(func.count(CatalogEntry.id))
                    .outerjoin(SourceResource, CatalogEntry.source_resource_id == SourceResource.id)
                    .where(SourceResource.last_verified_at.is_(None))
                )
                or 0,
            },
        ],
    }
    return {
        "items": [_catalog_item(entry, published_dataset_ids) for entry in entries],
        "municipalities": [
            {"ibge_code": row.ibge_code, "name": row.name, "state": row.state}
            for row in municipalities
        ],
        "count": total,
        "limit": limit,
        "offset": offset,
        "facets": facets,
        "summary": {
            "candidate_sources": candidate_total,
            "published_datasets": published_total,
        },
    }


@router.get("/sources/{identifier}")
def source_detail(identifier: str, db: DbSession) -> dict[str, Any]:
    entry = db.scalar(
        select(CatalogEntry)
        .where(CatalogEntry.external_catalog_id == identifier.upper())
        .options(
            joinedload(CatalogEntry.provider),
            joinedload(CatalogEntry.source_resource),
            joinedload(CatalogEntry.dataset),
        )
    )
    if entry:
        published_dataset_ids = set()
        if entry.dataset_id is not None:
            has_observation = db.scalar(
                select(Observation.id)
                .join(SourceSnapshot, SourceSnapshot.id == Observation.snapshot_id)
                .where(SourceSnapshot.dataset_id == entry.dataset_id)
                .limit(1)
            )
            if has_observation is not None:
                published_dataset_ids.add(entry.dataset_id)
        return {
            "kind": "catalog_candidate",
            **_catalog_item(entry, published_dataset_ids),
            "raw": entry.raw_record,
        }
    source = (
        db.execute(
            select(Source)
            .where(Source.slug == identifier)
            .options(joinedload(Source.primary_resource), joinedload(Source.datasets))
        )
        .unique()
        .scalar_one_or_none()
    )
    if source is None:
        raise HTTPException(status_code=404, detail="Fonte não encontrada")
    return {
        "kind": "integrated_source",
        "id": source.slug,
        "title": source.provider,
        "url": source.source_url,
        "license": source.license,
        "terms": source.terms,
        "source_status": source.source_status,
        "connector_status": source.connector_status,
        "verified_at": source.verified_at,
        "datasets": [
            {
                "id": str(dataset.id),
                "code": dataset.code,
                "title": dataset.title,
                "publication_status": dataset.publication_status,
            }
            for dataset in source.datasets
        ],
    }


@router.get("/datasets/{identifier}/coverage")
def dataset_coverage(identifier: str, db: DbSession) -> dict[str, Any]:
    conditions = [Dataset.code == identifier]
    try:
        conditions.append(Dataset.id == uuid.UUID(identifier))
    except ValueError:
        pass
    dataset = db.scalar(
        select(Dataset)
        .where(or_(*conditions))
        .options(joinedload(Dataset.source), joinedload(Dataset.source_resource))
    )
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset não encontrado")
    rows = list(
        db.scalars(
            select(DatasetCoverage)
            .where(DatasetCoverage.dataset_id == dataset.id)
            .options(joinedload(DatasetCoverage.geo_unit))
            .order_by(DatasetCoverage.period_start)
        )
    )
    observed = db.execute(
        select(
            func.count(func.distinct(Observation.municipality_ibge_code)),
            func.min(Observation.period_start),
            func.max(Observation.period_end),
            func.max(Observation.retrieved_at),
        )
        .join(SourceSnapshot, SourceSnapshot.id == Observation.snapshot_id)
        .where(SourceSnapshot.dataset_id == dataset.id)
    ).one()
    return {
        "dataset": {
            "id": str(dataset.id),
            "code": dataset.code,
            "title": dataset.title,
            "area": dataset.domain,
            "granularity": dataset.granularity,
            "publication_status": dataset.publication_status,
        },
        "source": {
            "provider": dataset.source.provider,
            "url": dataset.source.source_url,
            "license": dataset.source.license,
            "source_status": dataset.source.source_status,
            "connector_status": dataset.source.connector_status,
        },
        "observed": {
            "municipalities": observed[0],
            "period_start": observed[1],
            "period_end": observed[2],
            "collected_at": observed[3],
            "availability": "published" if observed[0] else "not_published",
        },
        "coverage": [
            {
                "status": row.coverage_status,
                "geography": None
                if row.geo_unit is None
                else {
                    "type": row.geo_unit.unit_type,
                    "code": row.geo_unit.code,
                    "name": row.geo_unit.name,
                    "state": row.geo_unit.state,
                },
                "scope": row.scope_json,
                "period_start": row.period_start,
                "period_end": row.period_end,
                "checked_at": row.checked_at,
                "notes": row.notes,
            }
            for row in rows
        ],
    }
