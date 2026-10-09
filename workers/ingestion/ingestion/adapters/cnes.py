from __future__ import annotations

import csv
import io
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from ingestion.adapters.base import (
    FetchedPayload,
    ObservationRecord,
    SourceAdapter,
    SourceValidationError,
)


class CnesAdapter(SourceAdapter):
    source_name = "cnes"
    dataset_code = "cnes_establishments"
    municipality_ibge_code = "3543402"
    cnes_municipality_code = "354340"
    catalog_url = "https://dadosabertos.saude.gov.br/dataset/cnes-cadastro-nacional-de-estabelecimentos-de-saude"
    data_url = (
        "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_csv.zip"
    )

    def __init__(self, *, raw_data_dir: Path):
        super().__init__(raw_data_dir=raw_data_dir)

    def discover(self) -> dict[str, Any]:
        response = self.get(self.catalog_url, timeout=45)
        if self.data_url not in response.text:
            raise SourceValidationError(
                "ZIP CSV do CNES não aparece no catálogo", code="resource_missing"
            )
        return {
            "catalog": self.catalog_url,
            "resource": self.data_url,
            "format": "ZIP/CSV",
        }

    def fetch(self) -> list[FetchedPayload]:
        response = self.get(self.data_url, timeout=240)
        return [
            FetchedPayload(
                content=response.content,
                url=str(response.url),
                fetched_at=datetime.now(UTC),
                original_format="csv.zip",
                response_headers=self.selected_headers(response),
                published_at=self.header_datetime(response, "last-modified"),
                persist_raw=False,
            )
        ]

    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        try:
            archive = zipfile.ZipFile(io.BytesIO(payload.content))
        except zipfile.BadZipFile as exc:
            raise SourceValidationError(
                "Recurso CNES não é ZIP válido", code="invalid_archive"
            ) from exc
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if len(names) != 1:
            raise SourceValidationError(
                "Arquivo CNES deve conter um único CSV",
                code="schema_drift",
                details={"files": archive.namelist()},
            )
        required = {"CO_IBGE", "CO_MOTIVO_DESAB", "CO_AMBULATORIAL_SUS"}
        total = without_disable_reason = sus_ambulatory = 0
        with archive.open(names[0]) as raw:
            # The official file contains Windows/Latin-1 bytes (for example 0xA0)
            # and does not publish a charset in its HTTP Content-Type.
            text_stream = io.TextIOWrapper(raw, encoding="latin-1", errors="strict", newline="")
            reader = csv.DictReader(text_stream, delimiter=";")
            fields = set(reader.fieldnames or [])
            if not required.issubset(fields):
                raise SourceValidationError(
                    "Cabeçalho CNES alterado",
                    code="schema_drift",
                    details={"missing": sorted(required - fields)},
                )
            for row in reader:
                if row.get("CO_IBGE", "").strip() != self.cnes_municipality_code:
                    continue
                total += 1
                if not row.get("CO_MOTIVO_DESAB", "").strip():
                    without_disable_reason += 1
                if row.get("CO_AMBULATORIAL_SUS", "").strip().upper() == "SIM":
                    sus_ambulatory += 1
        reference = payload.published_at or payload.fetched_at
        reference_date = reference.date()
        return [
            ObservationRecord(
                indicator_code="cnes_establishments_registered",
                municipality_ibge_code=self.municipality_ibge_code,
                period_start=reference_date,
                period_end=reference_date,
                value=Decimal(total),
                scope={"record_status": "all_rows_for_municipality"},
                source_reference_at=payload.published_at,
            ),
            ObservationRecord(
                indicator_code="cnes_establishments_without_disable_reason",
                municipality_ibge_code=self.municipality_ibge_code,
                period_start=reference_date,
                period_end=reference_date,
                value=Decimal(without_disable_reason),
                scope={"record_status": "disable_reason_blank"},
                source_reference_at=payload.published_at,
            ),
            ObservationRecord(
                indicator_code="cnes_establishments_sus_ambulatory",
                municipality_ibge_code=self.municipality_ibge_code,
                period_start=reference_date,
                period_end=reference_date,
                value=Decimal(sus_ambulatory),
                scope={"sus_ambulatory": True},
                source_reference_at=payload.published_at,
            ),
        ]

    def validate(self, records: list[ObservationRecord]) -> None:
        values = {record.indicator_code: record.value for record in records}
        required = {
            "cnes_establishments_registered",
            "cnes_establishments_without_disable_reason",
            "cnes_establishments_sus_ambulatory",
        }
        if set(values) != required:
            raise SourceValidationError("Agregados CNES incompletos", code="aggregate_mismatch")
        total = values["cnes_establishments_registered"]
        if total is None or total <= 0:
            raise SourceValidationError(
                "CNES não retornou registros municipais", code="empty_municipality"
            )
        if any(value is None or value < 0 or value > total for value in values.values()):
            raise SourceValidationError("Contagem CNES inconsistente", code="invalid_aggregate")
