from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from api.config import settings
from api.enums import AuditSeverity, SecurityEventType
from api.models import AlertNotification, AuditLog
from api.services.audit_service import create_audit_log, create_security_event

logger = logging.getLogger(__name__)

_SEVERITY_ORDER = {
    AuditSeverity.info: 0,
    AuditSeverity.notice: 1,
    AuditSeverity.warning: 2,
    AuditSeverity.critical: 3,
}

# Event types that should email at WARNING+ (not only critical).
_ALERTABLE_EVENT_PREFIXES = (
    "payment.", "refund.", "payout.", "wallet.", "webhook.",
    "security.", "auth.", "admin.", "migration.", "deploy.",
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _min_severity() -> int:
    raw = (settings.MONITORING_ALERT_MIN_SEVERITY or "warning").lower()
    return {
        "info": 0, "notice": 1, "warning": 2, "critical": 3,
    }.get(raw, 2)


def should_email(severity: AuditSeverity, action: str) -> bool:
    """Decide whether an event warrants an email alert."""
    if not settings.MONITORING_ENABLED or not settings.MONITORING_ALERT_EMAIL:
        return False
    if _SEVERITY_ORDER.get(severity, 0) >= _min_severity():
        return True
    # Notice-level business events that admins still want immediately.
    if severity == AuditSeverity.notice and action.startswith(_ALERTABLE_EVENT_PREFIXES):
        return True
    return False


def queue_email_alert(
    db: Session,
    *,
    dedup_key: str,
    subject: str,
    body_text: str,
    severity: AuditSeverity | str,
    event_type: str | None = None,
) -> AlertNotification | None:
    """Queue an alert email with deduplication.

    If an alert with the same dedup key was already queued/sent inside the
    configured window, bump its aggregate count instead of spamming email.
    Returns the notification row (existing aggregated one or a new one).
    """
    recipient = settings.MONITORING_ALERT_EMAIL
    if not recipient:
        return None

    sev = severity.value if isinstance(severity, AuditSeverity) else severity
    window_start = _now() - timedelta(minutes=settings.MONITORING_ALERT_WINDOW_MINUTES)

    existing = (
        db.query(AlertNotification)
        .filter(
            AlertNotification.dedup_key == dedup_key,
            AlertNotification.recipient == recipient,
            AlertNotification.created_at >= window_start,
            AlertNotification.status.in_(["pending", "sent", "failed"]),
        )
        .order_by(AlertNotification.created_at.desc())
        .first()
    )

    if existing is not None:
        existing.aggregate_count = (existing.aggregate_count or 1) + 1
        # If the alert already sent and we've exceeded the per-window cap,
        # we only update the counter — the next report/email references it.
        if (
            existing.status == "sent"
            and existing.attempts <= 0
        ):
            pass
        db.flush()
        return existing

    notification = AlertNotification(
        dedup_key=dedup_key[:200],
        recipient=recipient,
        subject=subject[:255],
        body_text=body_text,
        severity=sev,
        event_type=(event_type or dedup_key.split(":", 1)[0])[:120],
        status="pending",
        next_retry_at=_now(),
    )
    db.add(notification)
    db.flush()
    return notification


def record_business_event(
    db: Session,
    *,
    action: str,
    description: str | None = None,
    severity: AuditSeverity = AuditSeverity.info,
    actor_user_id: UUID | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    request_id: str | None = None,
    http_method: str | None = None,
    request_path: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    old_values: dict[str, Any] | None = None,
    new_values: dict[str, Any] | None = None,
    event_metadata: dict[str, Any] | None = None,
    dedup_key: str | None = None,
) -> AuditLog:
    """Audit + optional alert for a business/security-relevant event."""
    log = create_audit_log(
        db,
        request_id=request_id or f"evt_{uuid4().hex[:20]}",
        action=action,
        actor_user_id=actor_user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        http_method=http_method,
        request_path=request_path,
        event_metadata=event_metadata,
        old_values=old_values,
        new_values=new_values,
        ip_address=ip_address,
        user_agent=user_agent,
        severity=severity,
    )

    if should_email(severity, action):
        try:
            queue_email_alert(
                db,
                dedup_key=dedup_key or f"{action}:{resource_id or 'system'}",
                subject=f"[Xerin {severity.value.upper()}] {description or action}",
                body_text=_alert_body(
                    severity=severity,
                    title=description or action,
                    details={
                        "Action": action,
                        "Resource": f"{resource_type or '-'} {resource_id or ''}".strip(),
                        "Request ID": log.request_id,
                        "Path": request_path or "-",
                        "IP": ip_address or "-",
                        "User ID": str(actor_user_id) if actor_user_id else "-",
                    },
                ),
                severity=severity,
                event_type=action,
            )
        except Exception:
            # Alerting must never break the audited business flow.
            logger.exception("Failed to queue alert for %s", action)

    return log


def record_security_alert(
    db: Session,
    *,
    event_type: SecurityEventType,
    description: str,
    severity: AuditSeverity = AuditSeverity.warning,
    actor_user_id: UUID | None = None,
    request_id: str | None = None,
    request_path: str | None = None,
    http_method: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    event_metadata: dict[str, Any] | None = None,
    dedup_key: str | None = None,
) -> None:
    """Security event + deduplicated email alert."""
    event = create_security_event(
        db,
        request_id=request_id or f"sec_{uuid4().hex[:20]}",
        event_type=event_type,
        description=description,
        actor_user_id=actor_user_id,
        severity=severity,
        request_path=request_path,
        http_method=http_method,
        ip_address=ip_address,
        user_agent=user_agent,
        event_metadata=event_metadata,
    )

    if not should_email(severity, f"security.{event_type.value}"):
        return

    try:
        queue_email_alert(
            db,
            dedup_key=dedup_key or f"security.{event_type.value}:{request_path or '-'}",
            subject=f"[Xerin SECURITY {severity.value.upper()}] {event_type.value}",
            body_text=_alert_body(
                severity=severity,
                title=f"SECURITY ALERT — {event_type.value.replace('_', ' ').upper()}",
                details={
                    "Event": event_type.value,
                    "Endpoint": request_path or "-",
                    "Method": http_method or "-",
                    "Request ID": event.request_id,
                    "IP": ip_address or "-",
                    "Description": description,
                },
            ),
            severity=severity,
            event_type=f"security.{event_type.value}",
        )
    except Exception:
        logger.exception("Failed to queue security alert for %s", event_type)


def _alert_body(severity: AuditSeverity | str, title: str, details: dict[str, str]) -> str:
    sev = severity.value if isinstance(severity, AuditSeverity) else severity
    lines = [
        "XERIN MARKETPLACE",
        "=" * 40,
        title,
        "",
        f"Severity : {sev.upper()}",
        f"Time     : {_now().isoformat(timespec='seconds')}",
        f"Env      : {settings.APP_ENV}",
    ]
    for key, value in details.items():
        lines.append(f"{key:<10} : {value}")
    lines += [
        "",
        "This is an automated monitoring notification.",
        "Investigate via the admin Monitoring dashboard.",
    ]
    return "\n".join(lines)
