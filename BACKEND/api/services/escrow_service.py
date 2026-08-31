from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from api.models import (
    FinanceSettings,
    MarketplaceSettings,
    EscrowEvent,
    EscrowHold,
    Order,
    OrderItemCommission,
    Payment,
    ShipmentHandover,
    ShipmentItem,
    ShipmentPickupProof,
    ShipmentDeliveryProof,
    SettlementProtectionClaim,
)
from api.services.wallet_service import release_sale_credit_fraction
from api.services.broker_finance_service import make_commission_available_for_hold

MONEY = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY)


def _assert_trusted_pickup_evidence(db: Session, hold: EscrowHold) -> ShipmentPickupProof:
    """Validate the physical handover and customer-approved pickup chain."""
    if not hold.seller_release_shipment_id or not hold.seller_release_proof_id or not hold.seller_release_handover_id:
        raise ValueError("Seller settlement requires trusted pickup verification")
    proof = (
        db.query(ShipmentPickupProof)
        .filter(
            ShipmentPickupProof.id == hold.seller_release_proof_id,
            ShipmentPickupProof.shipment_id == hold.seller_release_shipment_id,
            ShipmentPickupProof.handover_id == hold.seller_release_handover_id,
            ShipmentPickupProof.seller_id == hold.seller_id,
            ShipmentPickupProof.status.in_(["pending", "approved", "auto_approved"]),
        )
        .first()
    )
    handover = (
        db.query(ShipmentHandover)
        .filter(
            ShipmentHandover.id == hold.seller_release_handover_id,
            ShipmentHandover.shipment_id == hold.seller_release_shipment_id,
            ShipmentHandover.seller_id == hold.seller_id,
            ShipmentHandover.status == "seller_confirmed",
            ShipmentHandover.seller_confirmed_at.is_not(None),
        )
        .first()
    )
    item_link = (
        db.query(ShipmentItem.id)
        .filter(
            ShipmentItem.shipment_id == hold.seller_release_shipment_id,
            ShipmentItem.order_item_id == hold.order_item_id,
        )
        .first()
    )
    if proof is None or handover is None or item_link is None:
        raise ValueError("Seller settlement pickup evidence is incomplete or inconsistent")
    return proof


def _assert_verified_delivery(db: Session, hold: EscrowHold) -> ShipmentDeliveryProof:
    """Require recipient-verified delivery for any seller release under F6."""
    if not hold.seller_release_shipment_id:
        raise ValueError("Seller settlement requires a verified delivery shipment")
    proof = (
        db.query(ShipmentDeliveryProof)
        .filter(
            ShipmentDeliveryProof.shipment_id == hold.seller_release_shipment_id,
            ShipmentDeliveryProof.order_id == hold.order_id,
            ShipmentDeliveryProof.status == "verified",
            ShipmentDeliveryProof.verified_at.is_not(None),
        )
        .first()
    )
    if proof is None:
        raise ValueError("Seller settlement requires verified customer receipt")
    return proof


def _seller_grace_hours(db: Session) -> int:
    row = db.query(MarketplaceSettings).filter(MarketplaceSettings.singleton_key == 1).first()
    return int(getattr(row, "seller_release_grace_hours", None) or 144)


