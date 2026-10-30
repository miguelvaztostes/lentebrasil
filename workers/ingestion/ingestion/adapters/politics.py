from __future__ import annotations

import csv
import io
import re
import tempfile
import unicodedata
import uuid
import zipfile
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
from lente_api.models import (
    Dataset,
    DeclaredAssetSummary,
    PoliticalCandidacy,
    PoliticalMandate,
    PoliticalPerson,
    SourceSnapshot,
)
from sqlalchemy import desc, insert, select
from sqlalchemy.orm import Session

from ingestion.adapters.base import (
    USER_AGENT,
    FetchedPayload,
    SourceAdapter,
    SourceValidationError,
)

TSE_HOST = "cdn.tse.jus.br"
TSE_CANDIDATE_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/consulta_cand/"
    "consulta_cand_2024.zip"
)
TSE_ASSET_URL = (
    "https://cdn.tse.jus.br/estatistica/sead/odsele/bem_candidato/"
    "bem_candidato_2024.zip"
)
MAX_DOWNLOAD_BYTES = 180 * 1024 * 1024
ELECTED_RESULTS = {
    "ELEITO",
    "ELEITO POR QP",
    "ELEITO POR MEDIA",
    "ELEITO 1 TURNO",
    "ELEITO 2 TURNO",
}


def normalize_name(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(char for char in decomposed if not unicodedata.combining(char))
    return re.sub(r"[^A-Z0-9]+", " ", ascii_text.upper()).strip()


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_name(value).lower()).strip("-")


@dataclass(slots=True)
class CandidateRecord:
    candidate_sequence: str
    municipality_code: str
    state: str
    election_year: int
    election_type: str
    office_code: str
    office_name: str
    full_name: str
    ballot_name: str
    ballot_number: str
    party_acronym: str
    registration_status: str
    election_result: str


@dataclass(slots=True)
class AssetRecord:
    candidate_sequence: str
    election_year: int
    asset_type_code: str
    asset_type_name: str
    asset_count: int
    total_amount: Decimal


