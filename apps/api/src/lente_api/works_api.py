from __future__ import annotations

import csv
import io
from datetime import date
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import Dataset, Municipality, PublicWork, Source, SourceSnapshot

router = APIRouter(prefix="/api/v1/works", tags=["public works"])
DbSession = Annotated[Session, Depends(get_db)]


def _current():
    latest = (
        select(
            PublicWork.source_system,
            PublicWork.source_key,
            func.max(PublicWork.revision).label("revision"),
        )
        .group_by(PublicWork.source_system, PublicWork.source_key)
        .subquery()
    )
    return select(PublicWork).join(
        latest,
        and_(
            PublicWork.source_system == latest.c.source_system,
            PublicWork.source_key == latest.c.source_key,
            PublicWork.revision == latest.c.revision,
        ),
    )


def _money(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _item(
    work: PublicWork,
    snapshot: SourceSnapshot,
    dataset: Dataset,
    source: Source,
) -> dict[str, Any]:
    return {
        "id": str(work.id),
        "source_key": work.source_key,
        "municipality_ibge_code": work.municipality_ibge_code,
        "state": work.state,
        "name": work.name,
        "description": work.description,
        "category": work.category,
        "status": work.status,
        "situation_detail": work.situation_detail,
        "executor": work.executor_name,
        "responsible_agency": work.responsible_agency,
        "dates": {
            "planned_start": work.planned_start,
            "planned_end": work.planned_end,
            "actual_start": work.actual_start,
            "actual_end": work.actual_end,
        },
        "amounts": {
            "estimated": _money(work.estimated_amount),
            "contracted": _money(work.contracted_amount),
            "paid": _money(work.paid_amount),
            "unit": "BRL nominal",
        },
        "physical_progress": (
            format(work.physical_progress, "f") if work.physical_progress is not None else None
        ),
        "location": {
            "latitude": format(work.latitude, "f") if work.latitude is not None else None,
            "longitude": (format(work.longitude, "f") if work.longitude is not None else None),
        },
        "source_updated_at": work.source_updated_at,
        "source": {
            "provider": source.provider,
            "dataset": dataset.code,
            "document_url": work.source_document_url,
            "retrieved_from": snapshot.url,
            "retrieved_at": snapshot.fetched_at,
            "published_at": snapshot.published_at,
            "sha256": snapshot.sha256,
            "license": source.license,
            "source_status": source.source_status,
            "connector_status": dataset.connector_status,
            "publication_status": dataset.publication_status,
        },
    }


def _query(
    *,
    municipality: str | None,
    state: str | None,
    status: str | None,
    category: str | None,
    start: date | None,
    end: date | None,
):
    statement = (
        _current()
        .join(SourceSnapshot, SourceSnapshot.id == PublicWork.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(SourceSnapshot, Dataset, Source)
    )
    if municipality:
        statement = statement.where(PublicWork.municipality_ibge_code == municipality)
    if state:
        statement = statement.where(PublicWork.state == state.upper())
    if status:
        statement = statement.where(PublicWork.status == status)
    if category:
        statement = statement.where(PublicWork.category == category)
    if start:
        statement = statement.where(
            func.coalesce(PublicWork.actual_start, PublicWork.planned_start) >= start
        )
    if end:
        statement = statement.where(
            func.coalesce(PublicWork.actual_start, PublicWork.planned_start) <= end
        )
    return statement


@router.get("")
def works(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    state: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    status: str | None = Query(None, max_length=120),
    category: str | None = Query(None, max_length=160),
    start: date | None = None,
    end: date | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = _query(
        municipality=municipality,
        state=state,
        status=status,
        category=category,
        start=start,
        end=end,
    )
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.execute(
        statement.order_by(PublicWork.source_updated_at.desc().nullslast(), PublicWork.name)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            _item(work, snapshot, dataset, source) for work, snapshot, dataset, source in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "A situação e os valores reproduzem a atualização do órgão gestor. "
            "Obra cadastrada não implica execução iniciada; valor estimado, contratado "
            "e pago são fases distintas e não são somadas entre si."
        ),
    }


@router.get("/overview")
def overview(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
) -> dict[str, Any]:
    city = db.get(Municipality, municipality)
    if city is None:
        return {
            "municipality_ibge_code": municipality,
            "coverage": "unknown_municipality",
            "items": [],
        }
    current = _current().where(PublicWork.municipality_ibge_code == municipality).subquery()
    rows = db.execute(
        select(
            current.c.status,
            func.count().label("works"),
            func.sum(current.c.estimated_amount).label("estimated"),
            func.sum(current.c.contracted_amount).label("contracted"),
            func.sum(current.c.paid_amount).label("paid"),
        ).group_by(current.c.status)
    ).all()
    return {
        "municipality": {
            "ibge_code": city.ibge_code,
            "name": city.name,
            "state": city.state,
        },
        "coverage": "available" if rows else "unavailable",
        "by_status": [
            {
                "status": status,
                "works": total,
                "estimated_amount": _money(estimated),
                "contracted_amount": _money(contracted),
                "paid_amount": _money(paid),
            }
            for status, total, estimated, contracted, paid in rows
        ],
    }


@router.get("/export.csv")
def export_csv(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    state: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    status: str | None = Query(None, max_length=120),
    category: str | None = Query(None, max_length=160),
    limit: int = Query(10_000, ge=1, le=50_000),
) -> Response:
    statement = _query(
        municipality=municipality,
        state=state,
        status=status,
        category=category,
        start=None,
        end=None,
    ).limit(limit)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "municipality_ibge_code",
            "state",
            "name",
            "category",
            "status",
            "estimated_amount",
            "contracted_amount",
            "paid_amount",
            "physical_progress",
            "source_document_url",
        ]
    )
    for work, *_ in db.execute(statement):
        writer.writerow(
            [
                work.municipality_ibge_code,
                work.state,
                work.name,
                work.category,
                work.status,
                _money(work.estimated_amount),
                _money(work.contracted_amount),
                _money(work.paid_amount),
                (
                    format(work.physical_progress, "f")
                    if work.physical_progress is not None
                    else None
                ),
                work.source_document_url,
            ]
        )
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="obras.csv"'},
    )
