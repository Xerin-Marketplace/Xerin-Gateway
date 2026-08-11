from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_current_user, get_db
from api.enums import PermissionCode, ShippingRateType
from api.models import Address, Order, Shipment, ShipmentStatus, ShipmentTrackingEvent, ShippingMethod, ShippingRate, ShippingZone, User
from api.permissions import require_permission
from api.schemas import (
    ShippingMethodCreate, ShippingMethodResponse, ShippingMethodUpdate,
    ShippingQuoteOption, ShippingQuoteRequest, ShippingRateCreate, ShippingRateResponse,
    ShippingZoneCreate, ShippingZoneResponse, ShippingZoneUpdate,
    ShipmentResponse, ShipmentTrackingEventCreate,
    PerSellerQuoteRequest, PerSellerQuoteResponse,
)

router = APIRouter(prefix="/shipping", tags=["Shipping"])

def _commit(db: Session):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Shipping record conflicts with existing data") from exc

@router.post("/zones", response_model=ShippingZoneResponse, status_code=status.HTTP_201_CREATED)
def create_zone(data: ShippingZoneCreate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.shipping_write.value))):
    zone = ShippingZone(**data.model_dump())
    db.add(zone); _commit(db); db.refresh(zone); return zone

@router.get("/zones", response_model=list[ShippingZoneResponse])
def list_zones(active_only: bool = True, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    q=db.query(ShippingZone)
    if active_only: q=q.filter(ShippingZone.is_active.is_(True))
    return q.order_by(ShippingZone.name).all()

@router.patch("/zones/{zone_id}", response_model=ShippingZoneResponse)
def update_zone(zone_id: UUID, data: ShippingZoneUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.shipping_write.value))):
    zone=db.get(ShippingZone, zone_id)
    if not zone: raise HTTPException(404, "Shipping zone not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(zone,k,v)
    _commit(db); db.refresh(zone); return zone

@router.post("/methods", response_model=ShippingMethodResponse, status_code=status.HTTP_201_CREATED)
def create_method(data: ShippingMethodCreate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.shipping_write.value))):
    method=ShippingMethod(**data.model_dump()); db.add(method); _commit(db); db.refresh(method); return method

@router.get("/methods", response_model=list[ShippingMethodResponse])
def list_methods(active_only: bool=True, db: Session=Depends(get_db), _: User=Depends(get_current_user)):
    q=db.query(ShippingMethod)
    if active_only: q=q.filter(ShippingMethod.is_active.is_(True))
    return q.order_by(ShippingMethod.name).all()

@router.post("/rates", response_model=ShippingRateResponse, status_code=status.HTTP_201_CREATED)
def create_rate(data: ShippingRateCreate, db: Session=Depends(get_db), _: User=Depends(require_permission(PermissionCode.shipping_write.value))):
    if not db.get(ShippingZone, data.zone_id): raise HTTPException(404, "Shipping zone not found")
    if not db.get(ShippingMethod, data.method_id): raise HTTPException(404, "Shipping method not found")
    rate=ShippingRate(**data.model_dump()); db.add(rate); _commit(db)
    return db.query(ShippingRate).options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method)).filter(ShippingRate.id==rate.id).one()

@router.get("/rates", response_model=list[ShippingRateResponse])
def list_rates(db: Session=Depends(get_db), _: User=Depends(require_permission(PermissionCode.shipping_read.value))):
    return db.query(ShippingRate).options(joinedload(ShippingRate.zone), joinedload(ShippingRate.method)).order_by(ShippingRate.created_at.desc()).all()

