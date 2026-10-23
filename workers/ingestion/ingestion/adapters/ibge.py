from __future__ import annotations

import json
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from ingestion.adapters.base import (
    FetchedPayload,
    ObservationRecord,
    SourceAdapter,
    SourceValidationError,
)


class IbgePopulationAdapter(SourceAdapter):
    source_name = "ibge"
    dataset_code = "ibge_population"
    sidra_base_url = "https://apisidra.ibge.gov.br/values/t/6579"

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        geographies: dict[str, dict[str, str]],
        period_range: tuple[int, int] | None = None,
        resource_version: str | None = None,
        batch_size: int = 50,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        if not geographies:
            raise ValueError("Ao menos um município deve ser selecionado")
        if any(len(code) != 7 or not code.isdigit() for code in geographies):
            raise ValueError("Códigos IBGE municipais devem ter sete dígitos")
        if period_range and period_range[0] > period_range[1]:
            raise ValueError("Período inicial deve ser menor ou igual ao final")
        self.geographies = geographies
        self.period_range = period_range
        self.resource_version = resource_version or "sidra-6579-variable-9324"
        self.batch_size = min(max(batch_size, 1), 100)

    def _period_path(self) -> str:
        if self.period_range is None:
            return "last%2010"
        start, end = self.period_range
        return ",".join(str(year) for year in range(start, end + 1))

    def _url(self, codes: list[str]) -> str:
        municipalities = ",".join(codes)
        return f"{self.sidra_base_url}/n6/{municipalities}/v/9324/p/{self._period_path()}?formato=json"

    def discover(self) -> dict[str, Any]:
        return {
            "municipalities": [
                {"ibge_code": code, **identity}
                for code, identity in sorted(self.geographies.items())
            ],
            "resource_version": self.resource_version,
            "table": "6579",
            "variable": "9324",
        }

    def fetch(self) -> list[FetchedPayload]:
        codes = sorted(self.geographies)
        payloads: list[FetchedPayload] = []
        for start in range(0, len(codes), self.batch_size):
            batch = codes[start : start + self.batch_size]
            response = self.get(self._url(batch), timeout=90)
            payloads.append(
                FetchedPayload(
                    content=response.content,
                    url=str(response.url),
                    fetched_at=datetime.now(UTC),
                    original_format="json",
                    response_headers=self.selected_headers(response),
                    published_at=self.header_datetime(response, "last-modified"),
                    persist_raw=True,
                    resource_version=self.resource_version,
                )
            )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        try:
            rows = json.loads(payload.read_bytes())
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Resposta SIDRA não é JSON válido", code="invalid_json"
            ) from exc
        if not isinstance(rows, list) or len(rows) < 2:
            raise SourceValidationError(
                "Resposta SIDRA sem observações", code="empty_payload"
            )
        required = {"V", "D1C", "D2C", "D3C", "MN"}
        if not required.issubset(rows[0]):
            raise SourceValidationError(
                "Cabeçalho SIDRA alterado",
                code="schema_drift",
                details={"header": rows[0]},
            )
        records: list[ObservationRecord] = []
        for row in rows[1:]:
            municipality_code = str(row.get("D1C"))
            if (
                municipality_code not in self.geographies
                or str(row.get("D2C")) != "9324"
            ):
                raise SourceValidationError(
                    "Linha SIDRA fora do lote solicitado",
                    code="domain_mismatch",
                    details={
                        "municipality": municipality_code,
                        "variable": row.get("D2C"),
                    },
                )
            year = int(row["D3C"])
            if (
                self.period_range
                and not self.period_range[0] <= year <= self.period_range[1]
            ):
                raise SourceValidationError(
                    "Linha SIDRA fora do período solicitado",
                    code="period_mismatch",
                    details={"year": year},
                )
            raw_value = str(row.get("V", "")).strip()
            try:
                value = (
                    Decimal(raw_value) if raw_value not in {"", "...", "-"} else None
                )
            except InvalidOperation as exc:
                raise SourceValidationError(
                    "Valor populacional inválido",
                    code="invalid_numeric",
                    details={"value": raw_value},
                ) from exc
            records.append(
                ObservationRecord(
                    indicator_code="population_estimated",
                    municipality_ibge_code=municipality_code,
                    period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31),
                    value=value,
                    scope={"resource_version": self.resource_version},
                    availability_status="available"
                    if value is not None
                    else "unavailable",
                    source_reference_at=payload.published_at,
                )
            )
        return records

    def validate(self, records: list[ObservationRecord]) -> None:
        if not records:
            raise SourceValidationError(
                "Nenhuma estimativa populacional recebida", code="empty_dataset"
            )
        keys = [
            (record.municipality_ibge_code, record.period_start.year)
            for record in records
        ]
        if len(keys) != len(set(keys)):
            raise SourceValidationError(
                "Município/ano duplicado na resposta SIDRA", code="duplicate_period"
            )
        for record in records:
            if record.municipality_ibge_code not in self.geographies:
                raise SourceValidationError(
                    "Município inesperado", code="domain_mismatch"
                )
            if record.value is not None and record.value <= 0:
                raise SourceValidationError(
                    "População deve ser positiva",
                    code="out_of_range",
                    details={
                        "municipality": record.municipality_ibge_code,
                        "year": record.period_start.year,
                    },
                )
