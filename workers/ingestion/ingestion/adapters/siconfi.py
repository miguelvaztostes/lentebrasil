from __future__ import annotations

import json
import time
from collections.abc import Callable, Sequence
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, ClassVar
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
    base_url = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt/rreo"

    column_map: ClassVar[dict[tuple[str, str], str]] = {
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

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_codes: Sequence[str],
        years: Sequence[int],
        periods: Sequence[int] = (6,),
        annexes: Sequence[str] = ("RREO-Anexo 01",),
        max_requests: int = 250,
        requests_per_second: float = 1.0,
        sleep_fn: Callable[[float], None] = time.sleep,
        monotonic_fn: Callable[[], float] = time.monotonic,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.municipality_codes = tuple(dict.fromkeys(municipality_codes))
        self.years = tuple(sorted(set(years)))
        self.periods = tuple(sorted(set(periods)))
        self.annexes = tuple(dict.fromkeys(annexes))
        self.max_requests = max_requests
        self.minimum_interval = 1.0 / requests_per_second
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn
        if not self.municipality_codes or not self.years:
            raise ValueError("Municípios e exercícios são obrigatórios")
        if any(
            len(code) != 7 or not code.isdigit() for code in self.municipality_codes
        ):
            raise ValueError("Códigos IBGE municipais devem ter sete dígitos")
        if any(period < 1 or period > 6 for period in self.periods):
            raise ValueError("Período RREO deve estar entre 1 e 6")
        planned = (
            len(self.municipality_codes)
            * len(self.years)
            * len(self.periods)
            * len(self.annexes)
        )
        if planned > self.max_requests:
            raise ValueError(
                f"Janela produziria {planned} requisições; limite explícito é {self.max_requests}"
            )

    def _url(self, municipality_code: str, year: int, period: int, annex: str) -> str:
        params = {
            "an_exercicio": year,
            "nr_periodo": period,
            "co_tipo_demonstrativo": "RREO",
            "co_esfera": "M",
            "id_ente": municipality_code,
            "no_anexo": annex,
        }
        return f"{self.base_url}?{urlencode(params)}"

    def discover(self) -> dict[str, Any]:
        response = self.get(
            "https://apidatalake.tesouro.gov.br/docs/siconfi.yaml", timeout=30
        )
        body = response.text
        if "/rreo:" not in body or 'name: "id_ente"' not in body:
            raise SourceValidationError(
                "Contrato RREO não encontrado no Swagger", code="contract_missing"
            )
        return {
            "endpoint": self.base_url,
            "rate_limit": "1 request/second",
            "license": "Apache 2.0",
            "municipalities": list(self.municipality_codes),
            "years": list(self.years),
            "periods": list(self.periods),
            "annexes": list(self.annexes),
        }

    def fetch(self) -> list[FetchedPayload]:
        payloads: list[FetchedPayload] = []
        last_request_at: float | None = None
        for municipality_code in self.municipality_codes:
            for year in self.years:
                for period in self.periods:
                    for annex in self.annexes:
                        now = self.monotonic_fn()
                        if last_request_at is not None:
                            remaining = self.minimum_interval - (now - last_request_at)
                            if remaining > 0:
                                self.sleep_fn(remaining)
                        response = self.get(
                            self._url(municipality_code, year, period, annex),
                            timeout=90,
                        )
                        last_request_at = self.monotonic_fn()
                        payloads.append(
                            FetchedPayload(
                                content=response.content,
                                url=str(response.url),
                                fetched_at=datetime.now(UTC),
                                original_format="json",
                                response_headers=self.selected_headers(response),
                                published_at=self.header_datetime(
                                    response, "last-modified"
                                ),
                                persist_raw=True,
                                resource_version=response.headers.get("etag")
                                or response.headers.get("last-modified"),
                            )
                        )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        try:
            envelope = json.loads(payload.read_bytes())
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Resposta Siconfi não é JSON válido", code="invalid_json"
            ) from exc
        items = envelope.get("items") if isinstance(envelope, dict) else None
        if not isinstance(items, list) or not items:
            raise SourceValidationError(
                "Resposta Siconfi sem itens", code="empty_payload"
            )
        records: list[ObservationRecord] = []
        for row in items:
            key = (row.get("cod_conta"), row.get("coluna"))
            indicator_code = self.column_map.get(key)
            if indicator_code is None:
                continue
            municipality_code = str(row.get("cod_ibge", ""))
            if municipality_code not in self.municipality_codes:
                raise SourceValidationError(
                    "Siconfi retornou ente fora do lote",
                    code="geographic_domain_mismatch",
                    details={"received": municipality_code},
                )
            year = int(row["exercicio"])
            period = int(row["periodo"])
            if year not in self.years or period not in self.periods:
                raise SourceValidationError(
                    "Siconfi retornou período fora do trabalho",
                    code="period_mismatch",
                    details={"year": year, "period": period},
                )
            try:
                value = None if row.get("valor") is None else Decimal(str(row["valor"]))
            except InvalidOperation as exc:
                raise SourceValidationError(
                    "Valor fiscal inválido",
                    code="invalid_numeric",
                    details={"row": row},
                ) from exc
            scope = {
                "demonstrativo": row["demonstrativo"],
                "anexo": row["anexo"],
                "periodo": period,
                "periodicidade": row.get("periodicidade"),
                "conta": row["cod_conta"],
                "conta_label": row["conta"],
                "coluna": row["coluna"],
            }
            records.append(
                ObservationRecord(
                    indicator_code=indicator_code,
                    municipality_ibge_code=municipality_code,
                    period_start=date(year, 1, 1),
                    period_end=date(year, 12, 31),
                    value=value,
                    scope=scope,
                    availability_status="available"
                    if value is not None
                    else "unavailable",
                    source_reference_at=payload.published_at,
                )
            )
        return records

    def validate(self, records: list[ObservationRecord]) -> None:
        expected = set(self.column_map.values())
        received = {record.indicator_code for record in records}
        if expected != received or len(records) != len(received):
            raise SourceValidationError(
                "Conjunto fiscal não contém exatamente uma linha por fase esperada",
                code="fiscal_phase_mismatch",
                details={
                    "missing": sorted(expected - received),
                    "received": sorted(received),
                    "count": len(records),
                },
            )
        identities = {
            (record.municipality_ibge_code, record.period_start.year)
            for record in records
        }
        if len(identities) != 1:
            raise SourceValidationError(
                "Payload Siconfi mistura município ou exercício", code="domain_mismatch"
            )
        for record in records:
            if record.value is not None and record.value < 0:
                raise SourceValidationError(
                    "Total fiscal negativo inesperado",
                    code="out_of_range",
                    details={"indicator": record.indicator_code},
                )
