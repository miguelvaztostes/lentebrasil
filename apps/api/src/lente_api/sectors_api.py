from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import (
    CatalogEntry,
    Dataset,
    EconomicActivity,
    EconomyFact,
    InfrastructureFact,
    InfrastructureService,
    LaborFact,
    Municipality,
    Source,
    SourceSnapshot,
)

router = APIRouter(prefix="/api/v1/sectors", tags=["sectors"])
DbSession = Annotated[Session, Depends(get_db)]


def _latest(model: Any):
    return (
        select(model.source_system, model.source_key, func.max(model.revision).label("revision"))
        .group_by(model.source_system, model.source_key)
        .subquery()
    )


def _current(model: Any):
    latest = _latest(model)
    return select(model).join(
        latest,
        and_(
            model.source_system == latest.c.source_system,
            model.source_key == latest.c.source_key,
            model.revision == latest.c.revision,
        ),
    )


def _page(db: Session, statement: Any, limit: int, offset: int) -> tuple[list[Any], int]:
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    return list(db.execute(statement.offset(offset).limit(limit)).all()), count


def _source(snapshot: SourceSnapshot, dataset: Dataset, source: Source) -> dict[str, Any]:
    return {
        "dataset": dataset.code,
        "provider": source.provider,
        "url": snapshot.url,
        "document_url": source.source_url,
        "license": source.license,
        "retrieved_at": snapshot.fetched_at,
        "published_at": snapshot.published_at,
        "sha256": snapshot.sha256,
        "source_status": source.source_status,
        "connector_status": dataset.connector_status,
        "publication_status": dataset.publication_status,
    }


def _filters(statement: Any, model: Any, municipality: str | None, uf: str | None):
    if municipality:
        statement = statement.where(model.municipality_ibge_code == municipality)
    if uf:
        statement = statement.join(
            Municipality, Municipality.ibge_code == model.municipality_ibge_code
        ).where(Municipality.state == uf.upper())
    return statement


