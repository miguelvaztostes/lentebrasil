from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

from lente_api.database import SessionLocal
from lente_api.settings import get_settings

from ingestion.factory import LEGACY_MUNICIPALITY
from ingestion.jobs import claim_next_job, execute_job, schedule_job

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("lente.ingestion")


def emit(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def seed_recurring_jobs() -> None:
    requested = [
        item.strip()
        for item in os.environ.get("INGESTION_SOURCES", "ibge,siconfi,cnes").split(",")
        if item.strip()
    ]
    recurring_seconds = max(
        3600, int(os.environ.get("INGESTION_INTERVAL_SECONDS", "86400"))
    )
    start_year = int(os.environ.get("SICONFI_START_YEAR", "2022"))
    end_year = int(os.environ.get("SICONFI_END_YEAR", "2025"))
    with SessionLocal() as db:
        for source in requested:
            base_parameters: dict[str, object] = {
                "municipality_codes": [LEGACY_MUNICIPALITY],
                "recurring_seconds": recurring_seconds,
            }
            parameter_sets = [base_parameters]
            if source == "siconfi":
                parameter_sets = [
                    {
                        **base_parameters,
                        "start_year": year,
                        "end_year": year,
                        "periods": [6],
                        "annexes": ["RREO-Anexo 01"],
                        "max_requests": 1,
                    }
                    for year in range(start_year, end_year + 1)
                ]
            for parameters in parameter_sets:
                try:
                    job = schedule_job(db, source, parameters)
                    emit("job_scheduled", source=source, job_key=job.job_key)
                except Exception as exc:  # noqa: BLE001 - isolate invalid configuration
                    emit("job_schedule_failed", source=source, error=str(exc)[:1000])


def cycle(*, max_jobs: int = 10) -> int:
    processed = 0
    while processed < max_jobs:
        with SessionLocal() as db:
            job = claim_next_job(db)
            if job is None:
                return processed
            try:
                result = execute_job(
                    db, job, raw_data_dir=Path(get_settings().raw_data_dir)
                )
                emit("ingestion_completed", **result)
            except Exception as exc:  # noqa: BLE001 - one job cannot block the queue
                emit("ingestion_failed", job_key=job.job_key, error=str(exc)[:1000])
        processed += 1
    return processed


def main() -> None:
    seed_recurring_jobs()
    poll_seconds = max(5, int(os.environ.get("INGESTION_POLL_SECONDS", "30")))
    while True:
        processed = cycle()
        emit("scheduler_waiting", poll_seconds=poll_seconds, processed=processed)
        time.sleep(poll_seconds)


if __name__ == "__main__":
    main()
