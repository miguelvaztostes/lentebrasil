from __future__ import annotations

import csv
import hashlib
import io
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from typing import Annotated, Any
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import Municipality, ResearchQuery
from lente_api.research import definition_by_code, research_definitions, research_points

router = APIRouter(prefix="/api/v1", tags=["research"])
DbSession = Annotated[Session, Depends(get_db)]
MAX_GEOS = 8


class SavedResearchParameters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    indicator: str = Field(min_length=3, max_length=180)
    geo_ids: list[str] = Field(min_length=1, max_length=MAX_GEOS)
    start_year: int | None = Field(None, ge=1900, le=2100)
    end_year: int | None = Field(None, ge=1900, le=2100)
    year: int | None = Field(None, ge=1900, le=2100)
    scope_key: str | None = Field(None, pattern=r"^[a-f0-9]{32,64}$")

    @field_validator("geo_ids")
    @classmethod
    def validate_geographies(cls, value: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value))
        if any(len(item) != 7 or not item.isdigit() for item in normalized):
            raise ValueError("geo_ids deve conter códigos IBGE municipais de sete dígitos")
        return normalized


def _geographies(value: str) -> list[str]:
    items = list(dict.fromkeys(part.strip() for part in value.split(",") if part.strip()))
    if not items or len(items) > MAX_GEOS:
        raise HTTPException(422, f"Selecione entre 1 e {MAX_GEOS} municípios")
    if any(len(item) != 7 or not item.isdigit() for item in items):
        raise HTTPException(422, "geo_ids deve conter códigos IBGE de sete dígitos")
    return items


def _require_geographies(db: Session, geo_ids: list[str]) -> None:
    found = set(
        db.scalars(select(Municipality.ibge_code).where(Municipality.ibge_code.in_(geo_ids)))
    )
    missing = sorted(set(geo_ids) - found)
    if missing:
        raise HTTPException(404, f"Municípios não encontrados: {', '.join(missing)}")


def _series(
    db: Session,
    indicator: str,
    geo_ids: str,
    start_year: int | None,
    end_year: int | None,
    scope_key: str | None,
    limit: int,
    offset: int,
) -> dict[str, Any]:
    if start_year and end_year and start_year > end_year:
        raise HTTPException(422, "start_year deve ser menor ou igual a end_year")
    geographies = _geographies(geo_ids)
    _require_geographies(db, geographies)
    try:
        return research_points(
            db,
            indicator=indicator,
            geo_ids=geographies,
            start_year=start_year,
            end_year=end_year,
            scope_key=scope_key,
            limit=limit,
            offset=offset,
        )
    except KeyError as exc:
        raise HTTPException(404, "Indicador de pesquisa não encontrado") from exc


@router.get("/research/indicators")
def indicator_dictionary(db: DbSession, response: Response) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300"
    items = research_definitions(db)
    domains: dict[str, dict[str, int]] = {}
    for item in items:
        domain = domains.setdefault(item["domain"], {"indicators": 0, "published": 0, "rows": 0})
        domain["indicators"] += 1
        domain["published"] += int(item["published"])
        domain["rows"] += item["row_count"]
    return {"items": items, "count": len(items), "domains": domains}


