from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.models import (
    Agency,
    BudgetAccount,
    Contract,
    Dataset,
    FiscalStatement,
    Procurement,
    Source,
    SourceSnapshot,
    Transfer,
)

router = APIRouter(prefix="/api/v1/transparency", tags=["transparency"])
DbSession = Annotated[Session, Depends(get_db)]


def _money(value: Decimal | None) -> str | None:
    return format(value, "f") if value is not None else None


def _latest(model: Any):
    return (
        select(model.source_system, model.source_key, func.max(model.revision).label("revision"))
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


def _source(db: Session, snapshot_id: Any, document_url: str) -> dict[str, Any]:
    row = db.execute(
        select(SourceSnapshot, Dataset, Source)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .where(SourceSnapshot.id == snapshot_id)
    ).first()
    if row is None:
        return {"document_url": document_url}
    snapshot, dataset, source = row
    return {
        "dataset": dataset.code,
        "provider": source.provider,
        "license": source.license,
        "source_status": source.source_status,
        "connector_status": source.connector_status,
        "document_url": document_url,
        "retrieved_from": snapshot.url,
        "retrieved_at": snapshot.fetched_at,
        "published_at": snapshot.published_at,
        "sha256": snapshot.sha256,
    }


def _page(db: Session, statement: Any, *, limit: int, offset: int) -> tuple[list[Any], int]:
    count = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery())) or 0
    return list(db.scalars(statement.offset(offset).limit(limit))), count


def _dataset_source(db: Session, code: str) -> dict[str, Any]:
    row = db.execute(
        select(Dataset, Source)
        .join(Source, Source.id == Dataset.source_id)
        .where(Dataset.code == code)
    ).first()
    if row is None:
        return {"dataset": code, "availability": "not_configured"}
    dataset, source = row
    return {
        "dataset": dataset.code,
        "provider": source.provider,
        "url": source.source_url,
        "license": source.license,
        "source_status": source.source_status,
        "connector_status": dataset.connector_status,
        "publication_status": dataset.publication_status,
    }


@router.get("/overview")
def overview(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    year: int = Query(datetime.now(UTC).year, ge=2000, le=2100),
    period: int | None = Query(None, ge=1, le=12),
) -> dict[str, Any]:
    expense_statement = _current(FiscalStatement).where(
        FiscalStatement.source_system == "tcesp_expense",
        FiscalStatement.municipality_ibge_code == municipality,
        FiscalStatement.reference_year == year,
    )
    revenue_statement = _current(FiscalStatement).where(
        FiscalStatement.source_system == "tcesp_revenue",
        FiscalStatement.municipality_ibge_code == municipality,
        FiscalStatement.reference_year == year,
    )
    if period is not None:
        expense_statement = expense_statement.where(FiscalStatement.reference_period == period)
        revenue_statement = revenue_statement.where(FiscalStatement.reference_period == period)
    expenses = expense_statement.subquery()
    phases = db.execute(
        select(expenses.c.column_code, func.sum(expenses.c.amount))
        .group_by(expenses.c.column_code)
        .order_by(expenses.c.column_code)
    ).all()
    revenues = revenue_statement.subquery()
    revenue_total = db.scalar(select(func.sum(revenues.c.amount)))

    procurement_statement = _current(Procurement).where(
        Procurement.municipality_ibge_code == municipality,
        Procurement.procurement_year == year,
    )
    contract_statement = _current(Contract).where(
        Contract.municipality_ibge_code == municipality,
        Contract.contract_year == year,
    )
    procurement_count = (
        db.scalar(select(func.count()).select_from(procurement_statement.subquery())) or 0
    )
    contract_count = db.scalar(select(func.count()).select_from(contract_statement.subquery())) or 0
    return {
        "municipality_ibge_code": municipality,
        "year": year,
        "period": period,
        "revenue_collected": _money(revenue_total),
        "expense_phases": [{"phase": phase, "amount": _money(amount)} for phase, amount in phases],
        "procurements": procurement_count,
        "contracts": contract_count,
        "availability": {
            "revenue": "available" if revenue_total is not None else "unavailable",
            "expenses": "available" if phases else "unavailable",
            "procurements": "available" if procurement_count else "unavailable",
            "contracts": "available" if contract_count else "unavailable",
        },
        "sources": [
            _dataset_source(db, "tcesp_revenues"),
            _dataset_source(db, "tcesp_expenses"),
            _dataset_source(db, "pncp_procurements"),
            _dataset_source(db, "pncp_contracts"),
        ],
        "methodology": (
            "Receita arrecadada e eventos de despesa TCE-SP são somados somente dentro do "
            "mesmo exercício e recorte mensal. Empenho, liquidação, pagamento, reforço e "
            "anulação permanecem separados; valores Siconfi não são adicionados aos totais."
        ),
    }


