from __future__ import annotations

import hashlib
import re
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from ftplib import FTP
from ftplib import all_errors as ftp_errors
from pathlib import Path
from typing import Any, ClassVar

import httpx
import pyreaddbc
from dbfread import DBF
from lente_api.models import (
    Dataset,
    HealthEstablishment,
    HealthProduction,
    HealthService,
    SourceSnapshot,
)
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from ingestion.adapters.base import (
    USER_AGENT,
    FetchedPayload,
    ObservationRecord,
    SourceAdapter,
    SourceValidationError,
)

DATASUS_FTP_HOST = "ftp.datasus.gov.br"
SIH_DIRECTORY = "/dissemin/publicos/SIHSUS/200801_/Dados"
SIA_DIRECTORY = "/dissemin/publicos/SIASUS/200801_/Dados"
CNES_SERVICES_DIRECTORY = "/dissemin/publicos/CNES/200508_/Dados/SR"
ANS_DIRECTORY_URL = (
    "https://dadosabertos.ans.gov.br/FTP/Base_de_dados/Microdados/"
    "dados_dbc/beneficiarios/municipios/"
)


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal(0)
    return Decimal(_text(value).replace(",", "."))


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("latin-1").strip()
    return str(value).strip()


def _month_bounds(value: str) -> tuple[date, date]:
    if not re.fullmatch(r"\d{6}", value):
        raise SourceValidationError("Competência inválida", code="period_mismatch")
    year, month = int(value[:4]), int(value[4:])
    start = date(year, month, 1)
    end = date(year + (month == 12), 1 if month == 12 else month + 1, 1)
    return start, date.fromordinal(end.toordinal() - 1)


def _selected_dbf_rows(
    path: Path, selected_fields: set[str]
) -> Iterable[dict[str, bytes]]:
    """Read only allowlisted DBF columns instead of materializing every microdata field."""
    with path.open("rb") as stream:
        header = stream.read(32)
        if len(header) != 32:
            raise SourceValidationError("Cabeçalho DBF inválido", code="invalid_dbc")
        record_count = int.from_bytes(header[4:8], "little")
        header_length = int.from_bytes(header[8:10], "little")
        record_length = int.from_bytes(header[10:12], "little")
        offset = 1
        selected: list[tuple[str, int, int]] = []
        while True:
            descriptor = stream.read(32)
            if not descriptor or descriptor[0] == 0x0D:
                break
            name = descriptor[:11].split(b"\0", 1)[0].decode("ascii").strip()
            length = descriptor[16]
            if name in selected_fields:
                selected.append((name, offset, length))
            offset += length
        if {name for name, _, _ in selected} != selected_fields:
            raise SourceValidationError("Schema DBF alterado", code="schema_drift")
        if header_length < 33 or record_length <= 1:
            raise SourceValidationError("Layout DBF inválido", code="invalid_dbc")
        stream.seek(header_length)
        for _ in range(record_count):
            record = stream.read(record_length)
            if len(record) != record_length:
                raise SourceValidationError("DBF truncado", code="truncated_payload")
            if record[0:1] == b"*":
                continue
            yield {
                name: record[start : start + length].strip()
                for name, start, length in selected
            }


def aggregate_sih_rows(
    rows: Iterable[dict[str, Any]], crosswalk: dict[str, str]
) -> list[ProductionRecord]:
    totals: dict[tuple[str, str, str, str, str], tuple[Decimal, Decimal]] = {}
    for row in rows:
        municipality = crosswalk.get(_text(row.get("MUNIC_MOV")))
        if municipality is None:
            continue
        competence = (
            f"{_text(row.get('ANO_CMPT'))}{_text(row.get('MES_CMPT')).zfill(2)}"
        )
        procedure = _text(row.get("PROC_REA"))
        specialty = _text(row.get("ESPEC"))
        complexity = _text(row.get("COMPLEX"))
        key = municipality, competence, procedure, specialty, complexity
        quantity, amount = totals.get(key, (Decimal(0), Decimal(0)))
        totals[key] = quantity + 1, amount + _decimal(row.get("VAL_TOT"))
    return [
        ProductionRecord(
            source_key=f"{municipality}:{competence}:{procedure}:{specialty}:{complexity}",
            municipality_code=municipality,
            competence=competence,
            care_type="hospital_admissions_authorizations",
            procedure_code=procedure,
            facility_type=f"specialty:{specialty or 'unknown'}",
            sus_sector=f"complexity:{complexity or 'unknown'}",
            quantity=quantity,
            approved_amount=amount,
        )
        for (municipality, competence, procedure, specialty, complexity), (
            quantity,
            amount,
        ) in sorted(totals.items())
    ]


