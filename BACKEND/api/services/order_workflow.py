"""End-to-end marketplace order workflow projection and safe reconciliation."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from sqlalchemy.orm import Session

from api.enums import SellerOrderStatus, ShipmentStatus
from api.models import (
    LogisticsPickupJob,
    Order,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentMethod,
    PaymentStatus,
    SellerOrder,
    Shipment,
    ShipmentHandover,
    ShipmentPickupProof,
    ShipmentTrackingEvent,
)


def _value(value: Any) -> str | None:
    if value is None:
        return None
    return value.value if hasattr(value, "value") else str(value)


def _stage(name: str, status: str, detail: str) -> dict[str, str]:
    return {"name": name, "status": status, "detail": detail}


def build_order_workflow(db: Session, order: Order) -> dict[str, Any]:
    """Build a single projection spanning checkout through delivery."""
    payments = db.query(Payment).filter(Payment.order_id == order.id).all()
    seller_orders = (
        db.query(SellerOrder)
        .filter(SellerOrder.order_id == order.id)
        .order_by(SellerOrder.created_at.asc())
        .all()
    )
    shipments = (
        db.query(Shipment)
        .filter(Shipment.order_id == order.id)
        .order_by(Shipment.created_at.asc())
        .all()
    )
    shipment_ids = [shipment.id for shipment in shipments]

    jobs: dict[Any, LogisticsPickupJob] = {}
    handovers: dict[Any, ShipmentHandover] = {}
    proofs: dict[Any, ShipmentPickupProof] = {}
    events: dict[Any, list[ShipmentTrackingEvent]] = defaultdict(list)
    if shipment_ids:
        jobs = {
            row.shipment_id: row
            for row in db.query(LogisticsPickupJob)
            .filter(LogisticsPickupJob.shipment_id.in_(shipment_ids))
            .all()
        }
        handovers = {
            row.shipment_id: row
            for row in db.query(ShipmentHandover)
            .filter(ShipmentHandover.shipment_id.in_(shipment_ids))
            .all()
        }
        proofs = {
            row.shipment_id: row
            for row in db.query(ShipmentPickupProof)
            .filter(ShipmentPickupProof.shipment_id.in_(shipment_ids))
            .all()
        }
        for row in (
            db.query(ShipmentTrackingEvent)
            .filter(ShipmentTrackingEvent.shipment_id.in_(shipment_ids))
            .order_by(ShipmentTrackingEvent.created_at.asc())
            .all()
        ):
            events[row.shipment_id].append(row)

    completed_payment = any(payment.status == PaymentStatus.completed for payment in payments)
    cash_on_delivery = any(payment.method == PaymentMethod.cash_on_delivery for payment in payments)
    payment_ready = completed_payment or cash_on_delivery
    terminal_order = order.status in {OrderStatus.cancelled, OrderStatus.refunded}

    blockers: list[str] = []
    if not order.items:
        blockers.append("Order has no items")
    if not payment_ready and not terminal_order:
        blockers.append("Payment is not completed and no cash-on-delivery payment exists")
    if payment_ready and not seller_orders and not terminal_order:
        blockers.append("Paid order has no seller orders")
    if seller_orders and not shipments and not terminal_order:
        blockers.append("Seller orders exist but no shipments have been created")

    seller_order_by_seller = {row.seller_id: row for row in seller_orders}
    shipment_flows: list[dict[str, Any]] = []
    delivered_count = 0
    for shipment in shipments:
        seller_order = seller_order_by_seller.get(shipment.seller_id)
        job = jobs.get(shipment.id)
        handover = handovers.get(shipment.id)
        proof = proofs.get(shipment.id)
        tracking = events.get(shipment.id, [])
        shipment_status = _value(shipment.status)
        latest_tracking_status = _value(tracking[-1].status) if tracking else None
        if shipment.status == ShipmentStatus.delivered:
            delivered_count += 1
        if seller_order is None:
            blockers.append(f"Shipment {shipment.id} has no matching seller order")
        if shipment.logistics_company_id is None and shipment.status not in {
            ShipmentStatus.cancelled,
            ShipmentStatus.returned_to_sender,
        }:
            blockers.append(f"Shipment {shipment.id} has no logistics company")
        if latest_tracking_status != shipment_status:
            blockers.append(f"Shipment {shipment.id} current status is missing from tracking history")

        shipment_flows.append(
            {
                "shipment_id": shipment.id,
                "seller_id": shipment.seller_id,
                "seller_order_id": seller_order.id if seller_order else None,
                "seller_order_status": _value(seller_order.status) if seller_order else None,
                "shipment_status": shipment_status,
                "logistics_company_id": shipment.logistics_company_id,
                "pickup_job_status": _value(job.status) if job else None,
                "handover_status": handover.status if handover else None,
                "pickup_proof_status": proof.status if proof else None,
                "latest_tracking_status": latest_tracking_status,
                "tracking_event_count": len(tracking),
            }
        )

    all_delivered = bool(shipments) and delivered_count == len(shipments)
    any_in_transit = any(
        shipment.status in {
            ShipmentStatus.dispatched,
            ShipmentStatus.in_transit,
            ShipmentStatus.out_for_delivery,
            ShipmentStatus.delivered,
        }
        for shipment in shipments
    )

    stages = [
        _stage("checkout", "complete" if order.items else "blocked", "Order and delivery selection captured" if order.items else "Order contains no items"),
        _stage("payment", "complete" if payment_ready else ("complete" if terminal_order else "waiting"), "Payment confirmed or cash on delivery" if payment_ready else "Awaiting confirmed payment"),
        _stage("seller_fulfillment", "complete" if seller_orders and all(row.status in {SellerOrderStatus.shipped, SellerOrderStatus.delivered} for row in seller_orders) else ("in_progress" if seller_orders else "waiting"), f"{len(seller_orders)} seller order(s)"),
        _stage("logistics", "complete" if shipments and all(row.logistics_company_id for row in shipments) else ("in_progress" if shipments else "waiting"), f"{len(shipments)} shipment(s) created"),
        _stage("pickup", "complete" if shipments and all((jobs.get(row.id) and _value(jobs[row.id].status) == 'completed') or row.status in {ShipmentStatus.in_transit, ShipmentStatus.out_for_delivery, ShipmentStatus.delivered} for row in shipments) else ("in_progress" if any(jobs.values()) else "waiting"), f"{len(handovers)} handover(s), {len(proofs)} proof(s)"),
        _stage("delivery", "complete" if all_delivered else ("in_progress" if any_in_transit else "waiting"), f"{delivered_count} of {len(shipments)} shipment(s) delivered"),
    ]

    overall = "terminal" if terminal_order else "complete" if all_delivered else "action_required" if blockers else "in_progress"
    return {
        "order_id": order.id,
        "order_status": _value(order.status),
        "overall_status": overall,
        "delivery_quote_id": order.delivery_quote_id,
        "payment_ready": payment_ready,
        "seller_order_count": len(seller_orders),
        "shipment_count": len(shipments),
        "delivered_shipment_count": delivered_count,
        "stages": stages,
        "shipments": shipment_flows,
        "blockers": list(dict.fromkeys(blockers)),
        "reconciliation_actions": [],
    }


def reconcile_order_workflow(db: Session, order: Order, *, actor_id: Any) -> dict[str, Any]:
    """Repair safe forward-only status drift and return the refreshed projection."""
    actions: list[str] = []
    shipments = db.query(Shipment).filter(Shipment.order_id == order.id).all()
    seller_orders = {
        row.seller_id: row
        for row in db.query(SellerOrder).filter(SellerOrder.order_id == order.id).all()
    }

    for shipment in shipments:
        latest = (
            db.query(ShipmentTrackingEvent)
            .filter(ShipmentTrackingEvent.shipment_id == shipment.id)
            .order_by(ShipmentTrackingEvent.created_at.desc())
            .first()
        )
        if latest is None or latest.status != shipment.status:
            db.add(ShipmentTrackingEvent(
                shipment_id=shipment.id,
                status=shipment.status,
                notes="Workflow reconciliation: synchronized current shipment status",
                created_by_id=actor_id,
            ))
            actions.append(f"Added tracking checkpoint for shipment {shipment.id}")

        seller_order = seller_orders.get(shipment.seller_id)
        if shipment.status == ShipmentStatus.delivered and seller_order and seller_order.status != SellerOrderStatus.delivered:
            seller_order.status = SellerOrderStatus.delivered
            seller_order.delivered_at = shipment.delivered_at
            actions.append(f"Marked seller order {seller_order.id} delivered")

    target: OrderStatus | None = None
    if shipments and all(row.status == ShipmentStatus.delivered for row in shipments):
        target = OrderStatus.delivered
    elif shipments and any(row.status in {ShipmentStatus.dispatched, ShipmentStatus.in_transit, ShipmentStatus.out_for_delivery, ShipmentStatus.delivered} for row in shipments):
        target = OrderStatus.shipped

    allowed_current = {OrderStatus.paid, OrderStatus.processing, OrderStatus.shipped}
    if target and order.status in allowed_current and order.status != target:
        order.status = target
        db.add(OrderStatusHistory(
            order_id=order.id,
            status=target.value,
            notes="Workflow reconciliation: synchronized parent order from shipment progress",
            created_by_id=actor_id,
        ))
        actions.append(f"Moved parent order to {target.value}")

    db.commit()
    db.refresh(order)
    result = build_order_workflow(db, order)
    result["reconciliation_actions"] = actions
    return result
