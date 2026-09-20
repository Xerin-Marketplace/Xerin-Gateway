"""Prioritized operational exception queue for marketplace administrators."""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from api.enums import NotificationDeliveryStatus, RefundStatus
from api.models import (
    DeliveryJob,
    NotificationDelivery,
    Payment,
    PaymentStatus,
    Refund,
    SecurityEvent,
    SupportTicket,
)

OPEN_TICKET_STATUSES = ("open", "pending", "in_progress", "processing")


def _age_minutes(created_at: datetime | None, now: datetime) -> int:
    if created_at is None:
        return 0
    value = created_at if created_at.tzinfo else created_at.replace(tzinfo=timezone.utc)
    return max(0, int((now - value).total_seconds() // 60))


def operations_overview(db: Session, *, limit: int = 50) -> dict:
    now = datetime.now(timezone.utc)
    stale_before = now - timedelta(minutes=15)
    open_query = db.query(SupportTicket).filter(SupportTicket.status.in_(OPEN_TICKET_STATUSES))

    breached_query = open_query.filter(
            (SupportTicket.sla_breached_at.is_not(None))
            | (SupportTicket.resolution_due_at < now)
            | ((SupportTicket.first_responded_at.is_(None)) & (SupportTicket.first_response_due_at < now))
        )
    breached_count = breached_query.count()
    breached_rows = (
        breached_query
        .order_by(SupportTicket.priority.desc(), SupportTicket.created_at.asc())
        .limit(limit)
        .all()
    )
    failed_notifications = (
        db.query(NotificationDelivery)
        .filter(NotificationDelivery.status == NotificationDeliveryStatus.failed)
        .order_by(NotificationDelivery.created_at.asc())
        .limit(limit)
        .all()
    )
    security_rows = (
        db.query(SecurityEvent)
        .filter(SecurityEvent.resolved.is_(False))
        .order_by(SecurityEvent.created_at.asc())
        .limit(limit)
        .all()
    )

    exceptions = []
    for ticket in breached_rows:
        exceptions.append({
            "type": "support_sla",
            "severity": "critical" if ticket.priority == "urgent" else "warning",
            "resource_id": str(ticket.id),
            "title": f"SLA attention required: {ticket.ticket_number}",
            "age_minutes": _age_minutes(ticket.created_at, now),
            "action_url": f"/admin/support-tickets/{ticket.id}",
        })
    for delivery in failed_notifications:
        exceptions.append({
            "type": "notification_failure",
            "severity": "warning",
            "resource_id": str(delivery.id),
            "title": f"{getattr(delivery.channel, 'value', delivery.channel)} notification delivery failed",
            "age_minutes": _age_minutes(delivery.created_at, now),
            "action_url": "/admin/dashboard/notifications",
        })
    for event in security_rows:
        severity = getattr(event.severity, "value", event.severity)
        exceptions.append({
            "type": "security_event",
            "severity": "critical" if severity == "critical" else "warning",
            "resource_id": str(event.id),
            "title": "Unresolved security event requires review",
            "age_minutes": _age_minutes(event.created_at, now),
            "action_url": "/admin/security-events",
        })
    exceptions.sort(key=lambda item: (item["severity"] != "critical", -item["age_minutes"]))

    return {
        "generated_at": now,
        "open_support_tickets": open_query.count(),
        "unassigned_support_tickets": open_query.filter(SupportTicket.assigned_to_id.is_(None)).count(),
        "breached_support_tickets": breached_count,
        "urgent_support_tickets": open_query.filter(SupportTicket.priority == "urgent").count(),
        "failed_notification_deliveries": db.query(NotificationDelivery).filter(NotificationDelivery.status == NotificationDeliveryStatus.failed).count(),
        "stale_notification_deliveries": db.query(NotificationDelivery).filter(NotificationDelivery.status.in_([NotificationDeliveryStatus.pending, NotificationDeliveryStatus.processing]), NotificationDelivery.created_at < stale_before).count(),
        "unresolved_security_events": db.query(SecurityEvent).filter(SecurityEvent.resolved.is_(False)).count(),
        "failed_payments": db.query(Payment).filter(Payment.status == PaymentStatus.failed).count(),
        "pending_refunds": db.query(Refund).filter(Refund.status.in_([RefundStatus.requested, RefundStatus.under_review, RefundStatus.approved, RefundStatus.processing])).count(),
        "failed_deliveries": db.query(DeliveryJob).filter(DeliveryJob.status == "delivery_failed").count(),
        "exceptions": exceptions[:limit],
    }
