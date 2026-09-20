from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.enums import AuditSeverity, SecurityEventType
from api.models import AuditLog, SecurityEvent

SENSITIVE_KEYS = {
    "password", "password_hash", "confirm_password", "token", "access_token",
    "refresh_token", "authorization", "otp", "otp_hash", "secret", "client_secret",
    "api_key", "card_number", "cvv", "cvc", "pin",
}


def redact_sensitive(value: Any) -> Any:
    """Recursively redact known secret fields before persistence."""
    if isinstance(value, dict):
        return {
            str(key): "[REDACTED]" if str(key).lower() in SENSITIVE_KEYS else redact_sensitive(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive(item) for item in value]
    return value


def create_audit_log(
    db: Session,
    *,
    request_id: str,
    action: str,
    actor_user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    http_method: str | None = None,
    request_path: str | None = None,
    response_status: int | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    event_metadata: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    severity: AuditSeverity = AuditSeverity.info,
) -> AuditLog:
    existing = db.query(AuditLog).filter(AuditLog.request_id == request_id).first()
    if existing:
        return existing

    record = AuditLog(
        actor_user_id=actor_user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        http_method=http_method,
        request_path=request_path,
        response_status=response_status,
        old_values=redact_sensitive(old_values),
        new_values=redact_sensitive(new_values),
        event_metadata=redact_sensitive(event_metadata),
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        severity=severity,
    )

    db.add(record)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        existing = db.query(AuditLog).filter(AuditLog.request_id == request_id).first()
        if existing:
            return existing
        raise

    return record


def create_security_event(
    db: Session,
    *,
    request_id: str,
    event_type: SecurityEventType,
    description: str,
    actor_user_id: UUID | None = None,
    severity: AuditSeverity = AuditSeverity.warning,
    request_path: str | None = None,
    http_method: str | None = None,
    response_status: int | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    event_metadata: dict[str, Any] | None = None,
) -> SecurityEvent:
    event = SecurityEvent(
        actor_user_id=actor_user_id,
        event_type=event_type,
        severity=severity,
        description=description,
        request_path=request_path,
        http_method=http_method,
        response_status=response_status,
        ip_address=ip_address,
        user_agent=user_agent,
        request_id=request_id,
        event_metadata=redact_sensitive(event_metadata),
    )
    db.add(event)
    db.flush()
    return event


def resolve_security_event(
    db: Session,
    event: SecurityEvent,
    *,
    resolved_by_id: UUID,
    note: str | None = None,
) -> SecurityEvent:
    event.resolved = True
    event.resolved_by_id = resolved_by_id
    event.resolved_at = datetime.now(timezone.utc)
    metadata = dict(event.event_metadata or {})
    if note:
        metadata["resolution_note"] = note
    event.event_metadata = redact_sensitive(metadata)
    db.flush()
    return event