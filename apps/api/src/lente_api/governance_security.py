from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import secrets
import socket
import time
from dataclasses import dataclass
from typing import Annotated, Any
from urllib.parse import urlparse

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lente_api.settings import get_settings

bearer = HTTPBearer(auto_error=False)
ROLE_RANK = {"registered_researcher": 0, "curator": 1, "data_steward": 2, "admin": 3}


@dataclass(frozen=True, slots=True)
class Principal:
    subject: str
    roles: frozenset[str]
    amr: frozenset[str]


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def captcha_challenge(now: int | None = None) -> dict[str, str | int]:
    timestamp = now or int(time.time())
    left, right = secrets.randbelow(8) + 1, secrets.randbelow(8) + 1
    nonce = secrets.token_hex(12)
    payload = f"{timestamp}:{left}:{right}:{nonce}"
    secret = get_settings().submission_captcha_secret.encode()
    signature = hmac.new(secret, payload.encode(), hashlib.sha256).hexdigest()
    return {
        "question": f"Quanto é {left} + {right}?",
        "token": _b64(payload.encode()) + "." + signature,
        "expires_in": 600,
    }


def verify_captcha(token: str, answer: str, *, now: int | None = None) -> str:
    try:
        encoded, supplied_signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
        timestamp, left, right, _nonce = payload.split(":", 3)
    except (ValueError, UnicodeDecodeError) as exc:
        raise HTTPException(422, "Desafio inválido") from exc
    expected = hmac.new(
        get_settings().submission_captcha_secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    current = now or int(time.time())
    if not hmac.compare_digest(expected, supplied_signature) or current - int(
        timestamp
    ) not in range(0, 601):
        raise HTTPException(422, "Desafio inválido ou expirado")
    if not hmac.compare_digest(answer.strip(), str(int(left) + int(right))):
        raise HTTPException(422, "Resposta do desafio incorreta")
    return hashlib.sha256(token.encode()).hexdigest()


def requester_fingerprint(request: Request) -> str:
    host = request.client.host if request.client else "unknown"
    agent = request.headers.get("user-agent", "")[:200]
    secret = get_settings().submission_fingerprint_secret
    return hmac.new(secret.encode(), f"{host}|{agent}".encode(), hashlib.sha256).hexdigest()


def encrypt_contact(value: str) -> str:
    key = get_settings().contact_encryption_key
    if not key:
        raise HTTPException(503, "Contato opcional temporariamente indisponível")
    try:
        return Fernet(key.encode()).encrypt(value.encode()).decode()
    except (ValueError, InvalidToken) as exc:
        raise HTTPException(503, "Configuração segura de contato indisponível") from exc


def validate_suggested_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(422, "Informe uma URL HTTPS pública, sem credenciais")
    if parsed.port not in (None, 443):
        raise HTTPException(422, "Porta da URL não permitida")
    if len(value) > 2048:
        raise HTTPException(422, "URL excede o limite")
    return parsed.geturl()


def resolve_public_ips(hostname: str) -> frozenset[str]:
    try:
        addresses = {
            item[4][0] for item in socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
        }
    except socket.gaierror as exc:
        raise ValueError("DNS indisponível") from exc
    if not addresses:
        raise ValueError("DNS sem endereço")
    for raw in addresses:
        address = ipaddress.ip_address(raw)
        if not address.is_global:
            raise ValueError("Endereço privado, reservado ou local bloqueado")
    return frozenset(addresses)


def validate_worker_target(
    url: str, *, allowed_hosts: set[str], previous_ips: frozenset[str] | None = None
) -> frozenset[str]:
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.hostname not in allowed_hosts:
        raise ValueError("Destino fora da allowlist HTTPS")
    current = resolve_public_ips(parsed.hostname)
    if previous_ips is not None and current != previous_ips:
        raise ValueError("Possível DNS rebinding detectado")
    return current


def _claim_set(value: Any) -> frozenset[str]:
    if isinstance(value, str):
        return frozenset(part for part in value.replace(",", " ").split() if part)
    if isinstance(value, list):
        return frozenset(str(part) for part in value)
    return frozenset()


def principal_from_introspection(payload: dict[str, Any]) -> Principal:
    settings = get_settings()
    now = int(time.time())
    try:
        expires_at = int(payload.get("exp", 0))
    except (TypeError, ValueError) as exc:
        raise HTTPException(401, "Token inválido ou expirado") from exc
    if payload.get("active") is not True or expires_at <= now:
        raise HTTPException(401, "Token inválido ou expirado")
    if settings.oidc_issuer and payload.get("iss") != settings.oidc_issuer:
        raise HTTPException(401, "Emissor do token inválido")
    audience = _claim_set(payload.get("aud"))
    if settings.oidc_audience and settings.oidc_audience not in audience:
        raise HTTPException(401, "Audiência do token inválida")
    subject = str(payload.get("sub") or "")
    if not subject:
        raise HTTPException(401, "Token sem sujeito")
    roles = _claim_set(payload.get("roles") or payload.get("role"))
    amr = _claim_set(payload.get("amr"))
    if settings.oidc_mfa_required and not amr.intersection({"mfa", "otp", "hwk", "webauthn"}):
        raise HTTPException(403, "MFA é obrigatório no backoffice")
    return Principal(subject=subject, roles=roles, amr=amr)


async def authenticated_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> Principal:
    settings = get_settings()
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Autenticação obrigatória")
    if (
        not settings.oidc_introspection_url
        or not settings.oidc_client_id
        or not settings.oidc_client_secret
    ):
        raise HTTPException(503, "IdP do backoffice não configurado")
    parsed = urlparse(settings.oidc_introspection_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        raise HTTPException(503, "Endpoint de identidade inseguro")
    try:
        async with httpx.AsyncClient(timeout=5, follow_redirects=False) as client:
            response = await client.post(
                settings.oidc_introspection_url,
                data={"token": credentials.credentials},
                auth=(settings.oidc_client_id, settings.oidc_client_secret),
                headers={"Accept": "application/json"},
            )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise HTTPException(503, "Resposta inválida do provedor de identidade")
        return principal_from_introspection(payload)
    except HTTPException:
        raise
    except (httpx.HTTPError, json.JSONDecodeError) as exc:
        raise HTTPException(503, "Falha ao validar identidade") from exc


def require_role(minimum: str):
    async def dependency(
        principal: Annotated[Principal, Depends(authenticated_principal)],
    ) -> Principal:
        rank = max((ROLE_RANK.get(role, -1) for role in principal.roles), default=-1)
        if rank < ROLE_RANK[minimum]:
            raise HTTPException(403, "Papel insuficiente")
        return principal

    return dependency
