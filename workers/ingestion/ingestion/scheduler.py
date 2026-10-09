from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict
from pathlib import Path

from ingestion.adapters import ADAPTERS
from lente_api.database import SessionLocal
from lente_api.settings import get_settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("lente.ingestion")


def emit(event: str, **fields: object) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False, default=str))


def cycle() -> None:
    requested = [
        item.strip() for item in os.environ.get("INGESTION_SOURCES", "ibge,siconfi,cnes").split(",")
    ]
    for source in requested:
        adapter_class = ADAPTERS.get(source)
        if adapter_class is None:
            emit("source_skipped", source=source, reason="unknown_source")
            continue
        adapter = adapter_class(raw_data_dir=Path(get_settings().raw_data_dir))
        try:
            with SessionLocal() as db:
                summary = adapter.run(db)
            emit("ingestion_completed", **asdict(summary))
        except Exception as exc:  # noqa: BLE001 - keep other sources running
            emit("ingestion_failed", source=source, error=str(exc)[:1000])


def main() -> None:
    interval = max(3600, int(os.environ.get("INGESTION_INTERVAL_SECONDS", "86400")))
    while True:
        cycle()
        emit("scheduler_waiting", interval_seconds=interval)
        time.sleep(interval)


if __name__ == "__main__":
    main()
