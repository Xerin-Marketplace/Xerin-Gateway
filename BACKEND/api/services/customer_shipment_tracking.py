from __future__ import annotations

from datetime import datetime, timezone
from math import ceil
from uuid import UUID

from sqlalchemy import String, cast, or_
from sqlalchemy.orm import Session, joinedload, selectinload

from api.enums import ShipmentStatus
from api.models import (
    Order,
    OrderItem,
    Seller,
    Shipment,
    ShipmentItem,
    ShipmentPickupProof,
    ShipmentTrackingEvent,
)
from api.services.pickup_proof_service import auto_approve_if_expired


class CustomerShipmentTrackingError(Exception):
    def __init__(self, message: str, *, code: str, status_code: int):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


STATUS_PROGRESS = {
    "pending": 5,
    "ready_for_dispatch": 25,
    "dispatched": 45,
    "in_transit": 65,
    "out_for_delivery": 85,
    "delivered": 100,
    "delivery_failed": 80,
    "returned": 100,
    "cancelled": 100,
}

STATUS_LABELS = {
    "pending": "Preparing",
    "ready_for_dispatch": "Ready for pickup",
    "dispatched": "Picked up",
    "in_transit": "In transit",
    "out_for_delivery": "Out for delivery",
    "delivered": "Delivered",
    "delivery_failed": "Delivery issue",
    "returned": "Returned",
    "cancelled": "Cancelled",
}


def _value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _page_count(total: int, page_size: int) -> int:
    return ceil(total / page_size) if total else 0


def _customer_order(db: Session, *, order_id: UUID, user_id: UUID) -> Order:
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == user_id)
        .first()
    )
    if order is None:
        raise CustomerShipmentTrackingError(
            "Order not found.",
            code="order_not_found",
            status_code=404,
        )
    return order


def _normalize_expired_proofs(
    db: Session,
    proofs: list[ShipmentPickupProof],
) -> None:
    changed = False
    for proof in proofs:
        before = proof.status
        auto_approve_if_expired(db, proof, commit=False)
        if proof.status != before:
            changed = True
    if changed:
        db.commit()


def _tracking_summary(order: Order, shipments: list[Shipment], proofs_by_shipment: dict) -> dict:
    counts = {
        "pending_count": 0,
        "ready_count": 0,
        "dispatched_count": 0,
        "in_transit_count": 0,
        "out_for_delivery_count": 0,
        "delivered_count": 0,
        "failed_or_returned_count": 0,
    }

    progress_values = []
    for shipment in shipments:
        status = _value(shipment.status)
        progress_values.append(STATUS_PROGRESS.get(status, 0))

        if status == "pending":
            counts["pending_count"] += 1
        elif status == "ready_for_dispatch":
            counts["ready_count"] += 1
        elif status == "dispatched":
            counts["dispatched_count"] += 1
        elif status == "in_transit":
            counts["in_transit_count"] += 1
        elif status == "out_for_delivery":
            counts["out_for_delivery_count"] += 1
        elif status == "delivered":
            counts["delivered_count"] += 1
        elif status in {"delivery_failed", "returned", "cancelled"}:
            counts["failed_or_returned_count"] += 1

    pending_reviews = sum(
        1 for proof in proofs_by_shipment.values()
        if proof is not None and proof.status == "pending"
    )
    disputed = sum(
        1 for proof in proofs_by_shipment.values()
        if proof is not None and proof.status == "disputed"
    )

    statuses = {_value(shipment.status) for shipment in shipments}
    shipment_count = len(shipments)

    if shipment_count == 0:
        overall = "preparing"
    elif counts["delivered_count"] == shipment_count:
        overall = "delivered"
    elif counts["failed_or_returned_count"] > 0:
        overall = "attention_required"
    elif counts["out_for_delivery_count"] > 0:
        overall = "out_for_delivery"
    elif statuses.intersection({"in_transit", "dispatched"}):
        overall = "in_transit"
    elif "ready_for_dispatch" in statuses:
        overall = "ready_for_pickup"
    else:
        overall = "preparing"

    eta_from = [
        shipment.estimated_delivery_from
        for shipment in shipments
        if shipment.estimated_delivery_from is not None
    ]
    eta_to = [
        shipment.estimated_delivery_to
        for shipment in shipments
        if shipment.estimated_delivery_to is not None
    ]

    return {
        "order_id": order.id,
        "order_status": order.status,
        "overall_tracking_status": overall,
        "overall_progress_percent": (
            round(sum(progress_values) / len(progress_values))
            if progress_values
            else 0
        ),
        "shipment_count": shipment_count,
        **counts,
        "pending_pickup_reviews": pending_reviews,
        "disputed_pickup_proofs": disputed,
        "requires_customer_action": bool(pending_reviews or disputed),
        "created_at": order.created_at,
        "estimated_delivery_from": min(eta_from) if eta_from else order.estimated_delivery_from,
        "estimated_delivery_to": max(eta_to) if eta_to else order.estimated_delivery_to,
    }


