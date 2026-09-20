from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from api.models import BrokerCommission, EscrowHold, Order, OrderItem


MONEY = Decimal("0.01")


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def create_order_broker_commissions(
    db: Session,
    *,
    order: Order,
) -> list[BrokerCommission]:
    """Create once-only pending Broker entitlements from immutable B4 snapshots."""
    created: list[BrokerCommission] = []
    for item in order.items:
        broker_id = getattr(item, "broker_id", None)
        amount = money(getattr(item, "broker_commission_amount", None))
        if broker_id is None or amount <= 0:
            continue

        existing = (
            db.query(BrokerCommission)
            .filter(BrokerCommission.order_item_id == item.id)
            .first()
        )
        if existing:
            created.append(existing)
            continue

        row = BrokerCommission(
            broker_id=broker_id,
            order_id=order.id,
            order_item_id=item.id,
            broker_offer_id=getattr(item, "broker_offer_id", None),
            broker_attribution_id=getattr(item, "broker_attribution_id", None),
            currency=order.currency,
            amount=amount,
            reversed_amount=Decimal("0.00"),
            status="pending",
            reference=f"broker_commission:{item.id}",
        )
        db.add(row)
        db.flush()
        from api.services.broker_wallet_service import sync_commission_to_wallet
        sync_commission_to_wallet(db, row)
        created.append(row)
    return created


def attach_commissions_to_escrow(
    db: Session,
    *,
    order: Order,
) -> None:
    """Link each Broker commission to the hold for the same order item."""
    commissions = (
        db.query(BrokerCommission)
        .filter(BrokerCommission.order_id == order.id)
        .all()
    )
    if not commissions:
        return

    holds = {
        h.order_item_id: h
        for h in db.query(EscrowHold)
        .filter(EscrowHold.order_id == order.id)
        .all()
        if h.order_item_id is not None
    }
    for commission in commissions:
        hold = holds.get(commission.order_item_id)
        if hold is not None:
            commission.escrow_hold_id = hold.id
    db.flush()


def make_commission_available_for_hold(
    db: Session,
    *,
    hold: EscrowHold,
) -> BrokerCommission | None:
    """Release a Broker entitlement only after the trusted escrow release event."""
    row = (
        db.query(BrokerCommission)
        .filter(BrokerCommission.order_item_id == hold.order_item_id)
        .with_for_update()
        .first()
    )
    if row is None:
        return None
    if row.status in {"reversed", "cancelled"}:
        return row

    remaining = money(row.amount - row.reversed_amount)
    if remaining <= 0:
        row.status = "reversed"
        row.reversed_at = row.reversed_at or datetime.now(timezone.utc)
        return row

    # Only expose the entitlement after the hold has fully reached its release
    # event.  B6 will convert this available entitlement into wallet balance.
    if hold.status == "released":
        row.status = "available" if row.reversed_amount == 0 else "partially_reversed"
        row.available_at = row.available_at or datetime.now(timezone.utc)
    db.flush()
    from api.services.broker_wallet_service import sync_commission_to_wallet
    sync_commission_to_wallet(db, row)
    return row


def reverse_broker_commission(
    db: Session,
    *,
    order_item: OrderItem,
    amount: Decimal,
) -> BrokerCommission | None:
    """Reverse all or part of a Broker entitlement for a completed refund."""
    row = (
        db.query(BrokerCommission)
        .filter(BrokerCommission.order_item_id == order_item.id)
        .with_for_update()
        .first()
    )
    if row is None:
        return None

    remaining = money(row.amount - row.reversed_amount)
    reversal = min(remaining, money(amount))
    if reversal <= 0:
        return row

    row.reversed_amount = money(row.reversed_amount + reversal)
    row.reversed_at = datetime.now(timezone.utc)
    if row.reversed_amount >= row.amount:
        row.status = "reversed"
    else:
        row.status = "partially_reversed"
    db.flush()
    from api.services.broker_wallet_service import sync_commission_to_wallet
    sync_commission_to_wallet(db, row)
    return row


def broker_commission_summary(db: Session, *, broker_id) -> dict:
    rows = db.query(BrokerCommission).filter(BrokerCommission.broker_id == broker_id).all()
    pending = Decimal("0.00")
    available = Decimal("0.00")
    reversed_total = Decimal("0.00")
    lifetime = Decimal("0.00")

    for row in rows:
        amount = money(row.amount)
        reversed_amount = money(row.reversed_amount)
        net = max(Decimal("0.00"), money(amount - reversed_amount))
        lifetime += amount
        reversed_total += reversed_amount
        if row.status == "pending":
            pending += net
        elif row.status in {"available", "partially_reversed"}:
            available += net

    return {
        "pending_amount": money(pending),
        "available_amount": money(available),
        "reversed_amount": money(reversed_total),
        "lifetime_commission": money(lifetime),
    }
