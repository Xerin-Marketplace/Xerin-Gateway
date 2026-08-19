from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from api.models import (
    FinanceSettings,
    EscrowEvent,
    EscrowHold,
    Order,
    OrderItemCommission,
    Payment,
)
from api.services.wallet_service import release_sale_credit_fraction

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


def release_escrow_hold_funds(
    db: Session,
    *,
    hold: EscrowHold,
    amount: Decimal | None = None,
    note: str | None = None,
    created_by_id=None,
    event_type: str = "released",
) -> EscrowHold:
    """Release escrow and the matching seller wallet entitlement atomically."""
    if hold.status == "released":
        return hold
    if hold.status == "disputed":
        raise ValueError("Disputed escrow cannot be released")
    if hold.status not in {"held", "release_pending", "partially_refunded"}:
        raise ValueError(f"Escrow hold cannot be released from status {hold.status}")

    gross = _money(hold.gross_amount)
    refunded = _money(hold.refunded_amount)
    previously_released = _money(hold.released_amount)
    available = _money(gross - refunded - previously_released)
    requested = _money(amount if amount is not None else available)

    if requested <= 0 or requested > available:
        raise ValueError("Release amount exceeds the remaining held amount")

    settings_row = (
        db.query(FinanceSettings)
        .filter(FinanceSettings.singleton_key == "default")
        .first()
    )
    if (
        requested != available
        and settings_row is not None
        and not settings_row.allow_partial_release
    ):
        raise ValueError("Partial escrow release is disabled")

    new_released = _money(previously_released + requested)
    remaining = _money(gross - refunded - new_released)
    fully_released = remaining == Decimal("0.00")

    event = EscrowEvent(
        escrow_hold_id=hold.id,
        event_type=event_type,
        amount=requested,
        note=note,
        created_by_id=created_by_id,
    )
    db.add(event)
    db.flush()

    # Seller wallet contains seller_net_amount only. Xerin commission is already
    # accounted in marketplace_transactions and must never be credited to seller.
    denominator = gross if gross > 0 else Decimal("1")
    fraction = min(Decimal("1"), new_released / denominator)
    release_sale_credit_fraction(
        db,
        order_item_id=hold.order_item_id,
        fraction=fraction,
        # A hold can be fully settled by a mixture of release and refund.
        # Only force the entire seller credit when no part was refunded.
        force_full=fully_released and refunded == Decimal("0.00"),
        reference=f"escrow_release:{hold.id}:{event.id}",
        description=(
            "Seller funds released from Xerin escrow"
            if event_type != "customer_approved"
            else "Customer approved delivery; seller funds released from Xerin escrow"
        ),
    )

    hold.released_amount = new_released
    if fully_released:
        hold.status = "released"
        hold.released_at = datetime.now().astimezone()
    else:
        hold.status = "held"

    db.flush()
    return hold


def record_escrow_refund(
    db: Session,
    *,
    order_item_id,
    amount: Decimal,
    refund_id,
    refund_item_id,
    created_by_id=None,
) -> EscrowHold | None:
    """Remove a refund from still-held escrow without double-settling funds.

    Refunds made after some or all funds were released are still recorded as
    events, while only the portion that remains held increases refunded_amount.
    The wallet reversal owns recovery of any already-released seller funds.
    """
    hold = (
        db.query(EscrowHold)
        .filter(EscrowHold.order_item_id == order_item_id)
        .with_for_update()
        .first()
    )
    if hold is None:
        return None

    reference = f"refund:{refund_item_id}"
    existing = (
        db.query(EscrowEvent)
        .filter(
            EscrowEvent.escrow_hold_id == hold.id,
            EscrowEvent.event_type == reference,
        )
        .first()
    )
    if existing:
        return hold

    requested = _money(amount)
    available = _money(
        _money(hold.gross_amount)
        - _money(hold.released_amount)
        - _money(hold.refunded_amount)
    )
    held_reversal = min(requested, max(Decimal("0.00"), available))
    hold.refunded_amount = _money(hold.refunded_amount) + held_reversal
    if held_reversal:
        hold.refunded_at = datetime.now().astimezone()

    remaining = _money(
        _money(hold.gross_amount)
        - _money(hold.released_amount)
        - _money(hold.refunded_amount)
    )
    if remaining == 0 and _money(hold.released_amount) == 0:
        hold.status = "refunded"
    elif remaining == 0:
        hold.status = "released"
    elif _money(hold.refunded_amount) > 0:
        hold.status = "partially_refunded"

    db.add(
        EscrowEvent(
            escrow_hold_id=hold.id,
            event_type=reference,
            amount=requested,
            note=(
                f"Refund {refund_id} recorded; {held_reversal} removed from "
                "unreleased escrow and any released portion is recovered by wallet reversal"
            ),
            created_by_id=created_by_id,
        )
    )
    db.flush()
    return hold


