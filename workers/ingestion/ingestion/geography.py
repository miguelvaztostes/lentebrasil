from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Any

from lente_api.models import GeoCodeMapping, GeoUnit, GeoUnitVersion, Municipality
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.adapters.base import SourceAdapter, SourceValidationError

UF_URL = "https://servicodados.ibge.gov.br/api/v1/localidades/estados?orderBy=nome"
MUNICIPALITIES_URL = (
    "https://servicodados.ibge.gov.br/api/v1/localidades/municipios?orderBy=nome"
)


@dataclass(slots=True)
class GeographySyncSummary:
    states: int
    municipalities: int
    mappings: int
    deactivated: int
    source_hash: str


def _municipality_uf(row: dict[str, Any]) -> str | None:
    immediate = row.get("regiao-imediata") or {}
    intermediate = immediate.get("regiao-intermediaria") or {}
    micro = row.get("microrregiao") or {}
    meso = micro.get("mesorregiao") or {}
    return (intermediate.get("UF") or meso.get("UF") or {}).get("sigla")


def fetch_official_geographies() -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], str
]:
    states_response = SourceAdapter.get(UF_URL, timeout=60)
    municipalities_response = SourceAdapter.get(MUNICIPALITIES_URL, timeout=180)
    states = states_response.json()
    municipalities = municipalities_response.json()
    if not isinstance(states, list) or not isinstance(municipalities, list):
        raise SourceValidationError(
            "API de Localidades retornou estrutura inválida", code="schema_drift"
        )
    digest = hashlib.sha256(
        states_response.content + municipalities_response.content
    ).hexdigest()
    return states, municipalities, digest


