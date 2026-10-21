from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import httpx
import pytest
from ingestion.adapters.base import FetchedPayload, SourceValidationError
from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.siconfi import SiconfiRreoAdapter


def payload(content: bytes, original_format: str = "json") -> FetchedPayload:
    return FetchedPayload(
        content=content,
        url="https://fonte.oficial.example/recurso",
        fetched_at=datetime(2026, 10, 9, tzinfo=UTC),
        original_format=original_format,
    )


def test_ibge_parser_preserves_missing_value_as_null(tmp_path: Path) -> None:
    body = [
        {"V": "Valor", "D1C": "Município", "D2C": "Variável", "D3C": "Ano", "MN": "Unidade"},
        {"V": "734538", "D1C": "3543402", "D2C": "9324", "D3C": "2026", "MN": "Pessoas"},
        {"V": "...", "D1C": "3543402", "D2C": "9324", "D3C": "2025", "MN": "Pessoas"},
    ]
    adapter = IbgePopulationAdapter(
        raw_data_dir=tmp_path,
        geographies={"3543402": {"name": "Ribeirão Preto", "state": "SP"}},
    )
    records = adapter.parse(payload(json.dumps(body).encode()))
    assert records[0].value == Decimal("734538")
    assert records[1].value is None
    assert records[1].availability_status == "unavailable"


def test_ibge_zero_is_not_treated_as_missing_but_fails_quality_gate(tmp_path: Path) -> None:
    body = [
        {"V": "Valor", "D1C": "Município", "D2C": "Variável", "D3C": "Ano", "MN": "Unidade"},
        {"V": "0", "D1C": "3543402", "D2C": "9324", "D3C": "2026", "MN": "Pessoas"},
    ]
    adapter = IbgePopulationAdapter(
        raw_data_dir=tmp_path,
        geographies={"3543402": {"name": "Ribeirão Preto", "state": "SP"}},
    )
    records = adapter.parse(payload(json.dumps(body).encode()))
    assert records[0].value == Decimal("0")
    with pytest.raises(SourceValidationError, match="positiva"):
        adapter.validate(records)


def test_siconfi_keeps_fiscal_phases_separate(tmp_path: Path) -> None:
    common = {
        "exercicio": 2025,
        "demonstrativo": "RREO",
        "periodo": 6,
        "periodicidade": "B",
        "cod_ibge": 3543402,
        "anexo": "RREO-Anexo 01",
        "conta": "TOTAL",
    }
    rows = [
        {
            **common,
            "cod_conta": "ReceitasExcetoIntraOrcamentarias",
            "coluna": "Até o Bimestre (c)",
            "valor": 100,
        },
        {
            **common,
            "cod_conta": "DespesasExcetoIntraOrcamentarias",
            "coluna": "DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)",
            "valor": 90,
        },
        {
            **common,
            "cod_conta": "DespesasExcetoIntraOrcamentarias",
            "coluna": "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)",
            "valor": 80,
        },
        {
            **common,
            "cod_conta": "DespesasExcetoIntraOrcamentarias",
            "coluna": "DESPESAS PAGAS ATÉ O BIMESTRE (j)",
            "valor": 70,
        },
    ]
    adapter = SiconfiRreoAdapter(
        raw_data_dir=tmp_path, municipality_codes=["3543402"], years=[2025]
    )
    records = adapter.parse(payload(json.dumps({"items": rows}).encode()))
    adapter.validate(records)
    assert {item.indicator_code: item.value for item in records} == {
        "revenue_realized": Decimal("100"),
        "expense_committed": Decimal("90"),
        "expense_liquidated": Decimal("80"),
        "expense_paid": Decimal("70"),
    }


def test_cnes_aggregates_without_persisting_contacts(tmp_path: Path) -> None:
    csv_body = (
        "CO_CNES;CO_IBGE;CO_MOTIVO_DESAB;CO_AMBULATORIAL_SUS;NO_EMAIL\n"
        "1;354340;;SIM;contato\xa0@example.org\n"
        "2;354340;06;NAO;pessoal@example.org\n"
        "3;999999;;SIM;fora@example.org\n"
    ).encode("latin-1")
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("cnes_estabelecimentos.csv", csv_body)
    adapter = CnesAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={"354340": "3543402", "999999": "9999999"},
        selected_municipalities={"3543402"},
    )
    records = adapter.parse(payload(archive_buffer.getvalue(), "csv.zip"))
    adapter.validate(records)
    values = {item.indicator_code: item.value for item in records}
    assert values["cnes_establishments_registered"] == 2
    assert values["cnes_establishments_without_disable_reason"] == 1
    assert values["cnes_establishments_sus_ambulatory"] == 1
    assert "contato@example.org" not in json.dumps([item.scope for item in records])


