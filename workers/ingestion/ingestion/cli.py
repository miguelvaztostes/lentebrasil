from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer
from lente_api.database import SessionLocal
from lente_api.settings import get_settings

from ingestion.adapters import ADAPTERS
from ingestion.adapters.education import rollback_education_release
from ingestion.factory import build_adapter, select_municipalities
from ingestion.geography import sync_official_geographies
from ingestion.jobs import claim_next_job, execute_job, schedule_job

app = typer.Typer(help="Coletores oficiais multicípio do Lente Brasil", no_args_is_help=True)


def _split(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def _parameters(
    *,
    municipalities: str | None,
    uf: str | None,
    start_year: int | None,
    end_year: int | None,
    periods: str,
    annexes: str,
    resource_version: str | None,
    batch_size: int,
    max_requests: int,
    start_date: str | None,
    end_date: str | None,
    modalities: str,
    entity_identifiers: str,
    publication_mode: bool,
) -> dict:
    return {
        "municipality_codes": _split(municipalities),
        "uf": uf,
        "start_year": start_year,
        "end_year": end_year,
        "periods": [int(item) for item in (_split(periods) or [])] or None,
        "annexes": _split(annexes) or ["RREO-Anexo 01"],
        "resource_version": resource_version,
        "batch_size": batch_size,
        "max_requests": max_requests,
        "start_date": start_date,
        "end_date": end_date,
        "modalities": [int(item) for item in (_split(modalities) or [])] or None,
        "entity_identifiers": _split(entity_identifiers),
        "update_mode": not publication_mode,
    }


@app.command("geo-sync")
def geo_sync() -> None:
    """Sincroniza UFs, municípios e crosswalks a partir da API oficial do IBGE."""
    with SessionLocal() as db:
        result = sync_official_geographies(db)
    typer.echo(json.dumps(asdict(result), ensure_ascii=False, indent=2))


@app.command()
def ingest(
    source: str = typer.Option(
        ...,
        help=(
            "ibge, siconfi, cnes, educação, pncp, pncp_contracts, tcesp_revenues, "
            "tcesp_expenses, "
            "siconfi_rgf, siconfi_dca, sim_mortality, cnes_beds, sinasc_births, "
            "siops_health_expenses ou all"
        ),
    ),
    dry_run: bool = typer.Option(False, help="Coleta e valida sem gravar no banco"),
    municipalities: str | None = typer.Option(
        None,
        help="Códigos IBGE separados por vírgula; padrão compatível: Ribeirão Preto",
    ),
    uf: str | None = typer.Option(None, help="Seleciona os municípios cadastrados de uma UF"),
    start_year: int | None = None,
    end_year: int | None = None,
    periods: str = "",
    annexes: str = "RREO-Anexo 01",
    resource_version: str | None = None,
    batch_size: int = 50,
    max_requests: int = 250,
    start_date: str | None = typer.Option(None, help="Data ISO inicial para PNCP"),
    end_date: str | None = typer.Option(
        None, help="Data ISO final para PNCP (janela máxima: 31 dias)"
    ),
    modalities: str = typer.Option("", help="Códigos de modalidade PNCP separados por vírgula"),
    entity_identifiers: str = typer.Option("", help="CNPJs de órgãos PNCP separados por vírgula"),
    publication_mode: bool = typer.Option(
        False, help="Usa data de publicação em vez de atualização"
    ),
) -> None:
    selected = list(ADAPTERS) if source == "all" else [source]
    unknown = [item for item in selected if item not in ADAPTERS]
    if unknown:
        raise typer.BadParameter(f"Fonte desconhecida: {', '.join(unknown)}")
    parameters = _parameters(
        municipalities=municipalities,
        uf=uf,
        start_year=start_year,
        end_year=end_year,
        periods=periods,
        annexes=annexes,
        resource_version=resource_version,
        batch_size=batch_size,
        max_requests=max_requests,
        start_date=start_date,
        end_date=end_date,
        modalities=modalities,
        entity_identifiers=entity_identifiers,
        publication_mode=publication_mode,
    )
    results = []
    failures = 0
    for item in selected:
        try:
            with SessionLocal() as db:
                adapter = build_adapter(
                    item,
                    db,
                    raw_data_dir=Path(get_settings().raw_data_dir),
                    **parameters,
                )
                results.append(asdict(adapter.run(db, dry_run=dry_run)))
        except Exception as exc:  # noqa: BLE001 - report every requested source
            failures += 1
            results.append(
                {
                    "source": item,
                    "dry_run": dry_run,
                    "status": "failed",
                    "message": str(exc)[:1000],
                }
            )
    typer.echo(json.dumps(results, ensure_ascii=False, default=str, indent=2))
    if failures:
        raise typer.Exit(code=1)


@app.command("schedule")
def schedule(
    source: str = typer.Option(
        ...,
        help=(
            "ibge, siconfi, cnes, censo_escolar, ideb, saeb, fnde_pnae, "
            "sim_mortality, cnes_beds, sinasc_births ou siops_health_expenses"
        ),
    ),
    municipalities: str | None = None,
    uf: str | None = None,
    start_year: int | None = None,
    end_year: int | None = None,
    periods: str = "",
    annexes: str = "RREO-Anexo 01",
    resource_version: str | None = None,
    batch_size: int = 50,
    max_requests: int = 250,
    start_date: str | None = None,
    end_date: str | None = None,
    modalities: str = "",
    entity_identifiers: str = "",
    publication_mode: bool = False,
    recurring_seconds: int | None = typer.Option(None, min=3600),
    dry_run: bool = False,
) -> None:
    parameters = _parameters(
        municipalities=municipalities,
        uf=uf,
        start_year=start_year,
        end_year=end_year,
        periods=periods,
        annexes=annexes,
        resource_version=resource_version,
        batch_size=batch_size,
        max_requests=max_requests,
        start_date=start_date,
        end_date=end_date,
        modalities=modalities,
        entity_identifiers=entity_identifiers,
        publication_mode=publication_mode,
    )
    parameters.update({"recurring_seconds": recurring_seconds, "dry_run": dry_run})
    with SessionLocal() as db:
        if source == "siconfi":
            selected = select_municipalities(
                db,
                municipality_codes=parameters.pop("municipality_codes"),
                uf=parameters.pop("uf"),
            )
            first = start_year if start_year is not None else 2022
            last = end_year if end_year is not None else 2025
            jobs = []
            for municipality in selected:
                for year in range(first, last + 1):
                    for period in parameters["periods"]:
                        for annex in parameters["annexes"]:
                            unit = {
                                **parameters,
                                "municipality_codes": [municipality.ibge_code],
                                "start_year": year,
                                "end_year": year,
                                "periods": [period],
                                "annexes": [annex],
                                "max_requests": 1,
                            }
                            jobs.append(schedule_job(db, source, unit))
        else:
            jobs = [schedule_job(db, source, parameters)]
    typer.echo(
        json.dumps([{"job_key": job.job_key, "status": job.status} for job in jobs], indent=2)
    )


@app.command("work")
def work_once() -> None:
    with SessionLocal() as db:
        job = claim_next_job(db)
        if job is None:
            typer.echo(json.dumps({"status": "idle"}))
            return
        result = execute_job(db, job, raw_data_dir=Path(get_settings().raw_data_dir))
    typer.echo(json.dumps(result, ensure_ascii=False, default=str, indent=2))


@app.command()
def health(
    source: str = typer.Option(
        "all",
        help="Fonte registrada ou all; fontes fiscais podem exigir parâmetros explícitos",
    ),
    municipalities: str | None = None,
) -> None:
    selected = list(ADAPTERS) if source == "all" else [source]
    results = {}
    for item in selected:
        if item not in ADAPTERS:
            raise typer.BadParameter(f"Fonte desconhecida: {item}")
        with SessionLocal() as db:
            adapter = build_adapter(
                item,
                db,
                raw_data_dir=Path(get_settings().raw_data_dir),
                municipality_codes=_split(municipalities),
            )
            results[item] = adapter.health()
    typer.echo(json.dumps(results, ensure_ascii=False, default=str, indent=2))


@app.command("education-rollback")
def education_rollback(
    dataset: str = typer.Option(
        ...,
        help=(
            "inep_censo_escolar, inep_ideb_municipal, inep_saeb_municipal ou fnde_pnae_municipal"
        ),
    ),
    release: str = typer.Option(..., help="Chave exata do release publicado"),
) -> None:
    if dataset not in {
        "inep_censo_escolar",
        "inep_ideb_municipal",
        "inep_saeb_municipal",
        "fnde_pnae_municipal",
    }:
        raise typer.BadParameter("Dataset educacional inválido")
    with SessionLocal() as db:
        restored = rollback_education_release(db, dataset, release)
    typer.echo(json.dumps({"withdrawn": release, "restored": restored}, ensure_ascii=False))


if __name__ == "__main__":
    app()