def sync_geographies(
    db: Session,
    states: list[dict[str, Any]],
    municipalities: list[dict[str, Any]],
    *,
    source_hash: str,
    effective_from: date | None = None,
) -> GeographySyncSummary:
    effective_from = effective_from or datetime.now(UTC).date()
    country = db.scalar(
        select(GeoUnit).where(GeoUnit.unit_type == "country", GeoUnit.code == "BR")
    )
    if country is None:
        country = GeoUnit(
            id=uuid.uuid4(),
            unit_type="country",
            code="BR",
            name="Brasil",
            country_code="BR",
        )
        db.add(country)
        db.flush()

    state_by_uf: dict[str, GeoUnit] = {}
    for row in states:
        uf = str(row.get("sigla", "")).upper()
        name = str(row.get("nome", "")).strip()
        if len(uf) != 2 or not name:
            raise SourceValidationError(
                "UF inválida na API de Localidades", details={"row": row}
            )
        unit = db.scalar(
            select(GeoUnit).where(GeoUnit.unit_type == "state", GeoUnit.code == uf)
        )
        if unit is None:
            unit = GeoUnit(
                id=uuid.uuid4(),
                parent_id=country.id,
                unit_type="state",
                code=uf,
                name=name,
                state=uf,
                country_code="BR",
                active=True,
            )
            db.add(unit)
        else:
            unit.parent_id = country.id
            unit.name = name
            unit.state = uf
            unit.active = True
        state_by_uf[uf] = unit
    db.flush()

    received_codes: set[str] = set()
    external_cnes_codes: dict[str, str] = {}
    mapping_count = 0
    for row in municipalities:
        code = str(row.get("id", ""))
        name = str(row.get("nome", "")).strip()
        uf = _municipality_uf(row)
        if len(code) != 7 or not code.isdigit() or not name or uf not in state_by_uf:
            raise SourceValidationError(
                "Município inválido na API de Localidades",
                code="geographic_domain_mismatch",
                details={"id": code, "name": name, "uf": uf},
            )
        received_codes.add(code)
        municipal = db.get(Municipality, code)
        if municipal is None:
            db.add(Municipality(ibge_code=code, name=name, state=uf))
        else:
            municipal.name = name
            municipal.state = uf

        unit = db.scalar(
            select(GeoUnit).where(
                GeoUnit.unit_type == "municipality", GeoUnit.code == code
            )
        )
        if unit is None:
            unit = GeoUnit(
                id=uuid.uuid4(),
                parent_id=state_by_uf[uf].id,
                unit_type="municipality",
                code=code,
                name=name,
                state=uf,
                country_code="BR",
                active=True,
            )
            db.add(unit)
            db.flush()
        else:
            unit.parent_id = state_by_uf[uf].id
            unit.name = name
            unit.state = uf
            unit.active = True

        current_version = db.scalar(
            select(GeoUnitVersion)
            .where(
                GeoUnitVersion.geo_unit_id == unit.id,
                GeoUnitVersion.effective_to.is_(None),
            )
            .order_by(GeoUnitVersion.effective_from.desc())
            .limit(1)
        )
        if current_version is None or (current_version.name, current_version.state) != (
            name,
            uf,
        ):
            if current_version is not None:
                current_version.effective_to = effective_from
            db.add(
                GeoUnitVersion(
                    id=uuid.uuid4(),
                    geo_unit_id=unit.id,
                    name=name,
                    state=uf,
                    effective_from=effective_from,
                    source_hash=source_hash,
                    metadata_json={"source": MUNICIPALITIES_URL},
                )
            )

        cnes_code = code[:6]
        collision = external_cnes_codes.get(cnes_code)
        if collision and collision != code:
            raise SourceValidationError(
                "Código municipal CNES ambíguo",
                code="crosswalk_collision",
                details={"external_code": cnes_code, "ibge_codes": [collision, code]},
            )
        external_cnes_codes[cnes_code] = code
        for system, external in (
            ("IBGE_MUNICIPALITY", code),
            ("CNES_MUNICIPALITY", cnes_code),
        ):
            mapping = db.scalar(
                select(GeoCodeMapping).where(
                    GeoCodeMapping.code_system == system,
                    GeoCodeMapping.external_code == external,
                    GeoCodeMapping.valid_to.is_(None),
                )
            )
            if mapping is None:
                db.add(
                    GeoCodeMapping(
                        id=uuid.uuid4(),
                        geo_unit_id=unit.id,
                        code_system=system,
                        external_code=external,
                        valid_from=effective_from,
                        metadata_json={
                            "source": MUNICIPALITIES_URL,
                            "canonical_ibge_code": code,
                            "derivation": "explicit_crosswalk_from_current_ibge_registry"
                            if system == "CNES_MUNICIPALITY"
                            else "official_identifier",
                        },
                    )
                )
                mapping_count += 1
            elif mapping.geo_unit_id != unit.id:
                raise SourceValidationError(
                    "Crosswalk aponta para outro município",
                    code="crosswalk_collision",
                    details={"system": system, "external_code": external},
                )

    deactivated = 0
    existing = db.scalars(
        select(GeoUnit).where(GeoUnit.unit_type == "municipality")
    ).all()
    for unit in existing:
        if unit.code not in received_codes and unit.active:
            unit.active = False
            deactivated += 1
            current_version = db.scalar(
                select(GeoUnitVersion).where(
                    GeoUnitVersion.geo_unit_id == unit.id,
                    GeoUnitVersion.effective_to.is_(None),
                )
            )
            if current_version is not None:
                current_version.effective_to = effective_from
    db.commit()
    return GeographySyncSummary(
        states=len(state_by_uf),
        municipalities=len(received_codes),
        mappings=mapping_count,
        deactivated=deactivated,
        source_hash=source_hash,
    )


def sync_official_geographies(db: Session) -> GeographySyncSummary:
    states, municipalities, digest = fetch_official_geographies()
    return sync_geographies(db, states, municipalities, source_hash=digest)


def crosswalk_for_municipalities(
    db: Session, municipality_codes: list[str], code_system: str
) -> dict[str, str]:
    rows = db.execute(
        select(GeoCodeMapping.external_code, GeoUnit.code)
        .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
        .where(
            GeoCodeMapping.code_system == code_system,
            GeoCodeMapping.valid_to.is_(None),
            GeoUnit.code.in_(municipality_codes),
            GeoUnit.active.is_(True),
        )
    ).all()
    result = {canonical: external for external, canonical in rows}
    missing = sorted(set(municipality_codes) - set(result))
    if missing:
        raise SourceValidationError(
            "Municípios sem crosswalk ativo",
            code="missing_crosswalk",
            details={"code_system": code_system, "municipalities": missing},
        )
    return result


def geography_payload_hash(
    states: list[dict[str, Any]], municipalities: list[dict[str, Any]]
) -> str:
    body = json.dumps(
        [states, municipalities], ensure_ascii=False, sort_keys=True
    ).encode()
    return hashlib.sha256(body).hexdigest()
