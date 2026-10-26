from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import uuid
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from lente_api.database import get_db
from lente_api.governance_security import (
    Principal,
    authenticated_principal,
    captcha_challenge,
    encrypt_contact,
    requester_fingerprint,
    require_role,
    validate_suggested_url,
    verify_captcha,
)
from lente_api.models import (
    AuditEvent,
    Organization,
    OrganizationRepresentative,
    QuarantinedUpload,
    SourceDiscovery,
    SourceSubmission,
    SubmissionReview,
)
from lente_api.settings import get_settings

router = APIRouter(prefix="/api/v1", tags=["governance"])
DbSession = Annotated[Session, Depends(get_db)]
Curator = Annotated[Principal, Depends(require_role("curator"))]
Authenticated = Annotated[Principal, Depends(authenticated_principal)]


class SubmissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    public_name: str = Field(min_length=2, max_length=160)
    organization: str = Field(min_length=2, max_length=240)
    url: str = Field(min_length=12, max_length=2048)
    description: str = Field(min_length=20, max_length=4000)
    contact: str | None = Field(None, max_length=320)
    notification_opt_in: bool = False
    captcha_token: str = Field(min_length=20, max_length=1000)
    captcha_answer: str = Field(min_length=1, max_length=10)
    website: str = Field("", max_length=1)  # honeypot; must remain empty

    @field_validator("contact")
    @classmethod
    def validate_contact(cls, value: str | None) -> str | None:
        if value and not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value.strip()):
            raise ValueError("Contato deve ser um e-mail válido")
        return value.strip().lower() if value else None


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    to_status: Literal["triage", "verified", "quarantined", "approved", "rejected", "published"]
    reason: str = Field(min_length=12, max_length=4000)
    evidence: dict[str, Any] = Field(default_factory=dict)


class RollbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=12, max_length=4000)
    evidence: dict[str, Any] = Field(default_factory=dict)


class OrganizationIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=2, max_length=240)
    legal_identifier: str | None = Field(None, min_length=8, max_length=40)
    official_domain: str | None = Field(None, max_length=200)


class RepresentativeIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subject: str = Field(min_length=2, max_length=240)
    reason: str = Field(min_length=12, max_length=4000)
    evidence_storage_key: str | None = Field(None, max_length=2000)
    evidence_sha256: str | None = Field(None, pattern=r"^[0-9a-f]{64}$")


class OrganizationSubmissionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    organization_id: uuid.UUID
    public_name: str = Field(min_length=2, max_length=160)
    url: str = Field(min_length=12, max_length=2048)
    description: str = Field(min_length=20, max_length=4000)


class DiscoveryReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["reviewed", "rejected"]
    reason: str = Field(min_length=12, max_length=4000)


TRANSITIONS: dict[str, set[str]] = {
    "received": {"triage", "quarantined", "rejected"},
    "triage": {"verified", "quarantined", "rejected"},
    "verified": {"approved", "quarantined", "rejected"},
    "quarantined": {"triage", "rejected"},
    "approved": {"published", "rejected"},
    "rejected": {"triage"},
    "published": set(),
}
REQUIRED_ROLE = {"approved": "data_steward", "published": "admin"}
ROLE_RANK = {"curator": 1, "data_steward": 2, "admin": 3}


def _principal_role(principal: Principal) -> str:
    return max(principal.roles, key=lambda role: ROLE_RANK.get(role, -1))