def arm_shipment_seller_escrow_after_delivery(
    db: Session,
    *,
    shipment_id,
    order_id,
    verified_at: datetime,
    actor_id=None,
) -> list[EscrowHold]:
    """Start the seller protection clock only after verified delivery.

    Pickup/handover evidence must already be attached to the hold. Disputed and
    settled holds remain untouched. This is idempotent for webhook/OTP retries.
    """
    order_item_ids = [
        row[0]
        for row in db.query(ShipmentItem.order_item_id)
        .filter(ShipmentItem.shipment_id == shipment_id)
        .all()
    ]
    if not order_item_ids:
        return []
    proof = (
        db.query(ShipmentPickupProof)
        .filter(ShipmentPickupProof.shipment_id == shipment_id)
        .with_for_update()
        .first()
    )
    if proof is None or proof.status == "disputed":
        raise ValueError("Verified delivery cannot arm seller settlement without undisputed pickup evidence")
    handover = (
        db.query(ShipmentHandover)
        .filter(
            ShipmentHandover.id == proof.handover_id,
            ShipmentHandover.shipment_id == shipment_id,
            ShipmentHandover.status == "seller_confirmed",
            ShipmentHandover.seller_confirmed_at.is_not(None),
        )
        .with_for_update()
        .first()
    )
    if handover is None:
        raise ValueError("Verified delivery cannot arm seller settlement without seller-confirmed handover")
    grace_hours = _seller_grace_hours(db)
    deadline = verified_at + timedelta(hours=grace_hours)
    holds = (
        db.query(EscrowHold)
        .filter(EscrowHold.order_id == order_id, EscrowHold.order_item_id.in_(order_item_ids))
        .order_by(EscrowHold.created_at)
        .with_for_update()
        .all()
    )
    for hold in holds:
        if hold.status in {"released", "refunded", "disputed"}:
            continue
        # Attach immutable custody evidence if the customer did not separately
        # review the pickup photo before delivery. F6 treats pickup as evidence,
        # not a settlement trigger.
        hold.seller_release_shipment_id = shipment_id
        hold.seller_release_handover_id = handover.id
        hold.seller_release_proof_id = proof.id
        _assert_trusted_pickup_evidence(db, hold)
        hold.seller_release_verified_at = verified_at
        hold.seller_release_trigger = "delivery_verified_waiting_customer"
        hold.release_after = deadline
        existing = db.query(EscrowEvent.id).filter(
            EscrowEvent.escrow_hold_id == hold.id,
            EscrowEvent.event_type == "delivery_verified_hold",
        ).first()
        if not existing:
            db.add(EscrowEvent(
                escrow_hold_id=hold.id,
                event_type="delivery_verified_hold",
                note=f"Verified delivery started the seller protection period ({grace_hours} hours)",
                created_by_id=actor_id,
            ))
    db.flush()
    return holds


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
        broker_amount = _money(getattr(item, "broker_commission_amount", 0) or 0)

        # Settlement obligation after seller-funded promotion. Broker rewards
        # remain inside the held obligation but are separated from seller/Xerin.
        gross_amount = _money(seller_amount + commission_amount + broker_amount)

        hold = EscrowHold(
            payment_id=payment.id,
            order_id=order.id,
            order_item_id=record.order_item_id,
            seller_id=record.seller_id,
            currency=order.currency,
            gross_amount=gross_amount,
            seller_amount=seller_amount,
            commission_amount=commission_amount,
            broker_amount=broker_amount,
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
    _assert_trusted_pickup_evidence(db, hold)
    _assert_verified_delivery(db, hold)
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

    # Notify the seller at the actual financial release milestone (not pickup).
    if fully_released and hold.seller is not None and getattr(hold.seller, "user_id", None):
        try:
            from api.enums import NotificationEvent
            from api.services.notification_service import notification_service
            notification_service.notify(
                db=db,
                user_id=hold.seller.user_id,
                event=NotificationEvent.payout_updated,
                title="Seller funds released",
                message="Xerin released the eligible seller entitlement after verified delivery and the customer-protection settlement rule was satisfied.",
                data={"order_id": str(hold.order_id), "order_item_id": str(hold.order_item_id), "escrow_hold_id": str(hold.id)},
                action_url="/seller/earnings",
                commit=False,
            )
        except Exception:
            # A notification failure must never roll back a valid financial release.
            pass

    db.flush()
    # Broker entitlement follows the same trusted settlement milestone as this
    # order item. This only changes commission state; B6 owns wallet credit.
    make_commission_available_for_hold(db, hold=hold)
    db.flush()
    return hold


def release_shipment_seller_entitlement(
    db: Session,
    *,
    proof: ShipmentPickupProof,
    actor_id=None,
    trigger: str,
) -> list[EscrowHold]:
    """Record trusted pickup custody evidence without releasing seller money."""
    proof = (
        db.query(ShipmentPickupProof)
        .filter(ShipmentPickupProof.id == proof.id)
        .with_for_update()
        .one()
    )
    if proof.status not in {"approved", "auto_approved"}:
        raise ValueError("Pickup proof must be approved before seller settlement")
    handover = (
        db.query(ShipmentHandover)
        .filter(
            ShipmentHandover.id == proof.handover_id,
            ShipmentHandover.shipment_id == proof.shipment_id,
        )
        .with_for_update()
        .first()
    )
    if handover is None or handover.status != "seller_confirmed" or handover.seller_confirmed_at is None:
        raise ValueError("Seller-confirmed physical handover is required for settlement")

    order_item_ids = [
        row[0]
        for row in db.query(ShipmentItem.order_item_id)
        .filter(ShipmentItem.shipment_id == proof.shipment_id)
        .all()
    ]
    if not order_item_ids:
        raise ValueError("Shipment has no order items eligible for settlement")
    holds = (
        db.query(EscrowHold)
        .filter(
            EscrowHold.order_id == proof.order_id,
            EscrowHold.seller_id == proof.seller_id,
            EscrowHold.order_item_id.in_(order_item_ids),
        )
        .order_by(EscrowHold.created_at)
        .with_for_update()
        .all()
    )
    now = datetime.now().astimezone()
    for hold in holds:
        if hold.status == "disputed":
            raise ValueError("Disputed seller settlement cannot be released")
        hold.seller_release_shipment_id = proof.shipment_id
        hold.seller_release_handover_id = handover.id
        hold.seller_release_proof_id = proof.id
        # F6: pickup proof is custody evidence only. It must never release seller
        # funds before verified delivery. Delivery verification later starts the
        # configurable customer-protection clock.
        hold.seller_release_trigger = "pickup_verified_custody"
        if hold.status == "refunded":
            continue
        existing = db.query(EscrowEvent.id).filter(
            EscrowEvent.escrow_hold_id == hold.id,
            EscrowEvent.event_type == "pickup_verified_custody",
        ).first()
        if not existing:
            db.add(EscrowEvent(
                escrow_hold_id=hold.id,
                event_type="pickup_verified_custody",
                note="Seller handover and pickup evidence verified; settlement remains held until verified delivery",
                created_by_id=actor_id,
            ))
    db.flush()
    return holds


def dispute_shipment_seller_entitlement(
    db: Session,
    *,
    proof: ShipmentPickupProof,
    actor_id=None,
) -> list[EscrowHold]:
    """Block the shipment's seller holds when pickup evidence is disputed."""
    order_item_ids = [
        row[0]
        for row in db.query(ShipmentItem.order_item_id)
        .filter(ShipmentItem.shipment_id == proof.shipment_id)
        .all()
    ]
    if not order_item_ids:
        return []
    holds = (
        db.query(EscrowHold)
        .filter(
            EscrowHold.order_id == proof.order_id,
            EscrowHold.seller_id == proof.seller_id,
            EscrowHold.order_item_id.in_(order_item_ids),
        )
        .with_for_update()
        .all()
    )
    for hold in holds:
        if hold.status == "released":
            raise ValueError("Seller settlement was already released and requires financial dispute handling")
        if hold.status == "refunded":
            continue
        hold.seller_release_shipment_id = proof.shipment_id
        hold.seller_release_handover_id = proof.handover_id
        hold.seller_release_proof_id = proof.id
        hold.seller_release_trigger = "pickup_disputed"
        hold.status = "disputed"
        existing = db.query(EscrowEvent.id).filter(
            EscrowEvent.escrow_hold_id == hold.id,
            EscrowEvent.event_type == "pickup_disputed",
        ).first()
        if not existing:
            db.add(EscrowEvent(
                escrow_hold_id=hold.id,
                event_type="pickup_disputed",
                note="Customer disputed pickup evidence; seller settlement remains held",
                created_by_id=actor_id,
            ))
    db.flush()
    return holds


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


def release_order_item_escrow(
    db: Session,
    *,
    order: Order,
    order_item_id,
    created_by_id=None,
    note: str | None = None,
    event_type: str = "customer_item_accepted",
) -> EscrowHold:
    hold = (
        db.query(EscrowHold)
        .filter(EscrowHold.order_id == order.id, EscrowHold.order_item_id == order_item_id)
        .with_for_update()
        .first()
    )
    if hold is None:
        raise ValueError("This order item has no escrow hold")
    if hold.status == "disputed":
        raise ValueError("This product is under dispute and cannot be accepted for settlement")
    if hold.status != "released":
        release_escrow_hold_funds(
            db,
            hold=hold,
            note=note or "Customer accepted this delivered product",
            created_by_id=created_by_id,
            event_type=event_type,
        )
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
    marketplace = db.query(MarketplaceSettings).filter(MarketplaceSettings.singleton_key == 1).first()
    grace_hours = int(getattr(marketplace, "seller_release_grace_hours", None) or 144)
    early_accept = bool(True if marketplace is None else getattr(marketplace, "allow_customer_early_acceptance", True))
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
            "delivery_verified_at": None,
            "seller_release_grace_hours": grace_hours,
            "allow_customer_early_acceptance": early_accept,
            "can_customer_approve": False,
            "can_report_problem": False,
            "items": [],
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
    verified_dates = [h.seller_release_verified_at for h in holds if h.seller_release_verified_at is not None]
    all_delivered = bool(order.shipments) and all(
        getattr(shipment.status, "value", shipment.status) == "delivered"
        and shipment.delivery_proof is not None
        and shipment.delivery_proof.status == "verified"
        for shipment in order.shipments
    )
    payment_completed = any(
        getattr(payment.status, "value", payment.status) == "completed"
        for payment in order.payments
    )
    can_act = all_delivered and payment_completed
    item_rows = []
    for h in holds:
        h_remaining = _money(_money(h.gross_amount) - _money(h.released_amount) - _money(h.refunded_amount))
        item_rows.append({
            "order_item_id": h.order_item_id,
            "seller_id": h.seller_id,
            "status": h.status,
            "seller_amount": _money(h.seller_amount),
            "released_amount": _money(h.released_amount),
            "remaining_amount": h_remaining,
            "release_after": h.release_after,
            "can_customer_accept": bool(early_accept and can_act and h.status in {"held", "partially_refunded"} and h_remaining > 0),
            "can_report_problem": bool(can_act and h.status in {"held", "partially_refunded", "disputed"} and h_remaining > 0),
        })

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
        "delivery_verified_at": min(verified_dates) if verified_dates else None,
        "seller_release_grace_hours": grace_hours,
        "allow_customer_early_acceptance": early_accept,
        "can_customer_approve": bool(early_accept and can_act and status in {"held", "partially_released", "partially_refunded"}),
        "can_report_problem": bool(can_act and remaining > 0 and status != "released"),
        "items": item_rows,
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
            EscrowHold.seller_release_verified_at.is_not(None),
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
            note="Automatic seller release after verified-delivery protection period expired with no active hold",
            event_type="delivery_grace_auto_released",
        )
        count += 1
    return count
