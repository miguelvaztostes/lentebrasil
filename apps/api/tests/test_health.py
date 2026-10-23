from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.health import (
    CnesBedsAdapter,
    SimMortalityAdapter,
    SinascBirthsAdapter,
    cid_chapter,
    sim_age_band,
)


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


def test_cnes_beds_rejects_unsafe_urls() -> None:
    for url in (
        "http://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2026.zip",
        "https://example.com/Leitos_csv_2026.zip",
        "https://s3.sa-east-1.amazonaws.com/outro.zip",
    ):
        try:
            CnesBedsAdapter._validate_url(url)
        except ValueError as error:
            assert getattr(error, "code", None) == "unsafe_source_url"
        else:
            raise AssertionError(f"URL fora da allowlist foi aceita: {url}")


def test_cnes_beds_selects_latest_competence_and_discards_contacts(tmp_path: Path) -> None:
    headers = sorted(CnesBedsAdapter.required_fields | {"NO_EMAIL", "NU_TELEFONE"})
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=headers, delimiter=";")
    writer.writeheader()
    base = {key: "" for key in headers}
    common = {
        "CO_IBGE": "354340",
        "CNES": "1234567",
        "NOME_ESTABELECIMENTO": "Hospital público",
        "TP_GESTAO": "M",
        "CO_TIPO_UNIDADE": "05",
        "DS_TIPO_UNIDADE": "HOSPITAL GERAL",
        "MOTIVO_DESABILITACAO": "",
        "NO_EMAIL": "privado@example.org",
        "NU_TELEFONE": "16999999999",
    }
    writer.writerow(
        {**base, **common, "COMP": "202608", "LEITOS_EXISTENTES": "20", "LEITOS_SUS": "10"}
    )
    writer.writerow(
        {**base, **common, "COMP": "202609", "LEITOS_EXISTENTES": "22", "LEITOS_SUS": "11"}
    )
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr("Leitos_2026.csv", output.getvalue().encode("cp1252"))
    adapter = CnesBedsAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={"354340": "3543402"},
        selected_municipalities={"3543402"},
    )
    records = adapter.parse(
        FetchedPayload(
            content=archive.getvalue(),
            url="https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2026.zip",
            fetched_at=datetime.now(UTC),
            original_format="csv.zip",
            persist_raw=False,
        )
    )
    adapter.validate(records)
    assert len(records) == 1
    assert records[0].reference_date.isoformat() == "2026-09-01"
    assert (records[0].existing_count, records[0].sus_count) == (22, 11)
    assert "privado" not in repr(records[0]) and "999999" not in repr(records[0])


def test_sinasc_aggregates_by_residence_and_discards_microdata(tmp_path: Path) -> None:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output,
        fieldnames=["CODMUNRES", "DTNASC", "NOME_MAE"],
        delimiter=";",
    )
    writer.writeheader()
    for day in range(1, 6):
        writer.writerow(
            {
                "CODMUNRES": "354340",
                "DTNASC": f"{day:02d}012024",
                "NOME_MAE": f"PESSOA {day}",
            }
        )
    writer.writerow({"CODMUNRES": "350950", "DTNASC": "01012024", "NOME_MAE": "OUTRA"})
    archive_path = tmp_path / "sinasc.zip"
    with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr("SINASC_2024.csv", output.getvalue().encode("latin-1"))
    adapter = SinascBirthsAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={"354340": "3543402"},
        selected_municipalities={"3543402"},
    )
    records = adapter.parse(
        FetchedPayload(
            content=None,
            file_path=archive_path,
            url="https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINASC/csv/SINASC_2024_csv.zip",
            fetched_at=datetime.now(UTC),
            original_format="csv.zip",
            persist_raw=False,
        )
    )
    adapter.validate(records)
    assert len(records) == 1 and records[0].count == 5
    assert records[0].category_code == "live_births"
    assert "PESSOA" not in repr(records[0])
    assert not archive_path.exists()
