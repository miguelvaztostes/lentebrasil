from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, cast, desc, func, or_, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from lente_api.database import get_db
from lente_api.discovery_api import normalize_text, normalized_column, public_status
from lente_api.models import (
    CatalogEntry,
    Dataset,
    Indicator,
    IngestionRun,
    Municipality,
    Observation,
    Source,
    SourceResource,
    SourceSnapshot,
)
from lente_api.schemas import IndicatorOut, MunicipalityOut

router = APIRouter(prefix="/api/v1")
DbSession = Annotated[Session, Depends(get_db)]


def _page(limit: int, offset: int, items: list[Any], count: int) -> dict[str, Any]:
    return {"items": items, "count": count, "limit": limit, "offset": offset}


def _latest_observations_query(*, eager: bool = False):
    latest = (
        select(
            Observation.municipality_ibge_code,
            Observation.indicator_id,
            Observation.period_start,
            Observation.period_end,
            Observation.scope_key,
            func.max(Observation.revision).label("max_revision"),
        )
        .group_by(
            Observation.municipality_ibge_code,
            Observation.indicator_id,
            Observation.period_start,
            Observation.period_end,
            Observation.scope_key,
        )
        .subquery()
    )
    statement = select(Observation).join(
        latest,
        and_(
            Observation.municipality_ibge_code == latest.c.municipality_ibge_code,
            Observation.indicator_id == latest.c.indicator_id,
            Observation.period_start == latest.c.period_start,
            Observation.period_end == latest.c.period_end,
            Observation.scope_key == latest.c.scope_key,
            Observation.revision == latest.c.max_revision,
        ),
    )
    if eager:
        statement = statement.options(
            joinedload(Observation.indicator),
            joinedload(Observation.municipality),
            joinedload(Observation.snapshot)
            .joinedload(SourceSnapshot.dataset)
            .joinedload(Dataset.source),
        )
    return statement


def _require_municipality(db: Session, code: str) -> Municipality:
    if len(code) != 7 or not code.isdigit():
        raise HTTPException(status_code=400, detail="Código IBGE municipal deve ter sete dígitos")
    municipality = db.get(Municipality, code)
    if municipality is None:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return municipality


def _observation_dict(observation: Observation) -> dict[str, Any]:
    snapshot = observation.snapshot
    dataset = snapshot.dataset
    source = dataset.source
    return {
        "period_start": observation.period_start,
        "period_end": observation.period_end,
        "scope": observation.scope_json,
        "value": observation.value,
        "availability_status": observation.availability_status,
        "revision": observation.revision,
        "source_reference_at": observation.source_reference_at,
        "retrieved_at": observation.retrieved_at,
        "source": {
            "provider": source.provider,
            "dataset": dataset.title,
            "url": snapshot.url,
            "sha256": snapshot.sha256,
            "fetched_at": snapshot.fetched_at,
            "license": source.license,
            "source_status": source.source_status,
            "connector_status": source.connector_status,
        },
    }


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "lente-ribeirao-api", "version": "0.1.0"}


@router.get("/ready")
def readiness(db: DbSession) -> dict[str, str]:
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Banco de dados indisponível") from exc
    return {"status": "ready"}


@router.get("/municipalities", response_model=list[MunicipalityOut])
def municipalities(db: DbSession) -> list[Municipality]:
    return list(db.scalars(select(Municipality).order_by(Municipality.name)))


