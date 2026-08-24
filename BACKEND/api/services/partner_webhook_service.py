from __future__ import annotations

import hashlib
import hmac
import ipaddress
import json
import socket
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import requests
from cryptography.fernet import InvalidToken
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.config import settings
from api.models import (
    LogisticsIntegrationConfig,
    LogisticsWebhookEvent,
    PartnerCredential,
    PartnerWebhookAttempt,
)
from api.services.partner_security_service import decrypt_signing_secret


RETRYABLE_HTTP_STATUSES = {408, 425, 429, 500, 502, 503, 504}
TERMINAL_STATUSES = {"delivered", "dead_letter"}


class WebhookConfigurationError(RuntimeError):
    pass


class RetryableWebhookConfigurationError(WebhookConfigurationError):
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _target(url: str) -> str:
    parsed = urlsplit(url)
    return (parsed.path or "/") + (f"?{parsed.query}" if parsed.query else "")


def validate_destination(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise WebhookConfigurationError("Webhook destination must be an absolute HTTP(S) URL without embedded credentials")
    if settings.is_production and parsed.scheme != "https":
        raise WebhookConfigurationError("Production webhook destinations must use HTTPS")
    try:
        addresses = {row[4][0] for row in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    except socket.gaierror as exc:
        raise RetryableWebhookConfigurationError("Webhook destination hostname could not be resolved") from exc
    if settings.PARTNER_WEBHOOK_ALLOW_PRIVATE_URLS:
        return
    for value in addresses:
        address = ipaddress.ip_address(value)
        if not address.is_global:
            raise WebhookConfigurationError("Webhook destination resolves to a private or reserved network")


def _integration_and_credential(db: Session, event: LogisticsWebhookEvent):
    integration = db.query(LogisticsIntegrationConfig).filter(
        LogisticsIntegrationConfig.logistics_company_id == event.logistics_company_id,
        LogisticsIntegrationConfig.is_active.is_(True),
    ).first()
    if integration is None or not integration.outbound_webhook_url:
        raise RetryableWebhookConfigurationError("Active outbound webhook configuration is missing")
    enabled = integration.webhook_enabled_events or []
    if enabled and event.event_type not in enabled:
        raise WebhookConfigurationError(f"Event type is not enabled: {event.event_type}")
    credential = db.query(PartnerCredential).filter(
        PartnerCredential.logistics_company_id == event.logistics_company_id,
        PartnerCredential.status == "active",
    ).order_by(PartnerCredential.created_at.desc()).first()
    if credential is None or (credential.expires_at and credential.expires_at <= _utcnow()):
        raise RetryableWebhookConfigurationError("An active partner signing credential is required")
    validate_destination(integration.outbound_webhook_url)
    return integration, credential


def _payload(event: LogisticsWebhookEvent) -> bytes:
    envelope = {
        "id": str(event.id),
        "type": event.event_type,
        "occurred_at": event.created_at.isoformat() if event.created_at else _utcnow().isoformat(),
        "data": event.request_payload or {},
    }
    return json.dumps(envelope, separators=(",", ":"), sort_keys=True, ensure_ascii=False).encode()


def _signed_headers(event: LogisticsWebhookEvent, credential: PartnerCredential, url: str, body: bytes) -> dict[str, str]:
    timestamp = str(int(time.time()))
    event_id = str(event.id)
    body_hash = hashlib.sha256(body).hexdigest()
    canonical = f"{timestamp}\n{event_id}\nPOST\n{_target(url)}\n{body_hash}".encode()
    try:
        secret = decrypt_signing_secret(credential)
    except InvalidToken as exc:
        raise WebhookConfigurationError("Partner signing credential cannot be decrypted") from exc
    signature = hmac.new(secret, canonical, hashlib.sha256).hexdigest()
    return {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Xerin-Partner-Webhooks/1.0",
        "X-Xerin-Key": credential.key_id,
        "X-Xerin-Timestamp": timestamp,
        "X-Xerin-Event-ID": event_id,
        "X-Xerin-Event-Type": event.event_type,
        "X-Xerin-Signature": signature,
        "Idempotency-Key": event_id,
    }


def _retry_delay(attempt_number: int) -> int:
    return min(
        settings.PARTNER_WEBHOOK_RETRY_BASE_SECONDS * (2 ** max(attempt_number - 1, 0)),
        settings.PARTNER_WEBHOOK_MAX_RETRY_SECONDS,
    )


def claim_due_events(db: Session, limit: int | None = None) -> list[tuple[UUID, UUID]]:
    now = _utcnow()
    stale_before = now - timedelta(seconds=settings.PARTNER_WEBHOOK_LOCK_TIMEOUT_SECONDS)
    rows = db.query(LogisticsWebhookEvent).filter(
        LogisticsWebhookEvent.direction == "outbound",
        or_(
            (
                LogisticsWebhookEvent.delivery_status.in_(("queued", "retrying"))
                & (LogisticsWebhookEvent.next_attempt_at.is_(None) | (LogisticsWebhookEvent.next_attempt_at <= now))
            ),
            (
                (LogisticsWebhookEvent.delivery_status == "delivering")
                & (LogisticsWebhookEvent.locked_at.is_(None) | (LogisticsWebhookEvent.locked_at < stale_before))
            ),
        ),
    ).order_by(LogisticsWebhookEvent.next_attempt_at.asc().nullsfirst(), LogisticsWebhookEvent.created_at.asc()).with_for_update(skip_locked=True).limit(limit or settings.PARTNER_WEBHOOK_BATCH_SIZE).all()
    claimed = []
    for event in rows:
        token = uuid4()
        event.delivery_status = "delivering"
        event.locked_at = now
        event.lock_token = token
        claimed.append((event.id, token))
    db.commit()
    return claimed


def deliver_claimed_event(db: Session, event_id: UUID, lock_token: UUID) -> str:
    event = db.query(LogisticsWebhookEvent).filter(
        LogisticsWebhookEvent.id == event_id,
        LogisticsWebhookEvent.delivery_status == "delivering",
        LogisticsWebhookEvent.lock_token == lock_token,
    ).first()
    if event is None:
        return "lost_lock"

    attempt_number = event.attempt_count + 1
    started = time.monotonic()
    now = _utcnow()
    url = "unconfigured"
    credential_key_id = None
    status_code = None
    response_excerpt = None
    error = None
    retryable = False

    try:
        integration, credential = _integration_and_credential(db, event)
        url = integration.outbound_webhook_url
        credential_key_id = credential.key_id
        body = _payload(event)
        response = requests.post(
            url,
            data=body,
            headers=_signed_headers(event, credential, url, body),
            timeout=settings.PARTNER_WEBHOOK_TIMEOUT_SECONDS,
            allow_redirects=False,
        )
        status_code = response.status_code
        response_excerpt = (response.text or "")[:2000]
        if 200 <= response.status_code < 300:
            outcome = "delivered"
        else:
            error = f"Partner returned HTTP {response.status_code}"
            retryable = response.status_code in RETRYABLE_HTTP_STATUSES
            outcome = "failed"
    except WebhookConfigurationError as exc:
        error = str(exc)
        retryable = isinstance(exc, RetryableWebhookConfigurationError)
        outcome = "failed"
    except requests.RequestException as exc:
        error = f"Partner webhook request failed: {type(exc).__name__}"
        retryable = True
        outcome = "failed"

    completed = _utcnow()
    attempt = PartnerWebhookAttempt(
        event_id=event.id,
        attempt_number=attempt_number,
        request_url=url,
        credential_key_id=credential_key_id,
        completed_at=completed,
        duration_ms=max(0, int((time.monotonic() - started) * 1000)),
        http_status=status_code,
        retryable=retryable,
        response_excerpt=response_excerpt,
        error_message=error,
    )
    db.add(attempt)
    event.attempt_count = attempt_number
    event.last_attempt_at = completed
    event.http_status = status_code
    event.response_payload = {"excerpt": response_excerpt} if response_excerpt else None
    event.error_message = error
    event.locked_at = None
    event.lock_token = None

    if outcome == "delivered":
        event.delivery_status = "delivered"
        event.processed = True
        event.delivered_at = completed
        event.dead_lettered_at = None
        event.next_attempt_at = None
        integration.last_webhook_sent_at = completed
    elif retryable and attempt_number < event.max_attempts:
        event.delivery_status = "retrying"
        event.processed = False
        event.next_attempt_at = completed + timedelta(seconds=_retry_delay(attempt_number))
    else:
        event.delivery_status = "dead_letter"
        event.processed = True
        event.dead_lettered_at = completed
        event.next_attempt_at = None
    db.commit()
    return event.delivery_status


def process_due_events(db: Session, limit: int | None = None) -> dict[str, int]:
    batch_size = limit or settings.PARTNER_WEBHOOK_BATCH_SIZE
    results: dict[str, int] = {"claimed": 0}
    # Claim immediately before each network call. This prevents later items in a
    # large batch from appearing stale while earlier requests are still running.
    for _ in range(batch_size):
        claims = claim_due_events(db, 1)
        if not claims:
            break
        event_id, token = claims[0]
        results["claimed"] += 1
        result = deliver_claimed_event(db, event_id, token)
        results[result] = results.get(result, 0) + 1
    return results


def replay_dead_letter(db: Session, event: LogisticsWebhookEvent) -> LogisticsWebhookEvent:
    if event.direction != "outbound" or event.delivery_status != "dead_letter":
        raise ValueError("Only outbound dead-letter events can be replayed")
    event.delivery_status = "queued"
    event.processed = False
    event.max_attempts = event.attempt_count + settings.PARTNER_WEBHOOK_MAX_ATTEMPTS
    event.next_attempt_at = _utcnow()
    event.dead_lettered_at = None
    event.error_message = None
    event.http_status = None
    event.response_payload = None
    event.locked_at = None
    event.lock_token = None
    return event
