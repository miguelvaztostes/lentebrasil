from __future__ import annotations

import hashlib
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import ExportJob
from lente_api.settings import get_settings

router = APIRouter(prefix="/api/v1/export-jobs", tags=["exports"])
DbSession = Annotated[Session, Depends(get_db)]

REVIEW_STATUSES = {
    "validated_and_published",
    "integrated_not_published",
    "under_review",
    "restricted",
    "portal_only",
    "unavailable",
}
DOMAIN_FILTERS = {
    "observations": {"municipality", "uf", "indicator", "start_year", "end_year"},
    "economy": {"municipality", "uf", "metric", "start_year", "end_year"},
    "labor": {"municipality", "uf", "section", "start_year", "end_year"},
    "infrastructure": {
        "municipality",
        "uf",
        "metric",
        "service_type",
        "start_year",
        "end_year",
    },
    "agriculture": {
        "municipality",
        "uf",
        "metric",
        "product",
        "start_year",
        "end_year",
    },
    "catalog": {"area", "review_status"},
}


class ExportFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    municipality: str | None = None
    uf: str | None = None
    indicator: str | None = Field(None, max_length=120)
    metric: str | None = Field(None, max_length=100)
    section: str | None = Field(None, max_length=2)
    service_type: str | None = Field(None, max_length=60)
    product: str | None = Field(None, max_length=40)
    area: str | None = Field(None, max_length=120)
    review_status: str | None = Field(None, max_length=40)
    start_year: int | None = Field(None, ge=1900, le=2100)
    end_year: int | None = Field(None, ge=1900, le=2100)

    @field_validator("municipality")
    @classmethod
    def validate_municipality(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"\d{7}", value):
            raise ValueError("municipality deve ser código IBGE de 7 dígitos")
        return value

    @field_validator("uf")
    @classmethod
    def validate_uf(cls, value: str | None) -> str | None:
        if value is not None and not re.fullmatch(r"[A-Za-z]{2}", value):
            raise ValueError("uf deve ter duas letras")
        return value.upper() if value else None

    @field_validator("review_status")
    @classmethod
    def validate_review_status(cls, value: str | None) -> str | None:
        if value is not None and value not in REVIEW_STATUSES:
            raise ValueError("review_status inválido")
        return value


class ExportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    domain: Literal["observations", "economy", "labor", "infrastructure", "agriculture", "catalog"]
    format: Literal["csv", "parquet"] = "csv"
    filters: ExportFilters = Field(default_factory=ExportFilters)
    row_limit: int = Field(100_000, ge=10_001, le=250_000)


def _requester_hash(request: Request) -> str:
    explicit = request.headers.get("x-client-id", "").strip()
    identity = explicit if re.fullmatch(r"[A-Za-z0-9._:-]{8,100}", explicit) else ""
    if not identity:
        identity = request.client.host if request.client else "anonymous"
    return hashlib.sha256(f"lente-export-v1:{identity}".encode()).hexdigest()


def _serialize(job: ExportJob) -> dict[str, object]:
    return {
        "id": str(job.id),
        "domain": job.domain,
        "format": job.format,
        "filters": job.filters,
        "status": job.status,
        "row_limit": job.row_limit,
        "row_count": job.row_count,
        "byte_count": job.byte_count,
        "sha256": job.sha256,
        "created_at": job.created_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "expires_at": job.expires_at,
        "error": job.error_details if job.status == "failed" else None,
        "download_url": f"/api/v1/export-jobs/{job.id}/download"
        if job.status == "completed"
        else None,
    }


@router.post("", status_code=status.HTTP_202_ACCEPTED)
def create_export_job(payload: ExportRequest, request: Request, db: DbSession) -> dict[str, object]:
    settings = get_settings()
    requester = _requester_hash(request)
    now = datetime.now(UTC)
    active = (
        db.scalar(
            select(func.count(ExportJob.id)).where(
                ExportJob.requester_hash == requester,
                ExportJob.status.in_(["pending", "running"]),
            )
        )
        or 0
    )
    recent = (
        db.scalar(
            select(func.count(ExportJob.id)).where(
                ExportJob.requester_hash == requester,
                ExportJob.created_at >= now - timedelta(hours=1),
            )
        )
        or 0
    )
    if active >= settings.export_active_quota or recent >= settings.export_hourly_quota:
        raise HTTPException(status_code=429, detail="Quota de exportação temporariamente excedida")
    filters = payload.filters.model_dump(exclude_none=True)
    unsupported = sorted(set(filters) - DOMAIN_FILTERS[payload.domain])
    if unsupported:
        raise HTTPException(
            status_code=422,
            detail=f"Filtros incompatíveis com {payload.domain}: {', '.join(unsupported)}",
        )
    if (
        filters.get("start_year") is not None
        and filters.get("end_year") is not None
        and filters["start_year"] > filters["end_year"]
    ):
        raise HTTPException(status_code=422, detail="start_year deve ser menor ou igual a end_year")
    job = ExportJob(
        id=uuid.uuid4(),
        requester_hash=requester,
        domain=payload.domain,
        format=payload.format,
        filters=filters,
        status="pending",
        row_limit=payload.row_limit,
        created_at=now,
        expires_at=now + timedelta(hours=settings.export_ttl_hours),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return _serialize(job)


def _owned_job(job_id: uuid.UUID, request: Request, db: Session) -> ExportJob:
    job = db.get(ExportJob, job_id)
    if job is None or job.requester_hash != _requester_hash(request):
        raise HTTPException(status_code=404, detail="Exportação não encontrada")
    return job


@router.get("/{job_id}")
def get_export_job(job_id: uuid.UUID, request: Request, db: DbSession) -> dict[str, object]:
    return _serialize(_owned_job(job_id, request, db))


@router.get("/{job_id}/download")
def download_export(job_id: uuid.UUID, request: Request, db: DbSession) -> FileResponse:
    job = _owned_job(job_id, request, db)
    now = datetime.now(UTC)
    if job.expires_at <= now:
        raise HTTPException(status_code=410, detail="Exportação expirada")
    if job.status != "completed" or not job.storage_path:
        raise HTTPException(status_code=409, detail="Exportação ainda não está disponível")
    root = (get_settings().raw_data_dir / "exports").resolve()
    path = Path(job.storage_path).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=410, detail="Artefato de exportação indisponível")
    media = "text/csv; charset=utf-8" if job.format == "csv" else "application/vnd.apache.parquet"
    return FileResponse(
        path, media_type=media, filename=f"lente-{job.domain}-{job.id}.{job.format}"
    )
