from __future__ import annotations

import csv
import io
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import (
    AgricultureFact,
    CatalogEntry,
    Dataset,
    GeospatialAsset,
    Municipality,
    Source,
    SourceSnapshot,
)

router = APIRouter(prefix="/api/v1", tags=["horizontal"])
DbSession = Annotated[Session, Depends(get_db)]


def _latest(model: Any):
    return (
        select(model.source_system, model.source_key, func.max(model.revision).label("revision"))
        .group_by(model.source_system, model.source_key)
        .subquery()
    )


def _matrix_item(entry: CatalogEntry) -> dict[str, Any]:
    raw = entry.raw_record
    dataset = entry.dataset
    return {
        "id": entry.external_catalog_id,
        "area": entry.area_slug,
        "provider": entry.provider.name,
        "title": raw.get("nome", entry.indicator_ref),
        "resource_url": raw.get("api") or raw.get("download") or raw.get("evidencia"),
        "resource_type": raw.get("modalidade"),
        "format": raw.get("formatos"),
        "authentication": raw.get("auth"),
        "geography": raw.get("geografia"),
        "priority": raw.get("prioridade"),
        "review_status": entry.review_status,
        "technical_owner": entry.technical_owner,
        "last_checked_at": entry.last_checked_at,
        "blocking_reason": entry.decision_reason,
        "dataset": dataset.code if dataset else None,
        "publication_status": dataset.publication_status if dataset else "not_published",
        "connector_status": dataset.connector_status if dataset else "not_implemented",
    }


def _matrix_statement(area: str | None, review_status: str | None):
    statement = select(CatalogEntry).order_by(CatalogEntry.external_catalog_id)
    if area:
        statement = statement.where(CatalogEntry.area_slug == area)
    if review_status:
        statement = statement.where(CatalogEntry.review_status == review_status)
    return statement


@router.get("/catalog/matrix")
def inventory_matrix(
    db: DbSession,
    area: str | None = Query(None, max_length=120),
    review_status: str | None = Query(None, max_length=40),
    limit: int = Query(200, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = _matrix_statement(area, review_status)
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    entries = list(db.scalars(statement.offset(offset).limit(limit)))
    status_counts = dict(
        db.execute(
            select(CatalogEntry.review_status, func.count(CatalogEntry.id)).group_by(
                CatalogEntry.review_status
            )
        ).all()
    )
    area_counts = dict(
        db.execute(
            select(CatalogEntry.area_slug, func.count(CatalogEntry.id)).group_by(
                CatalogEntry.area_slug
            )
        ).all()
    )
    return {
        "items": [_matrix_item(item) for item in entries],
        "count": count,
        "limit": limit,
        "offset": offset,
        "summary": {
            "inventory_records": sum(status_counts.values()),
            "areas": len(area_counts),
            "indicators": len(
                {
                    ref.get("indicator")
                    for entry in db.scalars(select(CatalogEntry))
                    for ref in entry.indicator_refs
                    if ref.get("indicator")
                }
            ),
            "by_status": status_counts,
            "by_area": area_counts,
        },
    }


@router.get("/catalog/matrix.csv")
def inventory_matrix_csv(db: DbSession) -> Response:
    items = [_matrix_item(item) for item in db.scalars(_matrix_statement(None, None))]
    output = io.StringIO()
    if items:
        writer = csv.DictWriter(output, fieldnames=list(items[0]))
        writer.writeheader()
        writer.writerows(items)
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="lente-inventory-matrix.csv"'},
    )


@router.get("/sectors/agriculture")
def agriculture(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    uf: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    start_year: int | None = Query(None, ge=1974, le=2100),
    end_year: int | None = Query(None, ge=1974, le=2100),
    product: str | None = Query(None, max_length=40),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    latest = _latest(AgricultureFact)
    statement = (
        select(AgricultureFact)
        .join(
            latest,
            and_(
                AgricultureFact.source_system == latest.c.source_system,
                AgricultureFact.source_key == latest.c.source_key,
                AgricultureFact.revision == latest.c.revision,
            ),
        )
        .join(SourceSnapshot, SourceSnapshot.id == AgricultureFact.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(SourceSnapshot, Dataset, Source)
    )
    if municipality:
        statement = statement.where(AgricultureFact.municipality_ibge_code == municipality)
    if uf:
        statement = statement.join(
            Municipality, Municipality.ibge_code == AgricultureFact.municipality_ibge_code
        ).where(Municipality.state == uf.upper())
    if start_year is not None:
        statement = statement.where(AgricultureFact.reference_year >= start_year)
    if end_year is not None:
        statement = statement.where(AgricultureFact.reference_year <= end_year)
    if product:
        statement = statement.where(AgricultureFact.product_code == product)
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.execute(
        statement.order_by(
            AgricultureFact.reference_year.desc(),
            AgricultureFact.municipality_ibge_code,
            AgricultureFact.product_name,
        )
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [
            {
                "municipality_ibge_code": fact.municipality_ibge_code,
                "year": fact.reference_year,
                "product": {"code": fact.product_code, "name": fact.product_name},
                "metric": fact.metric_code,
                "value": format(fact.value, "f") if fact.value is not None else None,
                "unit": fact.unit,
                "availability_status": fact.availability_status,
                "source": {
                    "dataset": dataset.code,
                    "provider": source.provider,
                    "url": snapshot.url,
                    "license": source.license,
                    "sha256": snapshot.sha256,
                    "retrieved_at": snapshot.fetched_at,
                    "publication_status": dataset.publication_status,
                },
            }
            for fact, snapshot, dataset, source in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "Quantidade produzida da PAM/SIDRA 5457. Ausência ou sigilo permanece nulo; "
            "período é ano civil da pesquisa e não estimativa mensal."
        ),
    }


@router.get("/geo/boundaries/{municipality_code}")
def municipality_boundary(municipality_code: str, db: DbSession) -> dict[str, Any]:
    if not municipality_code.isdigit() or len(municipality_code) != 7:
        raise HTTPException(status_code=400, detail="Código IBGE inválido")
    latest = _latest(GeospatialAsset)
    row = db.execute(
        select(GeospatialAsset, SourceSnapshot, Dataset, Source)
        .join(
            latest,
            and_(
                GeospatialAsset.source_system == latest.c.source_system,
                GeospatialAsset.source_key == latest.c.source_key,
                GeospatialAsset.revision == latest.c.revision,
            ),
        )
        .join(SourceSnapshot, SourceSnapshot.id == GeospatialAsset.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .where(
            GeospatialAsset.geo_type == "municipality",
            GeospatialAsset.geo_code == municipality_code,
        )
    ).one_or_none()
    if row is None:
        raise HTTPException(status_code=404, detail="Malha municipal não publicada")
    asset, snapshot, dataset, source = row
    return {
        "type": "Feature",
        "geometry": asset.geometry,
        "bbox": asset.bbox,
        "properties": {
            "municipality_ibge_code": asset.geo_code,
            "reference_date": asset.reference_date,
            "crs": asset.crs,
            "quality": "minima",
            "source_url": snapshot.url,
            "source_sha256": snapshot.sha256,
            "license": source.license,
            "dataset": dataset.code,
        },
    }
