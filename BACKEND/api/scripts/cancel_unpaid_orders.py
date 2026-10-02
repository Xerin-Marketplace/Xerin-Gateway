"""Cancel orders that stayed unpaid past PAYMENT_ORDER_TIMEOUT_MINUTES.

Releases inventory reservations, cancels dangling payment rows, marks the
order cancelled and records status history. Idempotent and safe to run on a
schedule (systemd timer / cron / worker loop).

Run:  .venv/bin/python -m api.scripts.cancel_unpaid_orders
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from api.config import settings
from api.database import SessionLocal
from api.enums import InventoryReservationStatus
from api.models import Order, OrderStatus, OrderStatusHistory, Payment, PaymentStatus
from api.services.inventory_reservations import release_order_reservations


def cancel_unpaid_orders(db, *, timeout_minutes: int | None = None, limit: int = 500) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(
        minutes=timeout_minutes or settings.PAYMENT_ORDER_TIMEOUT_MINUTES
    )
    orders = (
        db.query(Order)
        .filter(
            Order.status == OrderStatus.pending,
            Order.created_at <= cutoff,
        )
        .order_by(Order.created_at.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )

    now = datetime.now(timezone.utc)
    count = 0
    for order in orders:
        release_order_reservations(
            db, order, target_status=InventoryReservationStatus.cancelled
        )
        # Mark dangling payments cancelled so a late provider callback can't
        # complete against a cancelled order unnoticed.
        for payment in (
            db.query(Payment)
            .filter(
                Payment.order_id == order.id,
                Payment.status.in_([PaymentStatus.pending, PaymentStatus.processing]),
            )
            .all()
        ):
            payment.status = PaymentStatus.cancelled
        order.status = OrderStatus.cancelled
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                status=OrderStatus.cancelled.value,
                notes="Auto-cancelled: unpaid order exceeded payment timeout",
            )
        )
        count += 1
    return count


def main() -> None:
    db = SessionLocal()
    try:
        count = cancel_unpaid_orders(db)
        db.commit()
        print(f"Cancelled {count} unpaid order(s)")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
