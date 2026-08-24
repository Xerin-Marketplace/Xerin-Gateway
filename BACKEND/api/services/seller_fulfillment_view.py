from __future__ import annotations

from decimal import Decimal
from math import ceil
from uuid import UUID

from sqlalchemy import String, cast, func, or_
from sqlalchemy.orm import Session, selectinload

from api.models import (
    EscrowHold,
    LogisticsCompany,
    Order,
    SellerOrder,
    SellerOrderPackage,
    SellerPickupLocation,
    Shipment,
    ShipmentHandover,
    ShipmentTrackingEvent,
)
from api.services.seller_fulfillment_readiness import (
    evaluate_seller_fulfillment_readiness,
)


def seller_fulfillment_query(db: Session, seller_id: UUID):
    return (
        db.query(SellerOrder)
        .options(
            selectinload(SellerOrder.order).selectinload(Order.user),
            selectinload(SellerOrder.order).selectinload(Order.shipping_address),
            selectinload(SellerOrder.order).selectinload(Order.items),
            selectinload(SellerOrder.order)
                .selectinload(Order.shipments)
                .selectinload(Shipment.logistics_company),
            selectinload(SellerOrder.order)
                .selectinload(Order.shipments)
                .selectinload(Shipment.tracking_events),
            selectinload(SellerOrder.packages),
        )
        .filter(SellerOrder.seller_id == seller_id)
    )


def seller_shipment(row: SellerOrder) -> Shipment | None:
    return next(
        (
            shipment
            for shipment in row.order.shipments
            if shipment.seller_id == row.seller_id
        ),
        None,
    )


def seller_handover(
    db: Session,
    *,
    seller_order_id: UUID,
) -> ShipmentHandover | None:
    return (
        db.query(ShipmentHandover)
        .filter(ShipmentHandover.seller_order_id == seller_order_id)
        .first()
    )


def default_pickup(
    db: Session,
    *,
    seller_id: UUID,
) -> SellerPickupLocation | None:
    return (
        db.query(SellerPickupLocation)
        .filter(
            SellerPickupLocation.seller_id == seller_id,
            SellerPickupLocation.is_active.is_(True),
            SellerPickupLocation.is_default.is_(True),
        )
        .first()
    )


def package_totals(packages: list[SellerOrderPackage]) -> dict:
    physical_count = sum(int(package.package_count or 0) for package in packages)
    total_weight = sum(
        (
            Decimal(package.weight_kg or 0)
            * Decimal(package.package_count or 0)
        )
        for package in packages
    )
    ready = sum(1 for package in packages if package.is_ready)
    return {
        "package_groups": len(packages),
        "physical_package_count": physical_count,
        "total_weight_kg": total_weight,
        "packages_ready": ready,
    }


def settlement_snapshot(
    db: Session,
    *,
    order_id: UUID,
    seller_id: UUID,
) -> dict:
    """Read-only view of the current escrow ledger.

    Phase 1 Task 7 does not change release rules. Later settlement phases will
    replace the release policy with pickup-verification driven eligibility.
    """
    holds = (
        db.query(EscrowHold)
        .filter(
            EscrowHold.order_id == order_id,
            EscrowHold.seller_id == seller_id,
        )
        .all()
    )

    if not holds:
        return {
            "state": "not_created",
            "gross_held": Decimal("0"),
            "seller_amount": Decimal("0"),
            "commission_amount": Decimal("0"),
            "released_amount": Decimal("0"),
            "refunded_amount": Decimal("0"),
            "currency": None,
            "hold_count": 0,
            "note": (
                "No seller escrow hold exists for this order yet. "
                "Phase 7 will define the final pickup-verification settlement policy."
            ),
        }

    currencies = {hold.currency for hold in holds}
    currency = next(iter(currencies)) if len(currencies) == 1 else None

    statuses = {str(hold.status) for hold in holds}
    if any(status == "disputed" for status in statuses):
        state = "disputed"
    elif all(status == "released" for status in statuses):
        state = "released"
    elif all(status == "refunded" for status in statuses):
        state = "refunded"
    elif any(status == "released" for status in statuses):
        state = "partially_released"
    else:
        state = "held"

    return {
        "state": state,
        "gross_held": sum(Decimal(hold.gross_amount or 0) for hold in holds),
        "seller_amount": sum(Decimal(hold.seller_amount or 0) for hold in holds),
        "commission_amount": sum(
            Decimal(hold.commission_amount or 0) for hold in holds
        ),
        "released_amount": sum(
            Decimal(hold.released_amount or 0) for hold in holds
        ),
        "refunded_amount": sum(
            Decimal(hold.refunded_amount or 0) for hold in holds
        ),
        "currency": currency,
        "hold_count": len(holds),
        "note": (
            "Read-only snapshot of the current escrow ledger. "
            "Task 7 does not release funds; the later settlement phase will "
            "change eligibility to use verified pickup/customer approval."
        ),
    }


def pickup_view(location: SellerPickupLocation | None) -> dict | None:
    if location is None:
        return None
    return {
        "id": location.id,
        "label": location.label,
        "formatted_address": location.formatted_address,
        "country": location.country,
        "region": location.region,
        "city": location.city,
        "district": location.district,
        "ward": location.ward,
        "landmark": location.landmark,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "pickup_contact_name": location.pickup_contact_name,
        "pickup_phone": location.pickup_phone,
        "pickup_instructions": location.pickup_instructions,
        "is_default": location.is_default,
        "is_verified": location.is_verified,
    }


