from __future__ import annotations

import io
import os
import socket
import time
import zipfile
from pathlib import Path

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException
from fastapi.testclient import TestClient
from ingestion.governance import safe_metadata_get
from sqlalchemy import create_engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from lente_api.governance_security import (
    Principal,
    authenticated_principal,
    principal_from_introspection,
    resolve_public_ips,
    validate_suggested_url,
    validate_worker_target,
)
from lente_api.main import app
from lente_api.models import AuditEvent, QuarantinedUpload, SourceSubmission
from lente_api.settings import get_settings


def _principal(role: str, subject: str = "reviewer-1") -> Principal:
    return Principal(subject=subject, roles=frozenset({role}), amr=frozenset({"mfa"}))


def _challenge(client: TestClient) -> tuple[str, str]:
    body = client.get("/api/v1/source-submissions/captcha").json()
    numbers = [int(part) for part in body["question"].replace("?", "").split() if part.isdigit()]
    return body["token"], str(sum(numbers))


def _submit(client: TestClient, *, contact: str | None = None) -> dict:
    token, answer = _challenge(client)
    response = client.post(
        "/api/v1/source-submissions",
        json={
            "public_name": "Catálogo municipal",
            "organization": "Prefeitura de Teste",
            "url": "https://dados.example.gov.br/catalogo",
            "description": "Catálogo público sugerido para verificação de licença e qualidade.",
            "contact": contact,
            "notification_opt_in": bool(contact),
            "captcha_token": token,
            "captcha_answer": answer,
            "website": "",
        },
    )
    assert response.status_code == 202, response.text
    return {**response.json(), "token": token, "answer": answer}


def test_url_validation_never_resolves_or_fetches(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: pytest.fail("DNS usado"))
    assert validate_suggested_url("https://localhost/fonte") == "https://localhost/fonte"
    with pytest.raises(HTTPException):
        validate_suggested_url("http://127.0.0.1/private")
    with pytest.raises(HTTPException):
        validate_suggested_url("https://user:secret@example.org/file")


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.7", "169.254.169.254", "::1"])
def test_ssrf_blocks_non_public_addresses(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (address, 443))],
    )
    with pytest.raises(ValueError, match="bloqueado"):
        resolve_public_ips("catalog.example")


def test_worker_blocks_redirect_host_and_dns_rebinding(monkeypatch: pytest.MonkeyPatch) -> None:
    answers = iter([frozenset({"203.0.113.10"}), frozenset({"203.0.113.11"})])
    monkeypatch.setattr(
        "lente_api.governance_security.resolve_public_ips", lambda _hostname: next(answers)
    )
    first = validate_worker_target("https://catalog.example/api", allowed_hosts={"catalog.example"})
    with pytest.raises(ValueError, match="rebind"):
        validate_worker_target(
            "https://catalog.example/api", allowed_hosts={"catalog.example"}, previous_ips=first
        )
    with pytest.raises(ValueError, match="allowlist"):
        validate_worker_target("https://169.254.169.254/latest", allowed_hosts={"catalog.example"})


def test_metadata_fetch_rejects_redirect_outside_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        status_code = 302
        headers = {"location": "https://private.invalid/metadata"}

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

    class Client:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def stream(self, *_args, **_kwargs):
            return Response()

    monkeypatch.setattr("ingestion.governance.httpx.Client", Client)
    monkeypatch.setattr(
        "ingestion.governance.validate_worker_target",
        lambda url, **_kwargs: (
            frozenset({"1.1.1.1"})
            if "catalog.example" in url
            else (_ for _ in ()).throw(ValueError("Destino fora da allowlist HTTPS"))
        ),
    )
    with pytest.raises(ValueError, match="allowlist"):
        safe_metadata_get(
            "https://catalog.example/api/3/action/package_search",
            allowed_hosts={"catalog.example"},
        )


