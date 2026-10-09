from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

import typer

from ingestion.adapters import ADAPTERS
from lente_api.database import SessionLocal
from lente_api.settings import get_settings

app = typer.Typer(help="Coletores oficiais do Lente Ribeirão", no_args_is_help=True)


def _run_one(source: str, *, dry_run: bool) -> dict:
    adapter_class = ADAPTERS[source]
    adapter = adapter_class(raw_data_dir=Path(get_settings().raw_data_dir))
    with SessionLocal() as db:
        return asdict(adapter.run(db, dry_run=dry_run))


@app.command()
def ingest(
    source: str = typer.Option(..., help="ibge, siconfi, cnes ou all"),
    dry_run: bool = typer.Option(False, help="Coleta e valida sem gravar no banco"),
) -> None:
    selected = list(ADAPTERS) if source == "all" else [source]
    unknown = [item for item in selected if item not in ADAPTERS]
    if unknown:
        raise typer.BadParameter(f"Fonte desconhecida: {', '.join(unknown)}")
    results = []
    failures = 0
    for item in selected:
        try:
            results.append(_run_one(item, dry_run=dry_run))
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


@app.command()
def health(
    source: str = typer.Option("all", help="ibge, siconfi, cnes ou all"),
) -> None:
    selected = list(ADAPTERS) if source == "all" else [source]
    results = {}
    for item in selected:
        if item not in ADAPTERS:
            raise typer.BadParameter(f"Fonte desconhecida: {item}")
        adapter = ADAPTERS[item](raw_data_dir=Path(get_settings().raw_data_dir))
        results[item] = adapter.health()
    typer.echo(json.dumps(results, ensure_ascii=False, default=str, indent=2))


if __name__ == "__main__":
    app()