def release_order_escrow(
    db: Session,
    *,
    order: Order,
    created_by_id=None,
    note: str | None = None,
    event_type: str = "released",
) -> list[EscrowHold]:
    holds = (
        db.query(EscrowHold)
        .filter(EscrowHold.order_id == order.id)
        .order_by(EscrowHold.created_at)
        .with_for_update()
        .all()
    )
    if not holds:
        raise ValueError("This order has no escrow holds")
    if any(hold.status == "disputed" for hold in holds):
        raise ValueError("Order escrow is disputed and cannot be released")

    for hold in holds:
        if hold.status != "released":
            release_escrow_hold_funds(
                db,
                hold=hold,
                note=note,
                created_by_id=created_by_id,
                event_type=event_type,
            )
    return holds


def order_escrow_summary(db: Session, order: Order) -> dict:
    holds = db.query(EscrowHold).filter(EscrowHold.order_id == order.id).all()
    if not holds:
        return {
            "order_id": order.id,
            "currency": order.currency,
            "status": "not_applicable",
            "hold_count": 0,
            "gross_amount": Decimal("0.00"),
            "seller_amount": Decimal("0.00"),
            "commission_amount": Decimal("0.00"),
            "released_amount": Decimal("0.00"),
            "remaining_amount": Decimal("0.00"),
            "release_after": None,
            "can_customer_approve": False,
        }

    gross = sum((_money(h.gross_amount) for h in holds), Decimal("0.00"))
    seller = sum((_money(h.seller_amount) for h in holds), Decimal("0.00"))
    commission = sum((_money(h.commission_amount) for h in holds), Decimal("0.00"))
    released = sum((_money(h.released_amount) for h in holds), Decimal("0.00"))
    refunded = sum((_money(h.refunded_amount) for h in holds), Decimal("0.00"))
    remaining = _money(gross - released - refunded)

    statuses = {h.status for h in holds}
    if "disputed" in statuses:
        status = "disputed"
    elif statuses == {"released"}:
        status = "released"
    elif "refunded" in statuses and statuses <= {"refunded", "released"}:
        status = "refunded" if released == 0 else "settled_with_refunds"
    elif refunded > 0:
        status = "partially_refunded"
    elif released > 0:
        status = "partially_released"
    else:
        status = "held"

    release_dates = [h.release_after for h in holds if h.release_after is not None]
    all_delivered = bool(order.shipments) and all(
        getattr(shipment.status, "value", shipment.status) == "delivered"
        for shipment in order.shipments
    )
    payment_completed = any(
        getattr(payment.status, "value", payment.status) == "completed"
        for payment in order.payments
    )

    return {
        "order_id": order.id,
        "currency": order.currency,
        "status": status,
        "hold_count": len(holds),
        "gross_amount": gross,
        "seller_amount": seller,
        "commission_amount": commission,
        "released_amount": released,
        "remaining_amount": remaining,
        "release_after": max(release_dates) if release_dates else None,
        "can_customer_approve": (
            status in {"held", "partially_released", "partially_refunded"}
            and all_delivered
            and payment_completed
        ),
    }


def release_due_escrow_holds(db: Session, limit: int = 500) -> int:
    """Auto-release undisputed escrow holds after the configured release period."""
    from datetime import timezone

    settings_row = (
        db.query(FinanceSettings)
        .filter(FinanceSettings.singleton_key == "default")
        .first()
    )
    if settings_row is not None and not settings_row.auto_release_enabled:
        return 0

    now = datetime.now(timezone.utc)
    rows = (
        db.query(EscrowHold)
        .filter(
            EscrowHold.status.in_(["held", "release_pending", "partially_refunded"]),
            EscrowHold.release_after.is_not(None),
            EscrowHold.release_after <= now,
        )
        .order_by(EscrowHold.release_after)
        .with_for_update(skip_locked=True)
        .limit(limit)
        .all()
    )
    count = 0
    for hold in rows:
        release_escrow_hold_funds(
            db,
            hold=hold,
            note="Automatic escrow release period reached",
            event_type="auto_released",
        )
        count += 1
    return count
