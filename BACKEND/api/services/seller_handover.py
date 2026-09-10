from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from api.models import (
    SellerOrder,
    SellerOrderPackage,
    SellerPickupLocation,
    Shipment,
    ShipmentHandover,
)


def _num(value):
    if value is None:
        return None
    return float(value) if isinstance(value, Decimal) else value


def build_pickup_snapshot(db: Session, *, seller_order: SellerOrder) -> dict:
    pickup = (
        db.query(SellerPickupLocation)
        .filter(
            SellerPickupLocation.seller_id == seller_order.seller_id,
            SellerPickupLocation.is_active.is_(True),
            SellerPickupLocation.is_default.is_(True),
        )
        .first()
    )
    if pickup is None:
        return {}

    return {
        "pickup_location_id": str(pickup.id),
        "label": pickup.label,
        "formatted_address": pickup.formatted_address,
        "country": pickup.country,
        "region": pickup.region,
        "city": pickup.city,
        "district": pickup.district,
        "ward": pickup.ward,
        "street": pickup.street,
        "landmark": pickup.landmark,
        "latitude": _num(pickup.latitude),
        "longitude": _num(pickup.longitude),
        "pickup_contact_name": pickup.pickup_contact_name,
        "pickup_phone": pickup.pickup_phone,
        "pickup_instructions": pickup.pickup_instructions,
    }


def build_package_snapshot(db: Session, *, seller_order: SellerOrder) -> list[dict]:
    packages = (
        db.query(SellerOrderPackage)
        .filter(SellerOrderPackage.seller_order_id == seller_order.id)
        .order_by(SellerOrderPackage.created_at.asc())
        .all()
    )
    return [
        {
            "package_id": str(package.id),
            "package_label": package.package_label,
            "package_type": package.package_type,
            "contents_summary": package.contents_summary,
            "weight_kg": _num(package.weight_kg),
            "length_cm": _num(package.length_cm),
            "width_cm": _num(package.width_cm),
            "height_cm": _num(package.height_cm),
            "package_count": package.package_count,
            "fragile": package.fragile,
            "keep_upright": package.keep_upright,
            "temperature_sensitive": package.temperature_sensitive,
            "handling_instructions": package.handling_instructions,
            "declared_value": _num(package.declared_value),
            "declared_currency": package.declared_currency,
            "is_ready": package.is_ready,
            "sealed_at": package.sealed_at.isoformat() if package.sealed_at else None,
        }
        for package in packages
    ]


def ensure_shipment_handover(
    db: Session,
    *,
    seller_order: SellerOrder,
    shipment: Shipment,
) -> ShipmentHandover:
    existing = (
        db.query(ShipmentHandover)
        .filter(ShipmentHandover.shipment_id == shipment.id)
        .first()
    )
    if existing:
        return existing

    handover = ShipmentHandover(
        shipment_id=shipment.id,
        seller_order_id=seller_order.id,
        seller_id=seller_order.seller_id,
        logistics_company_id=shipment.logistics_company_id,
        status="awaiting_courier",
        pickup_snapshot=build_pickup_snapshot(db, seller_order=seller_order),
        package_snapshot=build_package_snapshot(db, seller_order=seller_order),
    )
    db.add(handover)
    db.flush()
    return handover
