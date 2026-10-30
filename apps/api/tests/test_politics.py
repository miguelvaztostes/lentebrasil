from __future__ import annotations

import io
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from ingestion.adapters.base import FetchedPayload
from ingestion.adapters.politics import (
    AssetRecord,
    CandidateRecord,
    TseCandidacyAdapter,
    normalize_name,
)


def _zip_csv(name: str, header: list[str], rows: list[list[str]]) -> bytes:
    content = ";".join(header) + "\n"
    content += "\n".join(";".join(row) for row in rows)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        archive.writestr(name, content.encode("latin-1"))
    return output.getvalue()


def _payload(content: bytes, kind: str) -> FetchedPayload:
    return FetchedPayload(
        content=content,
        url=f"https://cdn.tse.jus.br/{kind}.zip",
        fetched_at=datetime.now(UTC),
        original_format=f"tse.{kind}.csv.zip",
    )


def test_tse_parser_filters_territory_and_discards_sensitive_columns(tmp_path: Path) -> None:
    header = [
        "ANO_ELEICAO",
        "NM_TIPO_ELEICAO",
        "SG_UF",
        "NM_UE",
        "CD_CARGO",
        "DS_CARGO",
        "SQ_CANDIDATO",
        "NR_CANDIDATO",
        "NM_CANDIDATO",
        "NM_URNA_CANDIDATO",
        "SG_PARTIDO",
        "DS_SITUACAO_CANDIDATURA",
        "DS_SIT_TOT_TURNO",
        "NR_CPF_CANDIDATO",
        "DS_EMAIL",
        "DT_NASCIMENTO",
        "NR_TITULO_ELEITORAL_CANDIDATO",
    ]
    rows = [
        [
            "2024",
            "ELEIÇÃO ORDINÁRIA",
            "SP",
            "RIBEIRÃO PRETO",
            "11",
            "PREFEITO",
            "250000000001",
            "10",
            "PESSOA TESTE",
            "NOME DE URNA",
            "ABC",
            "APTO",
            "ELEITO",
            "12345678900",
            "privado@example.org",
            "01/01/1970",
            "123456789012",
        ],
        [
            "2024",
            "ELEIÇÃO ORDINÁRIA",
            "SP",
            "OUTRA CIDADE",
            "11",
            "PREFEITO",
            "250000000002",
            "20",
            "FORA DO RECORTE",
            "OUTRO",
            "XYZ",
            "APTO",
            "NÃO ELEITO",
            "",
            "",
            "",
            "",
        ],
    ]
    adapter = TseCandidacyAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={("SP", "RIBEIRAO PRETO"): "3543402"},
    )
    records = adapter.parse(_payload(_zip_csv("consulta_SP.csv", header, rows), "candidates"))

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, CandidateRecord)
    assert record.municipality_code == "3543402"
    assert record.candidate_sequence == "250000000001"
    assert not hasattr(record, "cpf")
    assert not hasattr(record, "email")
    assert not hasattr(record, "birth_date")
    assert normalize_name("Ribeirão Preto") == "RIBEIRAO PRETO"


def test_tse_assets_are_aggregated_without_free_text_description(tmp_path: Path) -> None:
    adapter = TseCandidacyAdapter(
        raw_data_dir=tmp_path,
        municipality_crosswalk={("SP", "RIBEIRAO PRETO"): "3543402"},
    )
    adapter._selected_candidate_sequences.add("250000000001")
    header = [
        "ANO_ELEICAO",
        "SQ_CANDIDATO",
        "CD_TIPO_BEM_CANDIDATO",
        "DS_TIPO_BEM_CANDIDATO",
        "VR_BEM_CANDIDATO",
        "DS_BEM_CANDIDATO",
    ]
    rows = [
        ["2024", "250000000001", "21", "Veículo automotor", "10000,50", "texto privado 1"],
        ["2024", "250000000001", "21", "Veículo automotor", "25000,00", "texto privado 2"],
        ["2024", "999999999999", "21", "Veículo automotor", "50000,00", "fora"],
    ]
    records = adapter.parse(_payload(_zip_csv("bem_SP.csv", header, rows), "assets"))

    assert len(records) == 1
    record = records[0]
    assert isinstance(record, AssetRecord)
    assert record.asset_count == 2
    assert str(record.total_amount) == "35000.50"
    assert not hasattr(record, "description")
