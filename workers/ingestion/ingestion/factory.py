from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any

from lente_api.models import (
    Agency,
    GeoCodeMapping,
    GeoUnit,
    HealthEpidemiology,
    Municipality,
)
from sqlalchemy import select
from sqlalchemy.orm import Session

from ingestion.adapters.cnes import CnesAdapter
from ingestion.adapters.datasus_health import (
    AnsBeneficiariesAdapter,
    CnesServicesAdapter,
    SiaProductionAdapter,
    SihProductionAdapter,
)
from ingestion.adapters.education import InepCensoEscolarAdapter, InepIdebAdapter
from ingestion.adapters.federal_education import (
    FndePnaeAdapter,
    InepSaebAdapter,
    normalize_fnde_municipality_name,
)
from ingestion.adapters.health import (
    CnesBedsAdapter,
    SimMortalityAdapter,
    SinascBirthsAdapter,
    SiopsHealthExpenseAdapter,
)
from ingestion.adapters.horizontal import IbgeBoundaryAdapter, IbgePamAdapter
from ingestion.adapters.ibge import IbgePopulationAdapter
from ingestion.adapters.ibge_munic import IbgeMunicAdapter
from ingestion.adapters.sectors import (
    IbgePibAdapter,
    NovoCagedAdapter,
    SenatranFleetAdapter,
)
from ingestion.adapters.sectors import (
    normalize_name as normalize_sector_name,
)
from ingestion.adapters.siconfi import SiconfiRreoAdapter
from ingestion.adapters.transparency import (
    PncpContractAdapter,
    PncpProcurementAdapter,
    SiconfiStatementAdapter,
    TceSpExpenseAdapter,
    TceSpRevenueAdapter,
    normalize_name,
)

LEGACY_MUNICIPALITY = "3543402"