def aggregate_sia_rows(
    rows: Iterable[dict[str, Any]], crosswalk: dict[str, str], part: str
) -> list[ProductionRecord]:
    totals: dict[tuple[str, str, str, str], tuple[Decimal, Decimal]] = {}
    for row in rows:
        municipality = crosswalk.get(_text(row.get("PA_UFMUN")))
        if municipality is None:
            continue
        competence = _text(row.get("PA_CMP"))
        if competence != "202512":
            continue
        procedure = _text(row.get("PA_PROC_ID"))
        facility_type = _text(row.get("PA_TPUPS"))
        key = municipality, competence, procedure, facility_type
        quantity, amount = totals.get(key, (Decimal(0), Decimal(0)))
        totals[key] = (
            quantity + _decimal(row.get("PA_QTDAPR")),
            amount + _decimal(row.get("PA_VALAPR")),
        )
    return [
        ProductionRecord(
            source_key=f"{part}:{municipality}:{competence}:{procedure}:{facility_type}",
            municipality_code=municipality,
            competence=competence,
            care_type="outpatient_procedures_approved",
            procedure_code=procedure,
            facility_type=f"unit_type:{facility_type or 'unknown'}",
            sus_sector="SUS — município do estabelecimento executor",
            quantity=quantity,
            approved_amount=amount,
        )
        for (municipality, competence, procedure, facility_type), (
            quantity,
            amount,
        ) in sorted(totals.items())
    ]


@dataclass(slots=True)
class ProductionRecord:
    source_key: str
    municipality_code: str
    competence: str
    care_type: str
    procedure_code: str
    facility_type: str
    sus_sector: str
    quantity: Decimal
    approved_amount: Decimal


@dataclass(slots=True)
class CnesServiceRecord:
    source_key: str
    municipality_code: str
    cnes_code: str
    service_code: str
    classification_code: str
    facility_type_code: str
    management_scope: str
    sus_available: bool
    competence: str


