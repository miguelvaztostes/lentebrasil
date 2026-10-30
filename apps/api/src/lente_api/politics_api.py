from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import (
    Dataset,
    DeclaredAssetSummary,
    Municipality,
    PoliticalCandidacy,
    PoliticalMandate,
    PoliticalPerson,
    PoliticalScore,
    Source,
    SourceSnapshot,
)

router = APIRouter(prefix="/api/v1/politics", tags=["politics"])
DbSession = Annotated[Session, Depends(get_db)]


def _latest(model: Any):
    return (
        select(
            model.source_system,
            model.source_key,
            func.max(model.revision).label("revision"),
        )
        .group_by(model.source_system, model.source_key)
        .subquery()
    )


def _current(model: Any):
    latest = _latest(model)
    return select(model).join(
        latest,
        and_(
            model.source_system == latest.c.source_system,
            model.source_key == latest.c.source_key,
            model.revision == latest.c.revision,
        ),
    )


def _source(snapshot: SourceSnapshot, dataset: Dataset, source: Source) -> dict[str, Any]:
    return {
        "provider": source.provider,
        "dataset": dataset.code,
        "url": snapshot.url,
        "license": source.license,
        "retrieved_at": snapshot.fetched_at,
        "published_at": snapshot.published_at,
        "sha256": snapshot.sha256,
        "source_status": source.source_status,
        "connector_status": dataset.connector_status,
        "publication_status": dataset.publication_status,
    }


def _person(person: PoliticalPerson) -> dict[str, Any]:
    return {
        "id": str(person.id),
        "name": person.full_name,
        "ballot_name": person.ballot_name,
        "slug": person.slug,
        "photo_url": person.photo_url,
    }


