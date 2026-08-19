from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from api.models import (
    LogisticsWebhookEvent,
    SellerOrder,
    SellerPickupLocation,
    Shipment,
)

READY_EVENT = "shipment.ready_for_pickup"


def _money(value):
    return str(Decimal(value or 0).quantize(Decimal("0.01")))


def build_ready_for_pickup_payload(db: Session, *, seller_order: SellerOrder, shipment: Shipment) -> dict:
    order = seller_order.order
    seller = seller_order.seller
    pickup = (
        db.query(SellerPickupLocation)
        .filter(
            SellerPickupLocation.seller_id == seller_order.seller_id,
            SellerPickupLocation.is_active.is_(True),
            SellerPickupLocation.is_default.is_(True),
        )
        .first()
    )
    address = order.shipping_address
    packages = list(seller_order.packages or [])

    return {
        "event": READY_EVENT,
        "shipment_id": str(shipment.id),
        "order_id": str(order.id),
        "seller_order_id": str(seller_order.id),
        "logistics_company_id": str(shipment.logistics_company_id) if shipment.logistics_company_id else None,
        "pickup": {
            "location_id": str(pickup.id) if pickup else None,
            "seller_id": str(seller_order.seller_id),
            "seller_name": seller.business_name if seller else None,
            "contact_name": pickup.pickup_contact_name if pickup else None,
            "phone": pickup.pickup_phone if pickup else None,
            "address": pickup.formatted_address if pickup else None,
            "country": pickup.country if pickup else None,
            "region": pickup.region if pickup else None,
            "city": pickup.city if pickup else None,
            "district": pickup.district if pickup else None,
            "ward": pickup.ward if pickup else None,
            "landmark": pickup.landmark if pickup else None,
            "latitude": float(pickup.latitude) if pickup else None,
            "longitude": float(pickup.longitude) if pickup else None,
            "instructions": pickup.pickup_instructions if pickup else None,
        },
        "dropoff": {
            "recipient_name": address.recipient_name if address else None,
            "recipient_phone": address.recipient_phone if address else None,
            "country": address.country if address else None,
            "region": address.region if address else None,
            "city": address.city if address else None,
            "district": address.district if address else None,
            "ward": address.ward if address else None,
            "street": address.street if address else None,
            "landmark": address.landmark if address else None,
            "postal_code": address.postal_code if address else None,
            "latitude": float(address.latitude) if address and address.latitude is not None else None,
            "longitude": float(address.longitude) if address and address.longitude is not None else None,
        },
        "packages": [
            {
                "package_id": str(package.id),
                "label": package.package_label,
                "type": package.package_type,
                "contents_summary": package.contents_summary,
                "weight_kg": str(package.weight_kg) if package.weight_kg is not None else None,
                "length_cm": str(package.length_cm) if package.length_cm is not None else None,
                "width_cm": str(package.width_cm) if package.width_cm is not None else None,
                "height_cm": str(package.height_cm) if package.height_cm is not None else None,
                "package_count": package.package_count,
                "fragile": package.fragile,
                "keep_upright": package.keep_upright,
                "temperature_sensitive": package.temperature_sensitive,
                "handling_instructions": package.handling_instructions,
                "declared_value": _money(package.declared_value) if package.declared_value is not None else None,
                "currency": package.declared_currency,
            }
            for package in packages
        ],
        "seller_subtotal": _money(seller_order.seller_subtotal),
        "currency": order.currency,
    }


def enqueue_ready_for_pickup(db: Session, *, seller_order: SellerOrder, shipment: Shipment) -> LogisticsWebhookEvent | None:
    """Create one durable outbound logistics event for a ready shipment.

    Network delivery is deliberately decoupled from the seller transaction. A later
    dispatcher/integration worker can deliver unprocessed outbound events with retries.
    """
    company_id = shipment.logistics_company_id or seller_order.order.logistics_company_id
    if company_id is None:
        return None

    if shipment.logistics_company_id is None:
        shipment.logistics_company_id = company_id

    existing = (
        db.query(LogisticsWebhookEvent)
        .filter(
            LogisticsWebhookEvent.logistics_company_id == company_id,
            LogisticsWebhookEvent.direction == "outbound",
            LogisticsWebhookEvent.event_type == READY_EVENT,
            LogisticsWebhookEvent.shipment_id == shipment.id,
        )
        .first()
    )
    if existing:
        return existing

    event = LogisticsWebhookEvent(
        logistics_company_id=company_id,
        direction="outbound",
        event_type=READY_EVENT,
        shipment_id=shipment.id,
        request_payload=build_ready_for_pickup_payload(db, seller_order=seller_order, shipment=shipment),
        processed=False,
    )
    db.add(event)
    db.flush()
    return event
