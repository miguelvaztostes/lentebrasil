from __future__ import annotations

import io
import json
import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import py7zr
import pytest
from fastapi.testclient import TestClient
from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.sectors import IbgePibAdapter, NovoCagedAdapter, SenatranFleetAdapter
from openpyxl import Workbook
from sqlalchemy import create_engine, delete, select
from sqlalchemy.orm import Session

from lente_api.main import app
from lente_api.models import (
    Dataset,
    EconomicActivity,
    EconomyFact,
    Municipality,
    SourceSnapshot,
)


def payload(content: bytes, *, url: str, original_format: str) -> FetchedPayload:
    return FetchedPayload(
        content=content, url=url, fetched_at=datetime.now(UTC), original_format=original_format
    )


def test_ibge_pib_preserves_nominal_units_and_unavailable(tmp_path: Path) -> None:
    rows = [
        {"V": "Valor", "D1C": "Município", "D2C": "Variável", "D3C": "Ano", "MN": "Unidade"},
        {"V": "52306820", "D1C": "3543402", "D2C": "37", "D3C": "2023", "MN": "Mil Reais"},
        {"V": "...", "D1C": "3543402", "D2C": "513", "D3C": "2023", "MN": ""},
    ]
    adapter = IbgePibAdapter(raw_data_dir=tmp_path, municipalities={"3543402"}, years=[2023])
    records = adapter.parse(
        payload(json.dumps(rows).encode(), url=adapter.base_url, original_format="json")
    )
    adapter.validate(records)
    assert records[0].value == Decimal("52306820000")
    assert records[0].unit == "BRL nominal"
    assert records[1].value is None
    assert records[1].availability_status == "unavailable"


def test_ibge_pib_batches_national_requests_to_bounded_urls(tmp_path: Path) -> None:
    municipalities = {f"{code:07d}" for code in range(1, 206)}
    adapter = IbgePibAdapter(
        raw_data_dir=tmp_path,
        municipalities=municipalities,
        years=[2023],
        batch_size=100,
    )

    batches = [
        sorted(municipalities)[start : start + adapter.batch_size]
        for start in range(0, len(municipalities), adapter.batch_size)
    ]

    assert [len(batch) for batch in batches] == [100, 100, 5]
    assert all(len(adapter._url(batch)) < 2_000 for batch in batches)


def test_ibge_pib_marks_historical_municipality_absence_as_unavailable(
    tmp_path: Path,
) -> None:
    rows = [
        {
            "V": "Valor",
            "D1C": "Município",
            "D2C": "Variável",
            "D3C": "Ano",
            "MN": "Unidade",
        },
        {
            "V": "10",
            "D1C": "3543402",
            "D2C": "37",
            "D3C": "2023",
            "MN": "Mil Reais",
        },
    ]
    adapter = IbgePibAdapter(
        raw_data_dir=tmp_path,
        municipalities={"3543402", "5101837"},
        years=[2023],
    )
    adapter._validation_batches.append({"3543402", "5101837"})

    records = adapter.parse(
        payload(json.dumps(rows).encode(), url=adapter.base_url, original_format="json")
    )
    adapter.validate(records)

    missing = next(item for item in records if item.municipality_ibge_code == "5101837")
    assert missing.value is None
    assert missing.availability_status == "unavailable"
    assert adapter.quality_warnings[0]["code"] == "historical_geography_unavailable"


def test_novo_caged_streams_and_reconciles_sections(tmp_path: Path) -> None:
    text = (
        "competênciamov;município;seção;saldomovimentação\n"
        "202512;354340;G;1\n202512;354340;G;-1\n"
        "202512;354340;C;1\n202512;350950;G;1\n"
    )
    source_text = tmp_path / "CAGEDMOV202512.txt"
    source_text.write_text(text, encoding="utf-8")
    archive = tmp_path / "CAGEDMOV202512.7z"
    with py7zr.SevenZipFile(archive, "w") as target:
        target.write(source_text, arcname=source_text.name)
    source_text.unlink()
    adapter = NovoCagedAdapter(raw_data_dir=tmp_path, municipality_crosswalk={"354340": "3543402"})
    records = adapter.parse(
        FetchedPayload(
            content=None,
            file_path=archive,
            url=adapter.source_url,
            fetched_at=datetime.now(UTC),
            original_format="7z",
            persist_raw=False,
        )
    )
    adapter.validate(records)
    commerce = next(item for item in records if item.section_code == "G")
    assert (commerce.admissions, commerce.dismissals, commerce.balance) == (1, 1, 0)
    assert all(item.municipality_ibge_code == "3543402" for item in records)
    assert not archive.exists()