@router.get("/geo/municipios")
def geo_municipalities(
    db: DbSession,
    uf: str | None = Query(None, min_length=2, max_length=2),
    q: str | None = Query(None, max_length=100),
    sort: Literal["name", "code"] = "name",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = select(Municipality)
    count_statement = select(func.count(Municipality.ibge_code))
    if uf:
        normalized_uf = uf.upper()
        statement = statement.where(Municipality.state == normalized_uf)
        count_statement = count_statement.where(Municipality.state == normalized_uf)
    if q and q.strip():
        pattern = f"%{normalize_text(q.strip())}%"
        condition = normalized_column(Municipality.name).like(pattern)
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    ordering = Municipality.ibge_code if sort == "code" else Municipality.name
    rows = list(db.scalars(statement.order_by(ordering).limit(limit).offset(offset)))
    return _page(
        limit,
        offset,
        [MunicipalityOut.model_validate(row).model_dump() for row in rows],
        db.scalar(count_statement) or 0,
    )


@router.get("/sources")
def sources(
    db: DbSession,
    q: str | None = Query(None, max_length=120),
    area: str | None = Query(None, max_length=120),
    provider: str | None = Query(None, max_length=200),
    resource: str | None = Query(None, max_length=140),
    resource_format: str | None = Query(None, alias="format", max_length=40),
    status: str | None = Query(None, max_length=40),
    freshness: Literal["current", "stale", "unknown"] | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(days=400)
    statement = select(Source).outerjoin(Source.primary_resource)
    count_statement = select(func.count(Source.id)).outerjoin(Source.primary_resource)
    conditions = []
    if q and q.strip():
        term = f"%{normalize_text(q.strip())}%"
        conditions.append(
            or_(
                normalized_column(Source.provider).like(term),
                normalized_column(SourceResource.title).like(term),
            )
        )
    if area:
        conditions.append(
            select(Dataset.id)
            .where(Dataset.source_id == Source.id, Dataset.domain == area)
            .exists()
        )
    if provider:
        conditions.append(normalized_column(Source.provider) == normalize_text(provider))
    if resource:
        conditions.append(SourceResource.slug == resource)
    if resource_format:
        conditions.append(SourceResource.format == resource_format)
    if status:
        conditions.append(
            or_(
                Source.status == status,
                Source.source_status == status,
                Source.connector_status == status,
            )
        )
    if freshness == "current":
        conditions.append(Source.verified_at >= cutoff)
    elif freshness == "stale":
        conditions.append(
            or_(
                Source.connector_status == "degraded",
                and_(Source.verified_at.is_not(None), Source.verified_at < cutoff),
            )
        )
    elif freshness == "unknown":
        conditions.append(Source.verified_at.is_(None))
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    rows = list(
        db.scalars(
            statement.options(joinedload(Source.primary_resource))
            .order_by(Source.provider)
            .limit(limit)
            .offset(offset)
        )
    )
    items = [
        {
            "provider": row.provider,
            "slug": row.slug,
            "source_url": row.source_url,
            "license": row.license,
            "terms": row.terms,
            "expected_frequency": row.expected_frequency,
            "status": row.status,
            "source_status": row.source_status,
            "connector_status": row.connector_status,
            "verified_at": row.verified_at,
            "failure_reason": row.failure_reason,
            "external_catalog_id": row.external_catalog_id,
            "public_status": public_status(
                source_status=row.source_status,
                connector_status=row.connector_status,
            ),
            "resource": None
            if row.primary_resource is None
            else {
                "title": row.primary_resource.title,
                "format": row.primary_resource.format,
                "source_status": row.primary_resource.source_status,
                "connector_status": row.primary_resource.connector_status,
            },
        }
        for row in rows
    ]
    response = _page(limit, offset, items, db.scalar(count_statement) or 0)
    response["facets"] = {
        "areas": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Dataset.domain, func.count(func.distinct(Source.id)))
                .join(Source, Source.id == Dataset.source_id)
                .group_by(Dataset.domain)
                .order_by(Dataset.domain)
            )
        ],
        "providers": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Source.provider, func.count(Source.id))
                .group_by(Source.provider)
                .order_by(Source.provider)
            )
        ],
        "formats": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(SourceResource.format, func.count(SourceResource.id))
                .group_by(SourceResource.format)
                .order_by(SourceResource.format)
            )
        ],
        "resources": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(SourceResource.slug, func.count(Source.id))
                .join(Source, Source.primary_resource_id == SourceResource.id)
                .group_by(SourceResource.slug)
                .order_by(SourceResource.slug)
            )
        ],
        "statuses": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Source.source_status, func.count(Source.id))
                .group_by(Source.source_status)
                .order_by(Source.source_status)
            )
        ],
        "freshness": [
            {
                "value": "current",
                "count": db.scalar(
                    select(func.count(Source.id)).where(Source.verified_at >= cutoff)
                )
                or 0,
            },
            {
                "value": "stale",
                "count": db.scalar(
                    select(func.count(Source.id)).where(
                        or_(
                            Source.connector_status == "degraded",
                            and_(Source.verified_at.is_not(None), Source.verified_at < cutoff),
                        )
                    )
                )
                or 0,
            },
            {
                "value": "unknown",
                "count": db.scalar(
                    select(func.count(Source.id)).where(Source.verified_at.is_(None))
                )
                or 0,
            },
        ],
    }
    return response


