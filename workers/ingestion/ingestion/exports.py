from __future__ import annotations

import csv
import hashlib
import uuid
from collections.abc import Iterable, Iterator
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

import duckdb
from lente_api.models import (
    AgricultureFact,
    CatalogEntry,
    Dataset,
    EconomicActivity,
    EconomyFact,
    ExportJob,
    Indicator,
    InfrastructureFact,
    InfrastructureService,
    LaborFact,
    Municipality,
    Observation,
    Source,
    SourceSnapshot,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

MAX_EXPORT_ROWS = 250_000
STALE_AFTER = timedelta(minutes=30)


def claim_export_job(db: Session) -> ExportJob | None:
    now = datetime.now(UTC)
    stale_before = now - STALE_AFTER
    stale = list(
        db.scalars(
            select(ExportJob)
            .where(ExportJob.status == "running", ExportJob.locked_at < stale_before)
            .with_for_update(skip_locked=True)
        )
    )
    for item in stale:
        item.status = "pending"
        item.locked_at = None
        item.lock_token = None
        item.error_details = "Job recuperado após lock expirado."
    job = db.scalar(
        select(ExportJob)
        .where(
            ExportJob.status == "pending",
            ExportJob.expires_at > now,
            or_(ExportJob.locked_at.is_(None), ExportJob.locked_at < stale_before),
        )
        .order_by(ExportJob.created_at)
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
    db.commit()
    db.refresh(job)
    return job


def execute_export_job(
    db: Session, job: ExportJob, *, raw_data_dir: Path
) -> dict[str, Any]:
    root = (raw_data_dir / "exports").resolve()
    root.mkdir(parents=True, exist_ok=True)
    suffix = "csv" if job.format == "csv" else "parquet"
    output = (root / f"{job.id}.{suffix}").resolve()
    if root not in output.parents:
        raise RuntimeError("Caminho de exportação inválido")
    temp_csv = output if job.format == "csv" else root / f"{job.id}.stage.csv"
    try:
        headers, rows = export_rows(db, job.domain, job.filters, job.row_limit)
        count = write_csv_stream(temp_csv, headers, rows)
        if job.format == "parquet":
            _csv_to_parquet(temp_csv, output)
            temp_csv.unlink(missing_ok=True)
        digest = _sha256(output)
        current = db.get(ExportJob, job.id)
        if current is None:
            raise RuntimeError("Job de exportação removido")
        current.status = "completed"
        current.row_count = count
        current.byte_count = output.stat().st_size
        current.sha256 = digest
        current.storage_path = str(output)
        current.finished_at = datetime.now(UTC)
        current.locked_at = None
        current.lock_token = None
        db.commit()
        return {
            "export_job_id": str(current.id),
            "domain": current.domain,
            "format": current.format,
            "rows": count,
            "bytes": current.byte_count,
            "sha256": digest,
        }
    except Exception as exc:
        output.unlink(missing_ok=True)
        temp_csv.unlink(missing_ok=True)
        db.rollback()
        current = db.get(ExportJob, job.id)
        if current is not None:
            current.status = "failed"
            current.finished_at = datetime.now(UTC)
            current.locked_at = None
            current.lock_token = None
            current.error_details = str(exc)[:2000]
            db.commit()
        raise


def cleanup_expired_exports(db: Session, *, raw_data_dir: Path) -> int:
    root = (raw_data_dir / "exports").resolve()
    now = datetime.now(UTC)
    jobs = list(
        db.scalars(
            select(ExportJob).where(
                ExportJob.expires_at <= now,
                ExportJob.status.in_(["pending", "completed", "failed"]),
            )
        )
    )
    for job in jobs:
        if job.storage_path:
            candidate = Path(job.storage_path).resolve()
            if root in candidate.parents:
                candidate.unlink(missing_ok=True)
        job.status = "expired"
        job.storage_path = None
    db.commit()
    return len(jobs)


def write_csv_stream(
    path: Path, headers: list[str], rows: Iterable[dict[str, Any]]
) -> int:
    count = 0
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
            count += 1
    return count


def export_rows(
    db: Session, domain: str, filters: dict[str, Any], row_limit: int
) -> tuple[list[str], Iterator[dict[str, Any]]]:
    if not 1 <= row_limit <= MAX_EXPORT_ROWS:
        raise ValueError("Limite de exportação inválido")
    builders = {
        "observations": _observation_query,
        "economy": _economy_query,
        "labor": _labor_query,
        "infrastructure": _infrastructure_query,
        "agriculture": _agriculture_query,
        "catalog": _catalog_query,
    }
    if domain not in builders:
        raise ValueError("Domínio de exportação não permitido")
    headers, statement, serializer = builders[domain](filters)
    result = db.execute(
        statement.limit(row_limit + 1), execution_options={"yield_per": 1000}
    )

    def iterate() -> Iterator[dict[str, Any]]:
        for index, row in enumerate(result):
            if index >= row_limit:
                raise ValueError(f"Resultado excede quota de {row_limit} linhas")
            yield serializer(row)

    return headers, iterate()


def _latest(model: Any):
    return (
        select(
            model.source_system,
            model.source_key,
            func.max(model.revision).label("revision"),
        )
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


def _municipality_filters(statement: Any, model: Any, filters: dict[str, Any]):
    if filters.get("municipality"):
        statement = statement.where(
            model.municipality_ibge_code == filters["municipality"]
        )
    if filters.get("uf"):
        statement = statement.join(
            Municipality, Municipality.ibge_code == model.municipality_ibge_code
        ).where(Municipality.state == str(filters["uf"]).upper())
    return statement


def _source_columns(statement: Any, model: Any):
    return (
        statement.join(SourceSnapshot, SourceSnapshot.id == model.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(
            SourceSnapshot.url, SourceSnapshot.sha256, Source.license, Dataset.code
        )
    )


def _observation_query(filters: dict[str, Any]):
    headers = [
        "municipality_ibge_code",
        "indicator",
        "period_start",
        "period_end",
        "value",
        "availability_status",
        "revision",
        "source_url",
        "source_sha256",
        "license",
        "dataset",
    ]
    statement = (
        select(Observation)
        .join(Indicator, Indicator.id == Observation.indicator_id)
        .join(SourceSnapshot, SourceSnapshot.id == Observation.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(
            Indicator.code,
            SourceSnapshot.url,
            SourceSnapshot.sha256,
            Source.license,
            Dataset.code,
        )
        .order_by(Observation.period_start.desc(), Observation.municipality_ibge_code)
    )
    if filters.get("municipality"):
        statement = statement.where(
            Observation.municipality_ibge_code == filters["municipality"]
        )
    if filters.get("uf"):
        statement = statement.join(
            Municipality, Municipality.ibge_code == Observation.municipality_ibge_code
        ).where(Municipality.state == str(filters["uf"]).upper())
    if filters.get("indicator"):
        statement = statement.where(Indicator.code == filters["indicator"])
    if filters.get("start_year"):
        statement = statement.where(
            Observation.period_end >= date(int(filters["start_year"]), 1, 1)
        )
    if filters.get("end_year"):
        statement = statement.where(
            Observation.period_start <= date(int(filters["end_year"]), 12, 31)
        )

    def serialize(row: Any) -> dict[str, Any]:
        item, indicator, url, sha256, license_name, dataset = row
        return {
            "municipality_ibge_code": item.municipality_ibge_code,
            "indicator": indicator,
            "period_start": item.period_start,
            "period_end": item.period_end,
            "value": item.value,
            "availability_status": item.availability_status,
            "revision": item.revision,
            "source_url": url,
            "source_sha256": sha256,
            "license": license_name,
            "dataset": dataset,
        }

    return headers, statement, serialize


def _economy_query(filters: dict[str, Any]):
    headers = [
        "municipality_ibge_code",
        "year",
        "metric",
        "activity",
        "value",
        "unit",
        "availability_status",
        "source_url",
        "source_sha256",
        "license",
        "dataset",
    ]
    statement = _source_columns(
        _current(EconomyFact).outerjoin(
            EconomicActivity, EconomicActivity.id == EconomyFact.activity_id
        ),
        EconomyFact,
    ).add_columns(EconomicActivity.code)
    statement = _municipality_filters(statement, EconomyFact, filters).order_by(
        EconomyFact.reference_year.desc(), EconomyFact.municipality_ibge_code
    )
    if filters.get("metric"):
        statement = statement.where(EconomyFact.metric_code == filters["metric"])
    if filters.get("start_year"):
        statement = statement.where(EconomyFact.reference_year >= filters["start_year"])
    if filters.get("end_year"):
        statement = statement.where(EconomyFact.reference_year <= filters["end_year"])

    def serialize(row: Any) -> dict[str, Any]:
        item, url, sha256, license_name, dataset, activity = row
        return {
            "municipality_ibge_code": item.municipality_ibge_code,
            "year": item.reference_year,
            "metric": item.metric_code,
            "activity": activity,
            "value": item.value,
            "unit": item.unit,
            "availability_status": item.availability_status,
            "source_url": url,
            "source_sha256": sha256,
            "license": license_name,
            "dataset": dataset,
        }

    return headers, statement, serialize


def _labor_query(filters: dict[str, Any]):
    headers = [
        "municipality_ibge_code",
        "period_start",
        "period_end",
        "section",
        "admissions",
        "dismissals",
        "balance",
        "availability_status",
        "source_url",
        "source_sha256",
        "license",
        "dataset",
    ]
    statement = _source_columns(
        _current(LaborFact).join(
            EconomicActivity, EconomicActivity.id == LaborFact.activity_id
        ),
        LaborFact,
    ).add_columns(EconomicActivity.code)
    statement = _municipality_filters(statement, LaborFact, filters).order_by(
        LaborFact.period_start.desc(), LaborFact.municipality_ibge_code
    )
    if filters.get("section"):
        statement = statement.where(EconomicActivity.code == filters["section"])
    if filters.get("start_year"):
        statement = statement.where(
            LaborFact.period_end >= date(int(filters["start_year"]), 1, 1)
        )
    if filters.get("end_year"):
        statement = statement.where(
            LaborFact.period_start <= date(int(filters["end_year"]), 12, 31)
        )

    def serialize(row: Any) -> dict[str, Any]:
        item, url, sha256, license_name, dataset, section = row
        return {
            "municipality_ibge_code": item.municipality_ibge_code,
            "period_start": item.period_start,
            "period_end": item.period_end,
            "section": section,
            "admissions": item.admissions,
            "dismissals": item.dismissals,
            "balance": item.balance,
            "availability_status": item.availability_status,
            "source_url": url,
            "source_sha256": sha256,
            "license": license_name,
            "dataset": dataset,
        }

    return headers, statement, serialize


def _infrastructure_query(filters: dict[str, Any]):
    headers = [
        "municipality_ibge_code",
        "reference_date",
        "service",
        "service_type",
        "metric",
        "value",
        "unit",
        "availability_status",
        "source_url",
        "source_sha256",
        "license",
        "dataset",
    ]
    statement = _source_columns(
        _current(InfrastructureFact).join(
            InfrastructureService,
            InfrastructureService.id == InfrastructureFact.service_id,
        ),
        InfrastructureFact,
    ).add_columns(InfrastructureService.code, InfrastructureService.service_type)
    statement = _municipality_filters(statement, InfrastructureFact, filters).order_by(
        InfrastructureFact.reference_date.desc(),
        InfrastructureFact.municipality_ibge_code,
    )
    if filters.get("metric"):
        statement = statement.where(InfrastructureFact.metric_code == filters["metric"])
    if filters.get("service_type"):
        statement = statement.where(
            InfrastructureService.service_type == filters["service_type"]
        )
    if filters.get("start_year"):
        statement = statement.where(
            InfrastructureFact.reference_date >= date(int(filters["start_year"]), 1, 1)
        )
    if filters.get("end_year"):
        statement = statement.where(
            InfrastructureFact.reference_date <= date(int(filters["end_year"]), 12, 31)
        )

    def serialize(row: Any) -> dict[str, Any]:
        item, url, sha256, license_name, dataset, service, service_type = row
        return {
            "municipality_ibge_code": item.municipality_ibge_code,
            "reference_date": item.reference_date,
            "service": service,
            "service_type": service_type,
            "metric": item.metric_code,
            "value": item.value,
            "unit": item.unit,
            "availability_status": item.availability_status,
            "source_url": url,
            "source_sha256": sha256,
            "license": license_name,
            "dataset": dataset,
        }

    return headers, statement, serialize


def _agriculture_query(filters: dict[str, Any]):
    headers = [
        "municipality_ibge_code",
        "year",
        "product_code",
        "product_name",
        "metric",
        "value",
        "unit",
        "availability_status",
        "source_url",
        "source_sha256",
        "license",
        "dataset",
    ]
    statement = _source_columns(_current(AgricultureFact), AgricultureFact)
    statement = _municipality_filters(statement, AgricultureFact, filters).order_by(
        AgricultureFact.reference_year.desc(),
        AgricultureFact.municipality_ibge_code,
        AgricultureFact.product_code,
    )
    if filters.get("product"):
        statement = statement.where(AgricultureFact.product_code == filters["product"])
    if filters.get("metric"):
        statement = statement.where(AgricultureFact.metric_code == filters["metric"])
    if filters.get("start_year"):
        statement = statement.where(
            AgricultureFact.reference_year >= filters["start_year"]
        )
    if filters.get("end_year"):
        statement = statement.where(
            AgricultureFact.reference_year <= filters["end_year"]
        )

    def serialize(row: Any) -> dict[str, Any]:
        item, url, sha256, license_name, dataset = row
        return {
            "municipality_ibge_code": item.municipality_ibge_code,
            "year": item.reference_year,
            "product_code": item.product_code,
            "product_name": item.product_name,
            "metric": item.metric_code,
            "value": item.value,
            "unit": item.unit,
            "availability_status": item.availability_status,
            "source_url": url,
            "source_sha256": sha256,
            "license": license_name,
            "dataset": dataset,
        }

    return headers, statement, serialize


def _catalog_query(filters: dict[str, Any]):
    headers = [
        "id",
        "area",
        "provider",
        "resource_url",
        "format",
        "auth",
        "priority",
        "review_status",
        "technical_owner",
        "last_checked_at",
        "blocking_reason",
    ]
    statement = (
        select(CatalogEntry)
        .join(CatalogEntry.provider)
        .order_by(CatalogEntry.external_catalog_id)
    )
    if filters.get("area"):
        statement = statement.where(CatalogEntry.area_slug == filters["area"])
    if filters.get("review_status"):
        statement = statement.where(
            CatalogEntry.review_status == filters["review_status"]
        )

    def serialize(row: Any) -> dict[str, Any]:
        item = row[0]
        raw = item.raw_record
        return {
            "id": item.external_catalog_id,
            "area": item.area_slug,
            "provider": item.provider.name,
            "resource_url": raw.get("api")
            or raw.get("download")
            or raw.get("evidencia"),
            "format": raw.get("formatos"),
            "auth": raw.get("auth"),
            "priority": raw.get("prioridade"),
            "review_status": item.review_status,
            "technical_owner": item.technical_owner,
            "last_checked_at": item.last_checked_at,
            "blocking_reason": item.decision_reason,
        }

    return headers, statement, serialize


def _csv_to_parquet(csv_path: Path, output: Path) -> None:
    source = str(csv_path).replace("'", "''")
    target = str(output).replace("'", "''")
    connection = duckdb.connect(database=":memory:")
    try:
        connection.execute("SET memory_limit='128MB'")
        connection.execute(
            f"COPY (SELECT * FROM read_csv_auto('{source}', header=true, all_varchar=true)) "
            f"TO '{target}' (FORMAT PARQUET, COMPRESSION ZSTD)"
        )
    finally:
        connection.close()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