class TseCandidacyAdapter(SourceAdapter):
    """TSE candidacies/elected mandates and privacy-safe asset aggregates.

    The adapter deliberately never reads into the domain model CPF, email, birth
    date, voter-registration number, addresses or free-text asset descriptions.
    ``SQ_CANDIDATO`` is an election-scoped official identifier, not a stable
    identity asserted across elections.
    """

    source_name = "TSE — candidaturas, eleitos e bens declarados 2024"
    dataset_code = "tse_candidacies"

    def __init__(
        self,
        *,
        raw_data_dir: Path,
        municipality_crosswalk: dict[tuple[str, str], str],
    ):
        super().__init__(raw_data_dir=raw_data_dir)
        self.municipality_crosswalk = municipality_crosswalk
        self._selected_candidate_sequences: set[str] = set()

    def discover(self) -> dict[str, Any]:
        evidence: dict[str, Any] = {"resources": []}
        for url in (TSE_CANDIDATE_URL, TSE_ASSET_URL):
            if urlparse(url).scheme != "https" or urlparse(url).hostname != TSE_HOST:
                raise SourceValidationError(
                    "URL TSE fora da allowlist", code="unsafe_source_url"
                )
            with httpx.Client(
                headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=90
            ) as client:
                response = client.head(url)
                response.raise_for_status()
            final = urlparse(str(response.url))
            if final.scheme != "https" or final.hostname != TSE_HOST:
                raise SourceValidationError(
                    "Redirecionamento TSE fora da allowlist", code="unsafe_redirect"
                )
            length = int(response.headers.get("content-length", "0"))
            if length > MAX_DOWNLOAD_BYTES:
                raise SourceValidationError(
                    "Arquivo TSE excede o limite homologado", code="oversized_payload"
                )
            evidence["resources"].append(
                {
                    "url": url,
                    "bytes": length,
                    "content_type": response.headers.get("content-type"),
                }
            )
        return evidence

    def fetch(self) -> list[FetchedPayload]:
        stage = self.raw_data_dir / "_stage"
        stage.mkdir(parents=True, exist_ok=True)
        payloads: list[FetchedPayload] = []
        for kind, url in (("candidates", TSE_CANDIDATE_URL), ("assets", TSE_ASSET_URL)):
            with (
                httpx.Client(
                    headers={"User-Agent": USER_AGENT},
                    follow_redirects=True,
                    timeout=httpx.Timeout(180),
                ) as client,
                client.stream("GET", url) as response,
            ):
                response.raise_for_status()
                final = urlparse(str(response.url))
                if final.scheme != "https" or final.hostname != TSE_HOST:
                    raise SourceValidationError(
                        "Redirecionamento TSE fora da allowlist", code="unsafe_redirect"
                    )
                with tempfile.NamedTemporaryFile(
                    prefix=f"tse-{kind}-", suffix=".zip", dir=stage, delete=False
                ) as output:
                    total = 0
                    for chunk in response.iter_bytes(1024 * 1024):
                        total += len(chunk)
                        if total > MAX_DOWNLOAD_BYTES:
                            raise SourceValidationError(
                                "Arquivo TSE excede o limite homologado",
                                code="oversized_payload",
                            )
                        output.write(chunk)
                    path = Path(output.name)
                payloads.append(
                    FetchedPayload(
                        content=None,
                        file_path=path,
                        url=url,
                        fetched_at=datetime.now(UTC),
                        published_at=self.header_datetime(response, "last-modified"),
                        original_format=f"tse.{kind}.csv.zip",
                        response_headers=self.selected_headers(response),
                        resource_version=f"2024-{kind}",
                            persist_raw=False,
                    )
                )
        return payloads

    def parse(self, payload: FetchedPayload) -> list[CandidateRecord | AssetRecord]:
        if "candidates" in payload.original_format:
            return self._parse_candidates(payload)
        return self._parse_assets(payload)

    def _csv_readers(self, payload: FetchedPayload):
        archive = zipfile.ZipFile(payload.file_path or io.BytesIO(payload.read_bytes()))
        try:
            for name in sorted(archive.namelist()):
                if not name.lower().endswith(".csv"):
                    continue
                binary = archive.open(name)
                text = io.TextIOWrapper(binary, encoding="latin-1", newline="")
                yield name, csv.DictReader(text, delimiter=";"), text
        finally:
            archive.close()

    def _parse_candidates(self, payload: FetchedPayload) -> list[CandidateRecord]:
        required = {
            "ANO_ELEICAO",
            "NM_TIPO_ELEICAO",
            "SG_UF",
            "NM_UE",
            "CD_CARGO",
            "DS_CARGO",
            "SQ_CANDIDATO",
            "NR_CANDIDATO",
            "NM_CANDIDATO",
            "NM_URNA_CANDIDATO",
            "SG_PARTIDO",
            "DS_SITUACAO_CANDIDATURA",
            "DS_SIT_TOT_TURNO",
        }
        records: list[CandidateRecord] = []
        seen: set[str] = set()
        unmapped: set[tuple[str, str]] = set()
        for _, reader, text in self._csv_readers(payload):
            try:
                missing = required - set(reader.fieldnames or [])
                if missing:
                    raise SourceValidationError(
                        f"Schema de candidaturas TSE alterado: {sorted(missing)}",
                        code="tse_candidate_schema_changed",
                    )
                for row in reader:
                    sequence = row["SQ_CANDIDATO"].strip()
                    if not sequence or sequence in seen:
                        continue
                    state = row["SG_UF"].strip().upper()
                    city_key = (state, normalize_name(row["NM_UE"]))
                    municipality = self.municipality_crosswalk.get(city_key)
                    if municipality is None:
                        unmapped.add(city_key)
                        continue
                    seen.add(sequence)
                    self._selected_candidate_sequences.add(sequence)
                    records.append(
                        CandidateRecord(
                            candidate_sequence=sequence,
                            municipality_code=municipality,
                            state=state,
                            election_year=int(row["ANO_ELEICAO"]),
                            election_type=row["NM_TIPO_ELEICAO"].strip(),
                            office_code=row["CD_CARGO"].strip(),
                            office_name=row["DS_CARGO"].strip(),
                            full_name=row["NM_CANDIDATO"].strip(),
                            ballot_name=row["NM_URNA_CANDIDATO"].strip(),
                            ballot_number=row["NR_CANDIDATO"].strip(),
                            party_acronym=row["SG_PARTIDO"].strip(),
                            registration_status=row["DS_SITUACAO_CANDIDATURA"].strip(),
                            election_result=row["DS_SIT_TOT_TURNO"].strip(),
                        )
                    )
            finally:
                text.close()
        if unmapped:
            self.quality_warnings.append(
                {
                    "code": "tse_unmapped_electoral_units",
                    "details": {
                        "count": len(unmapped),
                        "examples": [
                            f"{uf}/{name}" for uf, name in sorted(unmapped)[:20]
                        ],
                    },
                }
            )
        return records

    def _parse_assets(self, payload: FetchedPayload) -> list[AssetRecord]:
        required = {
            "ANO_ELEICAO",
            "SQ_CANDIDATO",
            "CD_TIPO_BEM_CANDIDATO",
            "DS_TIPO_BEM_CANDIDATO",
            "VR_BEM_CANDIDATO",
        }
        aggregates: dict[tuple[str, int, str, str], tuple[int, Decimal]] = {}
        for _, reader, text in self._csv_readers(payload):
            try:
                missing = required - set(reader.fieldnames or [])
                if missing:
                    raise SourceValidationError(
                        f"Schema de bens TSE alterado: {sorted(missing)}",
                        code="tse_asset_schema_changed",
                    )
                for row in reader:
                    sequence = row["SQ_CANDIDATO"].strip()
                    if sequence not in self._selected_candidate_sequences:
                        continue
                    try:
                        amount = Decimal(
                            row["VR_BEM_CANDIDATO"].strip().replace(",", ".")
                        )
                    except InvalidOperation as exc:
                        raise SourceValidationError(
                            "Valor de bem inválido no arquivo TSE",
                            code="tse_invalid_asset_amount",
                        ) from exc
                    key = (
                        sequence,
                        int(row["ANO_ELEICAO"]),
                        row["CD_TIPO_BEM_CANDIDATO"].strip(),
                        row["DS_TIPO_BEM_CANDIDATO"].strip(),
                    )
                    count, total = aggregates.get(key, (0, Decimal(0)))
                    aggregates[key] = (count + 1, total + amount)
            finally:
                text.close()
        return [
            AssetRecord(sequence, year, code, name, count, total)
            for (sequence, year, code, name), (count, total) in aggregates.items()
        ]

    def validate(self, records: list[CandidateRecord | AssetRecord]) -> None:
        if not records and not self._selected_candidate_sequences:
            raise SourceValidationError(
                "TSE sem registros para o recorte", code="empty_selection"
            )
        for record in records:
            if record.election_year != 2024:
                raise SourceValidationError(
                    "Ano eleitoral inesperado", code="tse_invalid_year"
                )
            if isinstance(record, AssetRecord) and record.total_amount < 0:
                raise SourceValidationError(
                    "Bem declarado negativo", code="tse_invalid_asset_amount"
                )

    def upsert(
        self,
        db: Session,
        records: list[CandidateRecord | AssetRecord],
        snapshot: SourceSnapshot,
    ) -> None:
        if not records:
            return
        if isinstance(records[0], CandidateRecord):
            self._upsert_candidates(db, records, snapshot)  # type: ignore[arg-type]
        else:
            self._upsert_assets(db, records, snapshot)  # type: ignore[arg-type]
        dataset = db.get(Dataset, snapshot.dataset_id)
        if dataset is not None:
            dataset.connector_status = "active"
            dataset.publication_status = "published"
            if dataset.source is not None:
                dataset.source.connector_status = "active"

    @staticmethod
    def _latest_by_key(db: Session, model: Any, keys: set[str]) -> dict[str, Any]:
        rows = db.scalars(
            select(model)
            .where(model.source_system == "tse", model.source_key.in_(keys))
            .order_by(model.source_key, desc(model.revision))
        )
        latest: dict[str, Any] = {}
        for row in rows:
            latest.setdefault(row.source_key, row)
        return latest

    def _upsert_candidates(
        self, db: Session, records: list[CandidateRecord], snapshot: SourceSnapshot
    ) -> None:
        keys = {f"2024:{record.candidate_sequence}" for record in records}
        people = self._latest_by_key(db, PoliticalPerson, keys)
        person_rows: list[dict[str, Any]] = []
        person_ids: dict[str, uuid.UUID] = {}
        for record in records:
            key = f"2024:{record.candidate_sequence}"
            previous = people.get(key)
            if previous is not None and (
                previous.full_name,
                previous.ballot_name,
            ) == (record.full_name, record.ballot_name):
                person_ids[key] = previous.id
                continue
            identifier = uuid.uuid4()
            person_ids[key] = identifier
            person_rows.append(
                {
                    "id": identifier,
                    "source_system": "tse",
                    "source_key": key,
                    "full_name": record.full_name,
                    "ballot_name": record.ballot_name,
                    "slug": f"{_slug(record.ballot_name or record.full_name)}-{record.candidate_sequence}",
                    "photo_url": None,
                    "source_document_url": snapshot.url,
                    "snapshot_id": snapshot.id,
                    "revision": 1 if previous is None else previous.revision + 1,
                }
            )
        if person_rows:
            db.execute(insert(PoliticalPerson), person_rows)

        previous_candidacies = self._latest_by_key(db, PoliticalCandidacy, keys)
        candidacy_rows: list[dict[str, Any]] = []
        mandate_rows: list[dict[str, Any]] = []
        previous_mandates = self._latest_by_key(db, PoliticalMandate, keys)
        today = datetime.now(UTC).date()
        for record in records:
            key = f"2024:{record.candidate_sequence}"
            person_id = person_ids[key]
            previous = previous_candidacies.get(key)
            values = (
                record.registration_status,
                record.election_result,
                record.party_acronym,
                record.office_code,
                record.ballot_number,
                record.municipality_code,
            )
            previous_values = (
                (
                    previous.registration_status,
                    previous.election_result,
                    previous.party_acronym,
                    previous.office_code,
                    previous.ballot_number,
                    previous.municipality_ibge_code,
                )
                if previous is not None
                else None
            )
            if (
                previous is None
                or previous_values != values
                or previous.person_id != person_id
            ):
                candidacy_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "source_system": "tse",
                        "source_key": key,
                        "person_id": person_id,
                        "election_year": record.election_year,
                        "election_type": record.election_type,
                        "office_code": record.office_code,
                        "office_name": record.office_name,
                        "state": record.state,
                        "municipality_ibge_code": record.municipality_code,
                        "ballot_number": record.ballot_number,
                        "party_acronym": record.party_acronym,
                        "registration_status": record.registration_status,
                        "election_result": record.election_result,
                        "vote_count": None,
                        "source_document_url": snapshot.url,
                        "snapshot_id": snapshot.id,
                        "revision": 1 if previous is None else previous.revision + 1,
                    }
                )
            normalized_result = normalize_name(record.election_result)
            if normalized_result not in ELECTED_RESULTS:
                continue
            previous_mandate = previous_mandates.get(key)
            term_start = date(2025, 1, 1)
            term_end = date(2028, 12, 31)
            active = term_start <= today <= term_end
            mandate_values = (
                person_id,
                record.party_acronym,
                record.office_code,
                record.municipality_code,
                record.election_result,
                active,
            )
            old_values = (
                (
                    previous_mandate.person_id,
                    previous_mandate.party_acronym,
                    previous_mandate.office_code,
                    previous_mandate.municipality_ibge_code,
                    previous_mandate.elected_status,
                    previous_mandate.active,
                )
                if previous_mandate is not None
                else None
            )
            if previous_mandate is None or old_values != mandate_values:
                mandate_rows.append(
                    {
                        "id": uuid.uuid4(),
                        "source_system": "tse",
                        "source_key": key,
                        "person_id": person_id,
                        "election_year": 2024,
                        "office_code": record.office_code,
                        "office_name": record.office_name,
                        "government_level": "municipal",
                        "state": record.state,
                        "municipality_ibge_code": record.municipality_code,
                        "party_acronym": record.party_acronym,
                        "elected_status": record.election_result,
                        "term_start": term_start,
                        "term_end": term_end,
                        "active": active,
                        "source_document_url": snapshot.url,
                        "snapshot_id": snapshot.id,
                        "revision": 1
                        if previous_mandate is None
                        else previous_mandate.revision + 1,
                    }
                )
        if candidacy_rows:
            db.execute(insert(PoliticalCandidacy), candidacy_rows)
        if mandate_rows:
            db.execute(insert(PoliticalMandate), mandate_rows)

    def _upsert_assets(
        self, db: Session, records: list[AssetRecord], snapshot: SourceSnapshot
    ) -> None:
        candidate_keys = {f"2024:{record.candidate_sequence}" for record in records}
        candidacies = self._latest_by_key(db, PoliticalCandidacy, candidate_keys)
        asset_keys = {
            f"2024:{record.candidate_sequence}:{record.asset_type_code}"
            for record in records
        }
        previous_assets = self._latest_by_key(db, DeclaredAssetSummary, asset_keys)
        rows: list[dict[str, Any]] = []
        for record in records:
            candidacy = candidacies.get(f"2024:{record.candidate_sequence}")
            if candidacy is None:
                continue
            key = f"2024:{record.candidate_sequence}:{record.asset_type_code}"
            previous = previous_assets.get(key)
            if previous is not None and (
                previous.asset_count,
                previous.total_amount,
                previous.asset_type_name,
            ) == (record.asset_count, record.total_amount, record.asset_type_name):
                continue
            rows.append(
                {
                    "id": uuid.uuid4(),
                    "source_system": "tse",
                    "source_key": key,
                    "candidacy_id": candidacy.id,
                    "election_year": record.election_year,
                    "asset_type_code": record.asset_type_code,
                    "asset_type_name": record.asset_type_name,
                    "asset_count": record.asset_count,
                    "total_amount": record.total_amount,
                    "source_document_url": snapshot.url,
                    "snapshot_id": snapshot.id,
                    "revision": 1 if previous is None else previous.revision + 1,
                }
            )
        if rows:
            db.execute(insert(DeclaredAssetSummary), rows)
