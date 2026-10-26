from __future__ import annotations

import os
import statistics
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from time import perf_counter

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from lente_api.main import app
from lente_api.models import (
    Dataset,
    Indicator,
    Municipality,
    Observation,
    ResearchQuery,
    Source,
    SourceSnapshot,
)
from lente_api.research import _indicator_select


def test_research_routes_are_public_and_read_only_except_saved_query() -> None:
    paths = TestClient(app).get("/api/openapi.json").json()["paths"]
    assert set(paths["/api/v1/research/indicators"]) == {"get"}
    assert set(paths["/api/v1/research/series"]) == {"get"}
    assert set(paths["/api/v1/compare"]) == {"get"}
    assert set(paths["/api/v1/coverage"]) == {"get"}
    assert set(paths["/api/v1/research/export.csv"]) == {"get"}
    assert set(paths["/api/v1/research/export.json"]) == {"get"}
    assert set(paths["/api/v1/research/queries"]) == {"post"}


def test_enrollment_uses_aggregate_table_instead_of_metric_prefix_query() -> None:
    enrollment_sql, enrollment_params = _indicator_select("education:enrollment_count")
    ideb_sql, ideb_params = _indicator_select("education:ideb")
    assert "FROM education_enrollments" in enrollment_sql
    assert enrollment_params == {"indicator": "education:enrollment_count"}
    assert "FROM education_metrics" in ideb_sql
    assert ideb_params == {"metric": "ideb"}


@pytest.mark.integration
def test_research_compare_coverage_exports_and_reproducible_url() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    token = uuid.uuid4().hex[:10]
    codes = ["3543402", "3509502", "3550308"]
    source_id = uuid.uuid4()
    dataset_id = uuid.uuid4()
    snapshot_id = uuid.uuid4()
    indicator_id = uuid.uuid4()
    indicator_code = f"research_test_{token}"
    scope_key = "a" * 32
    engine = create_engine(database_url)
    now = datetime.now(UTC)
    with Session(engine) as db:
        for code, name in zip(codes, ["Ribeirão Preto", "Campinas", "São Paulo"], strict=True):
            if db.get(Municipality, code) is None:
                db.add(Municipality(ibge_code=code, name=name, state="SP"))
        db.add(
            Source(
                id=source_id,
                provider="Fonte oficial de teste",
                slug=f"source-{token}",
                source_url="https://example.invalid/source",
                license="Teste",
                terms=None,
                expected_frequency="anual",
                status="active",
                verified_at=now,
                failure_reason=None,
                source_status="verified",
                connector_status="active",
                catalog_metadata={},
            )
        )
        db.add(
            Dataset(
                id=dataset_id,
                source_id=source_id,
                code=f"dataset_{token}",
                title="Dataset de teste",
                description="Contrato de pesquisa",
                domain="desenvolvimento",
                granularity="município/ano",
                update_policy="anual",
                status="active",
                connector_status="active",
                publication_status="published",
                catalog_metadata={},
            )
        )
        db.add(
            SourceSnapshot(
                id=snapshot_id,
                dataset_id=dataset_id,
                fetched_at=now,
                published_at=now,
                url="https://example.invalid/source.csv",
                sha256="b" * 64,
                storage_path=None,
                original_format="csv",
                response_headers={},
            )
        )
        db.add(
            Indicator(
                id=indicator_id,
                code=indicator_code,
                label="Indicador comparável de teste",
                definition="Definição",
                unit="unidades",
                periodicity="anual",
                methodology="Mesmo conceito nos três municípios.",
                disaggregation_schema={},
                limitations="Fixture de contrato.",
                domain="desenvolvimento",
                direction=None,
            )
        )
        for index, code in enumerate(codes):
            db.add(
                Observation(
                    id=uuid.uuid4(),
                    municipality_ibge_code=code,
                    indicator_id=indicator_id,
                    period_start=date(2024, 1, 1),
                    period_end=date(2024, 12, 31),
                    scope_json={"category": "total"},
                    scope_key=scope_key,
                    value=Decimal(100 + index),
                    availability_status="available",
                    snapshot_id=snapshot_id,
                    source_reference_at=now,
                    retrieved_at=now,
                    revision=1,
                )
            )
        db.commit()

    client = TestClient(app)
    params = {
        "indicator": f"observation:{indicator_code}",
        "geo_ids": ",".join(codes),
        "year": 2024,
        "scope_key": scope_key,
    }
    comparison = client.get("/api/v1/compare", params=params)
    assert comparison.status_code == 200
    assert comparison.json()["valid"] is True
    assert len(comparison.json()["items"]) == 3

    incompatible = client.get("/api/v1/compare", params={**params, "year": 2023})
    assert incompatible.status_code == 200
    assert incompatible.json()["valid"] is False
    assert {reason["code"] for reason in incompatible.json()["reasons"]} == {"outside_coverage"}

    coverage = client.get("/api/v1/coverage", params={**params, "year": 2023})
    assert {item["state"] for item in coverage.json()["items"]} == {"incompatible_period"}
    exported = client.get(
        "/api/v1/research/export.csv",
        params={
            "indicator": params["indicator"],
            "geo_ids": params["geo_ids"],
            "scope_key": scope_key,
        },
    )
    assert exported.status_code == 200
    assert "source_url" in exported.text and "Fonte oficial de teste" in exported.text

    saved_payload = {
        "indicator": params["indicator"],
        "geo_ids": codes,
        "year": 2024,
        "scope_key": scope_key,
    }
    saved = client.post("/api/v1/research/queries", json=saved_payload)
    repeated = client.post("/api/v1/research/queries", json=saved_payload)
    assert saved.status_code == repeated.status_code == 201
    assert saved.json()["slug"] == repeated.json()["slug"]
    assert saved.json()["canonical_url"].startswith("/pesquisa?indicador=")
    assert "inicio=2024" in saved.json()["canonical_url"]
    assert "fim=2024" in saved.json()["canonical_url"]
    assert f"escopo={scope_key}" in saved.json()["canonical_url"]

    durations = []
    for _ in range(12):
        started = perf_counter()
        assert (
            client.get(
                "/api/v1/research/series",
                params={
                    "indicator": params["indicator"],
                    "geo_ids": params["geo_ids"],
                    "scope_key": scope_key,
                },
            ).status_code
            == 200
        )
        durations.append((perf_counter() - started) * 1000)
    assert statistics.quantiles(durations, n=20)[18] < 3500

    with Session(engine) as db:
        db.execute(
            delete(ResearchQuery).where(
                ResearchQuery.parameters["indicator"].as_string() == params["indicator"]
            )
        )
        db.execute(delete(Observation).where(Observation.indicator_id == indicator_id))
        db.execute(delete(Indicator).where(Indicator.id == indicator_id))
        db.execute(delete(SourceSnapshot).where(SourceSnapshot.id == snapshot_id))
        db.execute(delete(Dataset).where(Dataset.id == dataset_id))
        db.execute(delete(Source).where(Source.id == source_id))
        db.commit()