class _DatasusFtpAdapter(SourceAdapter):
    ftp_directory: str
    file_pattern: re.Pattern[str]
    max_download_bytes = 250_000_000

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[str, str],
        selected_municipalities: set[str],
        selected_states: set[str],
        year: int = 2025,
        month: int = 12,
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        if not selected_municipalities:
            raise ValueError("O conector exige ao menos um município")
        if year != 2025 or month != 12:
            raise ValueError("A competência homologada nesta versão é dezembro de 2025")
        self.crosswalk = {
            external: canonical
            for external, canonical in municipality_crosswalk.items()
            if canonical in selected_municipalities
        }
        self.selected = selected_municipalities
        self.states = {state.upper() for state in selected_states}
        self.year = year
        self.month = month
        self._files: list[tuple[str, int]] = []

    def _listing(self) -> list[tuple[str, int]]:
        try:
            with FTP(DATASUS_FTP_HOST, timeout=45) as ftp:
                ftp.login()
                ftp.set_pasv(True)
                ftp.cwd(self.ftp_directory)
                names = ftp.nlst()
                files = [
                    (name, int(ftp.size(name) or 0))
                    for name in names
                    if self.file_pattern.fullmatch(name)
                ]
        except ftp_errors as exc:
            raise SourceValidationError(
                "FTP oficial DATASUS indisponível", code="network_error"
            ) from exc
        if not files or any(
            size <= 0 or size > self.max_download_bytes for _, size in files
        ):
            raise SourceValidationError(
                "Arquivos DATASUS ausentes ou fora do limite seguro",
                code="resource_size_invalid",
                details={"files": files},
            )
        return sorted(files)

    def discover(self) -> dict[str, Any]:
        self._files = self._listing()
        return {
            "transport": "passive FTP",
            "host": DATASUS_FTP_HOST,
            "directory": self.ftp_directory,
            "files": [{"name": name, "bytes": size} for name, size in self._files],
        }

    def fetch(self) -> list[FetchedPayload]:
        files = self._files or self._listing()
        stage = self.raw_data_dir / "_stage" / self.dataset_code
        stage.mkdir(parents=True, exist_ok=True)
        payloads: list[FetchedPayload] = []
        for name, expected_size in files:
            if "/" in name or "\\" in name or not self.file_pattern.fullmatch(name):
                raise SourceValidationError(
                    "Nome FTP inseguro", code="unsafe_source_url"
                )
            path = stage / name
            digest = hashlib.sha256()
            if path.exists() and path.stat().st_size == expected_size:
                with path.open("rb") as cached:
                    for chunk in iter(lambda: cached.read(1024 * 1024), b""):
                        digest.update(chunk)
                payloads.append(
                    FetchedPayload(
                        content=None,
                        file_path=path,
                        url=f"ftp://{DATASUS_FTP_HOST}{self.ftp_directory}/{name}",
                        fetched_at=datetime.now(UTC),
                        original_format="dbc",
                        response_headers={
                            "content-length": str(expected_size),
                            "transport": "ftp-passive-resume",
                        },
                        persist_raw=False,
                        resource_version=name,
                        sha256_value=digest.hexdigest(),
                    )
                )
                continue
            path.unlink(missing_ok=True)
            partial = path.with_suffix(".dbc.part")
            partial.unlink(missing_ok=True)
            received = 0
            try:
                with (
                    FTP(DATASUS_FTP_HOST, timeout=120) as ftp,
                    partial.open("wb") as target,
                ):
                    ftp.login()
                    ftp.set_pasv(True)
                    ftp.cwd(self.ftp_directory)

                    def write(
                        chunk: bytes,
                        _digest: Any = digest,
                        _target: Any = target,
                    ) -> None:
                        nonlocal received
                        received += len(chunk)
                        if received > self.max_download_bytes:
                            raise SourceValidationError(
                                "Arquivo DATASUS excedeu o limite",
                                code="resource_too_large",
                            )
                        _digest.update(chunk)
                        _target.write(chunk)

                    ftp.retrbinary(f"RETR {name}", write, blocksize=1024 * 1024)
            except Exception:
                partial.unlink(missing_ok=True)
                raise
            if received != expected_size:
                partial.unlink(missing_ok=True)
                raise SourceValidationError(
                    "Download FTP incompleto", code="truncated_payload"
                )
            partial.replace(path)
            payloads.append(
                FetchedPayload(
                    content=None,
                    file_path=path,
                    url=f"ftp://{DATASUS_FTP_HOST}{self.ftp_directory}/{name}",
                    fetched_at=datetime.now(UTC),
                    original_format="dbc",
                    response_headers={
                        "content-length": str(received),
                        "transport": "ftp-passive",
                    },
                    persist_raw=False,
                    resource_version=name,
                    sha256_value=digest.hexdigest(),
                )
            )
        return payloads

    @staticmethod
    def _dbf(payload: FetchedPayload) -> tuple[DBF, Path]:
        if payload.file_path is None:
            raise SourceValidationError("Payload DBC sem arquivo", code="empty_payload")
        target = payload.file_path.with_suffix(".dbf")
        try:
            pyreaddbc.dbc2dbf(str(payload.file_path), str(target))
            table = DBF(
                str(target),
                encoding="latin-1",
                load=False,
                raw=True,
                char_decode_errors="strict",
            )
            return table, target
        except Exception as exc:
            target.unlink(missing_ok=True)
            raise SourceValidationError(
                "Falha ao converter DBC oficial", code="invalid_dbc"
            ) from exc

    @staticmethod
    def _cleanup(payload: FetchedPayload, dbf_path: Path) -> None:
        dbf_path.unlink(missing_ok=True)
        if payload.file_path is not None:
            payload.file_path.unlink(missing_ok=True)


class SihProductionAdapter(_DatasusFtpAdapter):
    source_name = "DATASUS — SIH/SUS"
    dataset_code = "sih_production_municipal"
    ftp_directory = SIH_DIRECTORY
    required_fields: ClassVar[set[str]] = {
        "ANO_CMPT",
        "MES_CMPT",
        "MUNIC_MOV",
        "PROC_REA",
        "VAL_TOT",
        "ESPEC",
        "COMPLEX",
    }

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        states = "|".join(sorted(map(re.escape, self.states)))
        self.file_pattern = re.compile(rf"RD(?:{states})25{self.month:02d}\.dbc")

    def parse(self, payload: FetchedPayload) -> list[ProductionRecord]:
        table, target = self._dbf(payload)
        try:
            fields = {field.name.strip() for field in table.fields}
            if not self.required_fields.issubset(fields):
                raise SourceValidationError("Schema SIH alterado", code="schema_drift")
            return aggregate_sih_rows(
                _selected_dbf_rows(target, self.required_fields), self.crosswalk
            )
        finally:
            self._cleanup(payload, target)

    def validate(self, records: list[ProductionRecord]) -> None:
        if not records:
            raise SourceValidationError(
                "SIH sem dados no recorte", code="empty_selection"
            )
        if any(
            item.competence != "202512" or item.quantity < 0 or item.approved_amount < 0
            for item in records
        ):
            raise SourceValidationError(
                "Agregado SIH inválido", code="aggregate_mismatch"
            )

    def upsert(
        self, db: Session, records: list[ProductionRecord], snapshot: SourceSnapshot
    ) -> None:
        _upsert_production(db, records, snapshot, "sih")


