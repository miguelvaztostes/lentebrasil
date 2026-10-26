from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import (
    Dataset,
    EducationDependency,
    EducationEnrollment,
    EducationMetric,
    EducationStage,
    Municipality,
    PublicationRelease,
    SchoolVersion,
    Source,
)

router = APIRouter(prefix="/api/v1/education", tags=["education"])
DbSession = Annotated[Session, Depends(get_db)]
METRIC_DATASETS = (
    "inep_ideb_municipal",
    "inep_saeb_municipal",
    "fnde_pnae_municipal",
)


def _published_release(db: Session, dataset_code: str) -> tuple[Dataset, PublicationRelease] | None:
    row = db.execute(
        select(Dataset, PublicationRelease)
        .join(PublicationRelease, PublicationRelease.dataset_id == Dataset.id)
        .where(Dataset.code == dataset_code, PublicationRelease.status == "published")
        .order_by(PublicationRelease.reference_end.desc(), PublicationRelease.published_at.desc())
        .limit(1)
    ).first()
    return (row[0], row[1]) if row else None


def _source(db: Session, dataset: Dataset, release: PublicationRelease) -> dict[str, Any]:
    source = db.get(Source, dataset.source_id)
    return {
        "dataset": dataset.code,
        "provider": source.provider if source else None,
        "url": source.source_url if source else None,
        "license": source.license if source else None,
        "release": release.release_key,
        "reference_start": release.reference_start,
        "reference_end": release.reference_end,
        "published_at": release.published_at,
        "provenance": release.provenance,
    }


def _published_metric_releases(
    db: Session, dataset_code: str | None = None
) -> list[tuple[Dataset, PublicationRelease]]:
    codes = (dataset_code,) if dataset_code else METRIC_DATASETS
    return [current for code in codes if (current := _published_release(db, code)) is not None]


@router.get("/schools")
def schools(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    uf: str | None = Query(None, min_length=2, max_length=2),
    network: str | None = None,
    dependency: str | None = None,
    operating_status: str | None = None,
    q: str | None = Query(None, max_length=120),
    year: int | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    current = _published_release(db, "inep_censo_escolar")
    if current is None:
        return {"items": [], "count": 0, "limit": limit, "offset": offset, "source": None}
    dataset, release = current
    statement = (
        select(SchoolVersion)
        .join(EducationDependency, EducationDependency.code == SchoolVersion.dependency_code)
        .where(SchoolVersion.release_id == release.id)
    )
    if municipality:
        statement = statement.where(SchoolVersion.municipality_ibge_code == municipality)
    if uf:
        statement = statement.where(SchoolVersion.state == uf.upper())
    if network:
        statement = statement.where(EducationDependency.network_code == network)
    if dependency:
        statement = statement.where(SchoolVersion.dependency_code == dependency)
    if operating_status:
        statement = statement.where(SchoolVersion.operating_status == operating_status)
    if year:
        statement = statement.where(SchoolVersion.census_year == year)
    if q:
        statement = statement.where(SchoolVersion.name.ilike(f"%{q.strip()}%"))
    count = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(SchoolVersion.name, SchoolVersion.school_inep_code)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "inep_code": row.school_inep_code,
                "name": row.name,
                "municipality_ibge_code": row.municipality_ibge_code,
                "state": row.state,
                "year": row.census_year,
                "dependency_code": row.dependency_code,
                "network": db.get(EducationDependency, row.dependency_code).network_code,
                "operating_status": row.operating_status,
                "location_type": row.location_type,
                "infrastructure": row.infrastructure,
            }
            for row in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "source": _source(db, dataset, release),
    }


