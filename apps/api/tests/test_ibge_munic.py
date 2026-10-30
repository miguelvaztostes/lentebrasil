from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path

from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.ibge_munic import IbgeMunicAdapter, _normalize_value
from openpyxl import Workbook


def _workbook_payload() -> FetchedPayload:
    workbook = Workbook()
    dictionary = workbook.active
    dictionary.title = "Dicionário"
    dictionary.append(["variável", "descrição"])
    sheet = workbook.create_sheet("Informática e comunicação")
    sheet.append(["Cod Munic", "Desc Mun", "Mtic06", "Mtic08", "Mtic091", "Mtic092"])
    sheet.append([3543402, "Ribeirão Preto", "Sim", "Não", "Sim", "-"])
    output = BytesIO()
    workbook.save(output)
    return FetchedPayload(
        content=output.getvalue(),
        url="https://ftp.ibge.gov.br/Perfil_Municipios/2024/Base_de_Dados/Base_MUNIC_2024_20251107.xlsx",
        fetched_at=datetime.now(UTC),
        original_format="xlsx",
    )


def test_munic_parses_only_selected_municipality_and_preserves_response() -> None:
    adapter = IbgeMunicAdapter(
        raw_data_dir=Path("/tmp"),
        municipalities={"3543402"},
        profile="digital",
    )

    records = adapter.parse(_workbook_payload())
    adapter.validate(records)

    assert len(records) == 4
    assert records[0].indicator_code == "municipal_tic_structure"
    assert records[0].value == 1
    assert records[0].scope["response"] == "Sim"
    assert records[1].value == 0
    assert records[3].value is None
    assert records[3].availability_status == "unavailable"


def test_munic_normalizes_binary_numeric_and_missing_values() -> None:
    assert _normalize_value("Sim, por instrumento legal")[0] == 1
    assert _normalize_value("Não")[0] == 0
    assert _normalize_value(42)[0] == 42
    assert _normalize_value("-") == (None, "unavailable")


def test_munic_marks_municipality_absent_from_historical_edition() -> None:
    adapter = IbgeMunicAdapter(
        raw_data_dir=Path("/tmp"),
        municipalities={"3543402", "5101837"},
        profile="digital",
    )

    records = adapter.parse(_workbook_payload())
    adapter.validate(records)

    unavailable = [record for record in records if record.municipality_ibge_code == "5101837"]
    assert len(unavailable) == 4
    assert all(record.availability_status == "unavailable" for record in unavailable)
    assert all(
        record.scope["absence_reason"] == "not_present_in_source_edition" for record in unavailable
    )
    assert adapter.quality_warnings[0]["code"] == "historical_geography_unavailable"