def package_view(package: SellerOrderPackage) -> dict:
    return {
        "id": package.id,
        "package_label": package.package_label,
        "package_type": package.package_type,
        "contents_summary": package.contents_summary,
        "weight_kg": package.weight_kg,
        "length_cm": package.length_cm,
        "width_cm": package.width_cm,
        "height_cm": package.height_cm,
        "package_count": package.package_count,
        "fragile": package.fragile,
        "keep_upright": package.keep_upright,
        "temperature_sensitive": package.temperature_sensitive,
        "handling_instructions": package.handling_instructions,
        "declared_value": package.declared_value,
        "declared_currency": package.declared_currency,
        "is_ready": package.is_ready,
        "prepared_at": package.prepared_at,
        "sealed_at": package.sealed_at,
    }


def logistics_company_view(company: LogisticsCompany | None) -> dict | None:
    if company is None:
        return None
    return {
        "id": company.id,
        "name": company.name,
        "code": company.code,
        "contact_name": company.contact_name,
        "contact_email": company.contact_email,
        "contact_phone": company.contact_phone,
        "supports_tracking": company.supports_tracking,
        "supports_webhooks": company.supports_webhooks,
    }


def handover_view(handover: ShipmentHandover | None) -> dict | None:
    if handover is None:
        return None
    return {
        "id": handover.id,
        "status": handover.status,
        "courier_arrived_at": handover.courier_arrived_at,
        "courier_arrival_latitude": handover.courier_arrival_latitude,
        "courier_arrival_longitude": handover.courier_arrival_longitude,
        "courier_arrival_notes": handover.courier_arrival_notes,
        "seller_confirmed_at": handover.seller_confirmed_at,
        "seller_confirmation_notes": handover.seller_confirmation_notes,
    }


def readiness_view(db: Session, row: SellerOrder) -> dict:
    readiness = evaluate_seller_fulfillment_readiness(db, seller_order=row)
    return {
        "seller_order_id": row.id,
        "ready_to_ship": readiness.ready,
        "pickup_location_id": (
            readiness.pickup_location.id
            if readiness.pickup_location
            else None
        ),
        "package_id": readiness.package.id if readiness.package else None,
        "package_ids": [package.id for package in readiness.packages],
        "package_groups": len(readiness.packages),
        "physical_package_count": sum(
            (package.package_count or 0)
            for package in readiness.packages
        ),
        "total_weight_kg": sum(
            (
                Decimal(package.weight_kg or 0)
                * Decimal(package.package_count or 0)
            )
            for package in readiness.packages
        ),
        "shipment_id": readiness.shipment.id if readiness.shipment else None,
        "blockers": [
            check.detail or check.label
            for check in readiness.blockers
        ],
        "warnings": [
            check.detail or check.label
            for check in readiness.checks
            if not check.blocking and not check.ready
        ],
        "checks": [
            {
                "code": check.code,
                "label": check.label,
                "ready": check.ready,
                "blocking": check.blocking,
                "detail": check.detail,
            }
            for check in readiness.checks
        ],
    }


def customer_delivery_address(row: SellerOrder) -> dict | None:
    address = row.order.shipping_address
    if address is None:
        return None
    return {
        "id": str(address.id),
        "label": address.label,
        "recipient_name": address.recipient_name,
        "recipient_phone": address.recipient_phone,
        "street": address.street,
        "landmark": address.landmark,
        "ward": address.ward,
        "district": address.district,
        "city": address.city,
        "region": address.region,
        "postal_code": address.postal_code,
        "country": address.country,
        "latitude": address.latitude,
        "longitude": address.longitude,
    }


def customer_name(row: SellerOrder) -> str:
    user = row.order.user
    return (
        f"{user.first_name or ''} {user.last_name or ''}".strip()
        or user.email
    )


def detail_view(db: Session, row: SellerOrder) -> dict:
    shipment = seller_shipment(row)
    handover = seller_handover(db, seller_order_id=row.id)
    pickup = default_pickup(db, seller_id=row.seller_id)
    packages = list(row.packages or [])
    totals = package_totals(packages)

    company = shipment.logistics_company if shipment else None

    recent_tracking = []
    if shipment:
        recent_tracking = sorted(
            shipment.tracking_events,
            key=lambda event: event.created_at,
            reverse=True,
        )[:10]

    return {
        "seller_order_id": row.id,
        "order_id": row.order_id,
        "seller_id": row.seller_id,
        "seller_status": row.status,
        "order_status": row.order.status,
        "currency": row.order.currency,
        "seller_subtotal": row.seller_subtotal,
        "item_count": row.item_count,
        "customer_name": customer_name(row),
        "customer_phone": row.order.user.phone,
        "delivery_address": customer_delivery_address(row),
        "pickup_location": pickup_view(pickup),
        "packages": [package_view(package) for package in packages],
        **totals,
        "readiness": readiness_view(db, row),
        "shipment": shipment,
        "logistics_company": logistics_company_view(company),
        "handover": handover_view(handover),
        "settlement": settlement_snapshot(
            db,
            order_id=row.order_id,
            seller_id=row.seller_id,
        ),
        "recent_tracking": recent_tracking,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