def _audit(
    db: Session,
    *,
    actor: str,
    role: str,
    action: str,
    resource_type: str,
    resource_id: str,
    reason: str | None = None,
    details: dict[str, Any] | None = None,
) -> AuditEvent:
    db.execute(text("SELECT pg_advisory_xact_lock(74638291)"))
    previous = db.scalar(select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(1))
    sequence = (previous.sequence if previous else 0) + 1
    created_at = datetime.now(UTC)
    payload = json.dumps(
        {
            "sequence": sequence,
            "actor": actor,
            "role": role,
            "action": action,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "reason": reason,
            "details": details or {},
            "created_at": created_at.isoformat(),
            "previous_hash": previous.event_hash if previous else None,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    event = AuditEvent(
        id=uuid.uuid4(),
        sequence=sequence,
        actor_subject=actor,
        actor_role=role,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        reason=reason,
        details=details or {},
        previous_hash=previous.event_hash if previous else None,
        event_hash=hashlib.sha256(payload.encode()).hexdigest(),
        created_at=created_at,
    )
    db.add(event)
    return event


def _serialize_submission(item: SourceSubmission, *, internal: bool = False) -> dict[str, Any]:
    payload = {
        "id": str(item.id),
        "public_name": item.public_name,
        "organization": item.organization_name,
        "url": item.proposed_url,
        "description": item.description,
        "status": item.status,
        "source_origin": item.source_origin,
        "publication_scope": "source_suggestion_registry_only",
        "created_at": item.created_at,
        "updated_at": item.updated_at,
    }
    if internal:
        payload.update(
            {
                "notification_opt_in": item.notification_opt_in,
                "has_contact": bool(item.contact_ciphertext),
                "submitted_by_subject": item.submitted_by_subject,
            }
        )
    return payload


def _is_curator(principal: Principal) -> bool:
    return any(ROLE_RANK.get(role, -1) >= ROLE_RANK["curator"] for role in principal.roles)


def _verified_representative(
    db: Session, *, principal: Principal, organization_id: uuid.UUID
) -> OrganizationRepresentative | None:
    return db.scalar(
        select(OrganizationRepresentative).where(
            OrganizationRepresentative.organization_id == organization_id,
            OrganizationRepresentative.subject == principal.subject,
            OrganizationRepresentative.status == "verified",
        )
    )


def _subject_fingerprint(subject: str) -> str:
    secret = get_settings().submission_fingerprint_secret.encode()
    return hmac.new(secret, subject.encode(), hashlib.sha256).hexdigest()


@router.get("/source-submissions/captcha")
def get_captcha() -> dict[str, str | int]:
    return captcha_challenge()


@router.post("/source-submissions", status_code=status.HTTP_202_ACCEPTED)
def create_submission(payload: SubmissionIn, request: Request, db: DbSession) -> dict[str, Any]:
    if payload.website:
        raise HTTPException(422, "Submissão inválida")
    challenge_hash = verify_captcha(payload.captcha_token, payload.captcha_answer)
    fingerprint = requester_fingerprint(request)
    lock_key = int.from_bytes(bytes.fromhex(fingerprint[:16]), byteorder="big", signed=True)
    db.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": lock_key})
    cutoff = datetime.now(UTC) - timedelta(hours=1)
    recent = db.scalar(
        select(func.count(SourceSubmission.id)).where(
            SourceSubmission.submitter_fingerprint == fingerprint,
            SourceSubmission.created_at >= cutoff,
        )
    )
    if (recent or 0) >= get_settings().submission_hourly_quota:
        raise HTTPException(429, "Limite temporário de submissões atingido")
    now = datetime.now(UTC)
    item = SourceSubmission(
        id=uuid.uuid4(),
        public_name=payload.public_name.strip(),
        organization_name=payload.organization.strip(),
        proposed_url=validate_suggested_url(payload.url),
        description=payload.description.strip(),
        contact_ciphertext=encrypt_contact(payload.contact) if payload.contact else None,
        notification_opt_in=payload.notification_opt_in and bool(payload.contact),
        submitter_fingerprint=fingerprint,
        submitted_by_subject=None,
        organization_id=None,
        challenge_hash=challenge_hash,
        status="received",
        source_origin="third_party_submission",
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    _audit(
        db,
        actor=f"anonymous:{fingerprint[:12]}",
        role="anonymous",
        action="submission_received",
        resource_type="source_submission",
        resource_id=str(item.id),
        details={"organization": item.organization_name, "remote_fetch": False},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Desafio já utilizado") from exc
    return {
        "id": str(item.id),
        "status": item.status,
        "message": "Sugestão recebida para triagem humana; nenhum acesso à URL foi executado.",
    }


@router.post("/organization/source-submissions", status_code=status.HTTP_202_ACCEPTED)
def create_organization_submission(
    payload: OrganizationSubmissionIn,
    principal: Authenticated,
    db: DbSession,
) -> dict[str, Any]:
    organization = db.get(Organization, payload.organization_id)
    representative = _verified_representative(
        db, principal=principal, organization_id=payload.organization_id
    )
    if organization is None or organization.verification_status != "verified" or not representative:
        raise HTTPException(403, "Organização e representante precisam estar verificados")
    now = datetime.now(UTC)
    item = SourceSubmission(
        id=uuid.uuid4(),
        public_name=payload.public_name.strip(),
        organization_name=organization.name,
        proposed_url=validate_suggested_url(payload.url),
        description=payload.description.strip(),
        contact_ciphertext=None,
        notification_opt_in=False,
        submitter_fingerprint=_subject_fingerprint(principal.subject),
        submitted_by_subject=principal.subject,
        organization_id=organization.id,
        challenge_hash=hashlib.sha256(
            f"organization:{principal.subject}:{uuid.uuid4()}".encode()
        ).hexdigest(),
        status="received",
        source_origin="verified_organization_submission",
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    _audit(
        db,
        actor=principal.subject,
        role="organization_representative",
        action="organization_submission_received",
        resource_type="source_submission",
        resource_id=str(item.id),
        details={"organization_id": str(organization.id), "remote_fetch": False},
    )
    db.commit()
    return {
        "id": str(item.id),
        "status": item.status,
        "message": "Indicação recebida em quarentena lógica; nenhuma URL foi acessada.",
    }


@router.get("/curation/submissions")
def list_submissions(
    _principal: Curator,
    db: DbSession,
    review_status: str | None = Query(None, alias="status", max_length=40),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict[str, Any]:
    statement = select(SourceSubmission)
    count_statement = select(func.count(SourceSubmission.id))
    if review_status:
        statement = statement.where(SourceSubmission.status == review_status)
        count_statement = count_statement.where(SourceSubmission.status == review_status)
    rows = list(
        db.scalars(statement.order_by(SourceSubmission.created_at).limit(limit).offset(offset))
    )
    return {
        "items": [_serialize_submission(item, internal=True) for item in rows],
        "count": db.scalar(count_statement) or 0,
        "limit": limit,
        "offset": offset,
    }


@router.post("/curation/submissions/{submission_id}/reviews")
def review_submission(
    submission_id: uuid.UUID,
    payload: ReviewIn,
    principal: Curator,
    db: DbSession,
) -> dict[str, Any]:
    item = db.scalar(
        select(SourceSubmission).where(SourceSubmission.id == submission_id).with_for_update()
    )
    if item is None:
        raise HTTPException(404, "Submissão não encontrada")
    if payload.to_status not in TRANSITIONS[item.status]:
        raise HTTPException(409, f"Transição {item.status} → {payload.to_status} não permitida")
    role = _principal_role(principal)
    required = REQUIRED_ROLE.get(payload.to_status, "curator")
    if ROLE_RANK.get(role, -1) < ROLE_RANK[required]:
        raise HTTPException(403, f"A transição exige papel {required}")
    if item.submitted_by_subject and item.submitted_by_subject == principal.subject:
        raise HTTPException(403, "Quem submeteu não pode revisar ou aprovar")
    if payload.to_status in {"approved", "published"}:
        unsafe_uploads = db.scalar(
            select(func.count(QuarantinedUpload.id)).where(
                QuarantinedUpload.submission_id == item.id,
                QuarantinedUpload.scan_status != "clean",
            )
        )
        if unsafe_uploads:
            raise HTTPException(409, "Há arquivo sem resultado limpo do antivírus")
    previous = item.status
    item.status = payload.to_status
    item.updated_at = datetime.now(UTC)
    db.add(
        SubmissionReview(
            id=uuid.uuid4(),
            submission_id=item.id,
            from_status=previous,
            to_status=item.status,
            reviewer_subject=principal.subject,
            reviewer_role=role,
            reason=payload.reason,
            evidence=payload.evidence,
            created_at=item.updated_at,
        )
    )
    _audit(
        db,
        actor=principal.subject,
        role=role,
        action=f"submission_{payload.to_status}",
        resource_type="source_submission",
        resource_id=str(item.id),
        reason=payload.reason,
        details={"from": previous, "to": item.status, "evidence": payload.evidence},
    )
    db.commit()
    return _serialize_submission(item, internal=True)


@router.post("/curation/submissions/{submission_id}/rollback")
def rollback_publication(
    submission_id: uuid.UUID,
    payload: RollbackIn,
    principal: Annotated[Principal, Depends(require_role("admin"))],
    db: DbSession,
) -> dict[str, Any]:
    item = db.scalar(
        select(SourceSubmission).where(SourceSubmission.id == submission_id).with_for_update()
    )
    if item is None or item.status != "published":
        raise HTTPException(409, "Somente publicação existente pode ser retirada")
    item.status = "approved"
    item.updated_at = datetime.now(UTC)
    db.add(
        SubmissionReview(
            id=uuid.uuid4(),
            submission_id=item.id,
            from_status="published",
            to_status="approved",
            reviewer_subject=principal.subject,
            reviewer_role="admin",
            reason=payload.reason,
            evidence=payload.evidence,
            created_at=item.updated_at,
        )
    )
    _audit(
        db,
        actor=principal.subject,
        role="admin",
        action="submission_publication_withdrawn",
        resource_type="source_submission",
        resource_id=str(item.id),
        reason=payload.reason,
        details=payload.evidence,
    )
    db.commit()
    return _serialize_submission(item, internal=True)


@router.post("/curation/organizations", status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationIn,
    principal: Annotated[Principal, Depends(require_role("data_steward"))],
    db: DbSession,
) -> dict[str, Any]:
    legal_hash = (
        hmac.new(
            get_settings().submission_fingerprint_secret.encode(),
            payload.legal_identifier.encode(),
            hashlib.sha256,
        ).hexdigest()
        if payload.legal_identifier
        else None
    )
    domain = payload.official_domain.strip().lower() if payload.official_domain else None
    if domain and ("/" in domain or ":" in domain or "@" in domain):
        raise HTTPException(422, "Informe apenas o domínio institucional")
    item = Organization(
        id=uuid.uuid4(),
        name=payload.name.strip(),
        legal_identifier_hash=legal_hash,
        official_domain=domain,
        verification_status="pending",
        verification_evidence={},
        verified_at=None,
        verified_by_subject=None,
        created_at=datetime.now(UTC),
    )
    db.add(item)
    _audit(
        db,
        actor=principal.subject,
        role=_principal_role(principal),
        action="organization_created",
        resource_type="organization",
        resource_id=str(item.id),
        reason="Aguardando validação institucional humana",
    )
    db.commit()
    return {"id": str(item.id), "name": item.name, "verification_status": item.verification_status}


@router.post("/curation/organizations/{organization_id}/representatives/verify")
def verify_representative(
    organization_id: uuid.UUID,
    payload: RepresentativeIn,
    principal: Annotated[Principal, Depends(require_role("admin"))],
    db: DbSession,
) -> dict[str, Any]:
    organization = db.get(Organization, organization_id)
    if organization is None:
        raise HTTPException(404, "Organização não encontrada")
    representative = db.scalar(
        select(OrganizationRepresentative).where(
            OrganizationRepresentative.organization_id == organization_id,
            OrganizationRepresentative.subject == payload.subject,
        )
    )
    now = datetime.now(UTC)
    if representative is None:
        representative = OrganizationRepresentative(
            id=uuid.uuid4(),
            organization_id=organization_id,
            subject=payload.subject,
            created_at=now,
        )
        db.add(representative)
    representative.status = "verified"
    representative.evidence_storage_key = payload.evidence_storage_key
    representative.evidence_sha256 = payload.evidence_sha256
    representative.verified_at = now
    representative.verified_by_subject = principal.subject
    organization.verification_status = "verified"
    organization.verified_at = now
    organization.verified_by_subject = principal.subject
    organization.verification_evidence = {
        "reason": payload.reason,
        "evidence_sha256": payload.evidence_sha256,
    }
    _audit(
        db,
        actor=principal.subject,
        role="admin",
        action="organization_representative_verified",
        resource_type="organization_representative",
        resource_id=str(representative.id),
        reason=payload.reason,
        details={"organization_id": str(organization_id)},
    )
    db.commit()
    return {
        "organization_id": str(organization_id),
        "subject": representative.subject,
        "status": representative.status,
    }


def _validate_archive(path: Path) -> None:
    if not zipfile.is_zipfile(path):
        return
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 1000:
            raise HTTPException(422, "ZIP excede o limite de arquivos")
        total = 0
        for member in members:
            name = member.filename.replace("\\", "/")
            if name.startswith("/") or "../" in f"/{name}":
                raise HTTPException(422, "Caminho inseguro no ZIP")
            total += member.file_size
            if member.file_size > 100 * 1024 * 1024:
                raise HTTPException(422, "Arquivo expandido excede o limite")
            if member.compress_size and member.file_size / member.compress_size > 100:
                raise HTTPException(422, "Taxa de compressão suspeita")
        if total > 250 * 1024 * 1024:
            raise HTTPException(422, "Conteúdo expandido excede o limite")


@router.post("/curation/submissions/{submission_id}/uploads", status_code=202)
async def quarantine_upload(
    submission_id: uuid.UUID,
    principal: Authenticated,
    db: DbSession,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    item = db.get(SourceSubmission, submission_id)
    if item is None:
        raise HTTPException(404, "Submissão não encontrada")
    representative = (
        _verified_representative(db, principal=principal, organization_id=item.organization_id)
        if item.organization_id
        else None
    )
    if not _is_curator(principal) and not representative:
        raise HTTPException(403, "Upload restrito a curadores ou representante verificado")
    if (
        item.submitted_by_subject
        and item.submitted_by_subject != principal.subject
        and not _is_curator(principal)
    ):
        raise HTTPException(403, "Representante só pode anexar à própria submissão")
    allowed_types = {
        "text/csv",
        "application/json",
        "application/zip",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    }
    media_type = file.content_type or "application/octet-stream"
    if media_type not in allowed_types:
        raise HTTPException(415, "Tipo de arquivo não permitido")
    root = get_settings().quarantine_dir.resolve()
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    upload_id = uuid.uuid4()
    target = (root / f"{upload_id}.bin").resolve()
    if root not in target.parents:
        raise HTTPException(400, "Destino inválido")
    digest = hashlib.sha256()
    size = 0
    try:
        with target.open("xb") as stream:
            while chunk := await file.read(64 * 1024):
                size += len(chunk)
                if size > get_settings().quarantine_max_bytes:
                    raise HTTPException(413, "Arquivo excede o limite")
                digest.update(chunk)
                stream.write(chunk)
        _validate_archive(target)
    except Exception:
        target.unlink(missing_ok=True)
        raise
    os.chmod(target, 0o600)
    upload = QuarantinedUpload(
        id=upload_id,
        submission_id=item.id,
        organization_id=item.organization_id,
        uploaded_by_subject=principal.subject,
        original_filename=Path(file.filename or "arquivo").name[:260],
        storage_key=str(target),
        media_type=media_type,
        byte_count=size,
        sha256=digest.hexdigest(),
        scan_status="pending",
        scan_details="Aguardando antivírus no worker segregado",
        created_at=datetime.now(UTC),
        scanned_at=None,
    )
    db.add(upload)
    item.status = "quarantined"
    item.updated_at = datetime.now(UTC)
    actor_role = (
        _principal_role(principal) if _is_curator(principal) else "organization_representative"
    )
    _audit(
        db,
        actor=principal.subject,
        role=actor_role,
        action="upload_quarantined",
        resource_type="quarantined_upload",
        resource_id=str(upload.id),
        reason="Arquivo recebido em storage privado",
        details={"submission_id": str(item.id), "bytes": size, "sha256": upload.sha256},
    )
    db.commit()
    return {
        "id": str(upload.id),
        "scan_status": upload.scan_status,
        "byte_count": size,
        "sha256": upload.sha256,
    }


@router.get("/curation/discoveries")
def list_discoveries(
    _principal: Curator,
    db: DbSession,
    limit: int = Query(50, ge=1, le=100),
) -> dict[str, Any]:
    rows = list(
        db.scalars(
            select(SourceDiscovery).order_by(SourceDiscovery.last_seen_at.desc()).limit(limit)
        )
    )
    return {
        "items": [
            {
                "id": str(row.id),
                "registry": row.registry_name,
                "external_id": row.external_id,
                "title": row.title,
                "license": row.license,
                "canonical_url": row.canonical_url,
                "diff": row.diff_json,
                "status": row.status,
                "last_seen_at": row.last_seen_at,
            }
            for row in rows
        ]
    }


@router.post("/curation/discoveries/{discovery_id}/review")
def review_discovery(
    discovery_id: uuid.UUID,
    payload: DiscoveryReviewIn,
    principal: Curator,
    db: DbSession,
) -> dict[str, Any]:
    item = db.scalar(
        select(SourceDiscovery).where(SourceDiscovery.id == discovery_id).with_for_update()
    )
    if item is None:
        raise HTTPException(404, "Descoberta não encontrada")
    previous = item.status
    item.status = payload.status
    _audit(
        db,
        actor=principal.subject,
        role=_principal_role(principal),
        action=f"discovery_{payload.status}",
        resource_type="source_discovery",
        resource_id=str(item.id),
        reason=payload.reason,
        details={"from": previous, "to": item.status},
    )
    db.commit()
    return {
        "id": str(item.id),
        "status": item.status,
        "message": "Revisão registrada; nenhuma ingestão ou publicação foi habilitada.",
    }


@router.get("/curation/audit-events")
def audit_events(
    _principal: Curator,
    db: DbSession,
    limit: int = Query(100, ge=1, le=500),
) -> dict[str, Any]:
    rows = list(db.scalars(select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(limit)))
    return {
        "items": [
            {
                "sequence": row.sequence,
                "actor_subject": row.actor_subject,
                "actor_role": row.actor_role,
                "action": row.action,
                "resource_type": row.resource_type,
                "resource_id": row.resource_id,
                "reason": row.reason,
                "details": row.details,
                "previous_hash": row.previous_hash,
                "event_hash": row.event_hash,
                "created_at": row.created_at,
            }
            for row in rows
        ]
    }


@router.get("/curation/metrics")
def curation_metrics(_principal: Curator, db: DbSession) -> dict[str, Any]:
    cutoff = datetime.now(UTC) - timedelta(days=get_settings().discovery_stale_days)
    submissions = {
        key: value
        for key, value in db.execute(
            select(SourceSubmission.status, func.count(SourceSubmission.id)).group_by(
                SourceSubmission.status
            )
        )
    }
    scans = {
        key: value
        for key, value in db.execute(
            select(QuarantinedUpload.scan_status, func.count(QuarantinedUpload.id)).group_by(
                QuarantinedUpload.scan_status
            )
        )
    }
    return {
        "submissions_by_status": submissions,
        "uploads_by_scan_status": scans,
        "discoveries_pending": db.scalar(
            select(func.count(SourceDiscovery.id)).where(SourceDiscovery.status == "review_pending")
        )
        or 0,
        "discoveries_stale": db.scalar(
            select(func.count(SourceDiscovery.id)).where(SourceDiscovery.last_seen_at < cutoff)
        )
        or 0,
        "stale_after_days": get_settings().discovery_stale_days,
        "last_audit_sequence": db.scalar(select(func.max(AuditEvent.sequence))) or 0,
    }
