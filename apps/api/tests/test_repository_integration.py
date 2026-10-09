from __future__ import annotations

import os
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from ingestion.adapters.base import FetchedPayload, ObservationRecord, SourceAdapter
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from lente_api.models import Dataset, Observation


class RepositoryAdapter(SourceAdapter):
    source_name = "test"
    dataset_code = "ibge_population"

    def discover(self):
        return {}

    def fetch(self):
        return []

    def parse(self, payload):
        return []

    def validate(self, records):
        return None


@pytest.mark.integration
def test_upsert_is_idempotent_and_creates_real_revisions(tmp_path: Path) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    engine = create_engine(database_url)
    adapter = RepositoryAdapter(raw_data_dir=tmp_path)
    with Session(engine) as db:
        dataset = db.scalar(select(Dataset).where(Dataset.code == "ibge_population"))
        assert dataset is not None
        fetched = FetchedPayload(
            content=b"test",
            url="https://example.test",
            fetched_at=datetime.now(UTC),
            original_format="json",
        )
        snapshot = adapter._create_snapshot(db, dataset, fetched)
        record = ObservationRecord(
            "population_estimated",
            "3543402",
            date(2099, 1, 1),
            date(2099, 12, 31),
            Decimal("0"),
            {"test": True},
        )
        adapter.upsert(db, [record], snapshot)
        adapter.upsert(db, [record], snapshot)
        count = db.scalar(
            select(func.count(Observation.id)).where(Observation.period_start == date(2099, 1, 1))
        )
        assert count == 1
        changed = ObservationRecord(
            "population_estimated",
            "3543402",
            date(2099, 1, 1),
            date(2099, 12, 31),
            Decimal("1"),
            {"test": True},
        )
        adapter.upsert(db, [changed], snapshot)
        revisions = list(
            db.scalars(
                select(Observation.revision)
                .where(Observation.period_start == date(2099, 1, 1))
                .order_by(Observation.revision)
            )
        )
        assert revisions == [1, 2]
        db.query(Observation).filter(Observation.period_start == date(2099, 1, 1)).delete()
        db.delete(snapshot)
        db.commit()
