from __future__ import annotations

import json
import os
import time
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from ingestion.adapters.base import (
    FetchedPayload,
    ObservationRecord,
    SourceAdapter,
    SourceValidationError,
)


class SiconfiRreoAdapter(SourceAdapter):
    source_name = "siconfi"
    dataset_code = "siconfi_rreo"
    municipality_code = "3543402"
    base_url = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/rreo"

    column_map = {
        ("ReceitasExcetoIntraOrcamentarias", "Até o Bimestre (c)"): "revenue_realized",
        (
            "DespesasExcetoIntraOrcamentarias",
            "DESPESAS EMPENHADAS ATÉ O BIMESTRE (f)",
        ): "expense_committed",
        (
            "DespesasExcetoIntraOrcamentarias",
            "DESPESAS LIQUIDADAS ATÉ O BIMESTRE (h)",
        ): "expense_liquidated",
        (
            "DespesasExcetoIntraOrcamentarias",
            "DESPESAS PAGAS ATÉ O BIMESTRE (j)",
        ): "expense_paid",
    }

    def __init__(self, *, raw_data_dir: Path):
        super().__init__(raw_data_dir=raw_data_dir)
        self.start_year = int(os.environ.get("SICONFI_START_YEAR", "2022"))
        self.end_year = int(os.environ.get("SICONFI_END_YEAR", "2025"))
        if self.start_year > self.end_year:
            raise ValueError("SICONFI_START_YEAR deve ser menor ou igual a SICONFI_END_YEAR")

    def _url(self, year: int) -> str:
        params = {
            "an_exercicio": year,
            "nr_periodo": 6,
            "co_tipo_demonstrativo": "RREO",
            "co_esfera": "M",
            "id_ente": self.municipality_code,
            "no_anexo": "RREO-Anexo 01",
        }
        return f"{self.base_url}?{urlencode(params)}"

    def discover(self) -> dict[str, Any]:
        response = self.get("https://apidatalake.tesouro.gov.br/docs/siconfi.yaml", timeout=30)
        body = response.text
        if "/rreo:" not in body or 'name: "id_ente"' not in body:
            raise SourceValidationError(
                "Contrato RREO não encontrado no Swagger", code="contract_missing"
            )
        return {
            "endpoint": self.base_url,
            "rate_limit": "1 request/second",
            "license": "Apache 2.0",
        }

    def fetch(self) -> list[FetchedPayload]:
        payloads = []
        for index, year in enumerate(range(self.start_year, self.end_year + 1)):
            if index:
                time.sleep(1.05)
            response = self.get(self._url(year), timeout=90)
            payloads.append(
                FetchedPayload(
                    content=response.content,
                    url=str(response.url),
                    fetched_at=datetime.now(UTC),
                    original_format="json",
                    response_headers=self.selected_headers(response),
                    published_at=self.header_datetime(response, "last-modified"),
                    persist_raw=True,
                )
            )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        try:
            envelope = json.loads(payload.content)
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Resposta Siconfi não é JSON válido", code="invalid_json"
            ) from exc
        items = envelope.get("items") if isinstance(envelope, dict) else None
        if not isinstance(items, list) or not items:
            raise SourceValidationError("Resposta Siconfi sem itens", code="empty_payload")
        records: list[ObservationRecord] = []
        for row in items:
            key = (row.get("cod_conta"), row.get("coluna"))
            indicator_code = self.column_map.get(key)
            if indicator_code is None:
                continue
            if int(row.get("cod_ibge", 0)) != int(self.municipality_code):
                raise SourceValidationError(
                    "Siconfi retornou outro ente", code="geographic_domain_mismatch"
                )
            try:
                value = None if row.get("valor") is None else Decimal(str(row["valor"]))
            except InvalidOperation as exc:
                raise SourceValidationError(
                    "Valor fiscal inválido",
                    code="invalid_numeric",
                    details={"row": row},
                ) from exc
            year = int(row["exercicio"])
            scope = {
                "demonstrativo": row["demonstrativo"],
                "anexo": row["anexo"],
                "periodo": int(row["periodo"]),
                "periodicidade": row.get("periodicidade"),
                "conta": row["cod_conta"],
                "conta_label": row["conta"],
                "coluna": row["coluna"],
            }
            records.append(
                ObservationRecord(
                    indicator_code=indicator_code,
                    municipality_ibge_code=self.municipality_code,
                    period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31),
                    value=value,
                    scope=scope,
                    availability_status="available" if value is not None else "unavailable",
                    source_reference_at=payload.published_at,
                )
            )
        return records

    def validate(self, records: list[ObservationRecord]) -> None:
        expected = set(self.column_map.values())
        received = {record.indicator_code for record in records}
        missing = expected - received
        duplicates = len(records) != len(received)
        if missing or duplicates:
            raise SourceValidationError(
                "Conjunto fiscal não contém exatamente uma linha por fase esperada",
                code="fiscal_phase_mismatch",
                details={
                    "missing": sorted(missing),
                    "received": sorted(received),
                    "count": len(records),
                },
            )
        for record in records:
            if record.value is not None and record.value < 0:
                raise SourceValidationError(
                    "Total fiscal negativo inesperado",
                    code="out_of_range",
                    details={"indicator": record.indicator_code},
                )