def test_cnes_single_national_payload_aggregates_three_municipalities(tmp_path: Path) -> None:
    csv_body = (
        "CO_CNES;CO_IBGE;CO_MOTIVO_DESAB;CO_AMBULATORIAL_SUS;NO_EMAIL\n"
        "1;354340;;SIM;ribeirao@example.org\n"
        "2;350950;06;NAO;campinas@example.org\n"
        "3;355030;;SIM;saopaulo@example.org\n"
        "4;355030;;NAO;saopaulo2@example.org\n"
    ).encode("latin-1")
    archive_buffer = io.BytesIO()
    with zipfile.ZipFile(archive_buffer, "w") as archive:
        archive.writestr("cnes_estabelecimentos.csv", csv_body)
    adapter = CnesAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={
            "354340": "3543402",
            "350950": "3509502",
            "355030": "3550308",
        },
        selected_municipalities={"3543402", "3509502", "3550308"},
    )
    records = adapter.parse(payload(archive_buffer.getvalue(), "csv.zip"))
    adapter.validate(records)
    registered = {
        item.municipality_ibge_code: item.value
        for item in records
        if item.indicator_code == "cnes_establishments_registered"
    }
    assert registered == {
        "3543402": Decimal("1"),
        "3509502": Decimal("1"),
        "3550308": Decimal("2"),
    }
    assert all("email" not in json.dumps(item.scope).lower() for item in records)

    aggregate_files = list((tmp_path / "cnes_establishments").glob("aggregates-*.json"))
    assert len(aggregate_files) == 1
    second_adapter = CnesAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={
            "354340": "3543402",
            "350950": "3509502",
            "355030": "3550308",
        },
        selected_municipalities={"3550308"},
    )
    aggregate_payload = FetchedPayload(
        content=aggregate_files[0].read_bytes(),
        url="https://fonte.oficial.example/recurso",
        fetched_at=datetime(2026, 10, 21, tzinfo=UTC),
        original_format="cnes.aggregate.json",
        resource_version="fixture-v1",
    )
    cached_records = second_adapter.parse(aggregate_payload)
    assert {
        item.value
        for item in cached_records
        if item.indicator_code == "cnes_establishments_registered"
    } == {Decimal("2")}


def test_ibge_parser_keeps_three_municipalities_separate(tmp_path: Path) -> None:
    geographies = {
        "3543402": {"name": "Ribeirão Preto", "state": "SP"},
        "3509502": {"name": "Campinas", "state": "SP"},
        "3550308": {"name": "São Paulo", "state": "SP"},
    }
    body = [{"V": "Valor", "D1C": "Município", "D2C": "Variável", "D3C": "Ano", "MN": "Unidade"}]
    body.extend(
        {"V": str(value), "D1C": code, "D2C": "9324", "D3C": "2025", "MN": "Pessoas"}
        for code, value in zip(geographies, [1, 2, 3], strict=True)
    )
    adapter = IbgePopulationAdapter(raw_data_dir=tmp_path, geographies=geographies)
    records = adapter.parse(payload(json.dumps(body).encode()))
    adapter.validate(records)
    assert {item.municipality_ibge_code: item.value for item in records} == {
        "3543402": Decimal("1"),
        "3509502": Decimal("2"),
        "3550308": Decimal("3"),
    }


def test_siconfi_enforces_one_request_per_second(tmp_path: Path) -> None:
    sleeps: list[float] = []
    moments = iter([0.0, 0.0, 0.2, 1.0])
    adapter = SiconfiRreoAdapter(
        raw_data_dir=tmp_path,
        municipality_codes=["3543402", "3509502"],
        years=[2025],
        sleep_fn=sleeps.append,
        monotonic_fn=lambda: next(moments),
    )
    response = httpx.Response(
        200,
        content=b'{"items": []}',
        request=httpx.Request("GET", "https://apidatalake.tesouro.gov.br/test"),
    )
    adapter.get = lambda *_args, **_kwargs: response  # type: ignore[method-assign]
    payloads = adapter.fetch()
    assert len(payloads) == 2
    assert sleeps == pytest.approx([0.8])


def test_siconfi_rejects_unbounded_request_window(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="limite explícito"):
        SiconfiRreoAdapter(
            raw_data_dir=tmp_path,
            municipality_codes=["3543402", "3509502", "3550308"],
            years=range(2000, 2026),
            periods=range(1, 7),
            max_requests=100,
        )
