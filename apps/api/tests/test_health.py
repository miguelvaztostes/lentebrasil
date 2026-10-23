from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.health import SimMortalityAdapter, cid_chapter, sim_age_band


def test_sim_classifies_cid10_chapters_and_encoded_age() -> None:
    assert cid_chapter("A90") == "infectious"
    assert cid_chapter("D48") == "neoplasms"
    assert cid_chapter("D50") == "blood"
    assert cid_chapter("I21") == "circulatory"
    assert cid_chapter("X95") == "external"
    assert cid_chapter("") == "unknown"
    assert sim_age_band("305") == "under_1"
    assert sim_age_band("404") == "1_4"
    assert sim_age_band("459") == "30_59"
    assert sim_age_band("500") == "80_plus"
    assert sim_age_band("999") == "unknown"


def _sim_archive(path: Path) -> None:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=["TIPOBITO", "DTOBITO", "IDADE", "CODMUNRES", "CAUSABAS", "NOME"],
        delimiter=";",
        quoting=csv.QUOTE_ALL,
    )
    writer.writeheader()
    rows = [
        ("2", "01012024", "305", "354340", "I21", "PESSOA A"),
        ("2", "02012024", "305", "354340", "I21", "PESSOA B"),
        ("2", "03012024", "305", "354340", "I21", "PESSOA C"),
        ("2", "04012024", "305", "354340", "C50", "PESSOA D"),
        ("2", "05012024", "459", "354340", "C50", "PESSOA E"),
        ("1", "06012024", "305", "354340", "P95", "FETAL"),
        ("2", "07012024", "459", "999999", "J18", "OUTRO MUNICIPIO"),
    ]
    for row in rows:
        writer.writerow(dict(zip(writer.fieldnames, row, strict=True)))
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("DO24OPEN.csv", output.getvalue().encode("latin-1"))


def test_sim_aggregates_before_persistence_and_suppresses_small_cells(tmp_path: Path) -> None:
    archive_path = tmp_path / "sim.zip"
    _sim_archive(archive_path)
    payload = FetchedPayload(
        content=None,
        file_path=archive_path,
        url="https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SIM/csv/DO24OPEN_csv.zip",
        fetched_at=datetime(2026, 10, 22, tzinfo=UTC),
        original_format="csv.zip",
        persist_raw=False,
    )
    adapter = SimMortalityAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={"354340": "3543402"},
        selected_municipalities={"3543402"},
    )

    records = adapter.parse(payload)
    adapter.validate(records)

    overall = next(
        item for item in records if item.category_code == "all" and item.age_band == "all"
    )
    circulatory = next(item for item in records if item.category_code == "circulatory")
    neoplasms = next(item for item in records if item.category_code == "neoplasms")
    assert overall.count == 5
    assert circulatory.raw_count == 3 and circulatory.count is None
    assert neoplasms.raw_count == 2 and neoplasms.count is None
    assert circulatory.availability_status == "suppressed"
    assert all("PESSOA" not in repr(item) for item in records)
    assert not archive_path.exists()


def test_sim_rejects_unsafe_urls() -> None:
    try:
        SimMortalityAdapter._validate_url("https://example.com/DO24OPEN_csv.zip")
    except ValueError as error:
        assert getattr(error, "code", None) == "unsafe_source_url"
    else:
        raise AssertionError("URL fora da allowlist foi aceita")
