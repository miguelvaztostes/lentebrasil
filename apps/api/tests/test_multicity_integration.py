from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from ingestion.geography import geography_payload_hash, sync_geographies
from ingestion.jobs import claim_next_job, schedule_job
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from lente_api.main import app
from lente_api.models import (
    Dataset,
    GeoCodeMapping,
    GeoUnit,
    GeoUnitVersion,
    Indicator,
    IngestionJob,
    Municipality,
    Observation,
    SourceSnapshot,
)

MUNICIPALITIES = {
    "3543402": ("Ribeirão Preto", "354340"),
    "3509502": ("Campinas", "350950"),
    "3550308": ("São Paulo", "355030"),
}


def _database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL não configurada")
    return value


def _municipality_row(code: str, name: str) -> dict:
    return {
        "id": int(code),
        "nome": name,
        "regiao-imediata": {"regiao-intermediaria": {"UF": {"sigla": "SP"}}},
    }


@pytest.mark.integration
def test_geography_sync_creates_crosswalks_and_preserves_name_history() -> None:
    engine = create_engine(_database_url())
    states = [{"id": 35, "sigla": "SP", "nome": "São Paulo"}]
    municipalities = [_municipality_row(code, name) for code, (name, _) in MUNICIPALITIES.items()]
    digest = geography_payload_hash(states, municipalities)
    with Session(engine) as db:
        target_unit_ids = list(
            db.scalars(
                select(GeoUnit.id).where(
                    GeoUnit.unit_type == "municipality",
                    GeoUnit.code.in_(MUNICIPALITIES),
                )
            )
        )
        if target_unit_ids:
            db.execute(
                delete(GeoUnitVersion).where(GeoUnitVersion.geo_unit_id.in_(target_unit_ids))
            )
            db.commit()
        first = sync_geographies(
            db,
            states,
            municipalities,
            source_hash=digest,
            effective_from=date(2026, 1, 1),
        )
        assert first.states == 1
        assert first.municipalities == 3
        campinas = db.get(Municipality, "3509502")
        assert campinas is not None and campinas.state == "SP"
        mapping = db.scalar(
            select(GeoCodeMapping)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.external_code == "350950",
                GeoUnit.code == "3509502",
            )
        )
        assert mapping is not None

        renamed = [dict(row) for row in municipalities]
        renamed[1] = _municipality_row("3509502", "Campinas (nome atualizado)")
        sync_geographies(
            db,
            states,
            renamed,
            source_hash=geography_payload_hash(states, renamed),
            effective_from=date(2026, 2, 1),
        )
        unit = db.scalar(
            select(GeoUnit).where(GeoUnit.unit_type == "municipality", GeoUnit.code == "3509502")
        )
        assert unit is not None
        history = list(
            db.scalars(
                select(GeoUnitVersion)
                .where(GeoUnitVersion.geo_unit_id == unit.id)
                .order_by(GeoUnitVersion.effective_from)
            )
        )
        assert [item.name for item in history] == ["Campinas", "Campinas (nome atualizado)"]
        assert history[0].effective_to == date(2026, 2, 1)


