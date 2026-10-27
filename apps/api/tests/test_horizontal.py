from __future__ import annotations

import json
import os
import tracemalloc
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.horizontal import IbgeBoundaryAdapter, IbgePamAdapter
from ingestion.exports import _csv_to_parquet, write_csv_stream
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import Session

from lente_api.catalog import import_candidate_catalog
from lente_api.main import app
from lente_api.models import ExportJob


def _payload(content: bytes, url: str, original_format: str = "json") -> FetchedPayload:
    return FetchedPayload(
        content=content,
        url=url,
        fetched_at=datetime.now(UTC),
        original_format=original_format,
    )


def test_pam_preserves_unavailable_and_exact_product_grain(tmp_path: Path) -> None:
    rows = [
        {key: key for key in ("V", "D1C", "D2C", "D3C", "D4C", "D4N", "MN")},
        {
            "V": "168",
            "D1C": "3543402",
            "D2C": "214",
            "D3C": "2024",
            "D4C": "40129",
            "D4N": "Abacate",
            "MN": "Toneladas",
        },
        {
            "V": "..",
            "D1C": "3543402",
            "D2C": "214",
            "D3C": "2024",
            "D4C": "40135",
            "D4N": "Arroz",
            "MN": "Toneladas",
        },
    ]
    adapter = IbgePamAdapter(raw_data_dir=tmp_path, municipalities={"3543402"}, years=[2024])
    records = adapter.parse(_payload(json.dumps(rows).encode(), adapter.base_url))
    adapter.validate(records)
    assert records[0].value == 168
    assert records[0].metric_code == "production_quantity"
    assert records[1].value is None
    assert records[1].availability_status == "unavailable"


def test_pam_keeps_each_official_metric_separate(tmp_path: Path) -> None:
    rows = [
        {key: key for key in ("V", "D1C", "D2C", "D3C", "D4C", "D4N", "MN")},
        {
            "V": "37104",
            "D1C": "3543402",
            "D2C": "8331",
            "D3C": "2024",
            "D4C": "40106",
            "D4N": "Cana-de-açúcar",
            "MN": "Hectares",
        },
        {
            "V": "3002604",
            "D1C": "3543402",
            "D2C": "214",
            "D3C": "2024",
            "D4C": "40106",
            "D4N": "Cana-de-açúcar",
            "MN": "Toneladas",
        },
        {
            "V": "405352",
            "D1C": "3543402",
            "D2C": "215",
            "D3C": "2024",
            "D4C": "40106",
            "D4N": "Cana-de-açúcar",
            "MN": "Mil Reais",
        },
    ]
    adapter = IbgePamAdapter(raw_data_dir=tmp_path, municipalities={"3543402"}, years=[2024])
    records = adapter.parse(_payload(json.dumps(rows).encode(), adapter.base_url))
    adapter.validate(records)
    assert {item.metric_code for item in records} == {
        "planted_area",
        "production_quantity",
        "production_value",
    }
    assert {item.unit for item in records} == {"Hectares", "Toneladas", "Mil Reais"}


def test_boundary_declares_crs_and_bbox(tmp_path: Path) -> None:
    geometry = {
        "type": "Polygon",
        "coordinates": [[[-48.0, -22.0], [-47.0, -22.0], [-47.0, -21.0], [-48.0, -22.0]]],
    }
    url = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios/3543402?qualidade=minima"
    adapter = IbgeBoundaryAdapter(raw_data_dir=tmp_path, municipalities={"3543402"})
    document = {
        "type": "FeatureCollection",
        "features": [
            {"type": "Feature", "geometry": geometry, "properties": {"codarea": "3543402"}}
        ],
    }
    records = adapter.parse(_payload(json.dumps(document).encode(), url, "geojson"))
    adapter.validate(records)
    assert adapter.crs == "EPSG:4674"
    assert records[0].bbox == [-48.0, -22.0, -47.0, -21.0]


def test_streaming_csv_and_parquet_stay_bounded(tmp_path: Path) -> None:
    def rows():
        for index in range(50_000):
            yield {"id": index, "value": "x" * 20}

    csv_path = tmp_path / "large.csv"
    tracemalloc.start()
    count = write_csv_stream(csv_path, ["id", "value"], rows())
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert count == 50_000
    assert peak < 8_000_000
    parquet_path = tmp_path / "large.parquet"
    _csv_to_parquet(csv_path, parquet_path)
    content = parquet_path.read_bytes()
    assert content[:4] == b"PAR1"
    assert content[-4:] == b"PAR1"


@pytest.mark.integration
def test_inventory_matrix_covers_all_records_and_export_jobs_are_queued() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    catalog_path = (
        Path(__file__).parents[3] / "docs/catalog/input/lente_inventario_nacional_fontes_2026.json"
    )
    engine = create_engine(database_url)
    with Session(engine) as db:
        import_candidate_catalog(db, catalog_path)

    client = TestClient(app)
    matrix = client.get("/api/v1/catalog/matrix", params={"limit": 200})
    assert matrix.status_code == 200
    body = matrix.json()
    assert body["count"] == body["summary"]["inventory_records"] == 165
    assert body["summary"]["areas"] == 16
    assert body["summary"]["indicators"] == 95
    assert all(item["review_status"] for item in body["items"])
    assert all(item["technical_owner"] == "data-platform" for item in body["items"])
    assert all(item["blocking_reason"] for item in body["items"])

    queued = client.post(
        "/api/v1/export-jobs",
        headers={"X-Client-ID": "horizontal-test-client"},
        json={"domain": "catalog", "format": "parquet", "row_limit": 10001},
    )
    assert queued.status_code == 202
    assert queued.json()["status"] == "pending"
    assert queued.json()["download_url"] is None
    pending = client.get(
        f"/api/v1/export-jobs/{queued.json()['id']}",
        headers={"X-Client-ID": "horizontal-test-client"},
    )
    assert pending.status_code == 200
    assert (
        client.get(
            f"/api/v1/export-jobs/{queued.json()['id']}",
            headers={"X-Client-ID": "different-test-client"},
        ).status_code
        == 404
    )
    incompatible = client.post(
        "/api/v1/export-jobs",
        headers={"X-Client-ID": "horizontal-test-client"},
        json={
            "domain": "catalog",
            "format": "csv",
            "row_limit": 10001,
            "filters": {"municipality": "3543402"},
        },
    )
    assert incompatible.status_code == 422

    with Session(engine) as db:
        db.execute(delete(ExportJob).where(ExportJob.id == queued.json()["id"]))
        db.commit()