def get_customer_order_tracking(
    db: Session,
    *,
    order_id: UUID,
    user_id: UUID,
    page: int,
    page_size: int,
    search: str | None = None,
    shipment_status: ShipmentStatus | None = None,
    requires_action: bool | None = None,
) -> dict:
    """Aggregate one multi-seller order into customer-facing shipment tracking.

    Pagination is per seller shipment. Each shipment includes the latest five
    tracking events; full event history has a separate paginated endpoint.
    """
    order = _customer_order(db, order_id=order_id, user_id=user_id)

    all_shipments = (
        db.query(Shipment)
        .options(
            joinedload(Shipment.seller),
            joinedload(Shipment.logistics_company),
            selectinload(Shipment.items).joinedload(ShipmentItem.order_item),
            selectinload(Shipment.tracking_events),
        )
        .filter(Shipment.order_id == order.id)
        .order_by(Shipment.created_at.asc(), Shipment.id.asc())
        .all()
    )

    proofs = (
        db.query(ShipmentPickupProof)
        .options(joinedload(ShipmentPickupProof.shipment))
        .filter(
            ShipmentPickupProof.order_id == order.id,
            ShipmentPickupProof.customer_id == user_id,
        )
        .all()
    )
    _normalize_expired_proofs(db, proofs)
    proofs_by_shipment = {proof.shipment_id: proof for proof in proofs}

    summary = _tracking_summary(order, all_shipments, proofs_by_shipment)

    rows = all_shipments

    if shipment_status is not None:
        rows = [row for row in rows if row.status == shipment_status]

    term = (search or "").strip().casefold()
    if term:
        filtered = []
        for shipment in rows:
            seller_name = (
                shipment.seller.business_name
                if shipment.seller is not None
                else ""
            )
            logistics_name = (
                shipment.logistics_company.name
                if shipment.logistics_company is not None
                else ""
            )
            product_names = [
                item.order_item.product_name
                for item in shipment.items
                if item.order_item is not None
            ]
            haystack = " ".join(
                [
                    str(shipment.id),
                    shipment.tracking_number or "",
                    shipment.carrier_name or "",
                    seller_name,
                    logistics_name,
                    *product_names,
                ]
            ).casefold()
            if term in haystack:
                filtered.append(shipment)
        rows = filtered

    if requires_action is not None:
        rows = [
            shipment
            for shipment in rows
            if bool(
                proofs_by_shipment.get(shipment.id)
                and proofs_by_shipment[shipment.id].status in {"pending", "disputed"}
            )
            is requires_action
        ]

    total = len(rows)
    page_rows = rows[(page - 1) * page_size : page * page_size]

    result_rows = []
    for shipment in page_rows:
        proof = proofs_by_shipment.get(shipment.id)
        events = sorted(
            list(shipment.tracking_events or []),
            key=lambda row: row.created_at or datetime.min.replace(tzinfo=timezone.utc),
            reverse=True,
        )
        latest = events[0] if events else None

        products = []
        for shipment_item in shipment.items:
            order_item = shipment_item.order_item
            if order_item is None:
                continue
            products.append(
                {
                    "order_item_id": order_item.id,
                    "product_name": order_item.product_name,
                    "quantity": shipment_item.quantity,
                    "unit_price": order_item.unit_price,
                }
            )

        status_value = _value(shipment.status)
        proof_state = None
        if proof is not None:
            proof_state = {
                "proof_id": proof.id,
                "status": proof.status,
                "photo_url": proof.photo_url,
                "review_deadline": proof.review_deadline,
                "customer_reviewed_at": proof.customer_reviewed_at,
                "problem_reason": proof.problem_reason,
                "requires_customer_action": proof.status in {"pending", "disputed"},
            }

        result_rows.append(
            {
                "shipment_id": shipment.id,
                "seller_id": shipment.seller_id,
                "seller_name": (
                    shipment.seller.business_name
                    if shipment.seller is not None
                    else "Seller"
                ),
                "status": shipment.status,
                "status_label": STATUS_LABELS.get(
                    status_value,
                    status_value.replace("_", " ").title(),
                ),
                "progress_percent": STATUS_PROGRESS.get(status_value, 0),
                "logistics_company_id": shipment.logistics_company_id,
                "logistics_company_name": (
                    shipment.logistics_company.name
                    if shipment.logistics_company is not None
                    else None
                ),
                "carrier_name": shipment.carrier_name,
                "tracking_number": shipment.tracking_number,
                "estimated_delivery_from": shipment.estimated_delivery_from,
                "estimated_delivery_to": shipment.estimated_delivery_to,
                "dispatched_at": shipment.dispatched_at,
                "delivered_at": shipment.delivered_at,
                "item_count": sum(item.quantity for item in shipment.items),
                "items": products,
                "pickup_proof": proof_state,
                "latest_event": (
                    {
                        "id": latest.id,
                        "status": latest.status,
                        "location": latest.location,
                        "notes": latest.notes,
                        "created_at": latest.created_at,
                    }
                    if latest is not None
                    else None
                ),
                "recent_events": [
                    {
                        "id": event.id,
                        "status": event.status,
                        "location": event.location,
                        "notes": event.notes,
                        "created_at": event.created_at,
                    }
                    for event in events[:5]
                ],
                "requires_customer_action": bool(
                    proof is not None and proof.status in {"pending", "disputed"}
                ),
            }
        )

    return {
        "summary": summary,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _page_count(total, page_size),
        "results": result_rows,
    }


def get_customer_shipment_tracking_events(
    db: Session,
    *,
    order_id: UUID,
    shipment_id: UUID,
    user_id: UUID,
    page: int,
    page_size: int,
) -> dict:
    _customer_order(db, order_id=order_id, user_id=user_id)

    shipment_exists = (
        db.query(Shipment.id)
        .filter(Shipment.id == shipment_id, Shipment.order_id == order_id)
        .first()
    )
    if shipment_exists is None:
        raise CustomerShipmentTrackingError(
            "Shipment not found for this order.",
            code="shipment_not_found",
            status_code=404,
        )

    query = db.query(ShipmentTrackingEvent).filter(
        ShipmentTrackingEvent.shipment_id == shipment_id
    )
    total = query.count()
    rows = (
        query.order_by(
            ShipmentTrackingEvent.created_at.desc(),
            ShipmentTrackingEvent.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "shipment_id": shipment_id,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _page_count(total, page_size),
        "results": rows,
    }