@router.get("/economy")
def economy(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    uf: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    start_year: int | None = Query(None, ge=2000, le=2100),
    end_year: int | None = Query(None, ge=2000, le=2100),
    metric: str | None = None,
    activity: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = (
        _current(EconomyFact)
        .join(SourceSnapshot, SourceSnapshot.id == EconomyFact.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .outerjoin(EconomicActivity, EconomicActivity.id == EconomyFact.activity_id)
        .add_columns(EconomicActivity.code, EconomicActivity.label, SourceSnapshot, Dataset, Source)
    )
    statement = _filters(statement, EconomyFact, municipality, uf)
    if start_year is not None:
        statement = statement.where(EconomyFact.reference_year >= start_year)
    if end_year is not None:
        statement = statement.where(EconomyFact.reference_year <= end_year)
    if metric:
        statement = statement.where(EconomyFact.metric_code == metric)
    if activity:
        statement = statement.where(EconomicActivity.code == activity)
    rows, count = _page(
        db,
        statement.order_by(
            EconomyFact.reference_year.desc(),
            EconomyFact.municipality_ibge_code,
            EconomicActivity.code,
        ),
        limit,
        offset,
    )
    return {
        "items": [
            {
                "municipality_ibge_code": fact.municipality_ibge_code,
                "year": fact.reference_year,
                "metric": fact.metric_code,
                "activity": {"code": code, "label": label} if code else None,
                "value": format(fact.value, "f") if fact.value is not None else None,
                "unit": fact.unit,
                "price_basis": fact.price_basis,
                "availability_status": fact.availability_status,
                "source": _source(snapshot, dataset, source),
            }
            for fact, code, label, snapshot, dataset, source in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "PIB e VAB anuais a preços correntes. Valores nominais não são "
            "corrigidos pela inflação e não representam série mensal."
        ),
    }


@router.get("/labor")
def labor(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    uf: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    start: date | None = None,
    end: date | None = None,
    section: str | None = Query(None, max_length=2),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = (
        _current(LaborFact)
        .join(EconomicActivity, EconomicActivity.id == LaborFact.activity_id)
        .join(SourceSnapshot, SourceSnapshot.id == LaborFact.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(EconomicActivity.code, EconomicActivity.label, SourceSnapshot, Dataset, Source)
    )
    statement = _filters(statement, LaborFact, municipality, uf)
    if start:
        statement = statement.where(LaborFact.period_start >= start)
    if end:
        statement = statement.where(LaborFact.period_end <= end)
    if section:
        statement = statement.where(EconomicActivity.code == section.upper())
    rows, count = _page(
        db,
        statement.order_by(
            LaborFact.period_start.desc(), LaborFact.municipality_ibge_code, EconomicActivity.code
        ),
        limit,
        offset,
    )
    return {
        "items": [
            {
                "municipality_ibge_code": fact.municipality_ibge_code,
                "period_start": fact.period_start,
                "period_end": fact.period_end,
                "section": {"code": code, "label": label},
                "admissions": fact.admissions,
                "dismissals": fact.dismissals,
                "balance": fact.balance,
                "availability_status": fact.availability_status,
                "source": _source(snapshot, dataset, source),
            }
            for fact, code, label, snapshot, dataset, source in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "Fluxo mensal do Novo CAGED: saldo = admissões − desligamentos. "
            "Não representa estoque de empregos nem informalidade."
        ),
    }


@router.get("/infrastructure")
def infrastructure(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    uf: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    service_type: str | None = None,
    metric: str | None = None,
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = (
        _current(InfrastructureFact)
        .join(InfrastructureService, InfrastructureService.id == InfrastructureFact.service_id)
        .join(SourceSnapshot, SourceSnapshot.id == InfrastructureFact.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(
            InfrastructureService.code,
            InfrastructureService.label,
            InfrastructureService.service_type,
            SourceSnapshot,
            Dataset,
            Source,
        )
    )
    statement = _filters(statement, InfrastructureFact, municipality, uf)
    if service_type:
        statement = statement.where(InfrastructureService.service_type == service_type)
    if metric:
        statement = statement.where(InfrastructureFact.metric_code == metric)
    rows, count = _page(
        db,
        statement.order_by(
            InfrastructureFact.reference_date.desc(),
            InfrastructureFact.municipality_ibge_code,
            InfrastructureService.code,
        ),
        limit,
        offset,
    )
    return {
        "items": [
            {
                "municipality_ibge_code": fact.municipality_ibge_code,
                "reference_date": fact.reference_date,
                "service": {"code": code, "label": label, "type": kind},
                "metric": fact.metric_code,
                "value": format(fact.value, "f") if fact.value is not None else None,
                "unit": fact.unit,
                "availability_status": fact.availability_status,
                "source": _source(snapshot, dataset, source),
            }
            for fact, code, label, kind, snapshot, dataset, source in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "A frota corresponde a veículos registrados no município, "
            "não a veículos em circulação local."
        ),
    }


@router.get("/overview")
def overview(municipality: str, db: DbSession) -> dict[str, Any]:
    city = db.get(Municipality, municipality)
    if city is None:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    economy_data = economy(
        db,
        municipality=municipality,
        uf=None,
        start_year=None,
        end_year=None,
        metric=None,
        activity=None,
        limit=1000,
        offset=0,
    )
    labor_data = labor(
        db,
        municipality=municipality,
        uf=None,
        start=None,
        end=None,
        section=None,
        limit=1000,
        offset=0,
    )
    infrastructure_data = infrastructure(
        db, municipality=municipality, uf=None, service_type=None, metric=None, limit=1000, offset=0
    )
    social_entries = list(
        db.scalars(
            select(CatalogEntry).where(
                CatalogEntry.external_catalog_id.in_(["LNT-0043", "LNT-0044"])
            )
        )
    )
    return {
        "municipality": {"ibge_code": city.ibge_code, "name": city.name, "state": city.state},
        "economy": economy_data,
        "labor": labor_data,
        "infrastructure": infrastructure_data,
        "social": {
            "availability": "unavailable",
            "items": [],
            "reason": (
                "CGU exige token autorizado; CECAD não oferece neste momento "
                "um artefato versionado/API estável homologado."
            ),
            "catalog_sources": [
                {
                    "id": item.external_catalog_id,
                    "title": item.raw_record.get("nome", item.indicator_ref),
                    "status": item.provider.source_status,
                }
                for item in social_entries
            ],
        },
        "notice": (
            "Ausência de publicação é indisponível, nunca zero. Séries anuais de PIB "
            "não são convertidas em mensais nem comparadas como se fossem fluxo CAGED."
        ),
    }


@router.get("/exports/{domain}.csv")
def export_csv(
    domain: Literal["economy", "labor", "infrastructure"],
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    uf: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
) -> Response:
    if domain == "economy":
        payload = economy(
            db,
            municipality=municipality,
            uf=uf,
            start_year=None,
            end_year=None,
            metric=None,
            activity=None,
            limit=10_000,
            offset=0,
        )
    elif domain == "labor":
        payload = labor(
            db,
            municipality=municipality,
            uf=uf,
            start=None,
            end=None,
            section=None,
            limit=10_000,
            offset=0,
        )
    else:
        payload = infrastructure(
            db,
            municipality=municipality,
            uf=uf,
            service_type=None,
            metric=None,
            limit=10_000,
            offset=0,
        )
    output = io.StringIO()
    items = payload["items"]
    if items:
        keys = [
            key for key in items[0] if key not in {"source", "activity", "section", "service"}
        ] + ["category_code", "category_label", "source_url", "source_sha256"]
        writer = csv.DictWriter(output, fieldnames=keys)
        writer.writeheader()
        for item in items:
            category = item.get("activity") or item.get("section") or item.get("service") or {}
            writer.writerow(
                {
                    **{
                        key: item.get(key)
                        for key in keys
                        if key
                        not in {"category_code", "category_label", "source_url", "source_sha256"}
                    },
                    "category_code": category.get("code"),
                    "category_label": category.get("label"),
                    "source_url": item["source"]["url"],
                    "source_sha256": item["source"]["sha256"],
                }
            )
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="lente-{domain}.csv"'},
    )
