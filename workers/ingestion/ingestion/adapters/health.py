from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import tempfile
import unicodedata
import zipfile
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import httpx
from lente_api.models import (
    BudgetAccount,
    Dataset,
    FiscalStatement,
    HealthBed,
    HealthEpidemiology,
    HealthEstablishment,
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

SIM_CATALOG_URL = "https://dadosabertos.saude.gov.br/dataset/sim"
SIM_2024_URL = (
    "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SIM/csv/DO24OPEN_csv.zip"
)
CNES_BEDS_CATALOG_URL = "https://dadosabertos.saude.gov.br/dataset/hospitais-e-leitos"
CNES_BEDS_2026_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2026.zip"
SINASC_CATALOG_URL = "https://dadosabertos.saude.gov.br/dataset/sistema-de-informacao-sobre-nascidos-vivos-sinasc"
SINASC_2024_URL = "https://s3.sa-east-1.amazonaws.com/ckan.saude.gov.br/SINASC/csv/SINASC_2024_csv.zip"
SIOPS_CATALOG_URL = "https://portalfns.saude.gov.br/siops/siops-downloads/"
SIOPS_2025_URL = (
    "https://portalfns.saude.gov.br/wp-content/uploads/2026/07/"
    "SIOPS-%E2%80%93-Despesas-por-Fonte-Subfuncao-Natureza-Municipais-"
    "2025-6o-Bimestre_202607211532.zip"
)

CID_CHAPTERS: tuple[tuple[str, str], ...] = (
    ("infectious", "Algumas doenças infecciosas e parasitárias"),
    ("neoplasms", "Neoplasias"),
    ("blood", "Doenças do sangue e transtornos imunitários"),
    ("endocrine", "Doenças endócrinas, nutricionais e metabólicas"),
    ("mental", "Transtornos mentais e comportamentais"),
    ("nervous", "Doenças do sistema nervoso"),
    ("eye", "Doenças do olho e anexos"),
    ("ear", "Doenças do ouvido e apófise mastoide"),
    ("circulatory", "Doenças do aparelho circulatório"),
    ("respiratory", "Doenças do aparelho respiratório"),
    ("digestive", "Doenças do aparelho digestivo"),
    ("skin", "Doenças da pele e tecido subcutâneo"),
    ("musculoskeletal", "Doenças do sistema osteomuscular"),
    ("genitourinary", "Doenças do aparelho geniturinário"),
    ("pregnancy", "Gravidez, parto e puerpério"),
    ("perinatal", "Afecções originadas no período perinatal"),
    ("congenital", "Malformações congênitas"),
    ("symptoms", "Sintomas, sinais e achados anormais"),
    ("injury", "Lesões, envenenamentos e outras consequências externas"),
    ("external", "Causas externas de morbidade e mortalidade"),
    ("special", "Códigos para propósitos especiais"),
    ("unknown", "Causa básica ausente ou não classificada"),
)

AGE_BANDS: tuple[tuple[str, str], ...] = (
    ("under_1", "Menos de 1 ano"),
    ("1_4", "1 a 4 anos"),
    ("5_14", "5 a 14 anos"),
    ("15_29", "15 a 29 anos"),
    ("30_59", "30 a 59 anos"),
    ("60_79", "60 a 79 anos"),
    ("80_plus", "80 anos ou mais"),
    ("unknown", "Idade não informada ou inválida"),
)


@dataclass(slots=True)
class EpidemiologyRecord:
    source_key: str
    municipality_code: str
    year: int
    category_code: str
    category_name: str
    age_band: str
    count: int | None
    raw_count: int
    availability_status: str
    disclosure_threshold: int
    document_url: str


@dataclass(slots=True)
class CnesBedRecord:
    municipality_code: str
    cnes_code: str
    name: str
    facility_type_code: str
    facility_type_name: str
    management_scope: str
    active: bool
    reference_date: date
    existing_count: int
    sus_count: int
    document_url: str


@dataclass(slots=True)
class SiopsExpenseRecord:
    source_key: str
    municipality_code: str
    year: int
    funding_source: str
    subfunction_code: str
    subfunction_name: str
    nature_code: str
    nature_name: str
    phase: str
    amount: Decimal
    homologated_at: datetime | None
    document_url: str


class SiopsHealthExpenseAdapter(SourceAdapter):
    """SIOPS municipal expenses, preserving phase and accounting hierarchy."""

    source_name = "Ministério da Saúde/FNS — SIOPS"
    dataset_code = "siops_health_expenses"
    allowed_host = "portalfns.saude.gov.br"
    max_download_bytes = 80_000_000
    max_uncompressed_bytes = 2_200_000_000
    required_fields: ClassVar[set[str]] = {
        "Ano",
        "Cod_IBGE",
        "Cód.Município",
        "Fonte",
        "Subfuncao",
        "Codigo",
        "Descricao",
        "Fase",
        "Valor",
        "Data_Homologacao",
    }
    phase_codes: ClassVar[dict[str, str]] = {
        "despesas orcadas": "budgeted",
        "dotacao inicial": "initial_budget",
        "dotacao atualizada": "updated_budget",
        "despesas empenhadas": "committed",
        "despesas liquidadas": "liquidated",
        "despesas pagas": "paid",
        "inscritas em restos a pagar nao processados": "unpaid_commitments",
    }

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[str, str],
        selected_municipalities: set[str],
        year: int = 2025,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        if year != 2025:
            raise ValueError("Somente o arquivo municipal SIOPS 2025 foi homologado")
        self.year = year
        self.selected = selected_municipalities
        self.external_selected = {
            external: canonical
            for external, canonical in municipality_crosswalk.items()
            if canonical in selected_municipalities
        }
        if set(self.external_selected.values()) != selected_municipalities:
            missing = sorted(
                selected_municipalities - set(self.external_selected.values())
            )
            raise ValueError(f"Municípios sem crosswalk SIOPS: {missing}")

    @classmethod
    def _validate_url(cls, value: str) -> None:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != cls.allowed_host
            or parsed.path
            != (
                "/wp-content/uploads/2026/07/"
                "SIOPS-%E2%80%93-Despesas-por-Fonte-Subfuncao-Natureza-"
                "Municipais-2025-6o-Bimestre_202607211532.zip"
            )
            or parsed.query
            or parsed.fragment
        ):
            raise SourceValidationError(
                "URL SIOPS não permitida", code="unsafe_source_url"
            )

    @staticmethod
    def _normalized(value: str) -> str:
        return (
            "".join(
                character
                for character in unicodedata.normalize("NFKD", value)
                if not unicodedata.combining(character)
            )
            .strip()
            .lower()
        )

    def discover(self) -> dict[str, Any]:
        self._validate_url(SIOPS_2025_URL)
        response = httpx.head(
            SIOPS_2025_URL,
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        self._validate_url(str(response.url))
        size = int(response.headers.get("content-length", "0"))
        if not 0 < size <= self.max_download_bytes:
            raise SourceValidationError(
                "Tamanho do recurso SIOPS inválido", code="resource_size_invalid"
            )
        return {
            "catalog": SIOPS_CATALOG_URL,
            "resource": SIOPS_2025_URL,
            "year": self.year,
            "period": 6,
            "content_length": size,
        }

    def fetch(self) -> list[FetchedPayload]:
        self._validate_url(SIOPS_2025_URL)
        directory = self.raw_data_dir / "_stage" / self.dataset_code
        directory.mkdir(parents=True, exist_ok=True)
        try:
            with httpx.stream(
                "GET",
                SIOPS_2025_URL,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=300,
            ) as response:
                response.raise_for_status()
                self._validate_url(str(response.url))
                with tempfile.NamedTemporaryFile(
                    dir=directory, prefix="siops-", suffix=".zip.part", delete=False
                ) as target:
                    path = Path(target.name)
                    total = 0
                    digest = hashlib.sha256()
                    for chunk in response.iter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > self.max_download_bytes:
                            path.unlink(missing_ok=True)
                            raise SourceValidationError(
                                "Arquivo SIOPS excede o limite",
                                code="resource_too_large",
                            )
                        digest.update(chunk)
                        target.write(chunk)
                return [
                    FetchedPayload(
                        content=None,
                        file_path=path,
                        url=str(response.url),
                        fetched_at=datetime.now(UTC),
                        original_format="csv.zip",
                        response_headers=self.selected_headers(response),
                        published_at=self.header_datetime(response, "last-modified"),
                        persist_raw=False,
                        resource_version=response.headers.get("etag"),
                        sha256_value=digest.hexdigest(),
                    )
                ]
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SourceValidationError(
                "Falha de rede ao baixar SIOPS", code="network_error"
            ) from exc

    def parse(self, payload: FetchedPayload) -> list[SiopsExpenseRecord]:
        if payload.file_path is None:
            raise SourceValidationError(
                "Payload SIOPS sem arquivo", code="empty_payload"
            )
        records: list[SiopsExpenseRecord] = []
        try:
            with zipfile.ZipFile(payload.file_path) as archive:
                members = [
                    item
                    for item in archive.infolist()
                    if item.filename.lower().endswith(".csv")
                ]
                if len(members) != 1:
                    raise SourceValidationError(
                        "Arquivo SIOPS deve conter um único CSV", code="schema_drift"
                    )
                member = members[0]
                if member.file_size > self.max_uncompressed_bytes or (
                    member.compress_size
                    and member.file_size / member.compress_size > 100
                ):
                    raise SourceValidationError(
                        "ZIP SIOPS excede limites seguros", code="zip_bomb"
                    )
                with archive.open(member) as raw:
                    reader = csv.DictReader(
                        io.TextIOWrapper(
                            raw, encoding="utf-8-sig", errors="strict", newline=""
                        ),
                        delimiter=";",
                    )
                    fields = set(reader.fieldnames or [])
                    if not self.required_fields.issubset(fields):
                        raise SourceValidationError(
                            "Cabeçalho SIOPS alterado",
                            code="schema_drift",
                            details={"missing": sorted(self.required_fields - fields)},
                        )
                    for row in reader:
                        municipality = self.external_selected.get(
                            row["Cód.Município"].strip()
                        )
                        if municipality is None:
                            continue
                        if int(row["Ano"]) != self.year:
                            raise SourceValidationError(
                                "Exercício SIOPS inesperado", code="period_mismatch"
                            )
                        phase = self.phase_codes.get(self._normalized(row["Fase"]))
                        if phase is None:
                            raise SourceValidationError(
                                "Fase contábil SIOPS desconhecida",
                                code="schema_drift",
                                details={"phase": row["Fase"]},
                            )
                        subfunction = row["Subfuncao"].strip()
                        match = re.search(r"\b(\d{3})\b", subfunction)
                        if match is None and self._normalized(subfunction) != (
                            "subfuncao - demais subfuncoes"
                        ):
                            raise SourceValidationError(
                                "Subfunção SIOPS sem código", code="schema_drift"
                            )
                        subfunction_code = match.group(1) if match else "other"
                        try:
                            amount = Decimal(row["Valor"].strip())
                        except InvalidOperation as exc:
                            raise SourceValidationError(
                                "Valor monetário SIOPS inválido", code="invalid_amount"
                            ) from exc
                        homologated = row["Data_Homologacao"].strip()
                        homologated_at = (
                            datetime.fromisoformat(homologated).replace(
                                tzinfo=ZoneInfo("America/Sao_Paulo")
                            )
                            if homologated
                            else None
                        )
                        identity = "|".join(
                            (
                                municipality,
                                str(self.year),
                                row["Fonte"].strip(),
                                subfunction,
                                row["Codigo"].strip(),
                                phase,
                            )
                        )
                        records.append(
                            SiopsExpenseRecord(
                                source_key=hashlib.sha256(
                                    identity.encode()
                                ).hexdigest(),
                                municipality_code=municipality,
                                year=self.year,
                                funding_source=row["Fonte"].strip(),
                                subfunction_code=subfunction_code,
                                subfunction_name=subfunction,
                                nature_code=row["Codigo"].strip(),
                                nature_name=row["Descricao"].strip(),
                                phase=phase,
                                amount=amount,
                                homologated_at=homologated_at,
                                document_url=SIOPS_2025_URL,
                            )
                        )
        finally:
            payload.file_path.unlink(missing_ok=True)
        return records

    def validate(self, records: list[SiopsExpenseRecord]) -> None:
        if not records:
            raise SourceValidationError(
                "SIOPS sem linhas para o recorte", code="empty_selection"
            )
        keys = [record.source_key for record in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError("Chave SIOPS duplicada", code="duplicate_key")
        present = {record.municipality_code for record in records}
        if present != self.selected:
            raise SourceValidationError(
                "SIOPS não cobriu todos os municípios solicitados",
                code="incomplete_selection",
                details={"missing": sorted(self.selected - present)},
            )
        for municipality in present:
            phases = {
                record.phase
                for record in records
                if record.municipality_code == municipality
                and record.nature_code in {"3.0.00.00.00.00", "4.0.00.00.00.00"}
            }
            required = {
                "initial_budget",
                "updated_budget",
                "committed",
                "liquidated",
                "paid",
            }
            if not required.issubset(phases):
                raise SourceValidationError(
                    "SIOPS sem fases essenciais no nível total",
                    code="aggregate_mismatch",
                    details={
                        "municipality": municipality,
                        "missing": sorted(required - phases),
                    },
                )

    def checkpoint_metadata(self) -> dict[str, Any]:
        return {"year": self.year, "period": 6, "municipalities": sorted(self.selected)}

    def upsert(
        self, db: Session, records: list[SiopsExpenseRecord], snapshot: SourceSnapshot
    ) -> None:
        accounts: dict[tuple[str, str, str, str], BudgetAccount] = {}
        for record in records:
            account_identity = (
                record.funding_source,
                record.subfunction_code,
                record.subfunction_name,
                record.nature_code,
            )
            account = accounts.get(account_identity)
            if account is None:
                digest = hashlib.sha256(
                    "|".join(account_identity).encode()
                ).hexdigest()[:20]
                top_level = record.nature_code in {
                    "3.0.00.00.00.00",
                    "4.0.00.00.00.00",
                }
                account_code = f"{'total' if top_level else 'detail'}|{digest}"
                account = db.scalar(
                    select(BudgetAccount).where(
                        BudgetAccount.source_system == "siops",
                        BudgetAccount.account_code == account_code,
                    )
                )
                if account is None:
                    account = BudgetAccount(
                        source_system="siops",
                        account_code=account_code,
                        name=record.nature_name,
                        account_type="health_expense",
                        hierarchy={
                            "funding_source": record.funding_source,
                            "subfunction_code": record.subfunction_code,
                            "subfunction_name": record.subfunction_name,
                            "nature_code": record.nature_code,
                            "top_level": top_level,
                        },
                    )
                    db.add(account)
                    db.flush()
                accounts[account_identity] = account
            previous = db.scalar(
                select(FiscalStatement)
                .where(
                    FiscalStatement.source_system == "siops",
                    FiscalStatement.source_key == record.source_key,
                )
                .order_by(desc(FiscalStatement.revision))
                .limit(1)
            )
            if previous is not None and previous.amount == record.amount:
                continue
            db.add(
                FiscalStatement(
                    source_system="siops",
                    source_key=record.source_key,
                    municipality_ibge_code=record.municipality_code,
                    budget_account_id=account.id,
                    statement_type="health_expense",
                    reference_year=record.year,
                    reference_period=6,
                    periodicity="annual_cumulative",
                    annex="SIOPS Despesas por Fonte/Subfunção/Natureza",
                    column_code=record.phase,
                    amount=record.amount,
                    availability_status="available",
                    source_document_url=record.document_url,
                    source_published_at=record.homologated_at,
                    snapshot_id=snapshot.id,
                    revision=1 if previous is None else previous.revision + 1,
                )
            )
        dataset = db.get(Dataset, snapshot.dataset_id)
        if dataset is not None:
            dataset.publication_status = "published"
        db.flush()


class CnesBedsAdapter(SourceAdapter):
    source_name = "Ministério da Saúde — Hospitais e Leitos/CNES"
    dataset_code = "cnes_beds_establishments"
    allowed_host = "s3.sa-east-1.amazonaws.com"
    required_fields: ClassVar[set[str]] = {
        "COMP",
        "CO_IBGE",
        "CNES",
        "NOME_ESTABELECIMENTO",
        "MOTIVO_DESABILITACAO",
        "TP_GESTAO",
        "CO_TIPO_UNIDADE",
        "DS_TIPO_UNIDADE",
        "LEITOS_EXISTENTES",
        "LEITOS_SUS",
    }

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[str, str],
        selected_municipalities: set[str],
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.crosswalk = municipality_crosswalk
        self.selected = selected_municipalities

    @classmethod
    def _validate_url(cls, value: str) -> None:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != cls.allowed_host
            or parsed.path != "/ckan.saude.gov.br/Leitos_SUS/Leitos_csv_2026.zip"
            or parsed.query
            or parsed.fragment
        ):
            raise SourceValidationError(
                "URL de leitos CNES não permitida", code="unsafe_source_url"
            )

    def discover(self) -> dict[str, Any]:
        self._validate_url(CNES_BEDS_2026_URL)
        response = httpx.head(
            CNES_BEDS_2026_URL,
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        self._validate_url(str(response.url))
        size = int(response.headers.get("content-length", "0"))
        if not 0 < size <= 50_000_000:
            raise SourceValidationError(
                "Tamanho do recurso de leitos inválido", code="resource_size_invalid"
            )
        return {
            "catalog": CNES_BEDS_CATALOG_URL,
            "resource": CNES_BEDS_2026_URL,
            "content_length": size,
        }

    def fetch(self) -> list[FetchedPayload]:
        self._validate_url(CNES_BEDS_2026_URL)
        response = self.get(CNES_BEDS_2026_URL, timeout=180)
        self._validate_url(str(response.url))
        if len(response.content) > 50_000_000:
            raise SourceValidationError(
                "Recurso de leitos excede o limite", code="resource_too_large"
            )
        return [
            FetchedPayload(
                content=response.content,
                url=str(response.url),
                fetched_at=datetime.now(UTC),
                original_format="csv.zip",
                response_headers=self.selected_headers(response),
                published_at=self.header_datetime(response, "last-modified"),
                persist_raw=False,
            )
        ]

    def parse(self, payload: FetchedPayload) -> list[CnesBedRecord]:
        with zipfile.ZipFile(io.BytesIO(payload.read_bytes())) as archive:
            members = [
                item
                for item in archive.infolist()
                if item.filename.lower().endswith(".csv")
            ]
            if len(members) != 1 or members[0].file_size > 100_000_000:
                raise SourceValidationError(
                    "Conteúdo ZIP de leitos alterado", code="schema_drift"
                )
            with archive.open(members[0]) as raw:
                reader = csv.DictReader(
                    io.TextIOWrapper(
                        raw, encoding="cp1252", errors="strict", newline=""
                    ),
                    delimiter=";",
                )
                fields = set(reader.fieldnames or [])
                if not self.required_fields.issubset(fields):
                    raise SourceValidationError(
                        "Cabeçalho de leitos alterado",
                        code="schema_drift",
                        details={"missing": sorted(self.required_fields - fields)},
                    )
                selected_rows = [
                    row
                    for row in reader
                    if self.crosswalk.get(row["CO_IBGE"].strip()) in self.selected
                ]
        if not selected_rows:
            raise SourceValidationError(
                "Leitos sem linhas para o recorte", code="empty_selection"
            )
        latest = max(row["COMP"] for row in selected_rows)
        records = []
        for row in selected_rows:
            if row["COMP"] != latest:
                continue
            records.append(
                CnesBedRecord(
                    municipality_code=self.crosswalk[row["CO_IBGE"].strip()],
                    cnes_code=row["CNES"].strip(),
                    name=row["NOME_ESTABELECIMENTO"].strip(),
                    facility_type_code=row["CO_TIPO_UNIDADE"].strip(),
                    facility_type_name=row["DS_TIPO_UNIDADE"].strip(),
                    management_scope=row["TP_GESTAO"].strip(),
                    active=not bool(row["MOTIVO_DESABILITACAO"].strip()),
                    reference_date=date(int(latest[:4]), int(latest[4:]), 1),
                    existing_count=int(row["LEITOS_EXISTENTES"] or 0),
                    sus_count=int(row["LEITOS_SUS"] or 0),
                    document_url=CNES_BEDS_2026_URL,
                )
            )
        return records

    def validate(self, records: list[CnesBedRecord]) -> None:
        keys = [(item.municipality_code, item.cnes_code) for item in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError(
                "CNES duplicado na competência de leitos", code="duplicate_key"
            )
        if any(
            item.existing_count < 0
            or item.sus_count < 0
            or item.sus_count > item.existing_count
            for item in records
        ):
            raise SourceValidationError(
                "Quantitativo de leitos inválido", code="invalid_capacity"
            )

    def upsert(
        self, db: Session, records: list[CnesBedRecord], snapshot: SourceSnapshot
    ) -> None:
        for record in records:
            previous = db.scalar(
                select(HealthEstablishment)
                .where(
                    HealthEstablishment.source_system == "cnes_beds",
                    HealthEstablishment.source_key == record.cnes_code,
                )
                .order_by(desc(HealthEstablishment.revision))
                .limit(1)
            )
            unchanged = (
                previous is not None
                and previous.reference_date == record.reference_date
                and previous.name == record.name
                and previous.facility_type_code == record.facility_type_code
                and previous.facility_type_name == record.facility_type_name
                and previous.management_scope == record.management_scope
                and previous.sus_linked == (record.sus_count > 0)
                and previous.active == record.active
            )
            establishment = previous
            if not unchanged:
                establishment = HealthEstablishment(
                    source_system="cnes_beds",
                    source_key=record.cnes_code,
                    cnes_code=record.cnes_code,
                    municipality_ibge_code=record.municipality_code,
                    name=record.name,
                    facility_type_code=record.facility_type_code,
                    facility_type_name=record.facility_type_name,
                    management_scope=record.management_scope,
                    sus_linked=record.sus_count > 0,
                    active=record.active,
                    reference_date=record.reference_date,
                    source_document_url=record.document_url,
                    snapshot_id=snapshot.id,
                    revision=1 if previous is None else previous.revision + 1,
                )
                db.add(establishment)
                db.flush()
            assert establishment is not None
            bed_key = f"{record.cnes_code}:total"
            previous_bed = db.scalar(
                select(HealthBed)
                .where(
                    HealthBed.source_system == "cnes_beds",
                    HealthBed.source_key == bed_key,
                )
                .order_by(desc(HealthBed.revision))
                .limit(1)
            )
            if (
                previous_bed is not None
                and previous_bed.establishment_id == establishment.id
                and previous_bed.existing_count == record.existing_count
                and previous_bed.sus_count == record.sus_count
                and previous_bed.reference_date == record.reference_date
            ):
                continue
            db.add(
                HealthBed(
                    source_system="cnes_beds",
                    source_key=bed_key,
                    establishment_id=establishment.id,
                    bed_type_code="total",
                    bed_type_name="Total de leitos cadastrados",
                    existing_count=record.existing_count,
                    sus_count=record.sus_count,
                    reference_date=record.reference_date,
                    snapshot_id=snapshot.id,
                    revision=1 if previous_bed is None else previous_bed.revision + 1,
                )
            )
        dataset = db.get(Dataset, snapshot.dataset_id)
        if dataset is not None and records:
            dataset.publication_status = "published"
        db.flush()


class SinascBirthsAdapter(SourceAdapter):
    source_name = "DATASUS/SINASC — nascidos vivos municipais agregados"
    dataset_code = "sinasc_births_municipal"
    allowed_host = "s3.sa-east-1.amazonaws.com"
    max_download_bytes = 130_000_000
    max_uncompressed_bytes = 700_000_000
    required_fields: ClassVar[set[str]] = {"CODMUNRES", "DTNASC"}

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[str, str],
        selected_municipalities: set[str],
        year: int = 2024,
        disclosure_threshold: int = 5,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        if year != 2024:
            raise ValueError("Somente o artefato definitivo SINASC 2024 foi homologado")
        if not selected_municipalities:
            raise ValueError("SINASC exige ao menos um município")
        self.year = year
        self.disclosure_threshold = disclosure_threshold
        self.selected_municipalities = selected_municipalities
        self.external_selected = {
            external: canonical
            for external, canonical in municipality_crosswalk.items()
            if canonical in selected_municipalities
        }
        if set(self.external_selected.values()) != selected_municipalities:
            missing = sorted(
                selected_municipalities - set(self.external_selected.values())
            )
            raise ValueError(f"Municípios sem crosswalk SINASC: {missing}")

    @classmethod
    def _validate_url(cls, value: str) -> None:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != cls.allowed_host
            or parsed.path != "/ckan.saude.gov.br/SINASC/csv/SINASC_2024_csv.zip"
            or parsed.query
            or parsed.fragment
        ):
            raise SourceValidationError(
                "URL SINASC não permitida", code="unsafe_source_url"
            )

    def discover(self) -> dict[str, Any]:
        self._validate_url(SINASC_2024_URL)
        response = httpx.head(
            SINASC_2024_URL,
            follow_redirects=True,
            timeout=60,
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        self._validate_url(str(response.url))
        size = int(response.headers.get("content-length", "0"))
        if not 0 < size <= self.max_download_bytes:
            raise SourceValidationError(
                "Tamanho do recurso SINASC inválido", code="resource_size_invalid"
            )
        return {
            "catalog": SINASC_CATALOG_URL,
            "resource": SINASC_2024_URL,
            "content_length": size,
        }

    def fetch(self) -> list[FetchedPayload]:
        self._validate_url(SINASC_2024_URL)
        directory = self.raw_data_dir / self.dataset_code
        directory.mkdir(parents=True, exist_ok=True)
        try:
            with httpx.stream(
                "GET",
                SINASC_2024_URL,
                headers={"User-Agent": USER_AGENT},
                follow_redirects=True,
                timeout=300,
            ) as response:
                response.raise_for_status()
                self._validate_url(str(response.url))
                with tempfile.NamedTemporaryFile(
                    dir=directory, prefix="sinasc-", suffix=".zip.part", delete=False
                ) as target:
                    path = Path(target.name)
                    total = 0
                    for chunk in response.iter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > self.max_download_bytes:
                            target.close()
                            path.unlink(missing_ok=True)
                            raise SourceValidationError(
                                "Arquivo SINASC excede o limite",
                                code="resource_too_large",
                            )
                        target.write(chunk)
                return [
                    FetchedPayload(
                        content=None,
                        file_path=path,
                        url=str(response.url),
                        fetched_at=datetime.now(UTC),
                        original_format="csv.zip",
                        response_headers=self.selected_headers(response),
                        published_at=self.header_datetime(response, "last-modified"),
                        persist_raw=False,
                        resource_version=response.headers.get("etag"),
                    )
                ]
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SourceValidationError(
                "Falha de rede ao baixar SINASC", code="network_error"
            ) from exc

    def parse(self, payload: FetchedPayload) -> list[EpidemiologyRecord]:
        if payload.file_path is None:
            raise SourceValidationError(
                "Payload SINASC sem arquivo", code="empty_payload"
            )
        totals: Counter[str] = Counter()
        try:
            with zipfile.ZipFile(payload.file_path) as archive:
                members = [
                    item
                    for item in archive.infolist()
                    if item.filename.lower().endswith(".csv")
                ]
                if len(members) != 1:
                    raise SourceValidationError(
                        "Arquivo SINASC deve conter um único CSV", code="schema_drift"
                    )
                member = members[0]
                if member.file_size > self.max_uncompressed_bytes or (
                    member.compress_size
                    and member.file_size / member.compress_size > 200
                ):
                    raise SourceValidationError(
                        "ZIP SINASC excede limites seguros", code="zip_bomb"
                    )
                with archive.open(member) as raw:
                    reader = csv.DictReader(
                        io.TextIOWrapper(
                            raw, encoding="latin-1", errors="strict", newline=""
                        ),
                        delimiter=";",
                    )
                    fields = set(reader.fieldnames or [])
                    if not self.required_fields.issubset(fields):
                        raise SourceValidationError(
                            "Cabeçalho SINASC alterado",
                            code="schema_drift",
                            details={"missing": sorted(self.required_fields - fields)},
                        )
                    for row in reader:
                        municipality = self.external_selected.get(
                            row["CODMUNRES"].strip()
                        )
                        if municipality is None:
                            continue
                        birth_date = row["DTNASC"].strip()
                        if (
                            len(birth_date) != 8
                            or not birth_date.isdigit()
                            or int(birth_date[-4:]) != self.year
                        ):
                            raise SourceValidationError(
                                "Período SINASC inválido", code="period_mismatch"
                            )
                        totals[municipality] += 1
        except zipfile.BadZipFile as exc:
            raise SourceValidationError(
                "Recurso SINASC não é ZIP válido", code="invalid_archive"
            ) from exc
        finally:
            payload.file_path.unlink(missing_ok=True)

        records = []
        for municipality in sorted(self.selected_municipalities):
            raw_count = totals[municipality]
            suppressed = 0 < raw_count < self.disclosure_threshold
            available = raw_count >= self.disclosure_threshold
            records.append(
                EpidemiologyRecord(
                    source_key=f"{municipality}:{self.year}:live_births:all:residence",
                    municipality_code=municipality,
                    year=self.year,
                    category_code="live_births",
                    category_name="Nascidos vivos",
                    age_band="all",
                    count=raw_count if available else None,
                    raw_count=raw_count,
                    availability_status=(
                        "available"
                        if available
                        else "suppressed"
                        if suppressed
                        else "unavailable"
                    ),
                    disclosure_threshold=self.disclosure_threshold,
                    document_url=SINASC_2024_URL,
                )
            )
        return records

    def validate(self, records: list[EpidemiologyRecord]) -> None:
        if len(records) != len(self.selected_municipalities):
            raise SourceValidationError(
                "Recorte SINASC incompleto", code="aggregate_mismatch"
            )
        if any(
            item.raw_count < self.disclosure_threshold and item.count is not None
            for item in records
        ):
            raise SourceValidationError(
                "Célula SINASC pequena não foi suprimida", code="privacy_error"
            )

    def checkpoint_metadata(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "municipalities": sorted(self.selected_municipalities),
            "disclosure_threshold": self.disclosure_threshold,
        }

    def upsert(
        self,
        db: Session,
        records: list[EpidemiologyRecord],
        snapshot: SourceSnapshot,
    ) -> None:
        for record in records:
            previous = db.scalar(
                select(HealthEpidemiology)
                .where(
                    HealthEpidemiology.source_system == "sinasc",
                    HealthEpidemiology.source_key == record.source_key,
                )
                .order_by(desc(HealthEpidemiology.revision))
                .limit(1)
            )
            if (
                previous is not None
                and previous.count == record.count
                and previous.availability_status == record.availability_status
            ):
                continue
            db.add(
                HealthEpidemiology(
                    source_system="sinasc",
                    source_key=record.source_key,
                    municipality_ibge_code=record.municipality_code,
                    indicator_code="sinasc_live_births_residence",
                    period_start=date(record.year, 1, 1),
                    period_end=date(record.year, 12, 31),
                    geography_basis="residence",
                    category_code=record.category_code,
                    category_name=record.category_name,
                    age_band=record.age_band,
                    count=record.count,
                    availability_status=record.availability_status,
                    disclosure_threshold=record.disclosure_threshold,
                    source_document_url=record.document_url,
                    snapshot_id=snapshot.id,
                    revision=1 if previous is None else previous.revision + 1,
                )
            )
        dataset = db.get(Dataset, snapshot.dataset_id)
        if dataset is not None and records:
            dataset.publication_status = "published"
        db.flush()


def cid_chapter(value: str) -> str:
    code = value.strip().upper()
    if not code or not code[0].isalpha():
        return "unknown"
    letter = code[0]
    digits = int(code[1:3]) if len(code) >= 3 and code[1:3].isdigit() else None
    if letter in {"A", "B"}:
        return "infectious"
    if letter == "C" or (letter == "D" and digits is not None and digits <= 48):
        return "neoplasms"
    if letter == "D":
        return "blood"
    return {
        "E": "endocrine",
        "F": "mental",
        "G": "nervous",
        "H": "eye" if digits is not None and digits <= 59 else "ear",
        "I": "circulatory",
        "J": "respiratory",
        "K": "digestive",
        "L": "skin",
        "M": "musculoskeletal",
        "N": "genitourinary",
        "O": "pregnancy",
        "P": "perinatal",
        "Q": "congenital",
        "R": "symptoms",
        "S": "injury",
        "T": "injury",
        "V": "external",
        "W": "external",
        "X": "external",
        "Y": "external",
        "U": "special",
    }.get(letter, "unknown")


def sim_age_band(value: str) -> str:
    code = value.strip()
    if len(code) != 3 or not code.isdigit():
        return "unknown"
    unit = code[0]
    amount = int(code[1:])
    if unit in {"0", "1", "2", "3"}:
        return "under_1"
    if unit == "5":
        return "80_plus"
    if unit != "4":
        return "unknown"
    if amount == 0:
        return "under_1"
    if amount <= 4:
        return "1_4"
    if amount <= 14:
        return "5_14"
    if amount <= 29:
        return "15_29"
    if amount <= 59:
        return "30_59"
    if amount <= 79:
        return "60_79"
    return "80_plus"


class SimMortalityAdapter(SourceAdapter):
    source_name = "DATASUS/SIM — mortalidade municipal agregada"
    dataset_code = "sim_mortality_municipal"
    allowed_host = "s3.sa-east-1.amazonaws.com"
    max_download_bytes = 200_000_000
    max_uncompressed_bytes = 800_000_000
    required_fields: ClassVar[set[str]] = {
        "TIPOBITO",
        "DTOBITO",
        "IDADE",
        "CODMUNRES",
        "CAUSABAS",
    }

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[str, str],
        selected_municipalities: set[str],
        year: int = 2024,
        disclosure_threshold: int = 5,
        allow_not_modified: bool = True,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        if year != 2024:
            raise ValueError("Somente o artefato definitivo SIM 2024 foi homologado")
        if not selected_municipalities:
            raise ValueError("SIM exige ao menos um município")
        if disclosure_threshold < 5:
            raise ValueError("Limiar de divulgação SIM não pode ser menor que cinco")
        self.year = year
        self.disclosure_threshold = disclosure_threshold
        self.allow_not_modified = allow_not_modified
        self.selected_municipalities = selected_municipalities
        self.municipality_crosswalk = municipality_crosswalk
        external_selected = {
            external: canonical
            for external, canonical in municipality_crosswalk.items()
            if canonical in selected_municipalities
        }
        if set(external_selected.values()) != selected_municipalities:
            missing = sorted(selected_municipalities - set(external_selected.values()))
            raise ValueError(f"Municípios sem crosswalk SIM: {missing}")
        self.external_selected = external_selected

    @property
    def _state_path(self) -> Path:
        return self.raw_data_dir / self.dataset_code / "resource-state.json"

    def _load_state(self) -> dict[str, Any]:
        if not self._state_path.exists():
            return {}
        try:
            return json.loads(self._state_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, sort_keys=True), encoding="utf-8")
        temporary.replace(self._state_path)

    def _can_reuse_checkpoint(self, state: dict[str, Any]) -> bool:
        return bool(
            self.allow_not_modified
            and state.get("processed")
            and self.selected_municipalities
            <= set(state.get("processed_municipalities", []))
            and state.get("etag")
        )

    @classmethod
    def _validate_url(cls, value: str) -> None:
        parsed = urlparse(value)
        if parsed.scheme != "https" or parsed.hostname != cls.allowed_host:
            raise SourceValidationError(
                "URL SIM não permitida", code="unsafe_source_url"
            )

    def discover(self) -> dict[str, Any]:
        self._validate_url(SIM_2024_URL)
        with httpx.Client(
            headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=60
        ) as client:
            response = client.head(SIM_2024_URL)
            response.raise_for_status()
        self._validate_url(str(response.url))
        declared = int(response.headers.get("content-length", "0") or 0)
        if not declared or declared > self.max_download_bytes:
            raise SourceValidationError(
                "Tamanho do artefato SIM ausente ou fora do limite",
                code="resource_size_invalid",
                details={"content_length": declared},
            )
        return {
            "catalog": SIM_CATALOG_URL,
            "resource": SIM_2024_URL,
            "format": "ZIP/CSV",
            "year": self.year,
            "content_length": declared,
            "municipalities": sorted(self.selected_municipalities),
            "privacy": "microdados não persistidos; células de 1 a 4 suprimidas",
            "geography_basis": "residence",
        }

    def fetch(self) -> list[FetchedPayload]:
        state = self._load_state()
        headers = {"User-Agent": USER_AGENT, "Accept": "application/zip, */*"}
        if self._can_reuse_checkpoint(state):
            headers["If-None-Match"] = state["etag"]
        directory = self.raw_data_dir / self.dataset_code / "_stage"
        directory.mkdir(parents=True, exist_ok=True)
        try:
            with (
                httpx.Client(
                    headers=headers, follow_redirects=True, timeout=300
                ) as client,
                client.stream("GET", SIM_2024_URL) as response,
            ):
                if response.status_code == 304 and state.get("processed"):
                    return [
                        FetchedPayload(
                            content=None,
                            url=SIM_2024_URL,
                            fetched_at=datetime.now(UTC),
                            original_format="csv.zip",
                            persist_raw=False,
                            resource_version=state.get("etag"),
                            not_modified=True,
                            sha256_value=state.get("sha256"),
                        )
                    ]
                response.raise_for_status()
                self._validate_url(str(response.url))
                declared = int(response.headers.get("content-length", "0") or 0)
                if declared > self.max_download_bytes:
                    raise SourceValidationError(
                        "Arquivo SIM excede o limite de download",
                        code="resource_too_large",
                    )
                with tempfile.NamedTemporaryFile(
                    dir=directory, prefix="sim-", suffix=".zip.part", delete=False
                ) as target:
                    path = Path(target.name)
                    total = 0
                    for chunk in response.iter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > self.max_download_bytes:
                            target.close()
                            path.unlink(missing_ok=True)
                            raise SourceValidationError(
                                "Arquivo SIM excede o limite de download",
                                code="resource_too_large",
                            )
                        target.write(chunk)
                payload = FetchedPayload(
                    content=None,
                    file_path=path,
                    url=str(response.url),
                    fetched_at=datetime.now(UTC),
                    original_format="csv.zip",
                    response_headers=self.selected_headers(response),
                    published_at=self.header_datetime(response, "last-modified"),
                    persist_raw=False,
                    resource_version=response.headers.get("etag"),
                )
                self._save_state(
                    {
                        "etag": response.headers.get("etag"),
                        "last_modified": response.headers.get("last-modified"),
                        "sha256": payload.sha256,
                        "processed": False,
                    }
                )
                return [payload]
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            raise SourceValidationError(
                "Falha de rede ao baixar SIM", code="network_error"
            ) from exc

    def parse(self, payload: FetchedPayload) -> list[EpidemiologyRecord]:
        if payload.file_path is None:
            raise SourceValidationError("Payload SIM sem arquivo", code="empty_payload")
        try:
            with zipfile.ZipFile(payload.file_path) as archive:
                members = [
                    item
                    for item in archive.infolist()
                    if item.filename.lower().endswith(".csv")
                ]
                if len(members) != 1:
                    raise SourceValidationError(
                        "Arquivo SIM deve conter um único CSV",
                        code="schema_drift",
                        details={"files": archive.namelist()},
                    )
                member = members[0]
                if member.file_size > self.max_uncompressed_bytes or (
                    member.compress_size
                    and member.file_size / member.compress_size > 200
                ):
                    raise SourceValidationError(
                        "ZIP SIM excede limites seguros", code="zip_bomb"
                    )
                totals: Counter[tuple[str, str, str]] = Counter()
                with archive.open(member) as raw:
                    stream = io.TextIOWrapper(
                        raw, encoding="latin-1", errors="strict", newline=""
                    )
                    reader = csv.DictReader(stream, delimiter=";")
                    fields = set(reader.fieldnames or [])
                    if not self.required_fields.issubset(fields):
                        raise SourceValidationError(
                            "Cabeçalho SIM alterado",
                            code="schema_drift",
                            details={"missing": sorted(self.required_fields - fields)},
                        )
                    for row in reader:
                        if row["TIPOBITO"].strip() != "2":
                            continue
                        municipality = self.external_selected.get(
                            row["CODMUNRES"].strip()
                        )
                        if municipality is None:
                            continue
                        death_date = row["DTOBITO"].strip()
                        if len(death_date) != 8 or not death_date.isdigit():
                            raise SourceValidationError(
                                "Data de óbito SIM inválida", code="invalid_period"
                            )
                        if int(death_date[-4:]) != self.year:
                            raise SourceValidationError(
                                "Ano do registro SIM diverge do artefato",
                                code="period_mismatch",
                            )
                        totals[(municipality, "all", "all")] += 1
                        totals[(municipality, cid_chapter(row["CAUSABAS"]), "all")] += 1
                        totals[(municipality, "all", sim_age_band(row["IDADE"]))] += 1
        except zipfile.BadZipFile as exc:
            raise SourceValidationError(
                "Recurso SIM não é ZIP válido", code="invalid_archive"
            ) from exc
        finally:
            payload.file_path.unlink(missing_ok=True)

        records: list[EpidemiologyRecord] = []
        for municipality in sorted(self.selected_municipalities):
            records.append(
                self._record(municipality, "all", "Todas as causas", "all", totals)
            )
            for category_code, category_name in CID_CHAPTERS:
                records.append(
                    self._record(
                        municipality, category_code, category_name, "all", totals
                    )
                )
            for age_band, age_name in AGE_BANDS:
                records.append(
                    self._record(
                        municipality,
                        "all",
                        f"Todas as causas — {age_name}",
                        age_band,
                        totals,
                    )
                )
        return records

    def _record(
        self,
        municipality: str,
        category_code: str,
        category_name: str,
        age_band: str,
        totals: Counter[tuple[str, str, str]],
    ) -> EpidemiologyRecord:
        raw_count = totals[(municipality, category_code, age_band)]
        suppressed = 0 < raw_count < self.disclosure_threshold
        return EpidemiologyRecord(
            source_key=f"{municipality}:{self.year}:{category_code}:{age_band}:residence",
            municipality_code=municipality,
            year=self.year,
            category_code=category_code,
            category_name=category_name,
            age_band=age_band,
            count=None if suppressed else raw_count,
            raw_count=raw_count,
            availability_status="suppressed" if suppressed else "available",
            disclosure_threshold=self.disclosure_threshold,
            document_url=SIM_2024_URL,
        )

    def validate(self, records: list[EpidemiologyRecord]) -> None:
        keys = [record.source_key for record in records]
        if len(keys) != len(set(keys)):
            raise SourceValidationError("Agregado SIM duplicado", code="duplicate_key")
        for municipality in self.selected_municipalities:
            selected = [
                record for record in records if record.municipality_code == municipality
            ]
            overall = next(
                record.raw_count
                for record in selected
                if record.category_code == "all" and record.age_band == "all"
            )
            by_cause = sum(
                record.raw_count
                for record in selected
                if record.category_code != "all" and record.age_band == "all"
            )
            by_age = sum(
                record.raw_count
                for record in selected
                if record.category_code == "all" and record.age_band != "all"
            )
            if overall <= 0 or overall != by_cause or overall != by_age:
                raise SourceValidationError(
                    "Reconciliação interna SIM divergente",
                    code="aggregate_mismatch",
                    details={
                        "municipality": municipality,
                        "overall": overall,
                        "by_cause": by_cause,
                        "by_age": by_age,
                    },
                )
        if any(
            record.availability_status == "suppressed" and record.count is not None
            for record in records
        ):
            raise SourceValidationError(
                "Célula SIM pequena não foi suprimida", code="privacy_error"
            )

    def after_validate(
        self, payload: FetchedPayload, records: list[EpidemiologyRecord]
    ) -> None:
        state = self._load_state()
        if state.get("sha256") == payload.sha256:
            state["processed"] = True
            state["processed_municipalities"] = sorted(self.selected_municipalities)
            state["processed_at"] = datetime.now(UTC).isoformat()
            self._save_state(state)

    def checkpoint_metadata(self) -> dict[str, Any]:
        return {
            "year": self.year,
            "municipalities": sorted(self.selected_municipalities),
            "disclosure_threshold": self.disclosure_threshold,
        }

    def upsert(
        self,
        db: Session,
        records: list[EpidemiologyRecord],
        snapshot: SourceSnapshot,
    ) -> None:
        for record in records:
            previous = db.scalar(
                select(HealthEpidemiology)
                .where(
                    HealthEpidemiology.source_system == "sim",
                    HealthEpidemiology.source_key == record.source_key,
                )
                .order_by(desc(HealthEpidemiology.revision))
                .limit(1)
            )
            if (
                previous is not None
                and previous.count == record.count
                and previous.availability_status == record.availability_status
                and previous.category_name == record.category_name
            ):
                continue
            db.add(
                HealthEpidemiology(
                    source_system="sim",
                    source_key=record.source_key,
                    municipality_ibge_code=record.municipality_code,
                    indicator_code="sim_deaths_residence",
                    period_start=date(record.year, 1, 1),
                    period_end=date(record.year, 12, 31),
                    geography_basis="residence",
                    category_code=record.category_code,
                    category_name=record.category_name,
                    age_band=record.age_band,
                    count=record.count,
                    availability_status=record.availability_status,
                    disclosure_threshold=record.disclosure_threshold,
                    source_document_url=record.document_url,
                    snapshot_id=snapshot.id,
                    revision=1 if previous is None else previous.revision + 1,
                )
            )
        dataset = db.get(Dataset, snapshot.dataset_id)
        if dataset is not None and records:
            dataset.publication_status = "published"
        db.flush()
