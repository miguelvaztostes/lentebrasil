from __future__ import annotations

import hashlib
import json
import socket
import struct
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import httpx
from lente_api.governance_api import _audit
from lente_api.governance_security import validate_worker_target
from lente_api.models import QuarantinedUpload, SourceDiscovery
from lente_api.settings import get_settings
from sqlalchemy import select
from sqlalchemy.orm import Session

MAX_METADATA_BYTES = 5 * 1024 * 1024


def safe_metadata_get(
    url: str, *, allowed_hosts: set[str]
) -> tuple[dict, dict[str, str]]:
    current = url
    approved_ips = None
    with httpx.Client(timeout=15, follow_redirects=False) as client:
        for _ in range(4):
            approved_ips = validate_worker_target(
                current, allowed_hosts=allowed_hosts, previous_ips=approved_ips
            )
            with client.stream(
                "GET", current, headers={"Accept": "application/json"}
            ) as response:
                if response.status_code in {301, 302, 303, 307, 308}:
                    location = response.headers.get("location")
                    if not location:
                        raise ValueError("Redirect sem destino")
                    target = urljoin(current, location)
                    if urlparse(target).hostname != urlparse(current).hostname:
                        approved_ips = None
                    current = target
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").lower()
                if "json" not in content_type:
                    raise ValueError("CKAN retornou content-type não JSON")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body.extend(chunk)
                    if len(body) > MAX_METADATA_BYTES:
                        raise ValueError("Metadados excedem o limite")
                validate_worker_target(
                    current, allowed_hosts=allowed_hosts, previous_ips=approved_ips
                )
                return json.loads(body), {
                    "etag": response.headers.get("etag", ""),
                    "url": str(response.url),
                }
    raise ValueError("Limite de redirects excedido")