def test_senatran_reconciles_total_and_vehicle_types(tmp_path: Path) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["título"])
    sheet.append([None, None, 3])
    headers = [
        "UF",
        "MUNICIPIO",
        "TOTAL",
        "AUTOMOVEL",
        "BONDE",
        "CAMINHAO",
        "CAMINHAO TRATOR",
        "CAMINHONETE",
        "CAMIONETA",
        "CHASSI PLATAF",
        "CICLOMOTOR",
        "MICRO-ONIBUS",
        "MOTOCICLETA",
        "MOTONETA",
        "ONIBUS",
        "QUADRICICLO",
        "REBOQUE",
        "SEMI-REBOQUE",
        "SIDE-CAR",
        "OUTROS",
        "TRATOR ESTEI",
        "TRATOR RODAS",
        "TRICICLO",
        "UTILITARIO",
    ]
    sheet.append(headers)
    sheet.append(["SP", "RIBEIRAO PRETO", 3, 2, *([0] * 19), 1])
    stream = io.BytesIO()
    workbook.save(stream)
    adapter = SenatranFleetAdapter(
        raw_data_dir=tmp_path, municipality_names={("SP", "RIBEIRAO PRETO"): "3543402"}
    )
    records = adapter.parse(
        payload(stream.getvalue(), url=adapter.resource_url, original_format="xlsx")
    )
    adapter.validate(records)
    assert len(records) == 22
    assert next(item.value for item in records if item.service_code == "fleet_total") == 3


@pytest.mark.integration
def test_sector_api_paginates_in_sql_and_exports_provenance() -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    engine = create_engine(database_url)
    snapshot_id = None
    activity_id = None
    with Session(engine) as db:
        municipality = db.get(Municipality, "3543402")
        if municipality is None:
            db.add(Municipality(ibge_code="3543402", name="Ribeirão Preto", state="SP"))
        dataset = db.scalar(select(Dataset).where(Dataset.code == "ibge_pib_municipal"))
        assert dataset is not None
        activity = EconomicActivity(
            classification_system="test-sector-api",
            code="T",
            label="Fixture de paginação",
            level="section",
        )
        snapshot = SourceSnapshot(
            dataset_id=dataset.id,
            fetched_at=datetime.now(UTC),
            url="https://apisidra.ibge.gov.br/fixture-sector-api",
            sha256="e" * 64,
            original_format="json",
            response_headers={"fixture": "sector-api"},
        )
        db.add_all([activity, snapshot])
        db.flush()
        activity_id = activity.id
        snapshot_id = snapshot.id
        for index in range(3):
            db.add(
                EconomyFact(
                    source_system="test-sector-api",
                    source_key=f"pagination:{index}",
                    municipality_ibge_code="3543402",
                    reference_year=2098 - index,
                    metric_code="fixture",
                    activity_id=activity.id,
                    value=Decimal(index + 1),
                    unit="BRL nominal",
                    price_basis="current_prices",
                    availability_status="available",
                    source_document_url=snapshot.url,
                    snapshot_id=snapshot.id,
                    revision=1,
                )
            )
        db.commit()

    try:
        client = TestClient(app)
        first = client.get(
            "/api/v1/sectors/economy",
            params={"municipality": "3543402", "metric": "fixture", "limit": 2},
        )
        second = client.get(
            "/api/v1/sectors/economy",
            params={"municipality": "3543402", "metric": "fixture", "limit": 2, "offset": 2},
        )
        assert first.status_code == second.status_code == 200
        assert first.json()["count"] == second.json()["count"] == 3
        assert [item["year"] for item in first.json()["items"]] == [2098, 2097]
        assert [item["year"] for item in second.json()["items"]] == [2096]

        exported = client.get(
            "/api/v1/sectors/exports/economy.csv", params={"municipality": "3543402"}
        )
        assert exported.status_code == 200
        assert "source_url" in exported.text.splitlines()[0]
        assert "source_sha256" in exported.text.splitlines()[0]
        assert "https://apisidra.ibge.gov.br/fixture-sector-api" in exported.text
        assert "e" * 64 in exported.text
    finally:
        with Session(engine) as db:
            db.execute(delete(EconomyFact).where(EconomyFact.source_system == "test-sector-api"))
            if snapshot_id is not None:
                snapshot = db.get(SourceSnapshot, snapshot_id)
                if snapshot is not None:
                    db.delete(snapshot)
            if activity_id is not None:
                activity = db.get(EconomicActivity, activity_id)
                if activity is not None:
                    db.delete(activity)
            db.commit()
