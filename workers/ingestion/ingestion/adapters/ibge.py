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
    municipality_code = "3543402"
    locality_url = "https://servicodados.ibge.gov.br/api/v1/localidades/municipios/3543402"
    data_url = (
        "https://apisidra.ibge.gov.br/values/t/6579/n6/3543402/v/9324/p/last%2010?formato=json"
    )

    def __init__(self, *, raw_data_dir: Path):
        super().__init__(raw_data_dir=raw_data_dir)

    def discover(self) -> dict[str, Any]:
        response = self.get(self.locality_url, timeout=30)
        payload = response.json()
        uf = payload.get("microrregiao", {}).get("mesorregiao", {}).get("UF", {}).get("sigla")
        if payload.get("id") != 3543402 or payload.get("nome") != "Ribeirão Preto" or uf != "SP":
            raise SourceValidationError(
                "A API de Localidades não confirmou Ribeirão Preto/SP.",
                code="geographic_domain_mismatch",
                details={"received": payload},
            )
        return {
            "municipality": payload["nome"],
            "ibge_code": str(payload["id"]),
            "state": uf,
        }

    def fetch(self) -> list[FetchedPayload]:
        response = self.get(self.data_url, timeout=60)
        return [
            FetchedPayload(
                content=response.content,
                url=str(response.url),
                fetched_at=datetime.now(UTC),
                original_format="json",
                response_headers=self.selected_headers(response),
                published_at=self.header_datetime(response, "last-modified"),
                persist_raw=True,
            )
        ]

    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        try:
            rows = json.loads(payload.content)
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Resposta SIDRA não é JSON válido", code="invalid_json"
            ) from exc
        if not isinstance(rows, list) or len(rows) < 2:
            raise SourceValidationError("Resposta SIDRA sem observações", code="empty_payload")
        required = {"V", "D1C", "D2C", "D3C", "MN"}
        if not required.issubset(rows[0]):
            raise SourceValidationError(
                "Cabeçalho SIDRA alterado",
                code="schema_drift",
                details={"header": rows[0]},
            )
        records: list[ObservationRecord] = []
        for row in rows[1:]:
            if str(row.get("D1C")) != self.municipality_code or str(row.get("D2C")) != "9324":
                raise SourceValidationError(
                    "Linha SIDRA fora do domínio esperado",
                    code="domain_mismatch",
                    details={"row": row},
                )
            year = int(row["D3C"])
            raw_value = str(row.get("V", "")).strip()
            try:
                value = Decimal(raw_value) if raw_value not in {"", "...", "-"} else None
            except InvalidOperation as exc:
                raise SourceValidationError(
                    "Valor populacional inválido",
                    code="invalid_numeric",
                    details={"value": raw_value},
                ) from exc
            records.append(
                ObservationRecord(
                    indicator_code="population_estimated",
                    municipality_ibge_code=self.municipality_code,
                    period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31),
                    value=value,
                    scope={},
                    availability_status="available" if value is not None else "unavailable",
                    source_reference_at=payload.published_at,
                )
            )
        return records

    def validate(self, records: list[ObservationRecord]) -> None:
        if not records:
            raise SourceValidationError(
                "Nenhuma estimativa populacional recebida", code="empty_dataset"
            )
        years = [record.period_start.year for record in records]
        if len(years) != len(set(years)):
            raise SourceValidationError(
                "Anos duplicados na resposta SIDRA", code="duplicate_period"
            )
        for record in records:
            if record.value is not None and record.value <= 0:
                raise SourceValidationError(
                    "População deve ser positiva",
                    code="out_of_range",
                    details={"year": record.period_start.year},
                )