@router.get("/datasets")
def datasets(
    db: DbSession,
    q: str | None = Query(None, max_length=120),
    domain: str | None = Query(None, alias="area", max_length=120),
    provider: str | None = Query(None, max_length=200),
    resource: str | None = Query(None, max_length=140),
    resource_format: str | None = Query(None, alias="format", max_length=40),
    status: str | None = Query(None, max_length=40),
    granularity: str | None = Query(None, max_length=160),
    availability: Literal["published", "not_published"] | None = None,
    license_status: str | None = Query(None, max_length=40),
    freshness: Literal["current", "stale", "unknown"] | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = (
        select(Dataset)
        .join(Source, Source.id == Dataset.source_id)
        .outerjoin(SourceResource, SourceResource.id == Dataset.source_resource_id)
    )
    count_statement = (
        select(func.count(Dataset.id))
        .join(Source, Source.id == Dataset.source_id)
        .outerjoin(SourceResource, SourceResource.id == Dataset.source_resource_id)
    )
    conditions = []
    if q and q.strip():
        term = f"%{normalize_text(q.strip())}%"
        conditions.append(
            or_(
                normalized_column(Dataset.title).like(term),
                normalized_column(Dataset.description).like(term),
            )
        )
    if domain:
        conditions.append(Dataset.domain == domain)
    if provider:
        conditions.append(normalized_column(Source.provider) == normalize_text(provider))
    if resource:
        conditions.append(SourceResource.slug == resource)
    if resource_format:
        conditions.append(SourceResource.format == resource_format)
    if status:
        conditions.append(
            or_(
                Dataset.status == status,
                Dataset.connector_status == status,
                Dataset.publication_status == status,
            )
        )
    if granularity:
        conditions.append(Dataset.granularity == granularity)
    if availability:
        conditions.append(Dataset.publication_status == availability)
    if license_status:
        conditions.append(SourceResource.license_status == license_status)
    cutoff = datetime.now(UTC) - timedelta(days=400)
    recent_snapshot = (
        select(SourceSnapshot.id)
        .where(SourceSnapshot.dataset_id == Dataset.id, SourceSnapshot.fetched_at >= cutoff)
        .limit(1)
        .exists()
    )
    any_snapshot = (
        select(SourceSnapshot.id).where(SourceSnapshot.dataset_id == Dataset.id).limit(1).exists()
    )
    if freshness == "current":
        conditions.append(recent_snapshot)
    elif freshness == "stale":
        conditions.extend([any_snapshot, ~recent_snapshot])
    elif freshness == "unknown":
        conditions.append(~any_snapshot)
    if conditions:
        statement = statement.where(*conditions)
        count_statement = count_statement.where(*conditions)
    rows = list(
        db.scalars(
            statement.options(joinedload(Dataset.source))
            .order_by(Dataset.title)
            .limit(limit)
            .offset(offset)
        )
    )
    items = [
        {
            "code": row.code,
            "title": row.title,
            "description": row.description,
            "domain": row.domain,
            "granularity": row.granularity,
            "update_policy": row.update_policy,
            "status": row.status,
            "connector_status": row.connector_status,
            "publication_status": row.publication_status,
            "external_catalog_id": row.external_catalog_id,
            "source": {"provider": row.source.provider, "url": row.source.source_url},
            "public_status": public_status(
                source_status=row.source.source_status,
                connector_status=row.connector_status,
                publication_status=row.publication_status,
            ),
        }
        for row in rows
    ]
    response = _page(limit, offset, items, db.scalar(count_statement) or 0)
    response["facets"] = {
        "areas": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Dataset.domain, func.count(Dataset.id))
                .group_by(Dataset.domain)
                .order_by(Dataset.domain)
            )
        ],
        "granularities": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Dataset.granularity, func.count(Dataset.id))
                .group_by(Dataset.granularity)
                .order_by(Dataset.granularity)
            )
        ],
        "providers": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Source.provider, func.count(Dataset.id))
                .join(Dataset, Dataset.source_id == Source.id)
                .group_by(Source.provider)
                .order_by(Source.provider)
            )
        ],
        "formats": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(SourceResource.format, func.count(Dataset.id))
                .join(Dataset, Dataset.source_resource_id == SourceResource.id)
                .group_by(SourceResource.format)
                .order_by(SourceResource.format)
            )
        ],
        "resources": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(SourceResource.slug, func.count(Dataset.id))
                .join(Dataset, Dataset.source_resource_id == SourceResource.id)
                .group_by(SourceResource.slug)
                .order_by(SourceResource.slug)
            )
        ],
        "statuses": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Dataset.publication_status, func.count(Dataset.id))
                .group_by(Dataset.publication_status)
                .order_by(Dataset.publication_status)
            )
        ],
        "freshness": [
            {
                "value": "current",
                "count": db.scalar(select(func.count(Dataset.id)).where(recent_snapshot)) or 0,
            },
            {
                "value": "stale",
                "count": db.scalar(
                    select(func.count(Dataset.id)).where(any_snapshot, ~recent_snapshot)
                )
                or 0,
            },
            {
                "value": "unknown",
                "count": db.scalar(select(func.count(Dataset.id)).where(~any_snapshot)) or 0,
            },
        ],
    }
    return response