@router.post("/quote", response_model=list[ShippingQuoteOption])
def quote_shipping(data: ShippingQuoteRequest, db: Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    address=db.query(Address).filter(Address.id==data.address_id, Address.user_id==current_user.id).first()
    if not address: raise HTTPException(404, "Address not found")
    zones=db.query(ShippingZone).filter(ShippingZone.is_active.is_(True), ShippingZone.country.ilike(address.country)).all()
    matching=[]
    for zone in zones:
        regions={str(x).strip().lower() for x in (zone.regions or [])}
        cities={str(x).strip().lower() for x in (zone.cities or [])}
        if regions and address.region.strip().lower() not in regions: continue
        if cities and address.city.strip().lower() not in cities: continue
        matching.append(zone.id)
    if not matching: return []
    rates=(db.query(ShippingRate).options(joinedload(ShippingRate.method)).filter(ShippingRate.zone_id.in_(matching), ShippingRate.is_active.is_(True)).all())
    options=[]
    for rate in rates:
        if not rate.method or not rate.method.is_active: continue
        if rate.min_weight_kg is not None and data.weight_kg < rate.min_weight_kg: continue
        if rate.max_weight_kg is not None and data.weight_kg > rate.max_weight_kg: continue
        if rate.free_shipping_threshold is not None and data.subtotal >= rate.free_shipping_threshold:
            amount=Decimal("0.00")
        elif rate.rate_type == ShippingRateType.free:
            amount=Decimal("0.00")
        elif rate.rate_type == ShippingRateType.weight_based:
            amount=Decimal(rate.base_amount) + Decimal(rate.amount_per_kg) * data.weight_kg
        else:
            amount=Decimal(rate.base_amount)
        options.append(ShippingQuoteOption(rate_id=rate.id, method_id=rate.method.id, method_name=rate.method.name, carrier_name=rate.method.carrier_name, amount=amount.quantize(Decimal("0.01")), min_delivery_days=rate.method.min_delivery_days, max_delivery_days=rate.method.max_delivery_days))
    return sorted(options, key=lambda x: x.amount)


@router.post("/quote-per-seller", response_model=list[PerSellerQuoteResponse])
def quote_per_seller(
    data: PerSellerQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Calculate shipping per seller group based on seller origin → customer destination."""
    address = db.query(Address).filter(
        Address.id == data.address_id,
        Address.user_id == current_user.id,
    ).first()
    if not address:
        raise HTTPException(404, "Address not found")

    # Group items by seller
    seller_groups: dict[UUID, list] = {}
    for item in data.items:
        seller_groups.setdefault(item.seller_id, []).append(item)

    # Get all active shipping zones for the customer's country
    zones = db.query(ShippingZone).filter(
        ShippingZone.is_active.is_(True),
        ShippingZone.country.ilike(address.country),
    ).all()

    results: list[PerSellerQuoteResponse] = []

    for seller_id, items in seller_groups.items():
        seller_subtotal = sum((Decimal(item.unit_price) * item.quantity for item in items), Decimal("0.00"))

        # Match zones: customer destination region must be in zone
        matching_zone_ids = []
        for zone in zones:
            regions = {str(x).strip().lower() for x in (zone.regions or [])}
            cities = {str(x).strip().lower() for x in (zone.cities or [])}
            if regions and address.region.strip().lower() not in regions:
                continue
            if cities and address.city.strip().lower() not in cities:
                continue
            matching_zone_ids.append(zone.id)

        if not matching_zone_ids:
            # No matching zone — use a default flat rate
            results.append(PerSellerQuoteResponse(
                seller_id=seller_id,
                seller_subtotal=seller_subtotal,
                shipping_amount=Decimal("5000.00"),
                total=seller_subtotal + Decimal("5000.00"),
                method_name="Standard Delivery",
                carrier_name="Xerin Express",
                min_delivery_days=2,
                max_delivery_days=7,
            ))
            continue

        # Get the cheapest active rate for the matching zones
        rates = db.query(ShippingRate).options(
            joinedload(ShippingRate.method),
        ).filter(
            ShippingRate.zone_id.in_(matching_zone_ids),
            ShippingRate.is_active.is_(True),
        ).all()

        best = None
        for rate in rates:
            if not rate.method or not rate.method.is_active:
                continue
            if rate.free_shipping_threshold is not None and seller_subtotal >= rate.free_shipping_threshold:
                amount = Decimal("0.00")
            elif rate.rate_type == ShippingRateType.free:
                amount = Decimal("0.00")
            else:
                amount = Decimal(rate.base_amount)
            if best is None or amount < best[0]:
                best = (amount, rate)

        if best:
            amount, rate = best
            results.append(PerSellerQuoteResponse(
                seller_id=seller_id,
                seller_subtotal=seller_subtotal,
                shipping_amount=amount.quantize(Decimal("0.01")),
                total=(seller_subtotal + amount).quantize(Decimal("0.01")),
                method_name=rate.method.name,
                carrier_name=rate.method.carrier_name,
                min_delivery_days=rate.method.min_delivery_days,
                max_delivery_days=rate.method.max_delivery_days,
            ))
        else:
            results.append(PerSellerQuoteResponse(
                seller_id=seller_id,
                seller_subtotal=seller_subtotal,
                shipping_amount=Decimal("5000.00"),
                total=seller_subtotal + Decimal("5000.00"),
                method_name="Standard Delivery",
                carrier_name="Xerin Express",
                min_delivery_days=2,
                max_delivery_days=7,
            ))

    return results


ALLOWED_SHIPMENT_TRANSITIONS = {
    ShipmentStatus.pending: {ShipmentStatus.ready_for_dispatch, ShipmentStatus.cancelled},
    ShipmentStatus.ready_for_dispatch: {ShipmentStatus.dispatched, ShipmentStatus.cancelled},
    ShipmentStatus.dispatched: {ShipmentStatus.in_transit, ShipmentStatus.delivery_failed},
    ShipmentStatus.in_transit: {ShipmentStatus.out_for_delivery, ShipmentStatus.delivery_failed, ShipmentStatus.returned_to_sender},
    ShipmentStatus.out_for_delivery: {ShipmentStatus.delivered, ShipmentStatus.delivery_failed, ShipmentStatus.returned_to_sender},
    ShipmentStatus.delivery_failed: {ShipmentStatus.out_for_delivery, ShipmentStatus.returned_to_sender},
    ShipmentStatus.delivered: set(),
    ShipmentStatus.returned_to_sender: set(),
    ShipmentStatus.cancelled: set(),
}


def _can_manage_shipment(db: Session, user: User, shipment: Shipment) -> bool:
    from api.permissions import get_user_permissions, get_user_role_names
    roles = get_user_role_names(user)
    permissions = get_user_permissions(db, user)
    if "super_admin" in roles or PermissionCode.shipping_manage_all.value in permissions:
        return True
    return bool(user.seller_profile and user.seller_profile.id == shipment.seller_id and PermissionCode.shipping_manage_own.value in permissions)


def _can_view_shipment(db: Session, user: User, shipment: Shipment) -> bool:
    return shipment.order.user_id == user.id or _can_manage_shipment(db, user, shipment) or PermissionCode.shipping_read.value in __import__('api.permissions', fromlist=['get_user_permissions']).get_user_permissions(db, user)


@router.get("/shipments/my", response_model=list[ShipmentResponse])
def my_shipments(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events)).join(Order).filter(Order.user_id == current_user.id).order_by(Shipment.created_at.desc()).all()


@router.get("/shipments/seller", response_model=list[ShipmentResponse])
def seller_shipments(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.shipping_manage_own.value))):
    if not current_user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    return db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events)).filter(Shipment.seller_id == current_user.seller_profile.id).order_by(Shipment.created_at.desc()).all()


@router.get("/shipments/{shipment_id}", response_model=ShipmentResponse)
def get_shipment(shipment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    shipment = db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events), joinedload(Shipment.order)).filter(Shipment.id == shipment_id).first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not _can_view_shipment(db, current_user, shipment):
        raise HTTPException(status_code=403, detail="Not authorized to view this shipment")
    return shipment


@router.post("/shipments/{shipment_id}/events", response_model=ShipmentResponse)
def update_shipment(shipment_id: UUID, data: ShipmentTrackingEventCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    shipment = db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events), joinedload(Shipment.order)).filter(Shipment.id == shipment_id).with_for_update().first()
    if not shipment:
        raise HTTPException(status_code=404, detail="Shipment not found")
    if not _can_manage_shipment(db, current_user, shipment):
        raise HTTPException(status_code=403, detail="Not authorized to manage this shipment")
    if data.status not in ALLOWED_SHIPMENT_TRANSITIONS.get(shipment.status, set()):
        raise HTTPException(status_code=409, detail=f"Invalid shipment transition: {shipment.status.value} -> {data.status.value}")
    if data.tracking_number:
        duplicate = db.query(Shipment.id).filter(Shipment.tracking_number == data.tracking_number, Shipment.id != shipment.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Tracking number is already in use")
        shipment.tracking_number = data.tracking_number.strip()
    if data.carrier_name:
        shipment.carrier_name = data.carrier_name.strip()
    shipment.status = data.status
    now = datetime.now(timezone.utc)
    if data.status == ShipmentStatus.dispatched and shipment.dispatched_at is None:
        shipment.dispatched_at = now
    if data.status == ShipmentStatus.delivered:
        shipment.delivered_at = now
    db.add(ShipmentTrackingEvent(shipment_id=shipment.id, status=data.status, location=data.location, notes=data.notes, created_by_id=current_user.id))
    _commit(db)
    return db.query(Shipment).options(selectinload(Shipment.items), selectinload(Shipment.tracking_events)).filter(Shipment.id == shipment.id).one()
