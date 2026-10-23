from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import tempfile
import time
import unicodedata
import uuid
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlencode, urlparse

import httpx
from dateutil.parser import parse as parse_datetime
from lente_api.models import (
    Agency,
    BudgetAccount,
    Contract,
    FiscalStatement,
    Procurement,
    SourceSnapshot,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ingestion.adapters.base import (
    USER_AGENT,
    FetchedPayload,
    SourceAdapter,
    SourceValidationError,
)

PNCP_OPENAPI_URL = "https://pncp.gov.br/pncp-consulta/v3/api-docs"
PNCP_BASE_URL = "https://pncp.gov.br/api/consulta"
PNCP_MODALITIES_URL = "https://pncp.gov.br/api/pncp/v1/modalidades?statusAtivo=true"
SICONFI_OPENAPI_URL = "https://apidatalake.tesouro.gov.br/docs/siconfi.yaml"
SICONFI_BASE_URL = "https://apidatalake.tesouro.gov.br/ords/cdwhprd/siconfi/tt"
TCESP_DATASETS_URL = "https://transparencia.tce.sp.gov.br/conjunto-de-dados"
TCESP_API_URL = "https://transparencia.tce.sp.gov.br/api/json"
TCESP_REVENUE_URL = "https://transparencia.tce.sp.gov.br/sites/default/files/conjunto-dados/receitas-{year}.zip"


def normalize_name(value: str) -> str:
    normalized = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    return re.sub(r"[^A-Z0-9]+", " ", normalized.upper()).strip()


def digits(value: Any) -> str:
    return re.sub(r"\D", "", str(value or ""))


def decimal_value(value: Any, *, brazilian: bool = False) -> Decimal | None:
    if value is None or str(value).strip() in {"", "-", "..."}:
        return None
    raw = str(value).strip()
    if brazilian:
        raw = raw.replace(".", "").replace(",", ".")
    else:
        raw = raw.replace(",", ".")
    try:
        return Decimal(raw)
    except InvalidOperation as exc:
        raise SourceValidationError(
            f"Quantia monetária inválida: {value!r}", code="invalid_money"
        ) from exc


def parsed_datetime(value: Any) -> datetime | None:
    if value is None or not str(value).strip():
        return None
    parsed = parse_datetime(str(value))
    return (
        parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)
    )


def parsed_date(value: Any) -> date | None:
    parsed = parsed_datetime(value)
    return parsed.date() if parsed else None


@dataclass(slots=True)
class AgencyRecord:
    source_system: str
    source_key: str
    name: str
    entity_identifier: str | None
    unit_code: str | None
    municipality_code: str | None
    state: str | None
    power: str | None = None
    sphere: str | None = None


@dataclass(slots=True)
class ProcurementRecord:
    source_key: str
    municipality_code: str | None
    agency: AgencyRecord
    year: int
    number: str | None
    process: str | None
    object_description: str
    modality_code: str | None
    modality_name: str | None
    status: str | None
    estimated_amount: Decimal | None
    homologated_amount: Decimal | None
    proposal_start_at: datetime | None
    proposal_end_at: datetime | None
    published_at: datetime | None
    updated_at: datetime | None
    document_url: str


@dataclass(slots=True)
class ContractRecord:
    source_key: str
    procurement_source_key: str | None
    municipality_code: str | None
    agency: AgencyRecord
    year: int
    number: str | None
    object_description: str
    initial_amount: Decimal | None
    global_amount: Decimal | None
    signed_at: date | None
    validity_start: date | None
    validity_end: date | None
    published_at: datetime | None
    updated_at: datetime | None
    document_url: str


@dataclass(slots=True)
class FiscalRecord:
    source_system: str
    source_key: str
    municipality_code: str
    agency: AgencyRecord
    statement_type: str
    year: int
    period: int | None
    periodicity: str | None
    annex: str | None
    power: str | None
    column_code: str | None
    account_code: str
    account_name: str
    account_type: str | None
    hierarchy: dict[str, Any]
    amount: Decimal | None
    document_url: str
    source_published_at: datetime | None