def test_invalid_token_mfa_and_roles(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIDC_ISSUER", "https://id.example")
    monkeypatch.setenv("OIDC_AUDIENCE", "lente-curadoria")
    get_settings.cache_clear()
    base = {
        "active": True,
        "exp": int(time.time()) + 300,
        "iss": "https://id.example",
        "aud": "lente-curadoria",
        "sub": "curator-1",
        "roles": ["curator"],
    }
    with pytest.raises(HTTPException, match="MFA"):
        principal_from_introspection(base)
    with pytest.raises(HTTPException, match="inválido"):
        principal_from_introspection({**base, "exp": "not-a-number", "amr": ["mfa"]})
    principal = principal_from_introspection({**base, "amr": ["mfa"]})
    assert principal.roles == frozenset({"curator"})
    get_settings.cache_clear()


def test_public_reads_and_backoffice_requires_bearer() -> None:
    client = TestClient(app)
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/source-submissions/captcha").status_code == 200
    assert client.get("/api/v1/curation/submissions").status_code == 401
    assert (
        client.get("/api/v1/curation/submissions", cookies={"session": "fake"}).status_code == 401
    )


def test_zip_bomb_is_rejected(tmp_path: Path) -> None:
    archive = tmp_path / "bomb.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
        output.writestr("huge.csv", b"0" * (2 * 1024 * 1024))
    from lente_api.governance_api import _validate_archive

    with pytest.raises(HTTPException, match="compressão"):
        _validate_archive(archive)


@pytest.mark.integration
def test_submission_hourly_quota_is_enforced() -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL não configurada")
    client = TestClient(app, headers={"user-agent": "governance-quota-test"})
    responses = []
    for index in range(6):
        token, answer = _challenge(client)
        responses.append(
            client.post(
                "/api/v1/source-submissions",
                json={
                    "public_name": f"Fonte sob quota {index}",
                    "organization": "Órgão de teste de quota",
                    "url": f"https://dados.example.gov.br/quota/{index}",
                    "description": (
                        "Submissão usada apenas para validar o limite horário persistente."
                    ),
                    "captcha_token": token,
                    "captcha_answer": answer,
                    "website": "",
                },
            )
        )
    assert [response.status_code for response in responses] == [202, 202, 202, 202, 202, 429]


@pytest.mark.integration
def test_submission_replay_rbac_review_audit_upload_and_rollback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    database_url = os.environ.get("TEST_DATABASE_URL")
    if not database_url:
        pytest.skip("TEST_DATABASE_URL não configurada")
    monkeypatch.setenv("CONTACT_ENCRYPTION_KEY", Fernet.generate_key().decode())
    get_settings.cache_clear()
    client = TestClient(app)
    created = _submit(client, contact="pesquisador@example.org")
    submission_id = created["id"]

    replay = client.post(
        "/api/v1/source-submissions",
        json={
            "public_name": "Outra fonte",
            "organization": "Outro órgão",
            "url": "https://dados.example.gov.br/outro",
            "description": "Outra descrição suficientemente longa para a triagem humana.",
            "captcha_token": created["token"],
            "captcha_answer": created["answer"],
            "website": "",
        },
    )
    assert replay.status_code == 409

    engine = create_engine(database_url)
    with Session(engine) as db:
        item = db.get(SourceSubmission, submission_id)
        assert item is not None
        assert "pesquisador@example.org" not in (item.contact_ciphertext or "")

    app.dependency_overrides[authenticated_principal] = lambda: _principal("curator")
    try:
        listed = client.get("/api/v1/curation/submissions")
        assert listed.status_code == 200
        assert any(row["id"] == submission_id for row in listed.json()["items"])

        for status_name in ("triage", "verified"):
            response = client.post(
                f"/api/v1/curation/submissions/{submission_id}/reviews",
                json={
                    "to_status": status_name,
                    "reason": "Evidência revisada pela curadoria",
                    "evidence": {"checklist": True},
                },
            )
            assert response.status_code == 200, response.text

        forbidden = client.post(
            f"/api/v1/curation/submissions/{submission_id}/reviews",
            json={"to_status": "approved", "reason": "Tentativa sem papel adequado"},
        )
        assert forbidden.status_code == 403

        archive = io.BytesIO()
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as output:
            output.writestr("bomb.csv", b"0" * (2 * 1024 * 1024))
        upload = client.post(
            f"/api/v1/curation/submissions/{submission_id}/uploads",
            files={"file": ("bomb.zip", archive.getvalue(), "application/zip")},
        )
        assert upload.status_code == 422

        app.dependency_overrides[authenticated_principal] = lambda: _principal("data_steward")
        approved = client.post(
            f"/api/v1/curation/submissions/{submission_id}/reviews",
            json={"to_status": "approved", "reason": "Licença e privacidade verificadas"},
        )
        assert approved.status_code == 200

        app.dependency_overrides[authenticated_principal] = lambda: _principal("admin", "admin-1")
        published = client.post(
            f"/api/v1/curation/submissions/{submission_id}/reviews",
            json={"to_status": "published", "reason": "Registro da sugestão aprovado"},
        )
        assert published.status_code == 200
        assert published.json()["publication_scope"] == "source_suggestion_registry_only"
        rollback = client.post(
            f"/api/v1/curation/submissions/{submission_id}/rollback",
            json={"reason": "Retirada solicitada após nova evidência", "evidence": {}},
        )
        assert rollback.status_code == 200
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    with Session(engine) as db:
        upload_count = db.scalar(select(text("count(*)")).select_from(QuarantinedUpload))
        assert upload_count == 0
        event = db.scalar(select(AuditEvent).order_by(AuditEvent.sequence.desc()).limit(1))
        assert event is not None
        assert event.previous_hash is not None
        with pytest.raises(DBAPIError):
            db.execute(
                text("UPDATE audit_events SET reason = 'tampered' WHERE id = :id"),
                {"id": event.id},
            )
            db.commit()


@pytest.mark.integration
def test_verified_organization_submission_upload_and_separation() -> None:
    if not os.environ.get("TEST_DATABASE_URL"):
        pytest.skip("TEST_DATABASE_URL não configurada")
    client = TestClient(app)
    app.dependency_overrides[authenticated_principal] = lambda: _principal(
        "data_steward", "steward-organization"
    )
    try:
        organization = client.post(
            "/api/v1/curation/organizations",
            json={
                "name": "Prefeitura Institucional",
                "legal_identifier": "12345678000199",
                "official_domain": "prefeitura.example.gov.br",
            },
        )
        assert organization.status_code == 201, organization.text
        organization_id = organization.json()["id"]

        app.dependency_overrides[authenticated_principal] = lambda: _principal(
            "admin", "admin-organization"
        )
        verified = client.post(
            f"/api/v1/curation/organizations/{organization_id}/representatives/verify",
            json={
                "subject": "representative-1",
                "reason": "Documentação institucional conferida manualmente",
                "evidence_sha256": "a" * 64,
            },
        )
        assert verified.status_code == 200, verified.text

        app.dependency_overrides[authenticated_principal] = lambda: _principal(
            "registered_researcher", "representative-1"
        )
        submitted = client.post(
            "/api/v1/organization/source-submissions",
            json={
                "organization_id": organization_id,
                "public_name": "API institucional",
                "url": "https://prefeitura.example.gov.br/api",
                "description": "API oficial indicada por representante validado da organização.",
            },
        )
        assert submitted.status_code == 202, submitted.text
        submission_id = submitted.json()["id"]
        wrong_type = client.post(
            f"/api/v1/curation/submissions/{submission_id}/uploads",
            files={"file": ("payload.exe", b"unsafe", "application/octet-stream")},
        )
        assert wrong_type.status_code == 415
        uploaded = client.post(
            f"/api/v1/curation/submissions/{submission_id}/uploads",
            files={"file": ("dados.csv", b"codigo,valor\n1,2\n", "text/csv")},
        )
        assert uploaded.status_code == 202, uploaded.text
        assert uploaded.json()["scan_status"] == "pending"

        app.dependency_overrides[authenticated_principal] = lambda: _principal(
            "curator", "representative-1"
        )
        self_review = client.post(
            f"/api/v1/curation/submissions/{submission_id}/reviews",
            json={"to_status": "triage", "reason": "Tentativa de revisar a própria fonte"},
        )
        assert self_review.status_code == 403

        app.dependency_overrides[authenticated_principal] = lambda: _principal(
            "curator", "curator-other"
        )
        for status_name in ("triage", "verified"):
            reviewed = client.post(
                f"/api/v1/curation/submissions/{submission_id}/reviews",
                json={
                    "to_status": status_name,
                    "reason": "Revisão executada por pessoa diferente do representante",
                },
            )
            assert reviewed.status_code == 200, reviewed.text
        app.dependency_overrides[authenticated_principal] = lambda: _principal(
            "data_steward", "steward-other"
        )
        unsafe_approval = client.post(
            f"/api/v1/curation/submissions/{submission_id}/reviews",
            json={"to_status": "approved", "reason": "Tentativa antes do antivírus concluir"},
        )
        assert unsafe_approval.status_code == 409
    finally:
        app.dependency_overrides.clear()