@router.get("/fiscal-statements")
def fiscal_statements(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    source: str | None = None,
    statement_type: str | None = None,
    year: int | None = None,
    period: int | None = None,
    agency: str | None = Query(None, max_length=160),
    account: str | None = Query(None, max_length=160),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = (
        _current(FiscalStatement)
        .join(Agency, Agency.id == FiscalStatement.agency_id)
        .join(BudgetAccount, BudgetAccount.id == FiscalStatement.budget_account_id)
    )
    for column, value in (
        (FiscalStatement.municipality_ibge_code, municipality),
        (FiscalStatement.source_system, source),
        (FiscalStatement.statement_type, statement_type),
        (FiscalStatement.reference_year, year),
        (FiscalStatement.reference_period, period),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if agency:
        statement = statement.where(Agency.name.ilike(f"%{agency.strip()}%"))
    if account:
        term = f"%{account.strip()}%"
        statement = statement.where(
            or_(BudgetAccount.name.ilike(term), BudgetAccount.account_code.ilike(term))
        )
    statement = statement.order_by(
        FiscalStatement.reference_year.desc(), FiscalStatement.source_key
    )
    rows, count = _page(db, statement, limit=limit, offset=offset)
    return {
        "items": [
            {
                "source_key": row.source_key,
                "municipality_ibge_code": row.municipality_ibge_code,
                "source_system": row.source_system,
                "statement_type": row.statement_type,
                "year": row.reference_year,
                "period": row.reference_period,
                "periodicity": row.periodicity,
                "annex": row.annex,
                "power": row.power,
                "column": row.column_code,
                "account": {
                    "code": (current := db.get(BudgetAccount, row.budget_account_id)).account_code,
                    "name": current.name,
                },
                "agency": db.get(Agency, row.agency_id).name if row.agency_id else None,
                "amount": _money(row.amount),
                "availability_status": row.availability_status,
                "revision": row.revision,
                "source": _source(db, row.snapshot_id, row.source_document_url),
            }
            for row in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "methodology": (
            "Linhas e fases contábeis permanecem separadas; fontes não são somadas entre si."
        ),
    }


@router.get("/procurements")
def procurements(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    agency: str | None = Query(None, max_length=160),
    sector: str | None = Query(None, max_length=100),
    year: int | None = None,
    status: str | None = Query(None, max_length=160),
    modality: str | None = Query(None, max_length=160),
    min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = _current(Procurement).join(Agency, Agency.id == Procurement.agency_id)
    for column, value in (
        (Procurement.municipality_ibge_code, municipality),
        (Procurement.sector, sector),
        (Procurement.procurement_year, year),
        (Procurement.status, status),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if agency:
        statement = statement.where(Agency.name.ilike(f"%{agency.strip()}%"))
    if modality:
        term = f"%{modality.strip()}%"
        statement = statement.where(
            or_(Procurement.modality_name.ilike(term), Procurement.modality_code == modality)
        )
    if min_amount is not None:
        statement = statement.where(Procurement.estimated_amount >= min_amount)
    if max_amount is not None:
        statement = statement.where(Procurement.estimated_amount <= max_amount)
    rows, count = _page(
        db,
        statement.order_by(Procurement.published_at.desc().nullslast(), Procurement.source_key),
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "source_key": row.source_key,
                "municipality_ibge_code": row.municipality_ibge_code,
                "year": row.procurement_year,
                "number": row.procurement_number,
                "process": row.process_number,
                "object": row.object_description,
                "agency": db.get(Agency, row.agency_id).name,
                "sector": row.sector,
                "modality": row.modality_name,
                "status": row.status,
                "estimated_amount": _money(row.estimated_amount),
                "homologated_amount": _money(row.homologated_amount),
                "proposal_start_at": row.proposal_start_at,
                "proposal_end_at": row.proposal_end_at,
                "published_at": row.published_at,
                "updated_at": row.source_updated_at,
                "revision": row.revision,
                "source": _source(db, row.snapshot_id, row.source_document_url),
            }
            for row in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "notice": (
            "Consulta descritiva; os registros não constituem indicação automática "
            "de irregularidade."
        ),
    }


@router.get("/contracts")
def contracts(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    agency: str | None = Query(None, max_length=160),
    year: int | None = None,
    status: str | None = Query(None, max_length=100),
    min_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    max_amount: Annotated[Decimal | None, Query(ge=0)] = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = _current(Contract).join(Agency, Agency.id == Contract.agency_id)
    for column, value in (
        (Contract.municipality_ibge_code, municipality),
        (Contract.contract_year, year),
        (Contract.status, status),
    ):
        if value is not None:
            statement = statement.where(column == value)
    if agency:
        statement = statement.where(Agency.name.ilike(f"%{agency.strip()}%"))
    if min_amount is not None:
        statement = statement.where(Contract.global_amount >= min_amount)
    if max_amount is not None:
        statement = statement.where(Contract.global_amount <= max_amount)
    rows, count = _page(
        db,
        statement.order_by(Contract.published_at.desc().nullslast(), Contract.source_key),
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "source_key": row.source_key,
                "procurement_source_key": row.procurement_source_key,
                "municipality_ibge_code": row.municipality_ibge_code,
                "year": row.contract_year,
                "number": row.contract_number,
                "object": row.object_description,
                "agency": db.get(Agency, row.agency_id).name,
                "status": row.status,
                "initial_amount": _money(row.initial_amount),
                "global_amount": _money(row.global_amount),
                "signed_at": row.signed_at,
                "validity_start": row.validity_start,
                "validity_end": row.validity_end,
                "supplier": None,
                "supplier_note": "Identidade suprimida até revisão LGPD do tipo de documento.",
                "revision": row.revision,
                "source": _source(db, row.snapshot_id, row.source_document_url),
            }
            for row in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/transfers")
def transfers(
    db: DbSession,
    municipality: str | None = Query(None, pattern=r"^\d{7}$"),
    year: int | None = None,
    transfer_type: str | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = _current(Transfer)
    for column, value in (
        (Transfer.municipality_ibge_code, municipality),
        (Transfer.reference_year, year),
        (Transfer.transfer_type, transfer_type),
    ):
        if value is not None:
            statement = statement.where(column == value)
    rows, count = _page(
        db,
        statement.order_by(Transfer.reference_year.desc(), Transfer.source_key),
        limit=limit,
        offset=offset,
    )
    return {
        "items": [
            {
                "source_key": row.source_key,
                "municipality_ibge_code": row.municipality_ibge_code,
                "year": row.reference_year,
                "type": row.transfer_type,
                "program_code": row.program_code,
                "program_name": row.program_name,
                "planned_amount": _money(row.planned_amount),
                "paid_amount": _money(row.paid_amount),
                "revision": row.revision,
                "source": _source(db, row.snapshot_id, row.source_document_url),
            }
            for row in rows
        ],
        "count": count,
        "limit": limit,
        "offset": offset,
        "notice": (
            "Sem dado publicado, o retorno permanece vazio; ausência nunca é convertida em zero."
        ),
    }


def _csv_response(filename: str, headers: list[str], rows: list[list[Any]]) -> Response:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    writer.writerows(rows)
    return Response(
        "\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/exports/procurements.csv")
def export_procurements_csv(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    year: int | None = None,
    limit: int = Query(5000, ge=1, le=10000),
) -> Response:
    statement = _current(Procurement).where(Procurement.municipality_ibge_code == municipality)
    if year is not None:
        statement = statement.where(Procurement.procurement_year == year)
    rows = db.execute(
        statement.join(SourceSnapshot, SourceSnapshot.id == Procurement.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .add_columns(SourceSnapshot.sha256, SourceSnapshot.fetched_at, Source.license)
        .order_by(Procurement.source_key)
        .limit(limit)
    ).all()
    return _csv_response(
        "contratacoes.csv",
        [
            "chave_fonte",
            "ano",
            "objeto",
            "modalidade",
            "status",
            "valor_estimado",
            "url_fonte",
            "sha256_snapshot",
            "coletado_em",
            "licenca_status",
        ],
        [
            [
                procurement.source_key,
                procurement.procurement_year,
                procurement.object_description,
                procurement.modality_name,
                procurement.status,
                _money(procurement.estimated_amount),
                procurement.source_document_url,
                sha256,
                fetched_at,
                license_status,
            ]
            for procurement, sha256, fetched_at, license_status in rows
        ],
    )


@router.get("/exports/fiscal-statements.csv")
def export_fiscal_csv(
    db: DbSession,
    municipality: str = Query(..., pattern=r"^\d{7}$"),
    year: int | None = None,
    period: int | None = Query(None, ge=1, le=12),
    source: str | None = None,
    limit: int = Query(5000, ge=1, le=10000),
) -> Response:
    statement = _current(FiscalStatement).where(
        FiscalStatement.municipality_ibge_code == municipality
    )
    if year is not None:
        statement = statement.where(FiscalStatement.reference_year == year)
    if period is not None:
        statement = statement.where(FiscalStatement.reference_period == period)
    if source is not None:
        statement = statement.where(FiscalStatement.source_system == source)
    rows = db.execute(
        statement.join(SourceSnapshot, SourceSnapshot.id == FiscalStatement.snapshot_id)
        .join(Dataset, Dataset.id == SourceSnapshot.dataset_id)
        .join(Source, Source.id == Dataset.source_id)
        .join(BudgetAccount, BudgetAccount.id == FiscalStatement.budget_account_id)
        .add_columns(
            BudgetAccount.account_code,
            SourceSnapshot.sha256,
            SourceSnapshot.fetched_at,
            Source.license,
        )
        .order_by(FiscalStatement.source_key)
        .limit(limit)
    ).all()
    return _csv_response(
        "demonstrativos-fiscais.csv",
        [
            "chave_fonte",
            "fonte",
            "tipo",
            "ano",
            "periodo",
            "conta",
            "coluna",
            "valor",
            "url_fonte",
            "sha256_snapshot",
            "coletado_em",
            "licenca_status",
        ],
        [
            [
                fiscal.source_key,
                fiscal.source_system,
                fiscal.statement_type,
                fiscal.reference_year,
                fiscal.reference_period,
                account_code,
                fiscal.column_code,
                _money(fiscal.amount),
                fiscal.source_document_url,
                sha256,
                fetched_at,
                license_status,
            ]
            for fiscal, account_code, sha256, fetched_at, license_status in rows
        ],
    )