class SiaProductionAdapter(_DatasusFtpAdapter):
    source_name = "DATASUS — SIA/SUS"
    dataset_code = "sia_production_municipal"
    ftp_directory = SIA_DIRECTORY
    max_download_bytes = 260_000_000
    required_fields: ClassVar[set[str]] = {
        "PA_UFMUN",
        "PA_CMP",
        "PA_PROC_ID",
        "PA_TPUPS",
        "PA_QTDAPR",
        "PA_VALAPR",
    }

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        states = "|".join(sorted(map(re.escape, self.states)))
        self.file_pattern = re.compile(rf"PA(?:{states})25{self.month:02d}[a-z]?\.dbc")

    def parse(self, payload: FetchedPayload) -> list[ProductionRecord]:
        table, target = self._dbf(payload)
        try:
            fields = {field.name.strip() for field in table.fields}
            if not self.required_fields.issubset(fields):
                raise SourceValidationError("Schema SIA alterado", code="schema_drift")
            return aggregate_sia_rows(
                _selected_dbf_rows(target, self.required_fields),
                self.crosswalk,
                payload.resource_version or "part",
            )
        finally:
            self._cleanup(payload, target)

    def validate(self, records: list[ProductionRecord]) -> None:
        if any(
            item.competence != "202512" or item.quantity < 0 or item.approved_amount < 0
            for item in records
        ):
            raise SourceValidationError(
                "Agregado SIA inválido", code="aggregate_mismatch"
            )

    def upsert(
        self, db: Session, records: list[ProductionRecord], snapshot: SourceSnapshot
    ) -> None:
        _upsert_production(db, records, snapshot, "sia")


