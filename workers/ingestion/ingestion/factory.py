from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.siconfi import SiconfiRreoAdapter
from lente_api.models import GeoCodeMapping, GeoUnit, Municipality

LEGACY_MUNICIPALITY = "3543402"


def select_municipalities(
    db: Session, *, municipality_codes: list[str] | None = None, uf: str | None = None
) -> list[Municipality]:
    statement = select(Municipality)
    if municipality_codes:
        statement = statement.where(Municipality.ibge_code.in_(municipality_codes))
    elif uf:
        statement = statement.where(Municipality.state == uf.upper())
    else:
        statement = statement.where(Municipality.ibge_code == LEGACY_MUNICIPALITY)
    rows = list(db.scalars(statement.order_by(Municipality.ibge_code)))
    requested = set(municipality_codes or [])
    missing = sorted(requested - {row.ibge_code for row in rows})
    if missing:
        raise ValueError(f"Municípios não cadastrados: {', '.join(missing)}")
    if not rows:
        raise ValueError("Nenhum município corresponde ao recorte solicitado")
    return rows


def build_adapter(
    source: str,
    db: Session,
    *,
    raw_data_dir: Path,
    municipality_codes: list[str] | None = None,
    uf: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    periods: list[int] | None = None,
    annexes: list[str] | None = None,
    resource_version: str | None = None,
    batch_size: int = 50,
    max_requests: int = 250,
) -> Any:
    municipalities = select_municipalities(db, municipality_codes=municipality_codes, uf=uf)
    codes = [item.ibge_code for item in municipalities]
    if source == "ibge":
        period_range = None
        if start_year is not None or end_year is not None:
            start = start_year if start_year is not None else end_year
            end = end_year if end_year is not None else start_year
            assert start is not None and end is not None
            period_range = (start, end)
        return IbgePopulationAdapter(
            raw_data_dir=raw_data_dir,
            geographies={
                item.ibge_code: {"name": item.name, "state": item.state} for item in municipalities
            },
            period_range=period_range,
            resource_version=resource_version,
            batch_size=batch_size,
        )
    if source == "siconfi":
        default_start = int(os.environ.get("SICONFI_START_YEAR", "2022"))
        default_end = int(os.environ.get("SICONFI_END_YEAR", "2025"))
        first = start_year if start_year is not None else default_start
        last = end_year if end_year is not None else default_end
        if first > last:
            raise ValueError("Exercício inicial deve ser menor ou igual ao final")
        return SiconfiRreoAdapter(
            raw_data_dir=raw_data_dir,
            municipality_codes=codes,
            years=range(first, last + 1),
            periods=periods or [6],
            annexes=annexes or ["RREO-Anexo 01"],
            max_requests=max_requests,
        )
    if source == "cnes":
        mappings = db.execute(
            select(GeoCodeMapping.external_code, GeoUnit.code)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.valid_to.is_(None),
                GeoUnit.active.is_(True),
            )
        ).all()
        return CnesAdapter(
            raw_data_dir=raw_data_dir,
            municipality_crosswalk={external: canonical for external, canonical in mappings},
            selected_municipalities=set(codes),
            resource_version=resource_version,
        )
    raise ValueError(f"Fonte desconhecida: {source}")
