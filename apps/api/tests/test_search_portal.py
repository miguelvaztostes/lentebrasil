from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from lente_api.catalog import import_candidate_catalog
from lente_api.main import app
from lente_api.models import Municipality


def _database_url() -> str:
    value = os.environ.get("TEST_DATABASE_URL")
    if not value:
        pytest.skip("TEST_DATABASE_URL não configurada")
    return value


def _catalog_path() -> Path:
    return (
        Path(__file__).parents[3] / "docs/catalog/input/lente_inventario_nacional_fontes_2026.json"
    )


@pytest.fixture(scope="module", autouse=True)
def seed_search_contract() -> None:
    engine = create_engine(_database_url())
    with Session(engine) as db:
        summary = import_candidate_catalog(db, _catalog_path())
        assert summary.records == 165
        for code, name in (
            ("3543402", "Ribeirão Preto"),
            ("3509502", "Campinas"),
            ("3550308", "São Paulo"),
        ):
            if db.get(Municipality, code) is None:
                db.add(Municipality(ibge_code=code, name=name, state="SP"))
        db.commit()


@pytest.mark.integration
def test_catalog_search_is_complete_accent_insensitive_and_distinguishes_publication() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/search", params={"q": "saude", "limit": 100})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] > 0
    assert body["summary"]["candidate_sources"] == 165
    assert all(item["status"] != "published" for item in body["items"])
    assert all(item["publication_status"] == "not_published" for item in body["items"])
    assert {facet["value"] for facet in body["facets"]["sectors"]} >= {
        "saude",
        "educacao",
        "financas-publicas",
    }
    assert {"resources", "statuses", "freshness"} <= body["facets"].keys()

    source = client.get("/api/v1/sources/LNT-0001")
    assert source.status_code == 200
    assert source.json()["kind"] == "catalog_candidate"
    assert source.json()["status"] == "discovered"


@pytest.mark.integration
def test_territorial_search_shared_filters_invalid_id_and_empty_result() -> None:
    client = TestClient(app)
    municipality = client.get("/api/v1/geo/municipios", params={"q": "Sao Paulo", "uf": "sp"})
    assert municipality.status_code == 200
    assert any(item["ibge_code"] == "3550308" for item in municipality.json()["items"])

    shared = client.get("/api/v1/search", params={"q": "Ribeirao", "uf": "SP"})
    assert shared.status_code == 200
    assert any(item["ibge_code"] == "3543402" for item in shared.json()["municipalities"])

    empty = client.get("/api/v1/search", params={"q": "termo-que-nao-existe-987654321"})
    assert empty.status_code == 200
    assert empty.json()["count"] == 0
    assert empty.json()["items"] == []

    assert client.get("/api/v1/municipios/invalido/summary").status_code == 400
    assert client.get("/api/v1/municipios/9999999/summary").status_code == 404

    for endpoint in ("sources", "datasets", "indicators"):
        response = client.get(f"/api/v1/{endpoint}")
        assert response.status_code == 200
        assert {"areas", "providers", "resources", "formats", "statuses", "freshness"} <= (
            response.json()["facets"].keys()
        )


@pytest.mark.integration
def test_dataset_coverage_reports_observed_state_without_inventing_coverage() -> None:
    client = TestClient(app)
    response = client.get("/api/v1/datasets/ibge_population/coverage")
    assert response.status_code == 200
    body = response.json()
    assert body["dataset"]["code"] == "ibge_population"
    assert body["source"]["url"].startswith("https://")
    assert body["observed"]["availability"] in {"published", "not_published"}
    if body["observed"]["municipalities"] == 0:
        assert body["observed"]["period_start"] is None
        assert body["observed"]["period_end"] is None

    specification = client.get("/api/openapi.json")
    assert specification.status_code == 200
    assert specification.json()["info"]["title"] == "Lente Brasil API"
    assert "/api/v1/search" in specification.json()["paths"]
    assert "/api/v1/datasets/{identifier}/coverage" in specification.json()["paths"]