class CnesServicesAdapter(_DatasusFtpAdapter):
    source_name = "DATASUS/CNES — serviços especializados"
    dataset_code = "cnes_services"
    ftp_directory = CNES_SERVICES_DIRECTORY
    required_fields: ClassVar[set[str]] = {
        "CNES",
        "CODUFMUN",
        "SERV_ESP",
        "CLASS_SR",
        "TPGESTAO",
        "TP_UNID",
        "AMB_SUS",
        "HOSP_SUS",
        "COMPETEN",
    }

    def __init__(self, **kwargs: Any):
        super().__init__(**kwargs)
        states = "|".join(sorted(map(re.escape, self.states)))
        self.file_pattern = re.compile(rf"SR(?:{states})25{self.month:02d}\.dbc")

    def parse(self, payload: FetchedPayload) -> list[CnesServiceRecord]:
        table, target = self._dbf(payload)
        try:
            fields = {field.name.strip() for field in table.fields}
            if not self.required_fields.issubset(fields):
                raise SourceValidationError(
                    "Schema CNES SR alterado", code="schema_drift"
                )
            result: dict[str, CnesServiceRecord] = {}
            for row in _selected_dbf_rows(target, self.required_fields):
                municipality = self.crosswalk.get(_text(row["CODUFMUN"]))
                if municipality is None:
                    continue
                cnes = _text(row["CNES"])
                service = _text(row["SERV_ESP"])
                classification = _text(row["CLASS_SR"])
                competence = _text(row["COMPETEN"])
                source_key = f"{cnes}:{service}:{classification}"
                current = result.get(source_key)
                sus_available = (
                    _text(row["AMB_SUS"]) == "1" or _text(row["HOSP_SUS"]) == "1"
                )
                result[source_key] = CnesServiceRecord(
                    source_key=source_key,
                    municipality_code=municipality,
                    cnes_code=cnes,
                    service_code=service,
                    classification_code=classification,
                    facility_type_code=_text(row["TP_UNID"]),
                    management_scope=_text(row["TPGESTAO"]),
                    sus_available=sus_available
                    or bool(current and current.sus_available),
                    competence=competence,
                )
            return list(result.values())
        finally:
            self._cleanup(payload, target)

    def validate(self, records: list[CnesServiceRecord]) -> None:
        if not records:
            raise SourceValidationError(
                "CNES serviços sem dados no recorte", code="empty_selection"
            )
        if any(item.competence != "202512" for item in records):
            raise SourceValidationError(
                "Competência CNES divergente", code="period_mismatch"
            )

    def upsert(
        self, db: Session, records: list[CnesServiceRecord], snapshot: SourceSnapshot
    ) -> None:
        establishments: dict[str, HealthEstablishment] = {}
        for record in records:
            establishment = establishments.get(record.cnes_code)
            if establishment is None:
                establishment = db.scalar(
                    select(HealthEstablishment)
                    .where(HealthEstablishment.cnes_code == record.cnes_code)
                    .order_by(
                        desc(HealthEstablishment.reference_date),
                        desc(HealthEstablishment.revision),
                    )
                    .limit(1)
                )
                if establishment is None:
                    establishment = HealthEstablishment(
                        source_system="cnes_services",
                        source_key=record.cnes_code,
                        cnes_code=record.cnes_code,
                        municipality_ibge_code=record.municipality_code,
                        name=f"Estabelecimento CNES {record.cnes_code}",
                        facility_type_code=record.facility_type_code,
                        facility_type_name=f"Tipo de unidade CNES {record.facility_type_code}",
                        management_scope=record.management_scope,
                        sus_linked=record.sus_available,
                        active=True,
                        reference_date=date(2025, 12, 1),
                        source_document_url=snapshot.url,
                        snapshot_id=snapshot.id,
                        revision=1,
                    )
                    db.add(establishment)
                    db.flush()
                establishments[record.cnes_code] = establishment
            previous = db.scalar(
                select(HealthService)
                .where(
                    HealthService.source_system == "cnes_services",
                    HealthService.source_key == record.source_key,
                )
                .order_by(desc(HealthService.revision))
                .limit(1)
            )
            if (
                previous is not None
                and previous.reference_date == date(2025, 12, 1)
                and previous.sus_available == record.sus_available
            ):
                continue
            db.add(
                HealthService(
                    source_system="cnes_services",
                    source_key=record.source_key,
                    establishment_id=establishment.id,
                    service_code=record.service_code,
                    service_name=f"Serviço especializado CNES {record.service_code}",
                    classification_code=record.classification_code,
                    classification_name=f"Classificação CNES {record.classification_code}",
                    sus_available=record.sus_available,
                    reference_date=date(2025, 12, 1),
                    snapshot_id=snapshot.id,
                    revision=1 if previous is None else previous.revision + 1,
                )
            )
        dataset = db.get(Dataset, snapshot.dataset_id)
        if dataset is not None:
            dataset.publication_status = "published"
        db.flush()


def _upsert_production(
    db: Session,
    records: list[ProductionRecord],
    snapshot: SourceSnapshot,
    source_system: str,
) -> None:
    for record in records:
        start, end = _month_bounds(record.competence)
        previous = db.scalar(
            select(HealthProduction)
            .where(
                HealthProduction.source_system == source_system,
                HealthProduction.source_key == record.source_key,
            )
            .order_by(desc(HealthProduction.revision))
            .limit(1)
        )
        if (
            previous is not None
            and previous.quantity == record.quantity
            and previous.approved_amount == record.approved_amount
        ):
            continue
        db.add(
            HealthProduction(
                source_system=source_system,
                source_key=record.source_key,
                municipality_ibge_code=record.municipality_code,
                period_start=start,
                period_end=end,
                care_type=record.care_type,
                procedure_code=record.procedure_code,
                procedure_name=f"Procedimento SIGTAP {record.procedure_code}",
                facility_type=record.facility_type,
                sus_sector=record.sus_sector,
                quantity=record.quantity,
                approved_amount=record.approved_amount,
                availability_status="available",
                source_document_url=snapshot.url,
                snapshot_id=snapshot.id,
                revision=1 if previous is None else previous.revision + 1,
            )
        )
    dataset = db.get(Dataset, snapshot.dataset_id)
    if dataset is not None and records:
        dataset.publication_status = "published"
    db.flush()