class _PncpBaseAdapter(SourceAdapter):
    allowed_host = "pncp.gov.br"
    page_size = 50

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        selected_municipalities: set[str],
        start_date: date,
        end_date: date,
        max_requests: int = 250,
        update_mode: bool = True,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        if start_date > end_date:
            raise ValueError("Data inicial deve ser menor ou igual à final")
        if (end_date - start_date).days > 31:
            raise ValueError("A janela PNCP não pode exceder 31 dias por trabalho")
        self.selected_municipalities = selected_municipalities
        self.start_date = start_date
        self.end_date = end_date
        self.max_requests = max_requests
        self.update_mode = update_mode
        self.pages_fetched = 0
        self.last_updated_at: datetime | None = None
        self.last_source_key: str | None = None

    def discover(self) -> dict[str, Any]:
        response = self.get(PNCP_OPENAPI_URL, timeout=60)
        document = response.json()
        required_paths = {
            "/v1/contratacoes/publicacao",
            "/v1/contratacoes/atualizacao",
            "/v1/contratos",
            "/v1/contratos/atualizacao",
        }
        if not required_paths.issubset(document.get("paths", {})):
            raise SourceValidationError(
                "Contrato PNCP alterado", code="pncp_schema_changed"
            )
        return {
            "openapi": PNCP_OPENAPI_URL,
            "authentication": "consulta pública sem token",
            "selected_municipalities": sorted(self.selected_municipalities),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
        }

    def checkpoint_metadata(self) -> dict[str, Any]:
        return {
            "window_end": self.end_date.isoformat(),
            "last_source_updated_at": (
                self.last_updated_at.isoformat() if self.last_updated_at else None
            ),
            "last_source_key": self.last_source_key,
            "pages_fetched": self.pages_fetched,
        }

    @staticmethod
    def _payload(response: httpx.Response, *, version: str) -> FetchedPayload:
        return FetchedPayload(
            content=response.content,
            url=str(response.url),
            fetched_at=datetime.now(UTC),
            original_format="json",
            response_headers=SourceAdapter.selected_headers(response),
            published_at=SourceAdapter.header_datetime(response, "last-modified"),
            persist_raw=True,
            resource_version=version,
        )

    def _get_page(self, path: str, parameters: dict[str, Any]) -> httpx.Response:
        if self.pages_fetched >= self.max_requests:
            raise SourceValidationError(
                "PNCP excedeu o limite explícito de requisições", code="request_limit"
            )
        url = f"{PNCP_BASE_URL}{path}?{urlencode(parameters)}"
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname != self.allowed_host:
            raise SourceValidationError(
                "URL PNCP não permitida", code="unsafe_source_url"
            )
        response = self.get(url, timeout=90)
        self.pages_fetched += 1
        return response

    @staticmethod
    def _envelope(payload: FetchedPayload) -> tuple[list[dict[str, Any]], int, int]:
        try:
            envelope = json.loads(payload.read_bytes())
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Resposta PNCP inválida", code="invalid_json"
            ) from exc
        data = envelope.get("data") if isinstance(envelope, dict) else None
        pages = envelope.get("totalPaginas") if isinstance(envelope, dict) else None
        page = envelope.get("numeroPagina") if isinstance(envelope, dict) else None
        if (
            not isinstance(data, list)
            or not isinstance(pages, int)
            or not isinstance(page, int)
        ):
            raise SourceValidationError(
                "Envelope PNCP alterado", code="pncp_schema_changed"
            )
        return data, pages, page

    def _agency(self, row: dict[str, Any]) -> AgencyRecord:
        entity = row.get("orgaoEntidade") or {}
        unit = row.get("unidadeOrgao") or {}
        cnpj = digits(entity.get("cnpj"))
        unit_code = str(unit.get("codigoUnidade") or "").strip() or None
        key = f"{cnpj}:{unit_code or 'sem-unidade'}"
        municipality = str(unit.get("codigoIbge") or "").strip() or None
        return AgencyRecord(
            source_system="pncp",
            source_key=key,
            name=str(
                unit.get("nomeUnidade")
                or entity.get("razaoSocial")
                or "Órgão não informado"
            ),
            entity_identifier=cnpj or None,
            unit_code=unit_code,
            municipality_code=municipality,
            state=str(unit.get("ufSigla") or "").strip() or None,
            power=str(entity.get("poderId") or "").strip() or None,
            sphere=str(entity.get("esferaId") or "").strip() or None,
        )

    @staticmethod
    def _upsert_agency(db: Session, record: AgencyRecord) -> Agency:
        agency = db.scalar(
            select(Agency).where(
                Agency.source_system == record.source_system,
                Agency.source_key == record.source_key,
            )
        )
        if agency is None:
            agency = Agency(
                id=uuid.uuid4(),
                source_system=record.source_system,
                source_key=record.source_key,
                name=record.name,
                entity_identifier=record.entity_identifier,
                unit_code=record.unit_code,
                municipality_ibge_code=record.municipality_code,
                state=record.state,
                power=record.power,
                sphere=record.sphere,
            )
            db.add(agency)
            db.flush()
        else:
            agency.name = record.name
            agency.municipality_ibge_code = record.municipality_code
            agency.state = record.state
        return agency


