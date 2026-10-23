from __future__ import annotations

import csv
import io
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import (
    Dataset,
    HealthBed,
    HealthEpidemiology,
    HealthEstablishment,
    HealthProduction,
    Indicator,
    Municipality,
    Observation,
    Source,
    SourceSnapshot,
)

router = APIRouter(prefix="/api/v1/health", tags=["health"])
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


def _require_municipality(db: Session, code: str) -> Municipality:
    municipality = db.get(Municipality, code)
    if municipality is None:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    return municipality


def _source(db: Session, snapshot_id: Any, document_url: str) -> dict[str, Any]:
    row = db.execute(
        select(SourceSnapshot, Dataset, Source)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .where(SourceSnapshot.id == snapshot_id)
    ).first()
    if row is None:
        return {"document_url": document_url}
    snapshot, dataset, source = row
    return {
        "dataset": dataset.code,
        "provider": source.provider,
        "license": source.license,
        "source_status": source.source_status,
        "connector_status": dataset.connector_status,
        "document_url": document_url,
        "retrieved_from": snapshot.url,
        "retrieved_at": snapshot.fetched_at,
        "published_at": snapshot.published_at,
        "sha256": snapshot.sha256,
    }


def _dataset_source(db: Session, code: str) -> dict[str, Any]:
    row = db.execute(
        select(Dataset, Source)
        .join(Source, Source.id == Dataset.source_id)
        .where(Dataset.code == code)
    ).first()
    if row is None:
        return {"dataset": code, "availability": "not_configured"}
    dataset, source = row
    return {
        "dataset": code,
        "provider": source.provider,
        "url": source.source_url,
        "license": source.license,
        "source_status": source.source_status,
        "connector_status": dataset.connector_status,
        "publication_status": dataset.publication_status,
    }


def _epidemiology_dict(db: Session, item: HealthEpidemiology) -> dict[str, Any]:
    return {
        "source_key": item.source_key,
        "indicator": item.indicator_code,
        "period_start": item.period_start,
        "period_end": item.period_end,
        "geography_basis": item.geography_basis,
        "category": {"code": item.category_code, "name": item.category_name},
        "age_band": item.age_band,
        "count": item.count,
        "availability_status": item.availability_status,
        "disclosure_threshold": item.disclosure_threshold,
        "source": _source(db, item.snapshot_id, item.source_document_url),
    }


@router.get("/epidemiology")
def epidemiology(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    year: int | None = Query(None, ge=1979, le=2100),
    indicator: str | None = Query(None, max_length=80),
    category: str | None = Query(None, max_length=80),
    age_band: str | None = Query(None, max_length=40),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    _require_municipality(db, municipality)
    statement = _current(HealthEpidemiology).where(
        HealthEpidemiology.municipality_ibge_code == municipality
    )
    if year is not None:
        statement = statement.where(func.extract("year", HealthEpidemiology.period_start) == year)
    if indicator is not None:
        statement = statement.where(HealthEpidemiology.indicator_code == indicator)
    if category is not None:
        statement = statement.where(HealthEpidemiology.category_code == category)
    if age_band is not None:
        statement = statement.where(HealthEpidemiology.age_band == age_band)
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = list(
        db.scalars(
            statement.order_by(
                HealthEpidemiology.period_start.desc(),
                HealthEpidemiology.category_code,
                HealthEpidemiology.age_band,
            )
            .limit(limit)
            .offset(offset)
        )
    )
    return {
        "items": [_epidemiology_dict(db, item) for item in rows],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "Eventos agregados pelo município de residência. No SIM, categorias são capítulos "
            "CID-10 e faixas etárias são publicadas separadamente; no SINASC, publica-se o total "
            "anual de nascidos vivos."
        ),
        "privacy": "Contagens de 1 a 4 são suprimidas e armazenadas como NULL.",
    }


