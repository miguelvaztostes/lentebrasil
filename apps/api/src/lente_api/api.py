from __future__ import annotations

import csv
import io
import json
from datetime import UTC, date, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import and_, cast, desc, func, select, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from lente_api.database import get_db
from lente_api.models import (
    Dataset,
    Indicator,
    IngestionRun,
    Municipality,
    Observation,
    Source,
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
        pattern = f"%{q.strip()}%"
        statement = statement.where(Municipality.name.ilike(pattern))
        count_statement = count_statement.where(Municipality.name.ilike(pattern))
    rows = list(db.scalars(statement.order_by(Municipality.name).limit(limit).offset(offset)))
    return _page(
        limit,
        offset,
        [MunicipalityOut.model_validate(row).model_dump() for row in rows],
        db.scalar(count_statement) or 0,
    )


@router.get("/sources")
def sources(
    db: DbSession,
    status: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = select(Source)
    count_statement = select(func.count(Source.id))
    if status:
        statement = statement.where((Source.status == status) | (Source.source_status == status))
        count_statement = count_statement.where(
            (Source.status == status) | (Source.source_status == status)
        )
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
    return _page(limit, offset, items, db.scalar(count_statement) or 0)


@router.get("/datasets")
def datasets(
    db: DbSession,
    domain: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = select(Dataset)
    count_statement = select(func.count(Dataset.id))
    if domain:
        statement = statement.where(Dataset.domain == domain)
        count_statement = count_statement.where(Dataset.domain == domain)
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
        }
        for row in rows
    ]
    return _page(limit, offset, items, db.scalar(count_statement) or 0)


@router.get("/indicators")
def indicators(
    db: DbSession,
    domain: str | None = None,
    q: str | None = Query(None, max_length=100),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = select(Indicator)
    count_statement = select(func.count(Indicator.id))
    if domain:
        statement = statement.where(Indicator.domain == domain)
        count_statement = count_statement.where(Indicator.domain == domain)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(Indicator.label.ilike(pattern))
        count_statement = count_statement.where(Indicator.label.ilike(pattern))
    rows = list(db.scalars(statement.order_by(Indicator.label).limit(limit).offset(offset)))
    return _page(
        limit,
        offset,
        [IndicatorOut.model_validate(row).model_dump() for row in rows],
        db.scalar(count_statement) or 0,
    )


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
            .where(
                Observation.municipality_ibge_code == municipality_code,
                Indicator.code.in_(card_codes),
            )
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
    datasets_rows = list(db.scalars(select(Dataset).order_by(Dataset.domain)))
    return {
        "municipality": MunicipalityOut.model_validate(municipality).model_dump(),
        "generated_at": datetime.now(UTC),
        "cards": cards,
        "datasets": [
            {"code": item.code, "title": item.title, "domain": item.domain, "status": item.status}
            for item in datasets_rows
        ],
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
