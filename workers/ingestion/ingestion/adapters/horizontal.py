from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from lente_api.models import (
    AgricultureFact,
    CatalogEntry,
    Dataset,
    GeospatialAsset,
    SourceSnapshot,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ingestion.adapters.base import FetchedPayload, SourceAdapter, SourceValidationError


@dataclass(slots=True)
class AgricultureRecord:
    municipality_ibge_code: str
    year: int
    product_code: str
    product_name: str
    value: Decimal | None
    unit: str
    availability_status: str
    source_url: str


class IbgePamAdapter(SourceAdapter):
    source_name = "ibge_pam"
    dataset_code = "ibge_pam_production"
    base_url = "https://apisidra.ibge.gov.br/values/t/5457"

    def __init__(
        self, *, raw_data_dir: Path, municipalities: set[str], years: list[int]
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.municipalities = municipalities
        self.years = sorted(set(years))

    def discover(self) -> dict[str, Any]:
        return {
            "table": 5457,
            "variable": "214",
            "classification": "782/all",
            "years": self.years,
            "geography": "municipality",
        }

    def fetch(self) -> list[FetchedPayload]:
        payloads: list[FetchedPayload] = []
        codes = sorted(self.municipalities)
        for start in range(0, len(codes), 100):
            batch = ",".join(codes[start : start + 100])
            years = ",".join(str(year) for year in self.years)
            url = f"{self.base_url}/n6/{batch}/v/214/p/{years}/c782/all?formato=json"
            response = self.get(url, timeout=90)
            payloads.append(
                FetchedPayload(
                    content=response.content,
                    url=str(response.url),
                    fetched_at=datetime.now(UTC),
                    original_format="json",
                    response_headers=self.selected_headers(response),
                    persist_raw=True,
                    resource_version="sidra-5457-variable-214",
                )
            )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[AgricultureRecord]:
        try:
            rows = json.loads(payload.read_bytes())
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Resposta PAM inválida", code="invalid_json"
            ) from exc
        required = {"V", "D1C", "D2C", "D3C", "D4C", "D4N", "MN"}
        if (
            not isinstance(rows, list)
            or len(rows) < 2
            or not required.issubset(rows[0])
        ):
            raise SourceValidationError("Schema PAM alterado", code="schema_drift")
        records: list[AgricultureRecord] = []
        for row in rows[1:]:
            municipality = str(row["D1C"])
            year = int(row["D3C"])
            if (
                municipality not in self.municipalities
                or year not in self.years
                or str(row["D2C"]) != "214"
            ):
                raise SourceValidationError(
                    "Linha PAM fora do recorte", code="domain_mismatch"
                )
            raw = str(row.get("V", "")).strip()
            try:
                value = None if raw in {"", "..", "...", "-", "X"} else Decimal(raw)
            except InvalidOperation as exc:
                raise SourceValidationError(
                    "Valor PAM inválido", code="invalid_numeric"
                ) from exc
            records.append(
                AgricultureRecord(
                    municipality_ibge_code=municipality,
                    year=year,
                    product_code=str(row["D4C"]),
                    product_name=str(row["D4N"]),
                    value=value,
                    unit=str(row["MN"]),
                    availability_status="available"
                    if value is not None
                    else "unavailable",
                    source_url=payload.url,
                )
            )
        return records

    def validate(self, records: list[AgricultureRecord]) -> None:
        keys = [(r.municipality_ibge_code, r.year, r.product_code) for r in records]
        if not records:
            raise SourceValidationError("PAM sem linhas", code="empty_dataset")
        if len(keys) != len(set(keys)):
            raise SourceValidationError(
                "PAM contém chaves duplicadas", code="duplicate_key"
            )
        for municipality in self.municipalities:
            if not any(
                item.municipality_ibge_code == municipality and item.value is not None
                for item in records
            ):
                raise SourceValidationError(
                    "PAM sem produto publicado para município",
                    code="missing_municipality",
                    details={"municipality": municipality},
                )

    def upsert(
        self, db: Session, records: list[AgricultureRecord], snapshot: SourceSnapshot
    ) -> None:
        for record in records:
            key = f"{record.municipality_ibge_code}:{record.year}:{record.product_code}:214"
            previous = db.scalar(
                select(AgricultureFact)
                .where(
                    AgricultureFact.source_system == "sidra_pam",
                    AgricultureFact.source_key == key,
                )
                .order_by(desc(AgricultureFact.revision))
                .limit(1)
            )
            if (
                previous is not None
                and previous.value == record.value
                and previous.availability_status == record.availability_status
                and previous.product_name == record.product_name
            ):
                continue
            db.add(
                AgricultureFact(
                    id=uuid.uuid4(),
                    source_system="sidra_pam",
                    source_key=key,
                    municipality_ibge_code=record.municipality_ibge_code,
                    reference_year=record.year,
                    product_code=record.product_code,
                    product_name=record.product_name,
                    metric_code="production_quantity",
                    value=record.value,
                    unit=record.unit,
                    availability_status=record.availability_status,
                    source_document_url=record.source_url,
                    snapshot_id=snapshot.id,
                    revision=1 if previous is None else previous.revision + 1,
                )
            )
        _publish_dataset(db, snapshot)


@dataclass(slots=True)
class BoundaryRecord:
    municipality_ibge_code: str
    geometry: dict[str, Any]
    bbox: list[float]
    source_url: str


class IbgeBoundaryAdapter(SourceAdapter):
    source_name = "ibge_boundaries"
    dataset_code = "ibge_municipality_boundaries"
    base_url = "https://servicodados.ibge.gov.br/api/v3/malhas/municipios"
    crs = "EPSG:4674"

    def __init__(self, *, raw_data_dir: Path, municipalities: set[str]):
        super().__init__(raw_data_dir=raw_data_dir)
        self.municipalities = municipalities

    def discover(self) -> dict[str, Any]:
        return {
            "format": "GeoJSON",
            "crs": self.crs,
            "quality": "minima",
            "geography": "municipality",
        }

    def fetch(self) -> list[FetchedPayload]:
        payloads = []
        for code in sorted(self.municipalities):
            url = f"{self.base_url}/{code}?formato=application/vnd.geo+json&qualidade=minima"
            response = self.get(url, timeout=60)
            if len(response.content) > 5_000_000:
                raise SourceValidationError(
                    "GeoJSON excede limite", code="resource_size"
                )
            payloads.append(
                FetchedPayload(
                    content=response.content,
                    url=str(response.url),
                    fetched_at=datetime.now(UTC),
                    original_format="geojson",
                    response_headers=self.selected_headers(response),
                    persist_raw=True,
                    resource_version="ibge-malhas-minima-epsg4674",
                )
            )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[BoundaryRecord]:
        try:
            document = json.loads(payload.read_bytes())
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "GeoJSON inválido", code="invalid_json"
            ) from exc
        code = payload.url.split("/municipios/", 1)[1].split("?", 1)[0]
        if document.get("type") == "FeatureCollection":
            features = document.get("features") or []
            if (
                len(features) != 1
                or features[0].get("properties", {}).get("codarea") != code
            ):
                raise SourceValidationError(
                    "FeatureCollection municipal incompatível", code="domain_mismatch"
                )
            geometry = features[0].get("geometry") or {}
        else:
            geometry = document
        if geometry.get("type") not in {"Polygon", "MultiPolygon"}:
            raise SourceValidationError(
                "Geometria municipal inesperada", code="schema_drift"
            )
        if code not in self.municipalities:
            raise SourceValidationError("Malha fora do recorte", code="domain_mismatch")
        return [
            BoundaryRecord(code, geometry, _bbox(geometry["coordinates"]), payload.url)
        ]

    def validate(self, records: list[BoundaryRecord]) -> None:
        if len(records) != 1 or len(records[0].bbox) != 4:
            raise SourceValidationError(
                "Malha municipal incompleta", code="invalid_geometry"
            )

    def upsert(
        self, db: Session, records: list[BoundaryRecord], snapshot: SourceSnapshot
    ) -> None:
        for record in records:
            key = f"municipality:{record.municipality_ibge_code}:minimum"
            previous = db.scalar(
                select(GeospatialAsset)
                .where(
                    GeospatialAsset.source_system == "ibge_malhas",
                    GeospatialAsset.source_key == key,
                )
                .order_by(desc(GeospatialAsset.revision))
                .limit(1)
            )
            if previous is not None and previous.geometry == record.geometry:
                continue
            db.add(
                GeospatialAsset(
                    id=uuid.uuid4(),
                    source_system="ibge_malhas",
                    source_key=key,
                    geo_type="municipality",
                    geo_code=record.municipality_ibge_code,
                    reference_date=snapshot.fetched_at.date(),
                    crs=self.crs,
                    geometry=record.geometry,
                    bbox=record.bbox,
                    source_document_url=record.source_url,
                    snapshot_id=snapshot.id,
                    revision=1 if previous is None else previous.revision + 1,
                )
            )
        _publish_dataset(db, snapshot)


def _bbox(value: Any) -> list[float]:
    points: list[tuple[float, float]] = []

    def visit(node: Any) -> None:
        if (
            isinstance(node, list)
            and len(node) >= 2
            and isinstance(node[0], (int, float))
            and isinstance(node[1], (int, float))
        ):
            points.append((float(node[0]), float(node[1])))
            return
        if isinstance(node, list):
            for child in node:
                visit(child)

    visit(value)
    if not points:
        return []
    xs, ys = zip(*points, strict=True)
    return [min(xs), min(ys), max(xs), max(ys)]


def _publish_dataset(db: Session, snapshot: SourceSnapshot) -> None:
    dataset = db.get(Dataset, snapshot.dataset_id)
    if dataset is not None:
        dataset.publication_status = "published"
        entries = db.scalars(
            select(CatalogEntry).where(CatalogEntry.dataset_id == dataset.id)
        )
        for entry in entries:
            entry.review_status = "validated_and_published"
            entry.decision_reason = "Conector homologado e carga validada/publicada."
            entry.last_checked_at = snapshot.fetched_at
