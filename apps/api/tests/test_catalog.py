from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.orm import Session

from lente_api.catalog import (
    CatalogExpectations,
    import_candidate_catalog,
    validate_catalog_document,
)
from lente_api.main import app
from lente_api.models import (
    CatalogEntry,
    CatalogImport,
    DataProvider,
    Dataset,
    Source,
    SourceResource,
)


def _document(record_count: int, area_count: int, indicator_count: int) -> dict:
    return {
        "catalog_name": "Catálogo nacional de teste",
        "catalog_version": "test-1",
        "schema_version": "1.0",
        "records": [
            {
                "id": f"LNT-{index:04d}",
                "area": f"Área {((index - 1) % area_count) + 1}",
                "indicator": f"Indicador {((index - 1) % indicator_count) + 1}",
                "provider": f"Provedor de teste {((index - 1) % 2) + 1}",
                "provider_slug": f"provedor-teste-{((index - 1) % 2) + 1}",
                "url": f"https://dados.example.org/recurso/{((index - 1) % 2) + 1}",
                "format": "csv",
                "dataset_code": f"catalog_test_dataset_{((index - 1) % 2) + 1}",
            }
            for index in range(1, record_count + 1)
        ],
    }


def test_validator_accepts_reference_cardinality_without_changing_document() -> None:
    document = _document(165, 16, 95)
    original = json.loads(json.dumps(document))

    report = validate_catalog_document(document)

    assert report.valid
    assert (report.record_count, report.area_count, report.indicator_count) == (165, 16, 95)
    assert document == original


def test_validator_reports_duplicates_and_unsafe_urls() -> None:
    document = _document(2, 1, 1)
    document["records"][1]["id"] = "LNT-0001"
    document["records"][1]["url"] = "http://127.0.0.1/private"

    report = validate_catalog_document(
        document,
        expectations=CatalogExpectations(record_count=2, area_count=1, indicator_count=1),
    )

    assert not report.valid
    assert report.duplicate_ids == ["LNT-0001"]
    assert report.missing_ids == ["LNT-0002"]
    assert report.invalid_urls[0]["reason"] == "Endereço IP não público não é permitido"


@pytest.mark.integration
def test_candidate_import_is_idempotent_and_never_activates_connector(tmp_path: Path) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    path = tmp_path / "candidate.json"
    path.write_text(json.dumps(_document(3, 2, 2)), encoding="utf-8")
    engine = create_engine(database_url)
    expectations = CatalogExpectations(record_count=3, area_count=2, indicator_count=2)

    try:
        with Session(engine) as db:
            first = import_candidate_catalog(db, path, expectations=expectations)
            second = import_candidate_catalog(db, path, expectations=expectations)
            assert not first.already_imported
            assert second.already_imported
            assert first.catalog_import_id == second.catalog_import_id
            assert first.entries == second.entries == 3
            assert first.providers == second.providers == 2
            assert first.resources == second.resources == 2
            assert first.datasets == second.datasets == 2
            assert db.scalar(select(func.count(CatalogEntry.id))) >= 3
            resources = list(
                db.scalars(
                    select(SourceResource).where(SourceResource.slug.like("provedor-teste-%"))
                )
            )
            assert resources
            assert {item.source_status for item in resources} == {"discovered"}
            assert {item.connector_status for item in resources} == {"not_implemented"}
            datasets = list(
                db.scalars(select(Dataset).where(Dataset.code.like("catalog_test_dataset_%")))
            )
            assert {item.publication_status for item in datasets} == {"not_published"}

        response = TestClient(app).get("/api/v1/sources?status=discovered&limit=100")
        assert response.status_code == 200
        candidates = [
            item for item in response.json()["items"] if item["slug"].startswith("provedor-teste-")
        ]
        assert candidates
        assert {item["connector_status"] for item in candidates} == {"not_implemented"}
    finally:
        with Session(engine) as db:
            db.execute(
                delete(CatalogEntry).where(
                    CatalogEntry.external_catalog_id.in_(["LNT-0001", "LNT-0002", "LNT-0003"])
                )
            )
            db.execute(delete(Dataset).where(Dataset.code.like("catalog_test_dataset_%")))
            db.execute(delete(Source).where(Source.slug.like("provedor-teste-%")))
            db.execute(delete(SourceResource).where(SourceResource.slug.like("provedor-teste-%")))
            db.execute(delete(DataProvider).where(DataProvider.slug.like("provedor-teste-%")))
            db.execute(
                delete(CatalogImport).where(
                    CatalogImport.catalog_name == "Catálogo nacional de teste"
                )
            )
            db.commit()


@pytest.mark.integration
def test_legacy_api_contracts_remain_available() -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL não configurada")
    client = TestClient(app)

    health = client.get("/api/v1/health")
    municipalities = client.get("/api/v1/municipalities")
    sources = client.get("/api/v1/sources")
    datasets = client.get("/api/v1/datasets")
    indicators = client.get("/api/v1/indicators")

    assert health.status_code == municipalities.status_code == 200
    assert sources.status_code == datasets.status_code == indicators.status_code == 200
    assert {"provider", "slug", "source_url", "status"} <= sources.json()["items"][0].keys()
    assert {"code", "title", "domain", "status", "source"} <= datasets.json()["items"][0].keys()
    assert {"code", "label", "unit", "methodology"} <= indicators.json()["items"][0].keys()
    indicator_code = indicators.json()["items"][0]["code"]
    observations = client.get(f"/api/v1/indicators/{indicator_code}/observations")
    assert observations.status_code == 200
    assert {"indicator", "municipality_ibge_code", "items", "count"} <= (observations.json().keys())