class PncpProcurementAdapter(_PncpBaseAdapter):
    source_name = "PNCP — contratações públicas"
    dataset_code = "pncp_procurements"

    def __init__(self, *, modalities: Iterable[int] = range(1, 20), **kwargs: Any):
        super().__init__(**kwargs)
        self.modalities = sorted({int(item) for item in modalities})
        if not self.modalities or any(
            item < 1 or item > 99 for item in self.modalities
        ):
            raise ValueError("Modalidades PNCP inválidas")

    def discover(self) -> dict[str, Any]:
        evidence = super().discover()
        modalities = self.get(PNCP_MODALITIES_URL, timeout=60).json()
        if not isinstance(modalities, list) or not all(
            "id" in item for item in modalities
        ):
            raise SourceValidationError(
                "Domínio de modalidades alterado", code="pncp_schema_changed"
            )
        evidence["modalities"] = self.modalities
        evidence["active_modalities"] = len(modalities)
        return evidence

    def fetch(self) -> list[FetchedPayload]:
        payloads: list[FetchedPayload] = []
        path = (
            "/v1/contratacoes/atualizacao"
            if self.update_mode
            else "/v1/contratacoes/publicacao"
        )
        for municipality in sorted(self.selected_municipalities):
            for modality in self.modalities:
                page = 1
                while True:
                    response = self._get_page(
                        path,
                        {
                            "dataInicial": self.start_date.strftime("%Y%m%d"),
                            "dataFinal": self.end_date.strftime("%Y%m%d"),
                            "codigoModalidadeContratacao": modality,
                            "codigoMunicipioIbge": municipality,
                            "pagina": page,
                            "tamanhoPagina": self.page_size,
                        },
                    )
                    payload = self._payload(
                        response,
                        version=(
                            f"municipality:{municipality}:modality:{modality}:page:{page}:"
                            f"{'update' if self.update_mode else 'publication'}"
                        ),
                    )
                    _, total_pages, returned_page = self._envelope(payload)
                    if returned_page != page:
                        raise SourceValidationError(
                            "Paginação PNCP inconsistente", code="pagination_mismatch"
                        )
                    payloads.append(payload)
                    if page >= total_pages:
                        break
                    page += 1
        return payloads

    def parse(self, payload: FetchedPayload) -> list[ProcurementRecord]:
        rows, _, _ = self._envelope(payload)
        records: list[ProcurementRecord] = []
        for row in rows:
            required = {
                "numeroControlePNCP",
                "anoCompra",
                "objetoCompra",
                "orgaoEntidade",
            }
            if not required.issubset(row):
                raise SourceValidationError(
                    "Schema PNCP alterado", code="pncp_schema_changed"
                )
            agency = self._agency(row)
            municipality = agency.municipality_code
            if municipality not in self.selected_municipalities:
                raise SourceValidationError(
                    "PNCP retornou município fora do recorte",
                    code="geographic_domain_mismatch",
                )
            source_key = str(row["numeroControlePNCP"])
            cnpj = digits((row.get("orgaoEntidade") or {}).get("cnpj"))
            year = int(row["anoCompra"])
            sequential = int(row.get("sequencialCompra") or 0)
            updated = parsed_datetime(
                row.get("dataAtualizacaoGlobal") or row.get("dataAtualizacao")
            )
            records.append(
                ProcurementRecord(
                    source_key=source_key,
                    municipality_code=municipality,
                    agency=agency,
                    year=year,
                    number=str(row.get("numeroCompra") or "").strip() or None,
                    process=str(row.get("processo") or "").strip() or None,
                    object_description=str(row["objetoCompra"]).strip(),
                    modality_code=str(row.get("modalidadeId") or "").strip() or None,
                    modality_name=str(row.get("modalidadeNome") or "").strip() or None,
                    status=str(row.get("situacaoCompraNome") or "").strip() or None,
                    estimated_amount=decimal_value(row.get("valorTotalEstimado")),
                    homologated_amount=decimal_value(row.get("valorTotalHomologado")),
                    proposal_start_at=parsed_datetime(row.get("dataAberturaProposta")),
                    proposal_end_at=parsed_datetime(
                        row.get("dataEncerramentoProposta")
                    ),
                    published_at=parsed_datetime(row.get("dataPublicacaoPncp")),
                    updated_at=updated,
                    document_url=f"https://pncp.gov.br/app/editais/{cnpj}/{year}/{sequential}",
                )
            )
            if updated and (
                self.last_updated_at is None or updated >= self.last_updated_at
            ):
                self.last_updated_at = updated
                self.last_source_key = source_key
        return records

    def validate(self, records: list[ProcurementRecord]) -> None:
        keys = [record.source_key for record in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError(
                "Contratação PNCP duplicada na página", code="duplicate_key"
            )
        if any(
            (record.estimated_amount is not None and record.estimated_amount < 0)
            or (record.homologated_amount is not None and record.homologated_amount < 0)
            for record in records
        ):
            raise SourceValidationError("Valor PNCP negativo", code="invalid_money")

    def upsert(
        self, db: Session, records: list[ProcurementRecord], snapshot: SourceSnapshot
    ) -> None:
        for record in records:
            agency = self._upsert_agency(db, record.agency)
            previous = db.scalar(
                select(Procurement)
                .where(
                    Procurement.source_system == "pncp",
                    Procurement.source_key == record.source_key,
                )
                .order_by(desc(Procurement.revision))
                .limit(1)
            )
            comparable = (
                record.updated_at,
                record.status,
                record.estimated_amount,
                record.homologated_amount,
                record.object_description,
            )
            if previous is not None and comparable == (
                previous.source_updated_at,
                previous.status,
                previous.estimated_amount,
                previous.homologated_amount,
                previous.object_description,
            ):
                continue
            revision = 1 if previous is None else previous.revision + 1
            if revision > 1:
                self.quality_warnings.append(
                    {
                        "code": "source_republication",
                        "details": {
                            "source_key": record.source_key,
                            "revision": revision,
                        },
                    }
                )
            db.add(
                Procurement(
                    id=uuid.uuid4(),
                    source_system="pncp",
                    source_key=record.source_key,
                    municipality_ibge_code=record.municipality_code,
                    agency_id=agency.id,
                    procurement_year=record.year,
                    procurement_number=record.number,
                    process_number=record.process,
                    object_description=record.object_description,
                    modality_code=record.modality_code,
                    modality_name=record.modality_name,
                    status=record.status,
                    sector=None,
                    estimated_amount=record.estimated_amount,
                    homologated_amount=record.homologated_amount,
                    proposal_start_at=record.proposal_start_at,
                    proposal_end_at=record.proposal_end_at,
                    published_at=record.published_at,
                    source_updated_at=record.updated_at,
                    source_document_url=record.document_url,
                    snapshot_id=snapshot.id,
                    revision=revision,
                )
            )
        db.flush()


class PncpContractAdapter(_PncpBaseAdapter):
    source_name = "PNCP — contratos e empenhos"
    dataset_code = "pncp_contracts"
    page_size = 100

    def __init__(self, *, entity_identifiers: Iterable[str], **kwargs: Any):
        super().__init__(**kwargs)
        self.entity_identifiers = sorted(
            {digits(item) for item in entity_identifiers if digits(item)}
        )
        if not self.entity_identifiers:
            raise ValueError(
                "Contratos PNCP exigem CNPJs de órgãos já homologados "
                "para evitar varredura nacional"
            )

    def fetch(self) -> list[FetchedPayload]:
        payloads: list[FetchedPayload] = []
        path = "/v1/contratos/atualizacao" if self.update_mode else "/v1/contratos"
        for cnpj in self.entity_identifiers:
            page = 1
            while True:
                response = self._get_page(
                    path,
                    {
                        "dataInicial": self.start_date.strftime("%Y%m%d"),
                        "dataFinal": self.end_date.strftime("%Y%m%d"),
                        "cnpjOrgao": cnpj,
                        "pagina": page,
                        "tamanhoPagina": self.page_size,
                    },
                )
                payload = self._payload(response, version=f"cnpj:{cnpj}:page:{page}")
                _, total_pages, returned_page = self._envelope(payload)
                if returned_page != page:
                    raise SourceValidationError(
                        "Paginação PNCP inconsistente", code="pagination_mismatch"
                    )
                payloads.append(payload)
                if page >= total_pages:
                    break
                page += 1
        return payloads

    def parse(self, payload: FetchedPayload) -> list[ContractRecord]:
        rows, _, _ = self._envelope(payload)
        records: list[ContractRecord] = []
        for row in rows:
            required = {
                "numeroControlePNCP",
                "anoContrato",
                "objetoContrato",
                "orgaoEntidade",
            }
            if not required.issubset(row):
                raise SourceValidationError(
                    "Schema de contratos PNCP alterado", code="pncp_schema_changed"
                )
            agency = self._agency(row)
            municipality = agency.municipality_code
            if municipality not in self.selected_municipalities:
                continue
            source_key = str(row["numeroControlePNCP"])
            cnpj = digits((row.get("orgaoEntidade") or {}).get("cnpj"))
            year = int(row["anoContrato"])
            sequential = int(row.get("sequencialContrato") or 0)
            updated = parsed_datetime(
                row.get("dataAtualizacaoGlobal") or row.get("dataAtualizacao")
            )
            records.append(
                ContractRecord(
                    source_key=source_key,
                    procurement_source_key=(
                        str(row.get("numeroControlePncpCompra"))
                        if row.get("numeroControlePncpCompra")
                        else None
                    ),
                    municipality_code=municipality,
                    agency=agency,
                    year=year,
                    number=str(row.get("numeroContratoEmpenho") or "").strip() or None,
                    object_description=str(row["objetoContrato"]).strip(),
                    initial_amount=decimal_value(row.get("valorInicial")),
                    global_amount=decimal_value(row.get("valorGlobal")),
                    signed_at=parsed_date(row.get("dataAssinatura")),
                    validity_start=parsed_date(row.get("dataVigenciaInicio")),
                    validity_end=parsed_date(row.get("dataVigenciaFim")),
                    published_at=parsed_datetime(row.get("dataPublicacaoPncp")),
                    updated_at=updated,
                    document_url=f"https://pncp.gov.br/app/contratos/{cnpj}/{year}/{sequential}",
                )
            )
            if updated and (
                self.last_updated_at is None or updated >= self.last_updated_at
            ):
                self.last_updated_at = updated
                self.last_source_key = source_key
        return records

    def validate(self, records: list[ContractRecord]) -> None:
        keys = [record.source_key for record in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError(
                "Contrato PNCP duplicado na página", code="duplicate_key"
            )
        if any(
            (record.initial_amount is not None and record.initial_amount < 0)
            or (record.global_amount is not None and record.global_amount < 0)
            for record in records
        ):
            raise SourceValidationError(
                "Valor contratual negativo", code="invalid_money"
            )

    def upsert(
        self, db: Session, records: list[ContractRecord], snapshot: SourceSnapshot
    ) -> None:
        for record in records:
            agency = self._upsert_agency(db, record.agency)
            previous = db.scalar(
                select(Contract)
                .where(
                    Contract.source_system == "pncp",
                    Contract.source_key == record.source_key,
                )
                .order_by(desc(Contract.revision))
                .limit(1)
            )
            comparable = (
                record.updated_at,
                record.initial_amount,
                record.global_amount,
                record.object_description,
                record.validity_end,
            )
            if previous is not None and comparable == (
                previous.source_updated_at,
                previous.initial_amount,
                previous.global_amount,
                previous.object_description,
                previous.validity_end,
            ):
                continue
            revision = 1 if previous is None else previous.revision + 1
            if revision > 1:
                self.quality_warnings.append(
                    {
                        "code": "source_republication",
                        "details": {
                            "source_key": record.source_key,
                            "revision": revision,
                        },
                    }
                )
            db.add(
                Contract(
                    id=uuid.uuid4(),
                    source_system="pncp",
                    source_key=record.source_key,
                    procurement_source_key=record.procurement_source_key,
                    municipality_ibge_code=record.municipality_code,
                    agency_id=agency.id,
                    supplier_id=None,
                    contract_year=record.year,
                    contract_number=record.number,
                    object_description=record.object_description,
                    status=None,
                    initial_amount=record.initial_amount,
                    global_amount=record.global_amount,
                    signed_at=record.signed_at,
                    validity_start=record.validity_start,
                    validity_end=record.validity_end,
                    published_at=record.published_at,
                    source_updated_at=record.updated_at,
                    source_document_url=record.document_url,
                    snapshot_id=snapshot.id,
                    revision=revision,
                )
            )
        db.flush()


class SiconfiStatementAdapter(SourceAdapter):
    source_name = "Siconfi — demonstrativo fiscal"

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        statement_type: str,
        municipality_codes: Iterable[str],
        years: Iterable[int],
        periods: Iterable[int] = (3,),
        annex: str | None = None,
        power: str = "E",
        periodicity: str = "Q",
        max_requests: int = 250,
        sleep_fn=time.sleep,
        monotonic_fn=time.monotonic,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        if statement_type not in {"rgf", "dca"}:
            raise ValueError("Demonstrativo Siconfi inválido")
        self.statement_type = statement_type
        self.dataset_code = f"siconfi_{statement_type}"
        self.source_name = f"Siconfi — {statement_type.upper()}"
        self.municipality_codes = sorted(set(municipality_codes))
        self.years = sorted({int(year) for year in years})
        self.periods = sorted({int(period) for period in periods})
        self.annex = annex
        self.power = power
        self.periodicity = periodicity
        self.max_requests = max_requests
        self.sleep_fn = sleep_fn
        self.monotonic_fn = monotonic_fn

    def discover(self) -> dict[str, Any]:
        body = self.get(SICONFI_OPENAPI_URL, timeout=60).text
        if f"/{self.statement_type}:" not in body or 'name: "id_ente"' not in body:
            raise SourceValidationError(
                "Contrato Siconfi alterado", code="contract_missing"
            )
        return {
            "openapi": SICONFI_OPENAPI_URL,
            "endpoint": f"{SICONFI_BASE_URL}/{self.statement_type}",
            "license": "Apache 2.0",
            "rate_limit": "1 request/second",
        }

    def _requests(self) -> list[dict[str, Any]]:
        requests: list[dict[str, Any]] = []
        for municipality in self.municipality_codes:
            for year in self.years:
                if self.statement_type == "rgf":
                    for period in self.periods:
                        params: dict[str, Any] = {
                            "an_exercicio": year,
                            "in_periodicidade": self.periodicity,
                            "nr_periodo": period,
                            "co_tipo_demonstrativo": "RGF",
                            "co_poder": self.power,
                            "id_ente": municipality,
                        }
                        if self.annex:
                            params["no_anexo"] = self.annex
                        requests.append(params)
                else:
                    params = {"an_exercicio": year, "id_ente": municipality}
                    if self.annex:
                        params["no_anexo"] = self.annex
                    requests.append(params)
        if len(requests) > self.max_requests:
            raise ValueError(
                f"Lote Siconfi exige {len(requests)} chamadas; limite {self.max_requests}"
            )
        return requests

    def fetch(self) -> list[FetchedPayload]:
        payloads: list[FetchedPayload] = []
        last_request_at: float | None = None
        for parameters in self._requests():
            now = self.monotonic_fn()
            if last_request_at is not None:
                remaining = 1.0 - (now - last_request_at)
                if remaining > 0:
                    self.sleep_fn(remaining)
            url = f"{SICONFI_BASE_URL}/{self.statement_type}?{urlencode(parameters)}"
            response = self.get(url, timeout=90)
            last_request_at = self.monotonic_fn()
            payloads.append(
                FetchedPayload(
                    content=response.content,
                    url=str(response.url),
                    fetched_at=datetime.now(UTC),
                    original_format="json",
                    response_headers=self.selected_headers(response),
                    published_at=self.header_datetime(response, "last-modified"),
                    persist_raw=True,
                )
            )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[FiscalRecord]:
        try:
            envelope = json.loads(payload.read_bytes())
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Resposta Siconfi inválida", code="invalid_json"
            ) from exc
        rows = envelope.get("items") if isinstance(envelope, dict) else None
        if not isinstance(rows, list) or not rows:
            raise SourceValidationError("Siconfi sem linhas", code="empty_payload")
        records: list[FiscalRecord] = []
        for row in rows:
            required = {
                "exercicio",
                "cod_ibge",
                "anexo",
                "cod_conta",
                "conta",
                "coluna",
            }
            if not required.issubset(row):
                raise SourceValidationError(
                    "Schema Siconfi alterado", code="schema_drift"
                )
            municipality = str(row["cod_ibge"])
            if municipality not in self.municipality_codes:
                raise SourceValidationError(
                    "Siconfi retornou ente fora do lote",
                    code="geographic_domain_mismatch",
                )
            account_code = str(row["cod_conta"])
            column = str(row["coluna"])
            period = int(row["periodo"]) if row.get("periodo") is not None else None
            power = (
                str(row.get("co_poder") or self.power)
                if self.statement_type == "rgf"
                else None
            )
            source_key = ":".join(
                [
                    self.statement_type,
                    municipality,
                    str(row["exercicio"]),
                    str(period or 0),
                    str(row["anexo"]),
                    power or "-",
                    account_code,
                    column,
                ]
            )
            institution = str(row.get("instituicao") or f"Ente {municipality}")
            records.append(
                FiscalRecord(
                    source_system=f"siconfi_{self.statement_type}",
                    source_key=source_key,
                    municipality_code=municipality,
                    agency=AgencyRecord(
                        source_system="siconfi",
                        source_key=f"{municipality}:{power or 'ente'}",
                        name=institution,
                        entity_identifier=municipality,
                        unit_code=None,
                        municipality_code=municipality,
                        state=str(row.get("uf") or "").strip() or None,
                        power=power,
                        sphere=str(row.get("esfera") or "").strip() or None,
                    ),
                    statement_type=self.statement_type,
                    year=int(row["exercicio"]),
                    period=period,
                    periodicity=str(row.get("periodicidade") or "").strip() or None,
                    annex=str(row["anexo"]),
                    power=power,
                    column_code=column,
                    account_code=account_code,
                    account_name=str(row["conta"]),
                    account_type=self.statement_type,
                    hierarchy={"rotulo": row.get("rotulo")},
                    amount=decimal_value(row.get("valor")),
                    document_url=payload.url,
                    source_published_at=payload.published_at,
                )
            )
        return records

    def validate(self, records: list[FiscalRecord]) -> None:
        keys = [record.source_key for record in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError("Linha fiscal duplicada", code="duplicate_key")

    def upsert(
        self, db: Session, records: list[FiscalRecord], snapshot: SourceSnapshot
    ) -> None:
        _upsert_fiscal_records(db, records, snapshot, self.quality_warnings)


class TceSpRevenueAdapter(SourceAdapter):
    source_name = "TCE-SP/Audesp — receitas municipais"
    dataset_code = "tcesp_revenues"
    expected_headers: ClassVar[list[str]] = [
        "id_rec_arrec_detalhe",
        "ano_exercicio",
        "ds_municipio",
        "ds_orgao",
        "mes_referencia",
        "mes_ref_extenso",
        "ds_poder",
        "ds_fonte_recurso",
        "ds_cd_aplicacao_fixo",
        "ds_cd_aplicacao_variavel",
        "ds_categoria",
        "ds_subcategoria",
        "ds_fonte",
        "ds_d1",
        "ds_dd2",
        "ds_d3",
        "ds_tipo",
        "vl_arrecadacao",
    ]

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        years: Iterable[int],
        municipality_names: dict[str, str],
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.years = sorted({int(year) for year in years})
        self.municipality_names = municipality_names
        if any(year < 2008 or year > datetime.now(UTC).year for year in self.years):
            raise ValueError("Exercício TCE-SP fora da série publicada")

    def discover(self) -> dict[str, Any]:
        page = self.get(TCESP_DATASETS_URL, timeout=60).text
        missing = [year for year in self.years if f"receitas-{year}.zip" not in page]
        if missing:
            raise SourceValidationError(
                "Arquivo TCE-SP não listado",
                code="resource_missing",
                details={"years": missing},
            )
        return {
            "catalog": TCESP_DATASETS_URL,
            "years": self.years,
            "format": "ZIP/CSV separado por ponto e vírgula; Windows-1252",
            "license_status": "não declarada na página auditada",
        }

    def fetch(self) -> list[FetchedPayload]:
        stage = self.raw_data_dir / "_stage"
        stage.mkdir(parents=True, exist_ok=True)
        payloads: list[FetchedPayload] = []
        for year in self.years:
            url = TCESP_REVENUE_URL.format(year=year)
            handle, name = tempfile.mkstemp(
                prefix=f"tcesp-revenues-{year}-", suffix=".zip", dir=stage
            )
            os.close(handle)
            target = Path(name)
            try:
                with (
                    httpx.Client(
                        headers={"User-Agent": USER_AGENT},
                        follow_redirects=True,
                        timeout=httpx.Timeout(300),
                    ) as client,
                    client.stream("GET", url) as response,
                ):
                    response.raise_for_status()
                    parsed = urlparse(str(response.url))
                    if (
                        parsed.scheme != "https"
                        or parsed.hostname != "transparencia.tce.sp.gov.br"
                    ):
                        raise SourceValidationError(
                            "Redirect TCE-SP não permitido", code="unsafe_redirect"
                        )
                    total = 0
                    with target.open("wb") as stream:
                        for chunk in response.iter_bytes(1024 * 1024):
                            total += len(chunk)
                            if total > 150 * 1024 * 1024:
                                raise SourceValidationError(
                                    "ZIP TCE-SP excede o limite",
                                    code="download_too_large",
                                )
                            stream.write(chunk)
                    headers = self.selected_headers(response)
                self._validate_zip(target, year)
                payloads.append(
                    FetchedPayload(
                        content=None,
                        file_path=target,
                        url=url,
                        fetched_at=datetime.now(UTC),
                        original_format="csv.zip",
                        response_headers=headers,
                        published_at=(
                            parse_datetime(headers["last-modified"]).astimezone(UTC)
                            if headers.get("last-modified")
                            else None
                        ),
                        persist_raw=True,
                        resource_version=f"exercise:{year}",
                    )
                )
            except Exception:
                target.unlink(missing_ok=True)
                raise
        return payloads

    @staticmethod
    def _validate_zip(path: Path, year: int) -> None:
        if not zipfile.is_zipfile(path):
            raise SourceValidationError(
                "Recurso TCE-SP não é ZIP", code="unexpected_format"
            )
        with zipfile.ZipFile(path) as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if len(members) != 1 or members[0].filename != f"receitas-{year}.csv":
                raise SourceValidationError(
                    "Conteúdo ZIP TCE-SP alterado", code="schema_drift"
                )
            member = members[0]
            if member.file_size > 2 * 1024**3 or ".." in Path(member.filename).parts:
                raise SourceValidationError(
                    "ZIP TCE-SP inseguro", code="unsafe_archive"
                )

    def parse(self, payload: FetchedPayload) -> list[FiscalRecord]:
        if payload.file_path is None:
            raise SourceValidationError("ZIP TCE-SP sem staging", code="empty_payload")
        year_match = re.search(r"exercise:(\d{4})", payload.resource_version or "")
        if not year_match:
            raise SourceValidationError(
                "Exercício TCE-SP ausente", code="period_mismatch"
            )
        year = int(year_match.group(1))
        records: list[FiscalRecord] = []
        with (
            zipfile.ZipFile(payload.file_path) as archive,
            archive.open(f"receitas-{year}.csv") as raw,
            io.TextIOWrapper(
                raw, encoding="cp1252", errors="strict", newline=""
            ) as text,
        ):
            reader = csv.DictReader(text, delimiter=";")
            if reader.fieldnames != self.expected_headers:
                raise SourceValidationError(
                    "Cabeçalho TCE-SP alterado",
                    code="schema_drift",
                    details={"received": reader.fieldnames},
                )
            for row in reader:
                municipality = self.municipality_names.get(
                    normalize_name(row["ds_municipio"])
                )
                if municipality is None:
                    continue
                account_code, _, account_label = row["ds_tipo"].partition(" - ")
                agency_name = row["ds_orgao"].strip()
                agency_key = f"{municipality}:{normalize_name(agency_name)}"
                records.append(
                    FiscalRecord(
                        source_system="tcesp_revenue",
                        source_key=str(row["id_rec_arrec_detalhe"]).strip(),
                        municipality_code=municipality,
                        agency=AgencyRecord(
                            source_system="tcesp",
                            source_key=agency_key,
                            name=agency_name,
                            entity_identifier=None,
                            unit_code=None,
                            municipality_code=municipality,
                            state="SP",
                            power=row["ds_poder"].strip() or None,
                        ),
                        statement_type="revenue_collected_monthly",
                        year=int(row["ano_exercicio"]),
                        period=int(row["mes_referencia"]),
                        periodicity="monthly",
                        annex=None,
                        power=row["ds_poder"].strip() or None,
                        column_code="vl_arrecadacao",
                        account_code=account_code.strip(),
                        account_name=(account_label or row["ds_tipo"]).strip(),
                        account_type="revenue",
                        hierarchy={
                            key: row[key]
                            for key in (
                                "ds_fonte_recurso",
                                "ds_cd_aplicacao_fixo",
                                "ds_cd_aplicacao_variavel",
                                "ds_categoria",
                                "ds_subcategoria",
                                "ds_fonte",
                                "ds_d1",
                                "ds_dd2",
                                "ds_d3",
                            )
                        },
                        amount=decimal_value(row["vl_arrecadacao"], brazilian=True),
                        document_url=payload.url,
                        source_published_at=payload.published_at,
                    )
                )
        return records

    def validate(self, records: list[FiscalRecord]) -> None:
        if not records:
            raise SourceValidationError(
                "TCE-SP sem linhas para o recorte", code="empty_selection"
            )
        keys = [record.source_key for record in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError("ID TCE-SP duplicado", code="duplicate_key")
        if any(record.year not in self.years for record in records):
            raise SourceValidationError(
                "Exercício TCE-SP divergente", code="period_mismatch"
            )

    def upsert(
        self, db: Session, records: list[FiscalRecord], snapshot: SourceSnapshot
    ) -> None:
        _upsert_fiscal_records(db, records, snapshot, self.quality_warnings)


class TceSpExpenseAdapter(SourceAdapter):
    """Collect monthly expense phases without retaining supplier personal data."""

    source_name = "TCE-SP/Audesp — despesas municipais agregadas"
    dataset_code = "tcesp_expenses"
    required_fields: ClassVar[set[str]] = {
        "orgao",
        "mes",
        "evento",
        "nr_empenho",
        "id_fornecedor",
        "nm_fornecedor",
        "dt_emissao_despesa",
        "vl_despesa",
    }
    phase_labels: ClassVar[dict[str, str]] = {
        "committed": "Empenhado",
        "liquidated": "Liquidado",
        "paid": "Pago",
        "reinforcement": "Reforço",
        "annulment": "Anulação",
    }
    month_names: ClassVar[dict[int, str]] = {
        1: "JANEIRO",
        2: "FEVEREIRO",
        3: "MARCO",
        4: "ABRIL",
        5: "MAIO",
        6: "JUNHO",
        7: "JULHO",
        8: "AGOSTO",
        9: "SETEMBRO",
        10: "OUTUBRO",
        11: "NOVEMBRO",
        12: "DEZEMBRO",
    }

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipalities: dict[str, str],
        years: Iterable[int],
        months: Iterable[int],
        max_requests: int = 250,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.municipalities = dict(sorted(municipalities.items()))
        self.years = sorted({int(year) for year in years})
        self.months = sorted({int(month) for month in months})
        self.max_requests = max_requests
        self._slugs: dict[str, str] = {}
        if not self.municipalities:
            raise ValueError("TCE-SP exige ao menos um município")
        if any(year < 2014 or year > datetime.now(UTC).year for year in self.years):
            raise ValueError("Exercício TCE-SP fora do intervalo auditado")
        if not self.months or any(month < 1 or month > 12 for month in self.months):
            raise ValueError("Mês TCE-SP inválido")
        if len(self.municipalities) * len(self.years) * len(self.months) > max_requests:
            raise ValueError("Recorte TCE-SP excede o limite de requisições")

    def discover(self) -> dict[str, Any]:
        url = f"{TCESP_API_URL}/municipios"
        response = self.get(url, timeout=60)
        self._assert_url(response)
        try:
            rows = response.json()
        except json.JSONDecodeError as exc:
            raise SourceValidationError(
                "Lista de municípios TCE-SP inválida", code="invalid_json"
            ) from exc
        if not isinstance(rows, list) or not all(
            isinstance(row, dict) and {"municipio", "municipio_extenso"}.issubset(row)
            for row in rows
        ):
            raise SourceValidationError(
                "Schema de municípios TCE-SP alterado", code="schema_drift"
            )
        available = {
            normalize_name(row["municipio_extenso"]): row["municipio"] for row in rows
        }
        missing: list[str] = []
        for code, name in self.municipalities.items():
            slug = available.get(normalize_name(name))
            if slug:
                self._slugs[code] = slug
            else:
                missing.append(code)
        if missing:
            raise SourceValidationError(
                "Município ausente na API TCE-SP",
                code="geography_missing",
                details={"municipality_codes": missing},
            )
        return {
            "catalog": "https://transparencia.tce.sp.gov.br/apis",
            "years": self.years,
            "months": self.months,
            "municipalities": sorted(self._slugs),
            "format": "JSON agregado antes da persistência",
            "privacy": "fornecedor e identificador descartados em memória",
            "license_status": "não declarada na página auditada",
        }

    @staticmethod
    def _assert_url(response: httpx.Response) -> None:
        parsed = urlparse(str(response.url))
        if parsed.scheme != "https" or parsed.hostname != "transparencia.tce.sp.gov.br":
            raise SourceValidationError(
                "Redirect TCE-SP não permitido", code="unsafe_redirect"
            )

    @staticmethod
    def _phase(value: Any) -> str:
        normalized = normalize_name(str(value))
        if normalized == "EMPENHADO":
            return "committed"
        if normalized == "VALOR LIQUIDADO":
            return "liquidated"
        if normalized == "VALOR PAGO":
            return "paid"
        if normalized.startswith("REFOR"):
            return "reinforcement"
        if normalized.startswith("ANULA"):
            return "annulment"
        raise SourceValidationError(
            "Evento de despesa TCE-SP desconhecido",
            code="schema_drift",
            details={"event": str(value)[:80]},
        )

    def fetch(self) -> list[FetchedPayload]:
        if not self._slugs:
            self.discover()
        payloads: list[FetchedPayload] = []
        for municipality_code, slug in self._slugs.items():
            for year in self.years:
                for month in self.months:
                    url = f"{TCESP_API_URL}/despesas/{slug}/{year}/{month}"
                    response = self.get(url, timeout=120)
                    self._assert_url(response)
                    upstream = response.content
                    upstream_sha256 = hashlib.sha256(upstream).hexdigest()
                    try:
                        rows = response.json()
                    except json.JSONDecodeError as exc:
                        raise SourceValidationError(
                            "Resposta de despesas TCE-SP inválida", code="invalid_json"
                        ) from exc
                    if not isinstance(rows, list):
                        raise SourceValidationError(
                            "Envelope de despesas TCE-SP alterado", code="schema_drift"
                        )
                    totals: dict[str, Decimal] = {}
                    counts: dict[str, int] = {}
                    for row in rows:
                        if not isinstance(
                            row, dict
                        ) or not self.required_fields.issubset(row):
                            raise SourceValidationError(
                                "Schema de despesas TCE-SP alterado",
                                code="schema_drift",
                            )
                        if normalize_name(row["mes"]) != self.month_names[month]:
                            raise SourceValidationError(
                                "Período de despesas TCE-SP divergente",
                                code="period_mismatch",
                                details={
                                    "requested_month": month,
                                    "received": str(row["mes"])[:40],
                                },
                            )
                        phase = self._phase(row["evento"])
                        amount = decimal_value(row["vl_despesa"], brazilian=True)
                        if amount is None:
                            raise SourceValidationError(
                                "Valor de despesa TCE-SP ausente", code="invalid_money"
                            )
                        totals[phase] = totals.get(phase, Decimal(0)) + amount
                        counts[phase] = counts.get(phase, 0) + 1
                    sanitized = {
                        "municipality_code": municipality_code,
                        "year": year,
                        "month": month,
                        "phases": [
                            {
                                "code": phase,
                                "label": self.phase_labels[phase],
                                "amount": format(totals[phase], "f"),
                                "source_rows": counts[phase],
                            }
                            for phase in sorted(totals)
                        ],
                        "source_rows": len(rows),
                        "upstream_sha256": upstream_sha256,
                        "privacy": "supplier fields discarded before snapshot",
                    }
                    content = json.dumps(
                        sanitized,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode()
                    headers = self.selected_headers(response)
                    headers.update(
                        {
                            "x-lente-upstream-sha256": upstream_sha256,
                            "x-lente-source-rows": str(len(rows)),
                            "x-lente-personal-fields": "discarded-before-snapshot",
                        }
                    )
                    payloads.append(
                        FetchedPayload(
                            content=content,
                            url=url,
                            fetched_at=datetime.now(UTC),
                            original_format="json",
                            response_headers=headers,
                            published_at=self.header_datetime(
                                response, "last-modified"
                            ),
                            persist_raw=True,
                            resource_version=f"{municipality_code}:{year}:{month}",
                        )
                    )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[FiscalRecord]:
        document = json.loads(payload.read_bytes())
        municipality = str(document["municipality_code"])
        year = int(document["year"])
        month = int(document["month"])
        agency = AgencyRecord(
            source_system="tcesp_expense",
            source_key=f"{municipality}:all-municipal-agencies",
            name="Órgãos municipais agregados — TCE-SP/Audesp",
            entity_identifier=None,
            unit_code=None,
            municipality_code=municipality,
            state="SP",
        )
        return [
            FiscalRecord(
                source_system="tcesp_expense",
                source_key=f"{municipality}:{year}:{month}:{phase['code']}",
                municipality_code=municipality,
                agency=agency,
                statement_type="expense_event_monthly",
                year=year,
                period=month,
                periodicity="monthly",
                annex=None,
                power=None,
                column_code=phase["code"],
                account_code=phase["code"],
                account_name=phase["label"],
                account_type="expense",
                hierarchy={"source_rows": phase["source_rows"]},
                amount=decimal_value(phase["amount"]),
                document_url=payload.url,
                source_published_at=payload.published_at,
            )
            for phase in document["phases"]
        ]

    def validate(self, records: list[FiscalRecord]) -> None:
        if not records:
            return
        keys = [record.source_key for record in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError("Fase TCE-SP duplicada", code="duplicate_key")
        if any(record.amount is None or record.amount < 0 for record in records):
            raise SourceValidationError(
                "Total de fase TCE-SP inválido", code="invalid_money"
            )

    def checkpoint_metadata(self) -> dict[str, Any]:
        return {
            "years": self.years,
            "months": self.months,
            "municipalities": sorted(self.municipalities),
        }

    def upsert(
        self, db: Session, records: list[FiscalRecord], snapshot: SourceSnapshot
    ) -> None:
        _upsert_fiscal_records(db, records, snapshot, self.quality_warnings)


def _upsert_fiscal_records(
    db: Session,
    records: list[FiscalRecord],
    snapshot: SourceSnapshot,
    warnings: list[dict[str, Any]],
) -> None:
    for record in records:
        agency = _PncpBaseAdapter._upsert_agency(db, record.agency)
        account = db.scalar(
            select(BudgetAccount).where(
                BudgetAccount.source_system == record.source_system,
                BudgetAccount.account_code == record.account_code,
            )
        )
        if account is None:
            account = BudgetAccount(
                id=uuid.uuid4(),
                source_system=record.source_system,
                account_code=record.account_code,
                name=record.account_name,
                account_type=record.account_type,
                hierarchy=record.hierarchy,
            )
            db.add(account)
            db.flush()
        previous = db.scalar(
            select(FiscalStatement)
            .where(
                FiscalStatement.source_system == record.source_system,
                FiscalStatement.source_key == record.source_key,
            )
            .order_by(desc(FiscalStatement.revision))
            .limit(1)
        )
        if (
            previous is not None
            and previous.amount == record.amount
            and previous.budget_account_id == account.id
            and previous.availability_status
            == ("available" if record.amount is not None else "unavailable")
        ):
            continue
        revision = 1 if previous is None else previous.revision + 1
        if revision > 1:
            warnings.append(
                {
                    "code": "source_republication",
                    "details": {"source_key": record.source_key, "revision": revision},
                }
            )
        db.add(
            FiscalStatement(
                id=uuid.uuid4(),
                source_system=record.source_system,
                source_key=record.source_key,
                municipality_ibge_code=record.municipality_code,
                agency_id=agency.id,
                budget_account_id=account.id,
                statement_type=record.statement_type,
                reference_year=record.year,
                reference_period=record.period,
                periodicity=record.periodicity,
                annex=record.annex,
                power=record.power,
                column_code=record.column_code,
                amount=record.amount,
                availability_status="available"
                if record.amount is not None
                else "unavailable",
                source_document_url=record.document_url,
                source_published_at=record.source_published_at,
                snapshot_id=snapshot.id,
                revision=revision,
            )
        )
    db.flush()