@router.get("/schools/{inep_code}")
def school_detail(inep_code: str, db: DbSession) -> dict[str, Any]:
    if len(inep_code) != 8 or not inep_code.isdigit():
        raise HTTPException(400, "Código Inep deve ter oito dígitos")
    current = _published_release(db, "inep_censo_escolar")
    if current is None:
        raise HTTPException(404, "Nenhum release do Censo Escolar publicado")
    dataset, release = current
    row = db.scalar(
        select(SchoolVersion).where(
            SchoolVersion.release_id == release.id, SchoolVersion.school_inep_code == inep_code
        )
    )
    if row is None:
        raise HTTPException(404, "Escola não encontrada no release publicado")
    enrollment_rows = db.scalars(
        select(EducationEnrollment)
        .where(
            EducationEnrollment.release_id == release.id,
            EducationEnrollment.school_inep_code == inep_code,
        )
        .order_by(EducationEnrollment.stage_code)
    ).all()
    return {
        "inep_code": row.school_inep_code,
        "name": row.name,
        "municipality_ibge_code": row.municipality_ibge_code,
        "state": row.state,
        "year": row.census_year,
        "dependency_code": row.dependency_code,
        "operating_status": row.operating_status,
        "location_type": row.location_type,
        "infrastructure": row.infrastructure,
        "enrollments": [
            {
                "stage": item.stage_code,
                "value": item.enrollment_count,
                "availability_status": item.availability_status,
            }
            for item in enrollment_rows
        ],
        "source": _source(db, dataset, release),
    }


@router.get("/metrics")
def metrics(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    year: int | None = None,
    stage: str | None = None,
    network: str | None = None,
    indicator: str | None = None,
    dataset: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    if dataset is not None and dataset not in METRIC_DATASETS:
        raise HTTPException(400, "Dataset educacional de métricas inválido")
    currents = _published_metric_releases(db, dataset)
    if not currents:
        return {
            "items": [],
            "count": 0,
            "limit": limit,
            "offset": offset,
            "source": None,
            "sources": [],
        }
    release_datasets = {release.id: current_dataset for current_dataset, release in currents}
    statement = select(EducationMetric).where(EducationMetric.release_id.in_(release_datasets))
    for column, value in (
        (EducationMetric.municipality_ibge_code, municipality),
        (EducationMetric.reference_year, year),
        (EducationMetric.stage_code, stage),
        (EducationMetric.network_code, network),
        (EducationMetric.metric_code, indicator),
    ):
        if value is not None:
            statement = statement.where(column == value)
    count = db.scalar(select(func.count()).select_from(statement.subquery())) or 0
    rows = db.scalars(
        statement.order_by(
            EducationMetric.municipality_ibge_code,
            EducationMetric.metric_code,
            EducationMetric.network_code,
        )
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "municipality_ibge_code": row.municipality_ibge_code,
                "year": row.reference_year,
                "indicator": row.metric_code,
                "network": row.network_code,
                "stage": row.stage_code,
                "value": row.value,
                "availability_status": row.availability_status,
                "dataset": release_datasets[row.release_id].code,
            }
            for row in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "source": (_source(db, currents[0][0], currents[0][1]) if len(currents) == 1 else None),
        "sources": [_source(db, item_dataset, release) for item_dataset, release in currents],
    }


