from __future__ import annotations

import csv
import hashlib
import io
import json
import tempfile
import zipfile
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx

from ingestion.adapters.base import (
    USER_AGENT,
    FetchedPayload,
    ObservationRecord,
    SourceAdapter,
    SourceValidationError,
)


class CnesAdapter(SourceAdapter):
    source_name = "cnes"
    dataset_code = "cnes_establishments"
    catalog_url = (
        "https://dadosabertos.saude.gov.br/dataset/"
        "cnes-cadastro-nacional-de-estabelecimentos-de-saude"
    )
    data_url = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/CNES/cnes_estabelecimentos_csv.zip"
    max_download_bytes = 1_000_000_000
    max_uncompressed_bytes = 5_000_000_000

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[str, str],
        selected_municipalities: set[str],
        resource_version: str | None = None,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.municipality_crosswalk = municipality_crosswalk
        self.selected_municipalities = selected_municipalities
        self.resource_version = resource_version
        self._unknown_codes: set[str] = set()
        missing = selected_municipalities - set(municipality_crosswalk.values())
        if not selected_municipalities or missing:
            raise ValueError(f"Municípios sem crosswalk CNES: {sorted(missing)}")

    @property
    def _state_path(self) -> Path:
        return self.raw_data_dir / self.dataset_code / "resource-state.json"

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(state, ensure_ascii=False, sort_keys=True), encoding="utf-8"
        )
        temporary.replace(self._state_path)

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
            "selected_municipalities": sorted(self.selected_municipalities),
        }

    def fetch(self) -> list[FetchedPayload]:
        state = self._load_state()
        processed_municipalities = set(state.get("processed_municipalities", []))
        if (
            self.resource_version
            and state.get("version") == self.resource_version
            and self.selected_municipalities <= processed_municipalities
        ):
            return [
                FetchedPayload(
                    content=None,
                    url=self.data_url,
                    fetched_at=datetime.now(UTC),
                    original_format="csv.zip",
                    persist_raw=False,
                    resource_version=self.resource_version,
                    not_modified=True,
                    sha256_value=state.get("sha256"),
                )
            ]
        headers = {"User-Agent": USER_AGENT, "Accept": "application/zip, */*"}
        if state.get("processed") and state.get("etag"):
            headers["If-None-Match"] = state["etag"]
        if state.get("processed") and state.get("last_modified"):
            headers["If-Modified-Since"] = state["last_modified"]
        directory = self.raw_data_dir / self.dataset_code
        directory.mkdir(parents=True, exist_ok=True)
        try:
            with (
                httpx.Client(
                    headers=headers, follow_redirects=True, timeout=240
                ) as client,
                client.stream("GET", self.data_url) as response,
            ):
                if response.status_code == 304:
                    if not state.get("processed"):
                        raise SourceValidationError(
                            "CNES retornou 304 sem versão processada localmente",
                            code="resource_state_invalid",
                        )
                    if self.selected_municipalities <= processed_municipalities:
                        return [
                            FetchedPayload(
                                content=None,
                                url=str(response.url),
                                fetched_at=datetime.now(UTC),
                                original_format="csv.zip",
                                response_headers=self.selected_headers(response),
                                persist_raw=False,
                                resource_version=state.get("version"),
                                not_modified=True,
                                sha256_value=state.get("sha256"),
                            )
                        ]
                    aggregate_file = state.get("aggregate_file")
                    aggregate_path = (
                        directory / aggregate_file if aggregate_file else None
                    )
                    if aggregate_path is None or not aggregate_path.exists():
                        raise SourceValidationError(
                            "Agregado CNES indisponível para o novo recorte",
                            code="resource_state_invalid",
                        )
                    return [
                        FetchedPayload(
                            content=aggregate_path.read_bytes(),
                            url=str(response.url),
                            fetched_at=datetime.now(UTC),
                            original_format="cnes.aggregate.json",
                            response_headers=self.selected_headers(response),
                            persist_raw=False,
                            resource_version=state.get("version"),
                            sha256_value=state.get("sha256"),
                        )
                    ]
                response.raise_for_status()
                declared = int(response.headers.get("content-length", "0") or 0)
                if declared > self.max_download_bytes:
                    raise SourceValidationError(
                        "Arquivo CNES excede o limite de download",
                        code="resource_too_large",
                    )
                digest = hashlib.sha256()
                total = 0
                with tempfile.NamedTemporaryFile(
                    dir=directory, prefix="cnes-", suffix=".zip.part", delete=False
                ) as target:
                    path = Path(target.name)
                    for chunk in response.iter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > self.max_download_bytes:
                            target.close()
                            path.unlink(missing_ok=True)
                            raise SourceValidationError(
                                "Arquivo CNES excede o limite de download",
                                code="resource_too_large",
                            )
                        digest.update(chunk)
                        target.write(chunk)
                version = (
                    self.resource_version
                    or response.headers.get("etag")
                    or response.headers.get("last-modified")
                    or digest.hexdigest()
                )
                new_state = {
                    "version": version,
                    "etag": response.headers.get("etag"),
                    "last_modified": response.headers.get("last-modified"),
                    "sha256": digest.hexdigest(),
                    "processed": False,
                    "processed_municipalities": [],
                }
                self._save_state(new_state)
                return [
                    FetchedPayload(
                        content=None,
                        file_path=path,
                        url=str(response.url),
                        fetched_at=datetime.now(UTC),
                        original_format="csv.zip",
                        response_headers=self.selected_headers(response),
                        published_at=self.header_datetime(response, "last-modified"),
                        persist_raw=False,
                        resource_version=version,
                        sha256_value=digest.hexdigest(),
                    )
                ]
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SourceValidationError(
                "Falha de rede ao baixar CNES", code="network_error"
            ) from exc

    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        if payload.original_format == "cnes.aggregate.json":
            document = json.loads(payload.read_bytes())
            self._unknown_codes = set(document.get("unknown_codes", []))
            reference = document.get("published_at")
            if reference:
                payload.published_at = datetime.fromisoformat(reference)
            return self._records_from_counts(document["counts"], payload)
        source: io.BytesIO | Path
        source = (
            io.BytesIO(payload.content)
            if payload.content is not None
            else payload.file_path
        )  # type: ignore[assignment]
        if source is None:
            raise SourceValidationError("Payload CNES vazio", code="empty_payload")
        try:
            archive = zipfile.ZipFile(source)
        except zipfile.BadZipFile as exc:
            raise SourceValidationError(
                "Recurso CNES não é ZIP válido", code="invalid_archive"
            ) from exc
        try:
            members = [
                item
                for item in archive.infolist()
                if item.filename.lower().endswith(".csv")
            ]
            if len(members) != 1:
                raise SourceValidationError(
                    "Arquivo CNES deve conter um único CSV",
                    code="schema_drift",
                    details={"files": archive.namelist()},
                )
            member = members[0]
            if member.file_size > self.max_uncompressed_bytes or (
                member.compress_size and member.file_size / member.compress_size > 200
            ):
                raise SourceValidationError(
                    "ZIP CNES excede limites seguros", code="zip_bomb"
                )
            required = {"CO_IBGE", "CO_MOTIVO_DESAB", "CO_AMBULATORIAL_SUS"}
            counts: dict[str, dict[str, int]] = {}
            self._unknown_codes = set()
            with archive.open(member) as raw:
                text_stream = io.TextIOWrapper(
                    raw, encoding="latin-1", errors="strict", newline=""
                )
                reader = csv.DictReader(text_stream, delimiter=";")
                fields = set(reader.fieldnames or [])
                if not required.issubset(fields):
                    raise SourceValidationError(
                        "Cabeçalho CNES alterado",
                        code="schema_drift",
                        details={"missing": sorted(required - fields)},
                    )
                for row in reader:
                    external_code = row.get("CO_IBGE", "").strip()
                    canonical_code = self.municipality_crosswalk.get(external_code)
                    if canonical_code is None:
                        if external_code:
                            self._unknown_codes.add(external_code)
                        continue
                    aggregate = counts.setdefault(
                        canonical_code,
                        {"total": 0, "without_disable": 0, "sus_ambulatory": 0},
                    )
                    aggregate["total"] += 1
                    if not row.get("CO_MOTIVO_DESAB", "").strip():
                        aggregate["without_disable"] += 1
                    if row.get("CO_AMBULATORIAL_SUS", "").strip().upper() == "SIM":
                        aggregate["sus_ambulatory"] += 1
            state = self._load_state()
            aggregate_file = f"aggregates-{payload.sha256[:16]}.json"
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            (self._state_path.parent / aggregate_file).write_text(
                json.dumps(
                    {
                        "counts": counts,
                        "unknown_codes": sorted(self._unknown_codes),
                        "published_at": payload.published_at.isoformat()
                        if payload.published_at
                        else payload.fetched_at.isoformat(),
                    },
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            state["aggregate_file"] = aggregate_file
            self._save_state(state)
            return self._records_from_counts(counts, payload)
        finally:
            archive.close()
            if payload.file_path is not None:
                payload.file_path.unlink(missing_ok=True)

    def _records_from_counts(
        self, counts: dict[str, dict[str, int]], payload: FetchedPayload
    ) -> list[ObservationRecord]:
        reference = payload.published_at or payload.fetched_at
        records: list[ObservationRecord] = []
        definitions = (
            ("cnes_establishments_registered", "total", {"record_status": "all"}),
            (
                "cnes_establishments_without_disable_reason",
                "without_disable",
                {"record_status": "disable_reason_blank"},
            ),
            (
                "cnes_establishments_sus_ambulatory",
                "sus_ambulatory",
                {"sus_ambulatory": True},
            ),
        )
        for municipality_code in self.selected_municipalities:
            aggregate = counts.get(
                municipality_code,
                {"total": 0, "without_disable": 0, "sus_ambulatory": 0},
            )
            available = aggregate["total"] > 0
            for indicator, key, scope in definitions:
                records.append(
                    ObservationRecord(
                        indicator_code=indicator,
                        municipality_ibge_code=municipality_code,
                        period_start=reference.date(),
                        period_end=reference.date(),
                        value=Decimal(aggregate[key]) if available else None,
                        scope={**scope, "resource_version": payload.resource_version},
                        availability_status="available" if available else "unavailable",
                        source_reference_at=payload.published_at,
                    )
                )
        return records

    def validate(self, records: list[ObservationRecord]) -> None:
        if self._unknown_codes:
            self.quality_warnings.append(
                {
                    "code": "unknown_cnes_geography",
                    "details": {
                        "count": len(self._unknown_codes),
                        "sample": sorted(self._unknown_codes)[:20],
                        "decision": (
                            "Linhas fora do recorte selecionado foram ignoradas; códigos podem "
                            "representar regiões administrativas ou cadastros históricos."
                        ),
                    },
                },
            )
        by_municipality: dict[str, dict[str, Decimal | None]] = {}
        for record in records:
            by_municipality.setdefault(record.municipality_ibge_code, {})[
                record.indicator_code
            ] = record.value
        required = {
            "cnes_establishments_registered",
            "cnes_establishments_without_disable_reason",
            "cnes_establishments_sus_ambulatory",
        }
        if set(by_municipality) != self.selected_municipalities:
            raise SourceValidationError(
                "Cobertura municipal CNES incompleta", code="coverage_mismatch"
            )
        for municipality, values in by_municipality.items():
            if set(values) != required:
                raise SourceValidationError(
                    "Agregados CNES incompletos", code="aggregate_mismatch"
                )
            total = values["cnes_establishments_registered"]
            if total is None:
                if any(value is not None for value in values.values()):
                    raise SourceValidationError(
                        "Ausência CNES inconsistente", code="invalid_aggregate"
                    )
                continue
            if total <= 0 or any(
                value is None or value < 0 or value > total for value in values.values()
            ):
                raise SourceValidationError(
                    "Contagem CNES inconsistente",
                    code="invalid_aggregate",
                    details={"municipality": municipality},
                )

    def after_validate(
        self, payload: FetchedPayload, records: list[ObservationRecord]
    ) -> None:
        state = self._load_state()
        if state.get("sha256") == payload.sha256:
            state["processed"] = True
            state["processed_municipalities"] = sorted(
                set(state.get("processed_municipalities", []))
                | self.selected_municipalities
            )
            state["processed_at"] = datetime.now(UTC).isoformat()
            self._save_state(state)
