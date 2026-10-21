from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ingestion.factory import build_adapter
from lente_api.models import Dataset, IngestionJob


def job_key(source: str, parameters: dict[str, Any]) -> str:
    canonical = json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()[:20]
    return f"{source}:{digest}"


def schedule_job(
    db: Session,
    source: str,
    parameters: dict[str, Any],
    *,
    scheduled_for: datetime | None = None,
    max_attempts: int = 3,
) -> IngestionJob:
    dataset_code = {
        "ibge": "ibge_population",
        "siconfi": "siconfi_rreo",
        "cnes": "cnes_establishments",
    }.get(source)
    if dataset_code is None:
        raise ValueError(f"Fonte desconhecida: {source}")
    dataset = db.scalar(select(Dataset).where(Dataset.code == dataset_code))
    if dataset is None:
        raise ValueError(f"Dataset ausente: {dataset_code}")
    normalized = {"source": source, **parameters}
    key = job_key(source, normalized)
    existing = db.scalar(select(IngestionJob).where(IngestionJob.job_key == key))
    now = datetime.now(UTC)
    if existing is not None:
        if existing.status in {"success", "failed"} and parameters.get("recurring_seconds"):
            existing.status = "pending"
            existing.scheduled_for = scheduled_for or now
            existing.updated_at = now
        db.commit()
        return existing
    job = IngestionJob(
        id=uuid.uuid4(),
        job_key=key,
        dataset_id=dataset.id,
        parameters=normalized,
        checkpoint={},
        status="pending",
        scheduled_for=scheduled_for or now,
        attempts=0,
        max_attempts=max_attempts,
        created_at=now,
        updated_at=now,
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def claim_next_job(db: Session, *, stale_after_seconds: int = 3600) -> IngestionJob | None:
    now = datetime.now(UTC)
    stale_before = now - timedelta(seconds=stale_after_seconds)
    stale = list(
        db.scalars(
            select(IngestionJob)
            .where(IngestionJob.status == "running", IngestionJob.locked_at < stale_before)
            .with_for_update(skip_locked=True)
        )
    )
    for job in stale:
        job.status = "retry" if job.attempts < job.max_attempts else "failed"
        job.locked_at = None
        job.lock_token = None
        job.last_error = "Execução anterior perdeu o lock; retomada segura agendada."
        job.scheduled_for = now
        job.updated_at = now
    job = db.scalar(
        select(IngestionJob)
        .where(
            IngestionJob.status.in_(["pending", "retry"]),
            IngestionJob.scheduled_for <= now,
            or_(IngestionJob.locked_at.is_(None), IngestionJob.locked_at < stale_before),
        )
        .order_by(IngestionJob.scheduled_for, IngestionJob.created_at)
        .with_for_update(skip_locked=True)
        .limit(1)
    )
    if job is None:
        db.commit()
        return None
    job.status = "running"
    job.started_at = now
    job.locked_at = now
    job.lock_token = uuid.uuid4()
    job.attempts += 1
    job.updated_at = now
    db.commit()
    db.refresh(job)
    return job


def execute_job(db: Session, job: IngestionJob, *, raw_data_dir: Path) -> dict[str, Any]:
    parameters = dict(job.parameters)
    source = parameters.pop("source")
    recurring_seconds = parameters.pop("recurring_seconds", None)
    dry_run = bool(parameters.pop("dry_run", False))
    adapter = build_adapter(source, db, raw_data_dir=raw_data_dir, **parameters)
    try:
        summary = adapter.run(db, dry_run=dry_run)
        now = datetime.now(UTC)
        job = db.get(IngestionJob, job.id)
        assert job is not None
        job.checkpoint = {
            "checksum": summary.checksum,
            "items_received": summary.items_received,
            "items_accepted": summary.items_accepted,
            "finished_at": now.isoformat(),
        }
        job.finished_at = now
        job.last_success_at = now
        job.last_error = None
        job.locked_at = None
        job.lock_token = None
        if recurring_seconds:
            job.status = "pending"
            job.scheduled_for = now + timedelta(seconds=max(3600, int(recurring_seconds)))
        else:
            job.status = "success"
        job.updated_at = now
        db.commit()
        return {"job_key": job.job_key, "status": "success", **job.checkpoint}
    except Exception as exc:
        db.rollback()
        now = datetime.now(UTC)
        job = db.get(IngestionJob, job.id)
        assert job is not None
        job.finished_at = now
        job.last_error = str(exc)[:2000]
        job.locked_at = None
        job.lock_token = None
        if job.attempts < job.max_attempts:
            job.status = "retry"
            job.scheduled_for = now + timedelta(seconds=min(3600, 2**job.attempts * 30))
        else:
            job.status = "failed"
        job.updated_at = now
        db.commit()
        raise