@router.get("/politicians")
def politicians(
    db: DbSession,
    search: str | None = Query(None, min_length=2, max_length=120),
    state: str | None = Query(None, pattern=r"^[A-Za-z]{2}$"),
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    office: str | None = Query(None, max_length=80),
    party: str | None = Query(None, max_length=30),
    active: bool = True,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = (
        _current(PoliticalMandate)
        .join(PoliticalPerson, PoliticalPerson.id == PoliticalMandate.person_id)
        .join(SourceSnapshot, SourceSnapshot.id == PoliticalMandate.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(PoliticalPerson, SourceSnapshot, Dataset, Source)
    )
    if search:
        pattern = f"%{search}%"
        statement = statement.where(
            or_(
                PoliticalPerson.full_name.ilike(pattern),
                PoliticalPerson.ballot_name.ilike(pattern),
            )
        )
    if state:
        statement = statement.where(PoliticalMandate.state == state.upper())
    if municipality:
        statement = statement.where(PoliticalMandate.municipality_ibge_code == municipality)
    if office:
        statement = statement.where(PoliticalMandate.office_code == office)
    if party:
        statement = statement.where(PoliticalMandate.party_acronym == party.upper())
    if active:
        statement = statement.where(PoliticalMandate.active.is_(True))
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    rows = db.execute(
        statement.order_by(PoliticalPerson.ballot_name, PoliticalPerson.full_name)
        .offset(offset)
        .limit(limit)
    ).all()
    return {
        "items": [
            {
                "person": _person(person),
                "mandate": {
                    "id": str(mandate.id),
                    "office": {
                        "code": mandate.office_code,
                        "name": mandate.office_name,
                    },
                    "government_level": mandate.government_level,
                    "state": mandate.state,
                    "municipality_ibge_code": mandate.municipality_ibge_code,
                    "party": mandate.party_acronym,
                    "election_year": mandate.election_year,
                    "elected_status": mandate.elected_status,
                    "term_start": mandate.term_start,
                    "term_end": mandate.term_end,
                    "active": mandate.active,
                },
                "source": _source(snapshot, dataset, source),
            }
            for mandate, person, snapshot, dataset, source in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/representatives")
def representatives(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
) -> dict[str, Any]:
    city = db.get(Municipality, municipality)
    if city is None:
        raise HTTPException(status_code=404, detail="Município não encontrado")
    statement = (
        _current(PoliticalMandate)
        .join(PoliticalPerson, PoliticalPerson.id == PoliticalMandate.person_id)
        .add_columns(PoliticalPerson)
        .where(
            PoliticalMandate.active.is_(True),
            or_(
                PoliticalMandate.municipality_ibge_code == municipality,
                and_(
                    PoliticalMandate.municipality_ibge_code.is_(None),
                    PoliticalMandate.state == city.state,
                ),
                PoliticalMandate.government_level == "national",
            ),
        )
        .order_by(
            PoliticalMandate.government_level,
            PoliticalMandate.office_name,
            PoliticalPerson.ballot_name,
        )
    )
    rows = db.execute(statement).all()
    return {
        "municipality": {
            "ibge_code": city.ibge_code,
            "name": city.name,
            "state": city.state,
        },
        "items": [
            {
                "person": _person(person),
                "office": {
                    "code": mandate.office_code,
                    "name": mandate.office_name,
                    "level": mandate.government_level,
                },
                "party": mandate.party_acronym,
                "territory": {
                    "state": mandate.state,
                    "municipality_ibge_code": mandate.municipality_ibge_code,
                },
            }
            for mandate, person in rows
        ],
        "coverage": {
            "status": "available" if rows else "unavailable",
            "message": (
                "Representantes oficiais localizados nas fontes integradas."
                if rows
                else "Ainda não há mandatos validados para este território."
            ),
        },
    }


@router.get("/politicians/{person_id}")
def politician_detail(person_id: UUID, db: DbSession) -> dict[str, Any]:
    person = db.get(PoliticalPerson, person_id)
    if person is None:
        raise HTTPException(status_code=404, detail="Político não encontrado")
    mandates = list(
        db.scalars(
            _current(PoliticalMandate)
            .where(PoliticalMandate.person_id == person_id)
            .order_by(PoliticalMandate.election_year.desc())
        )
    )
    candidacies = list(
        db.scalars(
            _current(PoliticalCandidacy)
            .where(PoliticalCandidacy.person_id == person_id)
            .order_by(PoliticalCandidacy.election_year.desc())
        )
    )
    candidacy_ids = [item.id for item in candidacies]
    assets = (
        list(
            db.scalars(
                _current(DeclaredAssetSummary).where(
                    DeclaredAssetSummary.candidacy_id.in_(candidacy_ids)
                )
            )
        )
        if candidacy_ids
        else []
    )
    scores = list(
        db.scalars(
            select(PoliticalScore)
            .where(PoliticalScore.person_id == person_id)
            .order_by(PoliticalScore.reference_end.desc())
        )
    )
    return {
        "person": _person(person),
        "mandates": [
            {
                "office": item.office_name,
                "office_code": item.office_code,
                "government_level": item.government_level,
                "state": item.state,
                "municipality_ibge_code": item.municipality_ibge_code,
                "party": item.party_acronym,
                "election_year": item.election_year,
                "term_start": item.term_start,
                "term_end": item.term_end,
                "active": item.active,
            }
            for item in mandates
        ],
        "candidacies": [
            {
                "id": str(item.id),
                "election_year": item.election_year,
                "office": item.office_name,
                "party": item.party_acronym,
                "registration_status": item.registration_status,
                "election_result": item.election_result,
                "vote_count": item.vote_count,
            }
            for item in candidacies
        ],
        "declared_assets": [
            {
                "candidacy_id": str(item.candidacy_id),
                "election_year": item.election_year,
                "category": {
                    "code": item.asset_type_code,
                    "name": item.asset_type_name,
                },
                "count": item.asset_count,
                "total_amount": format(item.total_amount, "f"),
            }
            for item in assets
        ],
        "scores": [_score(item) for item in scores],
        "methodology_notice": (
            "Pontuações só são comparáveis dentro do mesmo cargo, legislatura e "
            "janela. Cobertura inferior a 80% não gera posição de ranking."
        ),
    }


def _score(score: PoliticalScore) -> dict[str, Any]:
    coverage = float(score.coverage_ratio)
    return {
        "peer_group": score.peer_group,
        "reference_start": score.reference_start,
        "reference_end": score.reference_end,
        "methodology_version": score.methodology_version,
        "score": format(score.score, "f"),
        "rank": score.rank if coverage >= 0.8 else None,
        "peer_count": score.peer_count if coverage >= 0.8 else None,
        "coverage_ratio": format(score.coverage_ratio, "f"),
        "components": score.components,
        "caveats": score.caveats,
        "rankable": coverage >= 0.8,
        "calculated_at": score.calculated_at,
    }


@router.get("/ranking")
def ranking(
    db: DbSession,
    peer_group: str = Query(..., min_length=3, max_length=180),
    methodology_version: str | None = Query(None, max_length=60),
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    statement = (
        select(PoliticalScore, PoliticalPerson)
        .join(PoliticalPerson, PoliticalPerson.id == PoliticalScore.person_id)
        .where(
            PoliticalScore.peer_group == peer_group,
            PoliticalScore.coverage_ratio >= 0.8,
        )
    )
    if methodology_version:
        statement = statement.where(PoliticalScore.methodology_version == methodology_version)
    rows = db.execute(
        statement.order_by(PoliticalScore.score.desc(), PoliticalPerson.full_name).limit(limit)
    ).all()
    return {
        "items": [{"person": _person(person), "score": _score(score)} for score, person in rows],
        "peer_group": peer_group,
        "methodology": (
            "Ranking descritivo de atuação, não recomendação eleitoral. Somente pares "
            "do mesmo cargo e período, com cobertura mínima de 80%."
        ),
    }