def select_municipalities(
    db: Session,
    *,
    municipality_codes: list[str] | None = None,
    uf: str | None = None,
    national: bool = False,
) -> list[Municipality]:
    if sum(bool(item) for item in (municipality_codes, uf, national)) > 1:
        raise ValueError("Use apenas um recorte: municípios, UF ou cobertura nacional")
    statement = select(Municipality)
    if municipality_codes:
        statement = statement.where(Municipality.ibge_code.in_(municipality_codes))
    elif uf:
        statement = statement.where(Municipality.state == uf.upper())
    elif national:
        # The municipal directory contains only the official IBGE units loaded by
        # the geography bootstrap. Municipality intentionally has no parallel
        # "active" flag; lifecycle is represented in the geography history.
        pass
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
    national: bool = False,
    start_year: int | None = None,
    end_year: int | None = None,
    periods: list[int] | None = None,
    annexes: list[str] | None = None,
    resource_version: str | None = None,
    batch_size: int = 50,
    max_requests: int = 250,
    start_date: str | date | None = None,
    end_date: str | date | None = None,
    modalities: list[int] | None = None,
    entity_identifiers: list[str] | None = None,
    update_mode: bool = True,
) -> Any:
    municipalities = select_municipalities(
        db,
        municipality_codes=municipality_codes,
        uf=uf,
        national=national,
    )
    codes = [item.ibge_code for item in municipalities]
    today = datetime.now(UTC).date()
    if source.startswith("ibge_munic_"):
        return IbgeMunicAdapter(
            raw_data_dir=raw_data_dir,
            municipalities=set(codes),
            profile=source.removeprefix("ibge_munic_"),
        )
    parsed_start = (
        date.fromisoformat(start_date) if isinstance(start_date, str) else start_date
    )
    parsed_end = date.fromisoformat(end_date) if isinstance(end_date, str) else end_date
    window_end = parsed_end or today
    window_start = parsed_start or (window_end - timedelta(days=1))
    if source == "ibge_pib":
        first = start_year if start_year is not None else 2021
        last = end_year if end_year is not None else 2023
        return IbgePibAdapter(
            raw_data_dir=raw_data_dir,
            municipalities=set(codes),
            years=list(range(first, last + 1)),
        )
    if source == "ibge_pam":
        first = start_year if start_year is not None else 2024
        last = end_year if end_year is not None else first
        if first < 1974 or last > today.year or first > last:
            raise ValueError("Janela anual PAM inválida")
        return IbgePamAdapter(
            raw_data_dir=raw_data_dir,
            municipalities=set(codes),
            years=list(range(first, last + 1)),
        )
    if source == "ibge_boundaries":
        return IbgeBoundaryAdapter(raw_data_dir=raw_data_dir, municipalities=set(codes))
    if source == "novo_caged":
        year = start_year if start_year is not None else 2025
        if end_year not in {None, year}:
            raise ValueError("Novo CAGED processa uma competência por execução")
        month = (periods or [12])[0]
        if len(periods or [12]) != 1 or not 1 <= month <= 12:
            raise ValueError("Novo CAGED exige exatamente um mês entre 1 e 12")
        mappings = db.execute(
            select(GeoCodeMapping.external_code, GeoUnit.code)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.valid_to.is_(None),
                GeoUnit.code.in_(codes),
            )
        ).all()
        return NovoCagedAdapter(
            raw_data_dir=raw_data_dir,
            municipality_crosswalk={
                external: canonical for external, canonical in mappings
            },
            year=year,
            month=month,
        )
    if source == "senatran_fleet":
        if start_year not in {None, 2026} or end_year not in {None, 2026}:
            raise ValueError("Apenas a competência homologada 2026-09 está disponível")
        official_names = db.execute(
            select(GeoUnit.code, GeoUnit.state, GeoUnit.name).where(
                GeoUnit.unit_type == "municipality",
                GeoUnit.code.in_(codes),
                GeoUnit.active.is_(True),
            )
        ).all()
        name_map = {
            (item.state, normalize_sector_name(item.name)): item.ibge_code
            for item in municipalities
        }
        name_map.update(
            {
                (state, normalize_sector_name(name)): code
                for code, state, name in official_names
            }
        )
        return SenatranFleetAdapter(
            raw_data_dir=raw_data_dir,
            municipality_names=name_map,
        )
    if source == "pncp":
        return PncpProcurementAdapter(
            raw_data_dir=raw_data_dir,
            selected_municipalities=set(codes),
            start_date=window_start,
            end_date=window_end,
            modalities=modalities or range(1, 20),
            max_requests=max_requests,
            update_mode=update_mode,
        )
    if source == "pncp_contracts":
        identifiers = entity_identifiers or list(
            db.scalars(
                select(Agency.entity_identifier).where(
                    Agency.source_system == "pncp",
                    Agency.municipality_ibge_code.in_(codes),
                    Agency.entity_identifier.is_not(None),
                )
            )
        )
        return PncpContractAdapter(
            raw_data_dir=raw_data_dir,
            selected_municipalities=set(codes),
            start_date=window_start,
            end_date=window_end,
            entity_identifiers=identifiers,
            max_requests=max_requests,
            update_mode=update_mode,
        )
    if source == "tcesp_revenues":
        if any(item.state != "SP" for item in municipalities):
            raise ValueError("TCE-SP só pode ser aplicado a municípios paulistas")
        first = start_year if start_year is not None else 2025
        last = end_year if end_year is not None else first
        return TceSpRevenueAdapter(
            raw_data_dir=raw_data_dir,
            municipality_names={
                normalize_name(item.name): item.ibge_code for item in municipalities
            },
            years=range(first, last + 1),
        )
    if source == "tcesp_expenses":
        if any(item.state != "SP" for item in municipalities):
            raise ValueError("TCE-SP só pode ser aplicado a municípios paulistas")
        first = start_year if start_year is not None else 2025
        last = end_year if end_year is not None else first
        return TceSpExpenseAdapter(
            raw_data_dir=raw_data_dir,
            municipalities={item.ibge_code: item.name for item in municipalities},
            years=range(first, last + 1),
            months=periods or range(1, 13),
            max_requests=max_requests,
        )
    if source in {"siconfi_rgf", "siconfi_dca"}:
        statement_type = source.removeprefix("siconfi_")
        default_year = 2025 if statement_type == "rgf" else 2024
        first = start_year if start_year is not None else default_year
        last = end_year if end_year is not None else first
        effective_annexes = (
            None
            if statement_type == "dca" and annexes == ["RREO-Anexo 01"]
            else annexes
        )
        selected_annexes = effective_annexes or (
            ["RGF-Anexo 01"] if statement_type == "rgf" else ["DCA-Anexo I-AB"]
        )
        if len(selected_annexes) != 1:
            raise ValueError(
                "Cada job fiscal Siconfi deve selecionar exatamente um anexo"
            )
        return SiconfiStatementAdapter(
            raw_data_dir=raw_data_dir,
            statement_type=statement_type,
            municipality_codes=codes,
            years=range(first, last + 1),
            periods=periods or [3],
            annex=selected_annexes[0],
            max_requests=max_requests,
        )
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
                item.ibge_code: {"name": item.name, "state": item.state}
                for item in municipalities
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
            municipality_crosswalk={
                external: canonical for external, canonical in mappings
            },
            selected_municipalities=set(codes),
            resource_version=resource_version,
        )
    if source == "sim_mortality":
        if start_year not in {None, 2024} or end_year not in {None, 2024}:
            raise ValueError("Somente o artefato definitivo SIM 2024 foi homologado")
        mappings = db.execute(
            select(GeoCodeMapping.external_code, GeoUnit.code)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.valid_to.is_(None),
                GeoUnit.active.is_(True),
            )
        ).all()
        published_municipalities = set(
            db.scalars(
                select(HealthEpidemiology.municipality_ibge_code)
                .where(
                    HealthEpidemiology.source_system == "sim",
                    HealthEpidemiology.municipality_ibge_code.in_(codes),
                )
                .distinct()
            )
        )
        return SimMortalityAdapter(
            raw_data_dir=raw_data_dir,
            municipality_crosswalk={
                external: canonical for external, canonical in mappings
            },
            selected_municipalities=set(codes),
            year=2024,
            allow_not_modified=set(codes) <= published_municipalities,
        )
    if source == "cnes_beds":
        mappings = db.execute(
            select(GeoCodeMapping.external_code, GeoUnit.code)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.valid_to.is_(None),
                GeoUnit.active.is_(True),
            )
        ).all()
        return CnesBedsAdapter(
            raw_data_dir=raw_data_dir,
            municipality_crosswalk={
                external: canonical for external, canonical in mappings
            },
            selected_municipalities=set(codes),
        )
    if source == "sinasc_births":
        if start_year not in {None, 2024} or end_year not in {None, 2024}:
            raise ValueError("Somente o artefato definitivo SINASC 2024 foi homologado")
        mappings = db.execute(
            select(GeoCodeMapping.external_code, GeoUnit.code)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.valid_to.is_(None),
                GeoUnit.active.is_(True),
            )
        ).all()
        return SinascBirthsAdapter(
            raw_data_dir=raw_data_dir,
            municipality_crosswalk={
                external: canonical for external, canonical in mappings
            },
            selected_municipalities=set(codes),
            year=2024,
        )
    if source == "siops_health_expenses":
        if start_year not in {None, 2025} or end_year not in {None, 2025}:
            raise ValueError("Somente o fechamento municipal SIOPS 2025 foi homologado")
        mappings = db.execute(
            select(GeoCodeMapping.external_code, GeoUnit.code)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.valid_to.is_(None),
                GeoUnit.active.is_(True),
            )
        ).all()
        return SiopsHealthExpenseAdapter(
            raw_data_dir=raw_data_dir,
            municipality_crosswalk={
                external: canonical for external, canonical in mappings
            },
            selected_municipalities=set(codes),
            year=2025,
        )
    if source in {
        "sih_production",
        "sia_production",
        "cnes_services",
        "ans_beneficiaries",
    }:
        if start_year not in {None, 2025} or end_year not in {None, 2025}:
            raise ValueError(
                "A competência homologada para este conector é dezembro de 2025"
            )
        mappings = db.execute(
            select(GeoCodeMapping.external_code, GeoUnit.code)
            .join(GeoUnit, GeoUnit.id == GeoCodeMapping.geo_unit_id)
            .where(
                GeoCodeMapping.code_system == "CNES_MUNICIPALITY",
                GeoCodeMapping.valid_to.is_(None),
                GeoUnit.active.is_(True),
            )
        ).all()
        common = {
            "raw_data_dir": raw_data_dir,
            "municipality_crosswalk": {
                external: canonical for external, canonical in mappings
            },
            "selected_municipalities": set(codes),
        }
        if source == "ans_beneficiaries":
            return AnsBeneficiariesAdapter(**common)
        adapter = {
            "sih_production": SihProductionAdapter,
            "sia_production": SiaProductionAdapter,
            "cnes_services": CnesServicesAdapter,
        }[source]
        return adapter(
            **common,
            selected_states={item.state for item in municipalities},
            year=2025,
            month=12,
        )
    if source == "censo_escolar":
        if start_year not in {None, 2024} or end_year not in {None, 2024}:
            raise ValueError(
                "Apenas o schema homologado do Censo Escolar 2024 está disponível"
            )
        return InepCensoEscolarAdapter(
            raw_data_dir=raw_data_dir, selected_municipalities=set(codes)
        )
    if source == "ideb":
        if start_year not in {None, 2025} or end_year not in {None, 2025}:
            raise ValueError("Apenas o pacote homologado do Ideb 2025 está disponível")
        return InepIdebAdapter(
            raw_data_dir=raw_data_dir, selected_municipalities=set(codes)
        )
    if source == "saeb":
        if start_year not in {None, 2023} or end_year not in {None, 2023}:
            raise ValueError("Apenas o pacote homologado do Saeb 2023 está disponível")
        return InepSaebAdapter(
            raw_data_dir=raw_data_dir, selected_municipalities=set(codes)
        )
    if source == "fnde_pnae":
        if start_year not in {None, 2024} or end_year not in {None, 2024}:
            raise ValueError(
                "Apenas a planilha homologada do PNAE 2024 está disponível"
            )
        return FndePnaeAdapter(
            raw_data_dir=raw_data_dir,
            selected_municipalities=set(codes),
            municipality_names={
                (
                    item.state,
                    normalize_fnde_municipality_name(item.name),
                ): item.ibge_code
                for item in municipalities
            },
        )
    raise ValueError(f"Fonte desconhecida: {source}")