@router.get("/indicators")
def indicators(
    db: DbSession,
    domain: str | None = Query(None, alias="area", max_length=120),
    q: str | None = Query(None, max_length=100),
    provider: str | None = Query(None, max_length=200),
    resource: str | None = Query(None, max_length=140),
    resource_format: str | None = Query(None, alias="format", max_length=40),
    status: Literal["published", "unavailable"] | None = None,
    freshness: Literal["current", "stale", "unknown"] | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = select(Indicator)
    count_statement = select(func.count(Indicator.id))
    if domain:
        statement = statement.where(Indicator.domain == domain)
        count_statement = count_statement.where(Indicator.domain == domain)
    if q:
        pattern = f"%{normalize_text(q.strip())}%"
        condition = normalized_column(Indicator.label).like(pattern)
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    related = (
        select(Observation.id)
        .join(SourceSnapshot, SourceSnapshot.id == Observation.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .outerjoin(SourceResource, SourceResource.id == Dataset.source_resource_id)
        .where(Observation.indicator_id == Indicator.id)
    )
    if provider:
        condition = related.where(
            normalized_column(Source.provider) == normalize_text(provider)
        ).exists()
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    if resource:
        condition = related.where(SourceResource.slug == resource).exists()
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    if resource_format:
        condition = related.where(SourceResource.format == resource_format).exists()
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    if status:
        published = (
            select(Observation.id).where(Observation.indicator_id == Indicator.id).limit(1).exists()
        )
        condition = published if status == "published" else ~published
        statement = statement.where(condition)
        count_statement = count_statement.where(condition)
    cutoff = datetime.now(UTC) - timedelta(days=400)
    recent = related.where(SourceSnapshot.fetched_at >= cutoff).exists()
    any_observation = related.exists()
    if freshness == "current":
        statement = statement.where(recent)
        count_statement = count_statement.where(recent)
    elif freshness == "stale":
        statement = statement.where(any_observation, ~recent)
        count_statement = count_statement.where(any_observation, ~recent)
    elif freshness == "unknown":
        statement = statement.where(~any_observation)
        count_statement = count_statement.where(~any_observation)
    rows = list(db.scalars(statement.order_by(Indicator.label).limit(limit).offset(offset)))
    response = _page(
        limit,
        offset,
        [IndicatorOut.model_validate(row).model_dump() for row in rows],
        db.scalar(count_statement) or 0,
    )
    response["facets"] = {
        "areas": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Indicator.domain, func.count(Indicator.id))
                .group_by(Indicator.domain)
                .order_by(Indicator.domain)
            )
        ],
        "providers": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(Source.provider, func.count(func.distinct(Observation.indicator_id)))
                .join(Dataset, Dataset.source_id == Source.id)
                .join(SourceSnapshot, SourceSnapshot.dataset_id == Dataset.id)
                .join(Observation, Observation.snapshot_id == SourceSnapshot.id)
                .group_by(Source.provider)
                .order_by(Source.provider)
            )
        ],
        "formats": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(SourceResource.format, func.count(func.distinct(Observation.indicator_id)))
                .join(Dataset, Dataset.source_resource_id == SourceResource.id)
                .join(SourceSnapshot, SourceSnapshot.dataset_id == Dataset.id)
                .join(Observation, Observation.snapshot_id == SourceSnapshot.id)
                .group_by(SourceResource.format)
                .order_by(SourceResource.format)
            )
        ],
        "resources": [
            {"value": value, "count": count}
            for value, count in db.execute(
                select(
                    SourceResource.slug,
                    func.count(func.distinct(Observation.indicator_id)),
                )
                .join(Dataset, Dataset.source_resource_id == SourceResource.id)
                .join(SourceSnapshot, SourceSnapshot.dataset_id == Dataset.id)
                .join(Observation, Observation.snapshot_id == SourceSnapshot.id)
                .group_by(SourceResource.slug)
                .order_by(SourceResource.slug)
            )
        ],
        "statuses": [
            {
                "value": "published",
                "count": db.scalar(select(func.count(Indicator.id)).where(any_observation)) or 0,
            },
            {
                "value": "unavailable",
                "count": db.scalar(select(func.count(Indicator.id)).where(~any_observation)) or 0,
            },
        ],
        "freshness": [
            {
                "value": "current",
                "count": db.scalar(select(func.count(Indicator.id)).where(recent)) or 0,
            },
            {
                "value": "stale",
                "count": db.scalar(select(func.count(Indicator.id)).where(any_observation, ~recent))
                or 0,
            },
            {
                "value": "unknown",
                "count": db.scalar(select(func.count(Indicator.id)).where(~any_observation)) or 0,
            },
        ],
    }
    return response


