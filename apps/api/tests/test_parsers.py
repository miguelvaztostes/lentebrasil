from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

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
    adapter = IbgePopulationAdapter(raw_data_dir=tmp_path)
    records = adapter.parse(payload(json.dumps(body).encode()))
    assert records[0].value == Decimal("734538")
    assert records[1].value is None
    assert records[1].availability_status == "unavailable"


def test_ibge_zero_is_not_treated_as_missing_but_fails_quality_gate(tmp_path: Path) -> None:
    body = [
        {"V": "Valor", "D1C": "Município", "D2C": "Variável", "D3C": "Ano", "MN": "Unidade"},
        {"V": "0", "D1C": "3543402", "D2C": "9324", "D3C": "2026", "MN": "Pessoas"},
    ]
    adapter = IbgePopulationAdapter(raw_data_dir=tmp_path)
    records = adapter.parse(payload(json.dumps(body).encode()))
    assert records[0].value == Decimal("0")
    with pytest.raises(SourceValidationError, match="positiva"):
        adapter.validate(records)


def test_siconfi_keeps_fiscal_phases_separate(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SICONFI_START_YEAR", "2025")
    monkeypatch.setenv("SICONFI_END_YEAR", "2025")
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
    adapter = SiconfiRreoAdapter(raw_data_dir=tmp_path)
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
    adapter = CnesAdapter(raw_data_dir=tmp_path)
    records = adapter.parse(payload(archive_buffer.getvalue(), "csv.zip"))
    adapter.validate(records)
    values = {item.indicator_code: item.value for item in records}
    assert values["cnes_establishments_registered"] == 2
    assert values["cnes_establishments_without_disable_reason"] == 1
    assert values["cnes_establishments_sus_ambulatory"] == 1
    assert "contato@example.org" not in json.dumps([item.scope for item in records])
