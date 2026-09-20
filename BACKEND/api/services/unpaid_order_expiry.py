from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from api.config import settings
from api.enums import InventoryReservationStatus
from api.models import (
    Order,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentStatus,
    PaymentTransaction,
)
from api.routers.email import send_order_cancelled_payment_timeout_email
from api.services.inventory_reservations import release_order_reservations

logger = logging.getLogger(__name__)

AUTO_CANCELLATION_REASON = "payment_confirmation_timeout"


def _payment_timeout_transaction(payment: Payment, order: Order) -> PaymentTransaction:
    return PaymentTransaction(
        payment_id=payment.id,
        transaction_type="order_timeout",
        status=PaymentStatus.cancelled.value,
        amount=Decimal(payment.amount),
        provider_response={
            "reason": AUTO_CANCELLATION_REASON,
            "order_id": str(order.id),
            "message": "Order expired before payment confirmation",
        },
        idempotency_key=f"order-timeout:{order.id}:{payment.id}"[:255],
    )


def expire_unpaid_orders(db: Session, *, limit: int = 100) -> dict[str, int]:
    """Cancel due pending orders and release their inventory reservations.

    Lock ordering intentionally matches payment callbacks: Payment rows first,
    then Order. This avoids an order/payment deadlock when the expiry worker
    runs at the same moment as a provider callback.
    """
    now = datetime.now(timezone.utc)
    candidate_ids = [
        row[0]
        for row in (
            db.query(Order.id)
            .filter(
                Order.status == OrderStatus.pending,
                Order.payment_due_at.isnot(None),
                Order.payment_due_at <= now,
            )
            .order_by(Order.payment_due_at.asc())
            .limit(limit)
            .all()
        )
    ]

    cancelled = 0
    released_reservations = 0
    skipped_paid = 0

    for order_id in candidate_ids:
        try:
            payments = (
                db.query(Payment)
                .filter(Payment.order_id == order_id)
                .order_by(Payment.created_at.asc())
                .with_for_update()
                .all()
            )
            order = (
                db.query(Order)
                .filter(Order.id == order_id)
                .with_for_update()
                .first()
            )
            if (
                order is None
                or order.status != OrderStatus.pending
                or order.payment_due_at is None
                or order.payment_due_at > now
            ):
                db.rollback()
                continue

            if any(payment.status == PaymentStatus.completed for payment in payments):
                # A verified payment always wins over timeout cancellation.
                skipped_paid += 1
                db.rollback()
                continue

            for payment in payments:
                if payment.status in {PaymentStatus.pending, PaymentStatus.processing}:
                    payment.status = PaymentStatus.cancelled
                    payment.failure_reason = "Order cancelled because payment confirmation timed out"
                    exists = (
                        db.query(PaymentTransaction.id)
                        .filter(
                            PaymentTransaction.idempotency_key
                            == f"order-timeout:{order.id}:{payment.id}"[:255]
                        )
                        .first()
                    )
                    if not exists:
                        db.add(_payment_timeout_transaction(payment, order))

            released_reservations += release_order_reservations(
                db,
                order,
                target_status=InventoryReservationStatus.cancelled,
            )
            order.status = OrderStatus.cancelled
            order.cancelled_at = now
            order.cancellation_reason = AUTO_CANCELLATION_REASON
            db.add(
                OrderStatusHistory(
                    order_id=order.id,
                    status=OrderStatus.cancelled.value,
                    notes=(
                        "Order automatically cancelled because payment was not "
                        f"confirmed within {settings.PAYMENT_ORDER_TIMEOUT_MINUTES} minutes; "
                        "reserved inventory released"
                    ),
                    created_by_id=None,
                )
            )
            db.commit()
            cancelled += 1
        except Exception:
            db.rollback()
            logger.exception("Failed to expire unpaid order %s", order_id)

    return {
        "cancelled_orders": cancelled,
        "released_reservations": released_reservations,
        "skipped_paid_orders": skipped_paid,
    }


def send_pending_timeout_cancellation_emails(
    db: Session,
    *,
    limit: int = 100,
) -> dict[str, int]:
    """Send/retry timeout cancellation emails.

    `cancellation_email_sent_at` makes delivery idempotent after success. An SMTP
    failure leaves it NULL so the next worker run can retry.
    """
    orders = (
        db.query(Order)
        .filter(
            Order.status == OrderStatus.cancelled,
            Order.cancellation_reason == AUTO_CANCELLATION_REASON,
            Order.cancellation_email_sent_at.is_(None),
        )
        .order_by(Order.cancelled_at.asc())
        .limit(limit)
        .all()
    )
    sent = 0
    failed = 0

    for order in orders:
        user = order.user
        if user is None or not (user.email or "").strip():
            failed += 1
            logger.warning("Cancelled order %s has no customer email", order.id)
            continue
        recipient_name = (
            f"{user.first_name or ''} {user.last_name or ''}".strip()
            or "Customer"
        )
        try:
            send_order_cancelled_payment_timeout_email(
                to=user.email,
                order_id=str(order.id),
                recipient_name=recipient_name,
                total=f"{Decimal(order.total):,.2f}",
                currency=order.currency,
                timeout_minutes=settings.PAYMENT_ORDER_TIMEOUT_MINUTES,
            )
            order.cancellation_email_sent_at = datetime.now(timezone.utc)
            db.commit()
            sent += 1
        except Exception:
            db.rollback()
            failed += 1
            logger.exception("Could not send cancellation email for order %s", order.id)

    return {"emails_sent": sent, "email_failures": failed}


def run_unpaid_order_expiry(db: Session, *, limit: int = 100) -> dict[str, int]:
    result = expire_unpaid_orders(db, limit=limit)
    result.update(send_pending_timeout_cancellation_emails(db, limit=limit))
    return result