@router.get("/research/series")
def series(
    db: DbSession,
    response: Response,
    indicator: str = Query(..., max_length=180),
    geo_ids: str = Query(..., max_length=80),
    start_year: int | None = Query(None, ge=1900, le=2100),
    end_year: int | None = Query(None, ge=1900, le=2100),
    scope_key: str | None = Query(None, pattern=r"^[a-f0-9]{32,64}$"),
    limit: int = Query(500, ge=1, le=5000),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300"
    result = _series(db, indicator, geo_ids, start_year, end_year, scope_key, limit, offset)
    result["query"] = {
        "indicator": indicator,
        "geo_ids": _geographies(geo_ids),
        "start_year": start_year,
        "end_year": end_year,
        "scope_key": scope_key,
    }
    return result


@router.get("/compare")
def compare(
    db: DbSession,
    response: Response,
    indicator: str = Query(..., max_length=180),
    geo_ids: str = Query(..., max_length=80),
    year: int | None = Query(None, ge=1900, le=2100),
    period_start: date | None = None,
    scope_key: str | None = Query(None, pattern=r"^[a-f0-9]{32,64}$"),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300"
    geographies = _geographies(geo_ids)
    if len(geographies) < 2:
        raise HTTPException(422, "A comparação exige ao menos dois municípios")
    result = _series(
        db,
        indicator,
        geo_ids,
        year,
        year,
        scope_key,
        5000,
        0,
    )
    reasons: list[dict[str, str]] = []
    if not scope_key and len(result["scopes"]) > 1:
        reasons.append(
            {
                "code": "scope_required",
                "message": "Escolha o mesmo escopo para evitar comparar categorias diferentes.",
            }
        )
    points = result["items"]
    if period_start:
        points = [item for item in points if item["period_start"] == period_start]
    periods = {(item["period_start"], item["period_end"]) for item in points}
    if len(periods) > 1:
        reasons.append(
            {
                "code": "period_incompatible",
                "message": "Há mais de um período no recorte; selecione uma referência exata.",
            }
        )
    by_geo: dict[str, list[dict[str, Any]]] = {geo: [] for geo in geographies}
    for item in points:
        by_geo[item["geo_id"]].append(item)
    for geo, rows in by_geo.items():
        if not rows:
            reasons.append(
                {"code": "outside_coverage", "message": f"Sem dado publicado para {geo}."}
            )
        elif any(item["availability_status"] != "available" for item in rows):
            reasons.append(
                {"code": "suppressed_or_unavailable", "message": f"Dado indisponível em {geo}."}
            )
        elif len(rows) > 1:
            reasons.append(
                {"code": "ambiguous_scope", "message": f"Mais de uma linha compatível em {geo}."}
            )
    valid = not reasons
    return {
        "valid": valid,
        "reasons": reasons,
        "definition": result["definition"],
        "items": [rows[0] for rows in by_geo.values() if len(rows) == 1] if valid else [],
        "available_periods": [
            {"period_start": start, "period_end": end} for start, end in sorted(periods)
        ],
        "available_scopes": result["scopes"],
        "rule": "Mesmo indicador, unidade, escopo e período; nenhum ajuste silencioso.",
    }


@router.get("/coverage")
def coverage(
    db: DbSession,
    response: Response,
    indicator: str = Query(..., max_length=180),
    geo_ids: str = Query(..., max_length=80),
    year: int | None = Query(None, ge=1900, le=2100),
    scope_key: str | None = Query(None, pattern=r"^[a-f0-9]{32,64}$"),
) -> dict[str, Any]:
    response.headers["Cache-Control"] = "public, max-age=300"
    geographies = _geographies(geo_ids)
    filtered = _series(db, indicator, geo_ids, year, year, scope_key, 5000, 0)
    all_periods = (
        filtered
        if year is None
        else _series(db, indicator, geo_ids, None, None, scope_key, 5000, 0)
    )
    items = []
    for geo in geographies:
        rows = [item for item in filtered["items"] if item["geo_id"] == geo]
        historical = [item for item in all_periods["items"] if item["geo_id"] == geo]
        if any(item["availability_status"] == "available" for item in rows):
            state = "published"
            reason = "Dado publicado no período e escopo solicitados."
        elif rows:
            state = "suppressed"
            reason = "A fonte publicou a célula como suprimida ou indisponível."
        elif historical and year is not None:
            state = "incompatible_period"
            reason = "Há dado para o território, mas não no período solicitado."
        elif filtered["definition"]["row_count"]:
            state = "outside_coverage"
            reason = "O dado publicado não cobre este território/escopo."
        else:
            state = "source_identified_no_connector"
            reason = "Definição catalogada sem linha publicada no banco."
        items.append({"geo_id": geo, "state": state, "reason": reason})
    return {"indicator": filtered["definition"], "items": items}


@router.get("/research/export.json")
def export_json(
    db: DbSession,
    indicator: str,
    geo_ids: str,
    start_year: int | None = None,
    end_year: int | None = None,
    scope_key: str | None = None,
) -> dict[str, Any]:
    return _series(db, indicator, geo_ids, start_year, end_year, scope_key, 10_000, 0)


@router.get("/research/export.csv")
def export_csv(
    db: DbSession,
    indicator: str,
    geo_ids: str,
    start_year: int | None = None,
    end_year: int | None = None,
    scope_key: str | None = None,
) -> Response:
    result = _series(db, indicator, geo_ids, start_year, end_year, scope_key, 10_000, 0)
    output = io.StringIO()
    fields = [
        "indicator_code",
        "geo_id",
        "geo_name",
        "state",
        "period_start",
        "period_end",
        "scope_key",
        "scope",
        "value",
        "availability_status",
        "unit",
        "dataset",
        "provider",
        "license",
        "source_url",
        "sha256",
        "retrieved_at",
        "published_at",
        "revision",
    ]
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for item in result["items"]:
        writer.writerow({**item, "scope": json.dumps(item["scope"], ensure_ascii=False)})
    return Response(
        output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="lente-research.csv"'},
    )


@router.post("/research/queries", status_code=status.HTTP_201_CREATED)
def save_query(payload: SavedResearchParameters, db: DbSession) -> dict[str, Any]:
    if payload.start_year and payload.end_year and payload.start_year > payload.end_year:
        raise HTTPException(422, "start_year deve ser menor ou igual a end_year")
    _require_geographies(db, payload.geo_ids)
    if definition_by_code(db, payload.indicator) is None:
        raise HTTPException(404, "Indicador de pesquisa não encontrado")
    parameters = payload.model_dump(exclude_none=True)
    canonical = json.dumps(parameters, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    query = db.scalar(select(ResearchQuery).where(ResearchQuery.parameters_hash == digest))
    now = datetime.now(UTC)
    if query is None:
        recent = db.scalar(
            select(func.count(ResearchQuery.id)).where(
                ResearchQuery.created_at >= now - timedelta(hours=1)
            )
        )
        if (recent or 0) >= 120:
            raise HTTPException(429, "Quota de consultas salvas temporariamente excedida")
        query = ResearchQuery(
            id=uuid.uuid4(),
            slug=digest[:16],
            parameters_hash=digest,
            parameters=parameters,
            created_at=now,
            last_accessed_at=now,
            access_count=0,
        )
        db.add(query)
    db.commit()
    return _saved_query(query)


@router.get("/research/queries/{slug}")
def get_saved_query(slug: str, db: DbSession) -> dict[str, Any]:
    if len(slug) != 16 or any(character not in "0123456789abcdef" for character in slug):
        raise HTTPException(404, "Consulta não encontrada")
    query = db.scalar(select(ResearchQuery).where(ResearchQuery.slug == slug))
    if query is None:
        raise HTTPException(404, "Consulta não encontrada")
    query.last_accessed_at = datetime.now(UTC)
    query.access_count += 1
    db.commit()
    return _saved_query(query)


def _saved_query(query: ResearchQuery) -> dict[str, Any]:
    params: list[tuple[str, str | int]] = [
        ("indicador", query.parameters["indicator"]),
        ("municipios", ",".join(query.parameters["geo_ids"])),
    ]
    query_names = {
        "start_year": "inicio",
        "end_year": "fim",
        "scope_key": "escopo",
    }
    for key, public_name in query_names.items():
        if key in query.parameters:
            params.append((public_name, query.parameters[key]))
    if "year" in query.parameters:
        params.extend([("inicio", query.parameters["year"]), ("fim", query.parameters["year"])])
    return {
        "slug": query.slug,
        "parameters": query.parameters,
        "canonical_url": f"/pesquisa?{urlencode(params)}",
        "created_at": query.created_at,
        "access_count": query.access_count,
    }
