from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.config import settings
from api.models import AlertNotification, WeeklyReport
from api.routers.email import send_email

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def deliver_alert(db: Session, notification: AlertNotification) -> AlertNotification:
    """Attempt SMTP delivery; records outcome without raising.

    Audit events are never tied to email success — a failed send only
    updates this notification row.
    """
    notification.attempts = (notification.attempts or 0) + 1
    try:
        send_email(
            to=notification.recipient,
            subject=notification.subject,
            body=notification.body_text,
        )
        notification.status = "sent"
        notification.sent_at = _now()
        notification.next_retry_at = None
        notification.last_error = None
    except Exception as exc:
        logger.warning(
            "Alert email %s failed (attempt %s): %s",
            notification.id, notification.attempts, type(exc).__name__,
        )
        notification.last_error = f"{type(exc).__name__}: {str(exc)[:300]}"
        if notification.attempts >= settings.ALERT_EMAIL_MAX_ATTEMPTS:
            notification.status = "failed"
            notification.next_retry_at = None
        else:
            notification.status = "pending"
            delay = settings.ALERT_EMAIL_RETRY_BASE_SECONDS * (2 ** (notification.attempts - 1))
            notification.next_retry_at = _now() + timedelta(seconds=delay)
    db.flush()
    return notification


def process_pending_alerts(db: Session, *, batch_size: int = 20) -> int:
    """Deliver due notifications. Called by the scheduler loop."""
    now = _now()
    due = (
        db.query(AlertNotification)
        .filter(
            AlertNotification.status == "pending",
            (AlertNotification.next_retry_at.is_(None)) | (AlertNotification.next_retry_at <= now),
        )
        .order_by(AlertNotification.created_at.asc())
        .limit(batch_size)
        .all()
    )
    delivered = 0
    for notification in due:
        deliver_alert(db, notification)
        if notification.status == "sent":
            delivered += 1
    db.commit()
    return delivered


def send_weekly_report(db: Session, report: WeeklyReport) -> WeeklyReport:
    try:
        send_email(to=report.recipient, subject=report.subject, body=report.body_text)
        report.status = "sent"
        report.sent_at = _now()
    except Exception as exc:
        report.status = "failed"
        logger.warning("Weekly report send failed: %s", type(exc).__name__)
    db.flush()
    return report
