from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from api.models import (
    EscrowEvent,
    EscrowHold,
    Order,
    OrderItemCommission,
    Payment,
)

MONEY = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY)


def create_order_escrow_holds(
    db: Session,
    *,
    order: Order,
    payment: Payment,
    commission_records: list[OrderItemCommission],
    release_after: datetime | None,
) -> list[EscrowHold]:
    """Create one immutable escrow allocation per order item.

    Idempotency is guaranteed by the unique `reference` on EscrowHold.
    Platform coupons remain platform-funded and therefore do not reduce seller
    entitlement. Seller promotions are already reflected in seller_net_amount.
    """

    holds: list[EscrowHold] = []
    items_by_id = {item.id: item for item in order.items}

    for record in commission_records:
        item = items_by_id.get(record.order_item_id)
        if item is None:
            continue

        reference = f"escrow:{payment.id}:{record.order_item_id}"
        existing = (
            db.query(EscrowHold)
            .filter(EscrowHold.reference == reference)
            .first()
        )
        if existing:
            holds.append(existing)
            continue

        seller_amount = _money(record.seller_net_amount)
        commission_amount = _money(record.commission_amount)

        # Settlement obligation after seller-funded promotion. This equals
        # seller amount + preserved Xerin commission.
        gross_amount = _money(seller_amount + commission_amount)

        hold = EscrowHold(
            payment_id=payment.id,
            order_id=order.id,
            order_item_id=record.order_item_id,
            seller_id=record.seller_id,
            currency=order.currency,
            gross_amount=gross_amount,
            seller_amount=seller_amount,
            commission_amount=commission_amount,
            refunded_amount=Decimal("0.00"),
            released_amount=Decimal("0.00"),
            status="held",
            release_after=release_after,
            reference=reference,
            note="Funds held after confirmed online payment",
        )
        db.add(hold)
        db.flush()

        db.add(
            EscrowEvent(
                escrow_hold_id=hold.id,
                event_type="held",
                amount=gross_amount,
                note=(
                    "Payment confirmed; seller settlement is held "
                    "until customer approval or escrow release rules apply"
                ),
            )
        )
        holds.append(hold)

    return holds