@router.get("/indicators/{code}/observations")
def observations(
    code: str,
    db: DbSession,
    from_period: Annotated[date | None, Query(alias="from")] = None,
    to_period: Annotated[date | None, Query(alias="to")] = None,
    scope: str | None = Query(None, max_length=2000),
    municipality: str = Query("3543402"),
    limit: int = Query(500, ge=1, le=2000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    indicator = db.scalar(select(Indicator).where(Indicator.code == code))
    if not indicator:
        raise HTTPException(status_code=404, detail="Indicador não encontrado")
    municipality_row = _require_municipality(db, municipality)
    if from_period and to_period and from_period > to_period:
        raise HTTPException(status_code=400, detail="O parâmetro from deve preceder to")
    requested_scope: dict[str, Any] | None = None
    if scope:
        try:
            requested_scope = json.loads(scope)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=400, detail="scope deve ser JSON válido") from exc
        if not isinstance(requested_scope, dict):
            raise HTTPException(status_code=400, detail="scope deve ser um objeto JSON")

    statement = _latest_observations_query(eager=True).where(
        Observation.indicator_id == indicator.id,
        Observation.municipality_ibge_code == municipality,
    )
    if from_period:
        statement = statement.where(Observation.period_end >= from_period)
    if to_period:
        statement = statement.where(Observation.period_start <= to_period)
    if requested_scope is not None:
        statement = statement.where(cast(Observation.scope_json, JSONB).contains(requested_scope))
    count_statement = select(func.count()).select_from(statement.order_by(None).subquery())
    total = db.scalar(count_statement) or 0
    rows = list(
        db.scalars(statement.order_by(Observation.period_start).limit(limit).offset(offset))
    )
    return {
        "indicator": IndicatorOut.model_validate(indicator).model_dump(),
        "municipality_ibge_code": municipality,
        "municipality": MunicipalityOut.model_validate(municipality_row).model_dump(),
        "items": [_observation_dict(row) for row in rows],
        "count": total,
        "limit": limit,
        "offset": offset,
    }


def _municipality_summary(db: Session, municipality_code: str) -> dict[str, Any]:
    municipality = _require_municipality(db, municipality_code)
    card_codes = [
        "population_estimated",
        "revenue_realized",
        "expense_paid",
        "cnes_establishments_without_disable_reason",
    ]
    rows = list(
        db.scalars(
            _latest_observations_query(eager=True)
            .join(Indicator, Indicator.id == Observation.indicator_id)
            .where(Observation.municipality_ibge_code == municipality_code)
            .order_by(Observation.period_end.desc())
        )
    )
    latest_by_indicator: dict[str, Observation] = {}
    for row in rows:
        latest_by_indicator.setdefault(row.indicator.code, row)
    cards = []
    for code in card_codes:
        row = latest_by_indicator.get(code)
        if row:
            cards.append(
                {
                    "indicator": IndicatorOut.model_validate(row.indicator).model_dump(),
                    **_observation_dict(row),
                }
            )
    available_indicators = [
        {
            "indicator": IndicatorOut.model_validate(row.indicator).model_dump(),
            **_observation_dict(row),
        }
        for row in latest_by_indicator.values()
    ]
    datasets_rows = list(db.scalars(select(Dataset).order_by(Dataset.domain)))
    candidate_by_area = dict(
        db.execute(
            select(CatalogEntry.area_slug, func.count(CatalogEntry.id))
            .group_by(CatalogEntry.area_slug)
            .order_by(CatalogEntry.area_slug)
        ).all()
    )
    # Publication facts live in domain-specific tables as well as in observations.
    # Counting only observations made loaded datasets (notably education and the
    # sector wave) appear as unavailable on the municipal profile.
    published_by_area = dict(
        db.execute(
            text(
                """
                SELECT published.domain, count(DISTINCT published.dataset_id)
                FROM (
                    SELECT d.domain, d.id AS dataset_id
                    FROM observations f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM school_versions f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM education_metrics f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM fiscal_statements f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM procurements f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM contracts f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM transfers f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM health_establishments f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM health_beds f
                    JOIN health_establishments establishment
                      ON establishment.id = f.establishment_id
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE establishment.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM health_services f
                    JOIN health_establishments establishment
                      ON establishment.id = f.establishment_id
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE establishment.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM health_production f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM health_epidemiology f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM economy_facts f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM labor_facts f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM social_benefit_facts f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM infrastructure_facts f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM agriculture_facts f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.municipality_ibge_code = :municipality
                    UNION ALL
                    SELECT d.domain, d.id
                    FROM geospatial_assets f
                    JOIN source_snapshots ss ON ss.id = f.snapshot_id
                    JOIN datasets d ON d.id = ss.dataset_id
                    WHERE f.geo_type = 'municipality' AND f.geo_code = :municipality
                ) AS published
                GROUP BY published.domain
                """
            ),
            {"municipality": municipality_code},
        ).all()
    )
    # Dataset domains predate the public catalog taxonomy in a few cases.
    # Present those releases in the sector users actually navigate to.
    domain_aliases = {"transparencia": "financas-publicas"}
    normalized_published: dict[str, int] = {}
    for domain, count in published_by_area.items():
        area = domain_aliases.get(domain, domain)
        normalized_published[area] = normalized_published.get(area, 0) + count
    published_by_area = normalized_published
    areas = sorted(set(candidate_by_area) | set(published_by_area))
    return {
        "municipality": MunicipalityOut.model_validate(municipality).model_dump(),
        "generated_at": datetime.now(UTC),
        "cards": cards,
        "available_indicators": available_indicators,
        "datasets": [
            {
                "code": item.code,
                "title": item.title,
                "domain": item.domain,
                "status": item.status,
                "publication_status": item.publication_status,
            }
            for item in datasets_rows
        ],
        "sectors": [
            {
                "slug": area,
                "candidate_sources": candidate_by_area.get(area, 0),
                "published_datasets": published_by_area.get(area, 0),
            }
            for area in areas
        ],
        "catalog_summary": {
            "candidate_sources": sum(candidate_by_area.values()),
            "published_datasets": sum(published_by_area.values()),
        },
        "independent_project": True,
    }


@router.get("/municipios/{ibge_code}/summary")
def municipality_summary(ibge_code: str, db: DbSession) -> dict[str, Any]:
    return _municipality_summary(db, ibge_code)


@router.get("/dashboard/summary")
def dashboard_summary(db: DbSession, municipality: str = Query("3543402")) -> dict[str, Any]:
    return _municipality_summary(db, municipality)


@router.get("/exports/observations.csv")
def export_observations(
    db: DbSession,
    indicator: str = Query(..., min_length=2, max_length=120),
    municipality: str = Query("3543402"),
) -> StreamingResponse:
    indicator_row = db.scalar(select(Indicator).where(Indicator.code == indicator))
    if not indicator_row:
        raise HTTPException(status_code=404, detail="Indicador não encontrado")
    _require_municipality(db, municipality)
    rows = list(
        db.scalars(
            _latest_observations_query(eager=True)
            .where(
                Observation.indicator_id == indicator_row.id,
                Observation.municipality_ibge_code == municipality,
            )
            .order_by(Observation.period_start)
            .limit(10_000)
        )
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "municipality_ibge_code",
            "indicator",
            "period_start",
            "period_end",
            "scope_json",
            "value",
            "unit",
            "availability_status",
            "revision",
            "retrieved_at",
            "source_url",
            "snapshot_sha256",
        ]
    )
    for row in rows:
        writer.writerow(
            [
                municipality,
                indicator_row.code,
                row.period_start.isoformat(),
                row.period_end.isoformat(),
                json.dumps(row.scope_json, ensure_ascii=False, sort_keys=True),
                "" if row.value is None else str(row.value),
                indicator_row.unit,
                row.availability_status,
                row.revision,
                row.retrieved_at.isoformat(),
                row.snapshot.url,
                row.snapshot.sha256,
            ]
        )
    filename = f"lente-brasil-{municipality}-{indicator}.csv"
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/pipelines/status")
def pipelines_status(db: DbSession) -> dict[str, Any]:
    datasets_rows = list(db.scalars(select(Dataset).order_by(Dataset.title)))
    items = []
    for dataset in datasets_rows:
        run = db.scalar(
            select(IngestionRun)
            .where(IngestionRun.dataset_id == dataset.id)
            .order_by(desc(IngestionRun.started_at))
            .limit(1)
        )
        items.append(
            {
                "dataset": dataset.code,
                "title": dataset.title,
                "catalog_status": dataset.status,
                "last_run": None
                if run is None
                else {
                    "started_at": run.started_at,
                    "finished_at": run.finished_at,
                    "status": run.status,
                    "items_received": run.items_received,
                    "items_accepted": run.items_accepted,
                    "items_rejected": run.items_rejected,
                },
            }
        )
    return {"items": items, "generated_at": datetime.now(UTC)}


@router.get("/openapi.json", include_in_schema=False)
def openapi_redirect() -> Response:
    return Response(status_code=307, headers={"Location": "/openapi.json"})