def discover_ckan(db: Session) -> dict[str, int]:
    settings = get_settings()
    urls = settings.ckan_discovery_urls
    allowed = set(settings.discovery_allowed_hosts)
    if not urls:
        return {"registries": 0, "seen": 0, "changed": 0}
    if not allowed:
        raise RuntimeError("DISCOVERY_ALLOWED_HOSTS é obrigatório")
    seen = changed = 0
    now = datetime.now(UTC)
    for url in urls:
        document, headers = safe_metadata_get(url, allowed_hosts=allowed)
        if document.get("success") is not True or not isinstance(
            document.get("result"), dict
        ):
            raise ValueError("Resposta CKAN inválida")
        packages = document["result"].get("results", [])
        if not isinstance(packages, list):
            raise TypeError("Lista CKAN inválida")
        registry = urlparse(url).hostname or "ckan"
        registry_seen: set[str] = set()
        for package in packages:
            if (
                not isinstance(package, dict)
                or not package.get("id")
                or not package.get("title")
            ):
                continue
            resources = (
                package.get("resources")
                if isinstance(package.get("resources"), list)
                else []
            )
            first_resource_url = next(
                (
                    row.get("url")
                    for row in resources
                    if isinstance(row, dict) and row.get("url")
                ),
                None,
            )
            schema = [
                {
                    "format": row.get("format"),
                    "name": row.get("name"),
                    "url_type": row.get("url_type"),
                }
                for row in resources
                if isinstance(row, dict)
            ]
            normalized = {
                "title": package["title"],
                "license": package.get("license_title") or package.get("license_id"),
                "url": package.get("url") or first_resource_url or url,
                "etag": headers.get("etag"),
                "schema": schema,
            }
            metadata_hash = hashlib.sha256(
                json.dumps(normalized, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            schema_hash = hashlib.sha256(
                json.dumps(schema, sort_keys=True, ensure_ascii=False).encode()
            ).hexdigest()
            item = db.scalar(
                select(SourceDiscovery).where(
                    SourceDiscovery.registry_name == registry,
                    SourceDiscovery.external_id == str(package["id"]),
                )
            )
            diff = {}
            registry_seen.add(str(package["id"]))
            if item is None:
                item = SourceDiscovery(
                    id=uuid.uuid4(),
                    registry_name=registry,
                    external_id=str(package["id"]),
                    title=str(package["title"])[:500],
                    license=normalized["license"],
                    canonical_url=str(normalized["url"]),
                    etag=headers.get("etag") or None,
                    schema_hash=schema_hash,
                    metadata_hash=metadata_hash,
                    metadata_json=package,
                    diff_json={"new": True},
                    status="review_pending",
                    first_seen_at=now,
                    last_seen_at=now,
                )
                db.add(item)
                _audit(
                    db,
                    actor="system:ckan-discovery",
                    role="system",
                    action="source_discovered",
                    resource_type="source_discovery",
                    resource_id=str(item.id),
                    reason="Metadado novo encaminhado à revisão humana",
                    details={"registry": registry, "external_id": item.external_id},
                )
                changed += 1
            elif item.metadata_hash != metadata_hash:
                for field, old, new in (
                    ("title", item.title, normalized["title"]),
                    ("license", item.license, normalized["license"]),
                    ("url", item.canonical_url, normalized["url"]),
                    ("etag", item.etag, headers.get("etag") or None),
                    ("schema_hash", item.schema_hash, schema_hash),
                ):
                    if old != new:
                        diff[field] = {"before": old, "after": new}
                item.title = str(normalized["title"])[:500]
                item.license = normalized["license"]
                item.canonical_url = str(normalized["url"])
                item.etag = headers.get("etag") or None
                item.schema_hash = schema_hash
                item.metadata_hash = metadata_hash
                item.metadata_json = package
                item.diff_json = diff
                item.status = "review_pending"
                _audit(
                    db,
                    actor="system:ckan-discovery",
                    role="system",
                    action="source_metadata_changed",
                    resource_type="source_discovery",
                    resource_id=str(item.id),
                    reason="Alteração encaminhada à revisão humana",
                    details=diff,
                )
                changed += 1
            item.last_seen_at = now
            seen += 1
        reported_count = document["result"].get("count")
        if isinstance(reported_count, int) and reported_count <= len(packages):
            missing = list(
                db.scalars(
                    select(SourceDiscovery).where(
                        SourceDiscovery.registry_name == registry,
                        SourceDiscovery.external_id.not_in(registry_seen),
                        SourceDiscovery.status != "missing_review",
                    )
                )
            )
            for item in missing:
                item.status = "missing_review"
                item.diff_json = {
                    "absence": {"before": "present", "after": "not_returned"}
                }
                _audit(
                    db,
                    actor="system:ckan-discovery",
                    role="system",
                    action="source_missing",
                    resource_type="source_discovery",
                    resource_id=str(item.id),
                    reason="Ausência detectada em varredura completa; requer revisão humana",
                    details={"registry": registry},
                )
                changed += 1
    db.commit()
    return {"registries": len(urls), "seen": seen, "changed": changed}


def _clamav_scan(path: Path, host: str, port: int) -> tuple[bool, str]:
    with socket.create_connection((host, port), timeout=10) as connection:
        connection.sendall(b"zINSTREAM\0")
        with path.open("rb") as stream:
            while chunk := stream.read(64 * 1024):
                connection.sendall(struct.pack(">I", len(chunk)) + chunk)
        connection.sendall(struct.pack(">I", 0))
        reply = connection.recv(4096).decode(errors="replace").strip("\0\r\n")
    if reply.endswith("OK"):
        return True, reply
    if "FOUND" in reply:
        return False, reply
    raise RuntimeError(f"Resposta ClamAV inesperada: {reply[:200]}")


def scan_quarantined_uploads(db: Session, *, limit: int = 5) -> dict[str, int]:
    settings = get_settings()
    if not settings.clamav_host:
        return {"pending": 0, "clean": 0, "infected": 0, "failed": 0}
    rows = list(
        db.scalars(
            select(QuarantinedUpload)
            .where(QuarantinedUpload.scan_status == "pending")
            .order_by(QuarantinedUpload.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
    )
    counts = {"pending": len(rows), "clean": 0, "infected": 0, "failed": 0}
    for item in rows:
        try:
            clean, detail = _clamav_scan(
                Path(item.storage_key), settings.clamav_host, settings.clamav_port
            )
            item.scan_status = "clean" if clean else "infected"
            counts[item.scan_status] += 1
            item.scan_details = detail[:1000]
            item.scanned_at = datetime.now(UTC)
            _audit(
                db,
                actor="system:clamav",
                role="system",
                action=f"upload_{item.scan_status}",
                resource_type="quarantined_upload",
                resource_id=str(item.id),
                reason="Resultado do antivírus",
                details={"sha256": item.sha256},
            )
        except Exception as exc:  # noqa: BLE001 - record and retry manually
            item.scan_status = "scan_failed"
            item.scan_details = str(exc)[:1000]
            item.scanned_at = datetime.now(UTC)
            counts["failed"] += 1
            _audit(
                db,
                actor="system:clamav",
                role="system",
                action="upload_scan_failed",
                resource_type="quarantined_upload",
                resource_id=str(item.id),
                reason="Falha no antivírus; arquivo permanece em quarentena",
                details={"sha256": item.sha256, "error_type": type(exc).__name__},
            )
    db.commit()
    return counts