@pytest.mark.integration
def test_observation_filters_count_and_paginate_more_than_2001_without_mixing() -> None:
    engine = create_engine(_database_url())
    inserted_snapshot_id = None
    with Session(engine) as db:
        for code, (name, _) in MUNICIPALITIES.items():
            municipality = db.get(Municipality, code)
            if municipality is None:
                db.add(Municipality(ibge_code=code, name=name, state="SP"))
        dataset = db.scalar(select(Dataset).where(Dataset.code == "ibge_population"))
        indicator = db.scalar(select(Indicator).where(Indicator.code == "population_estimated"))
        assert dataset is not None and indicator is not None
        snapshot = SourceSnapshot(
            dataset_id=dataset.id,
            fetched_at=datetime.now(UTC),
            url="https://apisidra.ibge.gov.br/fixture",
            sha256="f" * 64,
            original_format="json",
            response_headers={"fixture": "multicity"},
        )
        db.add(snapshot)
        db.flush()
        inserted_snapshot_id = snapshot.id
        observations = []
        for index in range(2105):
            scope = {"group": "bulk", "row": index}
            scope_key = hashlib.sha256(
                json.dumps(scope, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            observations.append(
                Observation(
                    municipality_ibge_code="3509502",
                    indicator_id=indicator.id,
                    period_start=date(2040, 1, 1),
                    period_end=date(2040, 12, 31),
                    scope_json=scope,
                    scope_key=scope_key,
                    value=Decimal(index),
                    availability_status="available",
                    snapshot_id=snapshot.id,
                    retrieved_at=datetime.now(UTC),
                    revision=1,
                )
            )
        db.add_all(observations)
        for code, value in (("3543402", 11), ("3509502", 22), ("3550308", 33)):
            scope = {"group": "summary-fixture"}
            db.add(
                Observation(
                    municipality_ibge_code=code,
                    indicator_id=indicator.id,
                    period_start=date(2099, 1, 1),
                    period_end=date(2099, 12, 31),
                    scope_json=scope,
                    scope_key=hashlib.sha256(
                        json.dumps(scope, sort_keys=True).encode()
                    ).hexdigest(),
                    value=Decimal(value),
                    availability_status="available",
                    snapshot_id=snapshot.id,
                    retrieved_at=datetime.now(UTC),
                    revision=1,
                )
            )
        db.commit()

    try:
        client = TestClient(app)
        scope = json.dumps({"group": "bulk"})
        response = client.get(
            "/api/v1/indicators/population_estimated/observations",
            params={"municipality": "3509502", "scope": scope, "limit": 100, "offset": 2000},
        )
        assert response.status_code == 200
        assert response.json()["count"] == 2105
        assert len(response.json()["items"]) == 100
        tail = client.get(
            "/api/v1/indicators/population_estimated/observations",
            params={"municipality": "3509502", "scope": scope, "limit": 100, "offset": 2100},
        )
        assert len(tail.json()["items"]) == 5
        assert client.get("/api/v1/municipios/invalido/summary").status_code == 400
        assert client.get("/api/v1/municipios/9999999/summary").status_code == 404
        for code, expected in (("3543402", 11), ("3509502", 22), ("3550308", 33)):
            summary = client.get(f"/api/v1/municipios/{code}/summary")
            assert summary.status_code == 200
            population = next(
                card
                for card in summary.json()["cards"]
                if card["indicator"]["code"] == "population_estimated"
            )
            assert Decimal(str(population["value"])) == expected
    finally:
        with Session(engine) as db:
            if inserted_snapshot_id is not None:
                db.execute(
                    delete(Observation).where(Observation.snapshot_id == inserted_snapshot_id)
                )
                snapshot = db.get(SourceSnapshot, inserted_snapshot_id)
                if snapshot is not None:
                    db.delete(snapshot)
                db.commit()


@pytest.mark.integration
def test_persistent_job_lock_prevents_duplicates_and_recovers_stale_execution() -> None:
    engine = create_engine(_database_url())
    key = None
    with Session(engine) as db:
        job = schedule_job(
            db,
            "ibge",
            {"municipality_codes": ["3543402"], "dry_run": True},
        )
        key = job.job_key
        claimed = claim_next_job(db)
        assert claimed is not None and claimed.job_key == key
        first_token = claimed.lock_token
        assert claim_next_job(db) is None
        claimed.status = "running"
        claimed.locked_at = datetime.now(UTC) - timedelta(hours=2)
        db.commit()
        reclaimed = claim_next_job(db, stale_after_seconds=60)
        assert reclaimed is not None and reclaimed.job_key == key
        assert reclaimed.lock_token != first_token
        assert reclaimed.attempts == 2
    with Session(engine) as db:
        db.execute(delete(IngestionJob).where(IngestionJob.job_key == key))
        db.commit()
        assert (
            db.scalar(select(func.count(IngestionJob.id)).where(IngestionJob.job_key == key)) == 0
        )