class AnsBeneficiariesAdapter(SourceAdapter):
    source_name = "ANS — beneficiários por município"
    dataset_code = "ans_beneficiaries_municipal"
    filename = "tb_bb_2025-12.dbc"
    max_download_bytes = 80_000_000
    required_fields: ClassVar[set[str]] = {
        "ID_CMPT",
        "TP_VIGENCI",
        "CD_MUNICIP",
        "NR_BENEF_T",
    }

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[str, str],
        selected_municipalities: set[str],
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.crosswalk = {
            external: canonical
            for external, canonical in municipality_crosswalk.items()
            if canonical in selected_municipalities
        }

    @property
    def url(self) -> str:
        return f"{ANS_DIRECTORY_URL}{self.filename}"

    def discover(self) -> dict[str, Any]:
        response = httpx.head(
            self.url,
            headers={"User-Agent": USER_AGENT},
            timeout=60,
            follow_redirects=True,
        )
        response.raise_for_status()
        if str(response.url) != self.url:
            raise SourceValidationError(
                "Redirecionamento ANS não permitido", code="unsafe_source_url"
            )
        size = int(response.headers.get("content-length", "0"))
        if not 0 < size <= self.max_download_bytes:
            raise SourceValidationError(
                "Tamanho ANS inválido", code="resource_size_invalid"
            )
        return {"resource": self.url, "content_length": size, "competence": "2025-12"}

    def fetch(self) -> list[FetchedPayload]:
        stage = self.raw_data_dir / "_stage" / self.dataset_code
        stage.mkdir(parents=True, exist_ok=True)
        path = Path(tempfile.mkstemp(prefix="ans-", suffix=".dbc", dir=stage)[1])
        digest = hashlib.sha256()
        total = 0
        try:
            with (
                httpx.stream(
                    "GET",
                    self.url,
                    headers={"User-Agent": USER_AGENT},
                    timeout=180,
                    follow_redirects=True,
                ) as response,
                path.open("wb") as target,
            ):
                response.raise_for_status()
                if str(response.url) != self.url:
                    raise SourceValidationError(
                        "Redirecionamento ANS não permitido", code="unsafe_source_url"
                    )
                for chunk in response.iter_bytes(1024 * 1024):
                    total += len(chunk)
                    if total > self.max_download_bytes:
                        raise SourceValidationError(
                            "Arquivo ANS excedeu o limite", code="resource_too_large"
                        )
                    digest.update(chunk)
                    target.write(chunk)
        except Exception:
            path.unlink(missing_ok=True)
            raise
        return [
            FetchedPayload(
                content=None,
                file_path=path,
                url=self.url,
                fetched_at=datetime.now(UTC),
                original_format="dbc",
                response_headers={"content-length": str(total)},
                persist_raw=False,
                resource_version=self.filename,
                sha256_value=digest.hexdigest(),
            )
        ]

    def parse(self, payload: FetchedPayload) -> list[ObservationRecord]:
        table, target = _DatasusFtpAdapter._dbf(payload)
        totals: dict[str, Decimal] = defaultdict(Decimal)
        try:
            fields = {field.name.strip() for field in table.fields}
            if not self.required_fields.issubset(fields):
                raise SourceValidationError("Schema ANS alterado", code="schema_drift")
            for row in _selected_dbf_rows(target, self.required_fields):
                municipality = self.crosswalk.get(_text(row["CD_MUNICIP"]))
                if municipality is None:
                    continue
                if _text(row["ID_CMPT"]) != "202512":
                    raise SourceValidationError(
                        "Competência ANS divergente", code="period_mismatch"
                    )
                totals[municipality] += _decimal(row["NR_BENEF_T"])
        finally:
            _DatasusFtpAdapter._cleanup(payload, target)
        return [
            ObservationRecord(
                indicator_code="ans_health_plan_beneficiary_links",
                municipality_ibge_code=municipality,
                period_start=date(2025, 12, 1),
                period_end=date(2025, 12, 31),
                value=value,
                scope={"coverage": "all", "counting_unit": "beneficiary_links"},
            )
            for municipality, value in sorted(totals.items())
        ]

    def validate(self, records: list[ObservationRecord]) -> None:
        if not records:
            raise SourceValidationError(
                "ANS sem dados no recorte", code="empty_selection"
            )
        if any(item.value is None or item.value < 0 for item in records):
            raise SourceValidationError(
                "Agregado ANS inválido", code="aggregate_mismatch"
            )

    def upsert(
        self, db: Session, records: list[ObservationRecord], snapshot: SourceSnapshot
    ) -> None:
        super().upsert(db, records, snapshot)
        dataset = db.get(Dataset, snapshot.dataset_id)
        if dataset is not None:
            dataset.publication_status = "published"
