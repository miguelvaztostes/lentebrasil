from __future__ import annotations

import hashlib
import json
import re
import shutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
from dateutil.parser import parse as parse_datetime
from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from lente_api.models import (
    DataQualityIssue,
    Dataset,
    Indicator,
    IngestionRun,
    Observation,
    SourceSnapshot,
)

USER_AGENT = "LenteRibeirao/0.1 (+observatorio civico; contato pendente)"


class SourceValidationError(ValueError):
    def __init__(
        self,
        message: str,
        *,
        code: str = "validation_error",
        details: dict | None = None,
    ):
        super().__init__(message)
        self.code = code
        self.details = details or {"message": message}


@dataclass(slots=True)
class FetchedPayload:
    content: bytes | None
    url: str
    fetched_at: datetime
    original_format: str
    response_headers: dict[str, str] = field(default_factory=dict)
    published_at: datetime | None = None
    persist_raw: bool = True
    file_path: Path | None = None
    resource_version: str | None = None
    not_modified: bool = False
    sha256_value: str | None = None

    @property
    def sha256(self) -> str:
        if self.sha256_value:
            return self.sha256_value
        if self.content is not None:
            self.sha256_value = hashlib.sha256(self.content).hexdigest()
            return self.sha256_value
        if self.file_path is None:
            return hashlib.sha256(b"").hexdigest()
        digest = hashlib.sha256()
        with self.file_path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        self.sha256_value = digest.hexdigest()
        return self.sha256_value

    def read_bytes(self) -> bytes:
        if self.content is not None:
            return self.content
        if self.file_path is None:
            raise SourceValidationError("Payload sem conteúdo", code="empty_payload")
        return self.file_path.read_bytes()


@dataclass(slots=True)
class ObservationRecord:
    indicator_code: str
    municipality_ibge_code: str
    period_start: date
    period_end: date
    value: Decimal | None
    scope: dict[str, Any]
    availability_status: str = "available"
    source_reference_at: datetime | None = None


@dataclass(slots=True)
class RunSummary:
    source: str
    dry_run: bool
    status: str
    items_received: int
    items_accepted: int
    items_rejected: int
    checksum: str | None
    message: str