@router.get("/municipalities/{code}")
def municipality_education(code: str, db: DbSession) -> dict[str, Any]:
    if len(code) != 7 or not code.isdigit():
        raise HTTPException(400, "Código IBGE municipal deve ter sete dígitos")
    municipality = db.get(Municipality, code)
    if municipality is None:
        raise HTTPException(404, "Município não encontrado")
    censo = _published_release(db, "inep_censo_escolar")
    metric_releases = _published_metric_releases(db)
    school_count = 0
    enrollment_total = None
    enrollments_by_dependency: list[dict[str, Any]] = []
    enrollments_by_stage: list[dict[str, Any]] = []
    schools_by_dependency: list[dict[str, Any]] = []
    schools_source = None
    if censo:
        dataset, release = censo
        school_count = (
            db.scalar(
                select(func.count(SchoolVersion.id)).where(
                    SchoolVersion.release_id == release.id,
                    SchoolVersion.municipality_ibge_code == code,
                )
            )
            or 0
        )
        enrollment_total = db.scalar(
            select(func.sum(EducationEnrollment.enrollment_count)).where(
                EducationEnrollment.release_id == release.id,
                EducationEnrollment.municipality_ibge_code == code,
                EducationEnrollment.stage_code == "all_basic",
                EducationEnrollment.availability_status == "available",
            )
        )
        dependency_rows = db.execute(
            select(
                EducationDependency.code,
                EducationDependency.name,
                EducationDependency.network_code,
                func.sum(EducationEnrollment.enrollment_count),
            )
            .join(
                EducationEnrollment,
                EducationEnrollment.dependency_code == EducationDependency.code,
            )
            .where(
                EducationEnrollment.release_id == release.id,
                EducationEnrollment.municipality_ibge_code == code,
                EducationEnrollment.stage_code == "all_basic",
                EducationEnrollment.availability_status == "available",
            )
            .group_by(
                EducationDependency.code,
                EducationDependency.name,
                EducationDependency.network_code,
            )
            .order_by(EducationDependency.code)
        ).all()
        enrollments_by_dependency = [
            {
                "code": dependency_code,
                "label": dependency_name,
                "network": network_code,
                "value": value,
            }
            for dependency_code, dependency_name, network_code, value in dependency_rows
        ]
        school_rows = db.execute(
            select(
                EducationDependency.code,
                EducationDependency.name,
                EducationDependency.network_code,
                func.count(SchoolVersion.id),
            )
            .join(
                SchoolVersion,
                SchoolVersion.dependency_code == EducationDependency.code,
            )
            .where(
                SchoolVersion.release_id == release.id,
                SchoolVersion.municipality_ibge_code == code,
            )
            .group_by(
                EducationDependency.code,
                EducationDependency.name,
                EducationDependency.network_code,
            )
            .order_by(EducationDependency.code)
        ).all()
        schools_by_dependency = [
            {
                "code": dependency_code,
                "label": dependency_name,
                "network": network_code,
                "value": value,
            }
            for dependency_code, dependency_name, network_code, value in school_rows
        ]
        stage_rows = db.execute(
            select(
                EducationStage.code,
                EducationStage.name,
                EducationStage.display_order,
                func.sum(EducationEnrollment.enrollment_count),
            )
            .join(EducationEnrollment, EducationEnrollment.stage_code == EducationStage.code)
            .where(
                EducationEnrollment.release_id == release.id,
                EducationEnrollment.municipality_ibge_code == code,
                EducationEnrollment.stage_code != "all_basic",
                EducationEnrollment.availability_status == "available",
            )
            .group_by(
                EducationStage.code,
                EducationStage.name,
                EducationStage.display_order,
            )
            .order_by(EducationStage.display_order)
        ).all()
        enrollments_by_stage = [
            {"code": stage_code, "label": stage_name, "value": value}
            for stage_code, stage_name, _display_order, value in stage_rows
        ]
        schools_source = _source(db, dataset, release)
    metric_items: list[dict[str, Any]] = []
    metric_sources: dict[str, Any] = {}
    for dataset, release in metric_releases:
        rows = db.scalars(
            select(EducationMetric)
            .where(
                EducationMetric.release_id == release.id,
                EducationMetric.municipality_ibge_code == code,
            )
            .order_by(EducationMetric.metric_code, EducationMetric.network_code)
        ).all()
        metric_items.extend(
            {
                "year": row.reference_year,
                "indicator": row.metric_code,
                "network": row.network_code,
                "stage": row.stage_code,
                "value": row.value,
                "availability_status": row.availability_status,
                "dataset": dataset.code,
            }
            for row in rows
        )
        metric_sources[dataset.code] = _source(db, dataset, release)
    return {
        "municipality": {
            "ibge_code": municipality.ibge_code,
            "name": municipality.name,
            "state": municipality.state,
        },
        "school_count": school_count,
        "enrollment_total": enrollment_total,
        "schools_by_dependency": schools_by_dependency,
        "enrollments_by_dependency": enrollments_by_dependency,
        "enrollments_by_stage": enrollments_by_stage,
        "metrics": metric_items,
        "sources": {
            "schools": schools_source,
            "metrics": metric_sources.get("inep_ideb_municipal"),
            "ideb": metric_sources.get("inep_ideb_municipal"),
            "saeb": metric_sources.get("inep_saeb_municipal"),
            "fnde_pnae": metric_sources.get("fnde_pnae_municipal"),
        },
    }