@router.get("/establishments")
def establishments(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    facility_type: str | None = Query(None, max_length=40),
    sus_linked: bool | None = None,
    active: bool | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    _require_municipality(db, municipality)
    statement = _current(HealthEstablishment).where(
        HealthEstablishment.municipality_ibge_code == municipality
    )
    if facility_type is not None:
        statement = statement.where(HealthEstablishment.facility_type_code == facility_type)
    if sus_linked is not None:
        statement = statement.where(HealthEstablishment.sus_linked == sus_linked)
    if active is not None:
        statement = statement.where(HealthEstablishment.active == active)
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = list(
        db.scalars(statement.order_by(HealthEstablishment.name).limit(limit).offset(offset))
    )
    return {
        "items": [
            {
                "cnes_code": item.cnes_code,
                "name": item.name,
                "facility_type_code": item.facility_type_code,
                "facility_type_name": item.facility_type_name,
                "management_scope": item.management_scope,
                "sus_linked": item.sus_linked,
                "active": item.active,
                "reference_date": item.reference_date,
                "source": _source(db, item.snapshot_id, item.source_document_url),
            }
            for item in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "Cadastro CNES; não representa atendimento, qualidade ou funcionamento em tempo real."
        ),
    }


@router.get("/production")
def production(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    year: int | None = Query(None, ge=2000, le=2100),
    care_type: str | None = Query(None, max_length=60),
    facility_type: str | None = Query(None, max_length=160),
    sus_sector: str | None = Query(None, max_length=80),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    _require_municipality(db, municipality)
    statement = _current(HealthProduction).where(
        HealthProduction.municipality_ibge_code == municipality
    )
    if year is not None:
        statement = statement.where(func.extract("year", HealthProduction.period_start) == year)
    if care_type is not None:
        statement = statement.where(HealthProduction.care_type == care_type)
    if facility_type is not None:
        statement = statement.where(HealthProduction.facility_type == facility_type)
    if sus_sector is not None:
        statement = statement.where(HealthProduction.sus_sector == sus_sector)
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = list(
        db.scalars(
            statement.order_by(HealthProduction.period_start.desc()).limit(limit).offset(offset)
        )
    )
    return {
        "items": [
            {
                "period_start": item.period_start,
                "period_end": item.period_end,
                "care_type": item.care_type,
                "procedure_code": item.procedure_code,
                "procedure_name": item.procedure_name,
                "facility_type": item.facility_type,
                "sus_sector": item.sus_sector,
                "quantity": _number(item.quantity),
                "approved_amount": _number(item.approved_amount),
                "availability_status": item.availability_status,
                "source": _source(db, item.snapshot_id, item.source_document_url),
            }
            for item in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": "Produção registrada no SUS não equivale a pessoas únicas atendidas.",
    }


@router.get("/beds")
def beds(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    facility_type: str | None = Query(None, max_length=40),
    sus_linked: bool | None = None,
    active: bool | None = True,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    _require_municipality(db, municipality)
    establishments = _current(HealthEstablishment).where(
        HealthEstablishment.municipality_ibge_code == municipality
    )
    if facility_type is not None:
        establishments = establishments.where(
            HealthEstablishment.facility_type_code == facility_type
        )
    if sus_linked is not None:
        establishments = establishments.where(HealthEstablishment.sus_linked == sus_linked)
    if active is not None:
        establishments = establishments.where(HealthEstablishment.active == active)
    establishment_rows = establishments.subquery()
    bed_rows = _current(HealthBed).subquery()
    statement = (
        select(
            establishment_rows.c.cnes_code,
            establishment_rows.c.name,
            establishment_rows.c.facility_type_code,
            establishment_rows.c.facility_type_name,
            establishment_rows.c.active,
            establishment_rows.c.source_document_url,
            bed_rows.c.bed_type_code,
            bed_rows.c.bed_type_name,
            bed_rows.c.existing_count,
            bed_rows.c.sus_count,
            bed_rows.c.reference_date,
            bed_rows.c.snapshot_id,
        )
        .join(
            establishment_rows,
            establishment_rows.c.id == bed_rows.c.establishment_id,
        )
        .order_by(establishment_rows.c.name)
    )
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.execute(statement.limit(limit).offset(offset)).all()
    return {
        "items": [
            {
                "cnes_code": row.cnes_code,
                "establishment": row.name,
                "facility_type_code": row.facility_type_code,
                "facility_type_name": row.facility_type_name,
                "active": row.active,
                "bed_type_code": row.bed_type_code,
                "bed_type_name": row.bed_type_name,
                "registered_beds": row.existing_count,
                "registered_sus_beds": row.sus_count,
                "reference_date": row.reference_date,
                "source": _source(db, row.snapshot_id, row.source_document_url),
            }
            for row in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "Leitos cadastrados no CNES na competência mais recente homologada; não indicam "
            "ocupação nem disponibilidade em tempo real."
        ),
    }


def _number(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


@router.get("/overview")
def overview(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    year: int = Query(2024, ge=1979, le=2100),
) -> dict[str, Any]:
    municipality_row = _require_municipality(db, municipality)
    epidemiology_statement = _current(HealthEpidemiology).where(
        HealthEpidemiology.municipality_ibge_code == municipality,
        func.extract("year", HealthEpidemiology.period_start) == year,
    )
    epidemiology_rows = list(db.scalars(epidemiology_statement))
    total_deaths = next(
        (
            item
            for item in epidemiology_rows
            if item.indicator_code == "sim_deaths_residence"
            and item.category_code == "all"
            and item.age_band == "all"
        ),
        None,
    )
    live_births = next(
        (
            item
            for item in epidemiology_rows
            if item.indicator_code == "sinasc_live_births_residence"
        ),
        None,
    )
    causes = [
        item
        for item in epidemiology_rows
        if item.indicator_code == "sim_deaths_residence"
        and item.category_code != "all"
        and item.age_band == "all"
    ]
    ages = [
        item
        for item in epidemiology_rows
        if item.indicator_code == "sim_deaths_residence"
        and item.category_code == "all"
        and item.age_band != "all"
    ]
    establishment_statement = _current(HealthEstablishment).where(
        HealthEstablishment.municipality_ibge_code == municipality
    )
    establishments_count = (
        db.scalar(select(func.count()).select_from(establishment_statement.subquery())) or 0
    )
    aggregate_establishments = db.scalar(
        select(Observation)
        .join(Indicator, Indicator.id == Observation.indicator_id)
        .where(
            Observation.municipality_ibge_code == municipality,
            Indicator.code == "cnes_establishments_registered",
        )
        .order_by(Observation.period_end.desc(), Observation.revision.desc())
        .limit(1)
    )
    published_establishments = (
        establishments_count
        if establishments_count
        else int(aggregate_establishments.value)
        if aggregate_establishments is not None and aggregate_establishments.value is not None
        else None
    )
    current_establishments = establishment_statement.subquery()
    current_beds = _current(HealthBed).subquery()
    beds = db.execute(
        select(func.sum(current_beds.c.existing_count), func.sum(current_beds.c.sus_count))
        .select_from(current_beds)
        .join(
            current_establishments,
            current_establishments.c.id == current_beds.c.establishment_id,
        )
    ).first()
    existing_beds, sus_beds = beds if beds is not None else (None, None)
    return {
        "municipality": {
            "ibge_code": municipality_row.ibge_code,
            "name": municipality_row.name,
            "state": municipality_row.state,
        },
        "year": year,
        "network": {
            "establishments": published_establishments,
            "registered_beds": existing_beds,
            "registered_sus_beds": sus_beds,
            "availability": "available" if published_establishments is not None else "unavailable",
            "methodology": (
                "Capacidade cadastrada no CNES; não indica ocupação nem disponibilidade "
                "em tempo real."
            ),
        },
        "epidemiology": {
            "total_deaths": None if total_deaths is None else total_deaths.count,
            "live_births": None if live_births is None else live_births.count,
            "availability": (
                "available"
                if total_deaths is not None or live_births is not None
                else "unavailable"
            ),
            "causes": [
                {
                    "code": item.category_code,
                    "name": item.category_name,
                    "count": item.count,
                    "availability_status": item.availability_status,
                }
                for item in causes
            ],
            "age_bands": [
                {
                    "code": item.age_band,
                    "name": item.category_name.removeprefix("Todas as causas — "),
                    "count": item.count,
                    "availability_status": item.availability_status,
                }
                for item in ages
            ],
            "methodology": (
                "Óbitos registrados no SIM por residência; não são casos notificados "
                "nem incidência."
            ),
        },
        "production": {
            "availability": "unavailable",
            "methodology": (
                "SIA/SUS e SIH/SUS permanecem indisponíveis até homologação de recurso e schema."
            ),
        },
        "health_spending": {
            "availability": "unavailable",
            "value": None,
            "methodology": (
                "SIOPS permanece sem extração homologada; valores fiscais gerais não são "
                "reclassificados automaticamente como gasto em saúde."
            ),
        },
        "sources": [
            _dataset_source(db, "cnes_establishments"),
            _dataset_source(db, "cnes_beds_establishments"),
            _dataset_source(db, "sim_mortality_municipal"),
            _dataset_source(db, "sinasc_births_municipal"),
        ],
    }


@router.get("/exports/epidemiology.csv")
def export_epidemiology_csv(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    year: int | None = Query(None, ge=1979, le=2100),
    limit: int = Query(5000, ge=1, le=10_000),
) -> Response:
    _require_municipality(db, municipality)
    statement = _current(HealthEpidemiology).where(
        HealthEpidemiology.municipality_ibge_code == municipality
    )
    if year is not None:
        statement = statement.where(func.extract("year", HealthEpidemiology.period_start) == year)
    rows = list(
        db.scalars(
            statement.order_by(
                HealthEpidemiology.period_start,
                HealthEpidemiology.category_code,
                HealthEpidemiology.age_band,
            ).limit(limit)
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
            "geography_basis",
            "category_code",
            "category_name",
            "age_band",
            "count",
            "availability_status",
            "disclosure_threshold",
            "source_url",
            "snapshot_sha256",
            "retrieved_at",
            "license_status",
        ]
    )
    for item in rows:
        source = _source(db, item.snapshot_id, item.source_document_url)
        writer.writerow(
            [
                municipality,
                item.indicator_code,
                item.period_start,
                item.period_end,
                item.geography_basis,
                item.category_code,
                item.category_name,
                item.age_band,
                "" if item.count is None else item.count,
                item.availability_status,
                item.disclosure_threshold,
                source.get("document_url"),
                source.get("sha256"),
                source.get("retrieved_at"),
                source.get("license"),
            ]
        )
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": (f'attachment; filename="lente-brasil-saude-{municipality}.csv"')
        },
    )