class SourceAdapter(ABC):
    source_name: str
    dataset_code: str

    def __init__(self, *, raw_data_dir: Path):
        self.raw_data_dir = raw_data_dir
        self.quality_warnings: list[dict[str, Any]] = []

    @abstractmethod
    def discover(self) -> dict[str, Any]:
        """Validate the official endpoint and geographic domain."""

    @abstractmethod
    def fetch(self) -> list[FetchedPayload]:
        """Fetch one or more immutable source payloads."""

    @abstractmethod
    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        """Parse a source payload into normalized observations."""

    @abstractmethod
    def validate(self, records: list[ObservationRecord]) -> None:
        """Raise SourceValidationError when publishing must be blocked."""

    def after_validate(self, payload: FetchedPayload, records: list[ObservationRecord]) -> None:
        """Persist source-specific checkpoint metadata after validation succeeds."""
        return

    def checkpoint_metadata(self) -> dict[str, Any]:
        """Return source-specific progress that can safely resume a scheduled job."""
        return {}

    def health(self) -> dict[str, Any]:
        try:
            evidence = self.discover()
            return {"status": "available", "evidence": evidence}
        except Exception as exc:  # noqa: BLE001 - health must return a bounded state
            return {"status": "unavailable", "reason": str(exc)[:500]}

    def run(self, db: Session, *, dry_run: bool = False) -> RunSummary:
        dataset = db.scalar(select(Dataset).where(Dataset.code == self.dataset_code))
        if dataset is None:
            raise RuntimeError(f"Dataset ausente no catálogo: {self.dataset_code}")
        started_at = datetime.now(UTC)
        run = IngestionRun(
            dataset_id=dataset.id,
            started_at=started_at,
            status="running",
            items_received=0,
            items_accepted=0,
            items_rejected=0,
        )
        if not dry_run:
            db.add(run)
            db.commit()
            db.refresh(run)

        checksums: list[str] = []
        received = accepted = rejected = 0
        try:
            self.discover()
            payloads = self.fetch()
            parsed_payloads: list[tuple[FetchedPayload, list[ObservationRecord]]] = []
            for payload in payloads:
                checksums.append(payload.sha256)
                if payload.not_modified:
                    continue
                records = self.parse(payload)
                received += len(records)
                self.validate(records)
                self.after_validate(payload, records)
                accepted += len(records)
                parsed_payloads.append((payload, records))
            if not dry_run:
                for payload, records in parsed_payloads:
                    snapshot = self._create_snapshot(db, dataset, payload)
                    self.upsert(db, records, snapshot)
                for warning in self.quality_warnings:
                    db.add(
                        DataQualityIssue(
                            run_id=run.id,
                            issue_code=warning["code"],
                            severity="warning",
                            details=warning["details"],
                            status="open",
                        )
                    )
            combined_checksum = hashlib.sha256("".join(checksums).encode()).hexdigest()
            if not dry_run:
                run.status = "success"
                run.finished_at = datetime.now(UTC)
                run.items_received = received
                run.items_accepted = accepted
                run.items_rejected = rejected
                run.checksum = combined_checksum
                db.commit()
            return RunSummary(
                source=self.source_name,
                dry_run=dry_run,
                status="success",
                items_received=received,
                items_accepted=accepted,
                items_rejected=rejected,
                checksum=combined_checksum,
                message="Validação concluída sem dados simulados.",
            )
        except Exception as exc:
            db.rollback()
            if not dry_run:
                run = db.get(IngestionRun, run.id)
                if run is not None:
                    run.status = "failed"
                    run.finished_at = datetime.now(UTC)
                    run.items_received = received
                    run.items_accepted = accepted
                    run.items_rejected = max(rejected, 1)
                    run.error_details = str(exc)[:2000]
                    if isinstance(exc, SourceValidationError):
                        db.add(
                            DataQualityIssue(
                                run_id=run.id,
                                issue_code=exc.code,
                                severity="error",
                                details=exc.details,
                                status="open",
                            )
                        )
                    db.commit()
            raise

    def upsert(
        self,
        db: Session,
        records: list[ObservationRecord],
        snapshot: SourceSnapshot,
    ) -> None:
        retrieved_at = snapshot.fetched_at
        for record in records:
            indicator = db.scalar(select(Indicator).where(Indicator.code == record.indicator_code))
            if indicator is None:
                raise SourceValidationError(
                    f"Indicador não cadastrado: {record.indicator_code}",
                    code="unknown_indicator",
                )
            scope_key = hashlib.sha256(
                json.dumps(
                    record.scope,
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            previous = db.scalar(
                select(Observation)
                .where(
                    Observation.municipality_ibge_code == record.municipality_ibge_code,
                    Observation.indicator_id == indicator.id,
                    Observation.period_start == record.period_start,
                    Observation.period_end == record.period_end,
                    Observation.scope_key == scope_key,
                )
                .order_by(desc(Observation.revision))
                .limit(1)
            )
            if (
                previous is not None
                and previous.value == record.value
                and previous.availability_status == record.availability_status
            ):
                continue
            db.add(
                Observation(
                    municipality_ibge_code=record.municipality_ibge_code,
                    indicator_id=indicator.id,
                    period_start=record.period_start,
                    period_end=record.period_end,
                    scope_json=record.scope,
                    scope_key=scope_key,
                    value=record.value,
                    availability_status=record.availability_status,
                    snapshot_id=snapshot.id,
                    source_reference_at=record.source_reference_at,
                    retrieved_at=retrieved_at,
                    revision=1 if previous is None else previous.revision + 1,
                )
            )
        db.flush()

    def _create_snapshot(
        self, db: Session, dataset: Dataset, payload: FetchedPayload
    ) -> SourceSnapshot:
        existing = db.scalar(
            select(SourceSnapshot)
            .where(
                SourceSnapshot.dataset_id == dataset.id,
                SourceSnapshot.sha256 == payload.sha256,
            )
            .limit(1)
        )
        if existing is not None:
            if payload.file_path is not None and "_stage" in payload.file_path.parts:
                payload.file_path.unlink(missing_ok=True)
            return existing
        storage_path = None
        if payload.persist_raw:
            directory = self.raw_data_dir / self.dataset_code
            directory.mkdir(parents=True, exist_ok=True)
            suffix = {"json": "json", "csv.zip": "zip"}.get(
                payload.original_format,
                re.sub(r"[^a-zA-Z0-9_-]", "_", payload.original_format),
            )
            filename = f"{payload.fetched_at:%Y%m%dT%H%M%SZ}-{payload.sha256[:16]}.{suffix}"
            path = directory / filename
            if not path.exists():
                if payload.file_path is not None:
                    shutil.copyfile(payload.file_path, path)
                else:
                    path.write_bytes(payload.content or b"")
            storage_path = str(path)
            if payload.file_path is not None and "_stage" in payload.file_path.parts:
                payload.file_path.unlink(missing_ok=True)
        headers = dict(payload.response_headers)
        if payload.resource_version:
            headers["x-lente-resource-version"] = payload.resource_version
        snapshot = SourceSnapshot(
            dataset_id=dataset.id,
            fetched_at=payload.fetched_at,
            published_at=payload.published_at,
            url=payload.url,
            sha256=payload.sha256,
            storage_path=storage_path,
            original_format=payload.original_format,
            response_headers=headers,
        )
        db.add(snapshot)
        db.flush()
        return snapshot

    @staticmethod
    @retry(
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.TransportError)),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        reraise=True,
    )
    def get(url: str, *, timeout: float = 60.0) -> httpx.Response:
        with httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json, */*"},
            follow_redirects=True,
            timeout=httpx.Timeout(timeout),
        ) as client:
            response = client.get(url)
            response.raise_for_status()
            return response

    @staticmethod
    def selected_headers(response: httpx.Response) -> dict[str, str]:
        return {
            key: value
            for key, value in response.headers.items()
            if key.lower() in {"etag", "last-modified", "content-type", "content-length"}
        }

    @staticmethod
    def header_datetime(response: httpx.Response, name: str) -> datetime | None:
        raw = response.headers.get(name)
        return parse_datetime(raw).astimezone(UTC) if raw else None
