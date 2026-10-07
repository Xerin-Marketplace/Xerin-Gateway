import math
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_current_user, get_db
from api.enums import PermissionCode, ShippingRateType
from api.models import Address, Cart, CartItem, Order, Seller, Shipment, ShipmentStatus, ShipmentTrackingEvent, ShippingMethod, ShippingRate, ShippingZone, Store, SystemSetting, User
from api.config import settings
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

@router.get("/checkout-config")
def checkout_config(db: Session = Depends(get_db)):
    """Public checkout capability flags — derived from real shipping setup."""
    ensure_default_shipping(db)
    zones = db.query(ShippingZone).filter(ShippingZone.is_active.is_(True)).all()
    methods = db.query(ShippingMethod).filter(ShippingMethod.is_active.is_(True)).all()
    rates = db.query(ShippingRate).filter(ShippingRate.is_active.is_(True)).count()

    countries = {z.country.lower() for z in zones if z.country}
    local_country = (settings.DEFAULT_COUNTRY or "Tanzania").lower()
    local_allowed = local_country in countries or not zones

    cod_setting = db.query(SystemSetting).filter(
        SystemSetting.key == "cod_allowed"
    ).first()
    cod_allowed = bool(
        cod_setting and str(cod_setting.value).lower() in ("true", "1", "yes")
    )

    return {
        "default_country": settings.DEFAULT_COUNTRY or "Tanzania",
        "local_delivery_allowed": local_allowed,
        "international_delivery_allowed": bool(countries - {local_country}),
        "cod_allowed": cod_allowed,
        "configured": bool(zones and methods and rates),
    }


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


# ---------------------------------------------------------------------------
# Checkout delivery engine — detect mode, eligible carriers, express tiers,
# multi-seller pricing and frozen quotes. Built on ShippingZone/ShippingMethod/
# ShippingRate; Xerin Logistics is presented as the single carrier covering
# domestic routes (partners are assigned automatically at dispatch time).
# ---------------------------------------------------------------------------

XERIN_LOGISTICS_ID = UUID("00000000-0000-4000-8000-000000000001")
XERIN_LOGISTICS_NAME = "Xerin Express"
XERIN_LOGISTICS_CODE = "XERIN"
QUOTE_EXPIRY_MINUTES = 30


def _norm_place(value: str | None) -> str:
    return (value or "").strip().lower()


_COUNTRY_ALIASES = {
    "tz": "tanzania",
    "tanzania": "tanzania",
    "united republic of tanzania": "tanzania",
    "tanzania, united republic of": "tanzania",
    "the united republic of tanzania": "tanzania",
    "ke": "kenya",
    "kenya": "kenya",
    "ug": "uganda",
    "uganda": "uganda",
    "rw": "rwanda",
    "rwanda": "rwanda",
    "cn": "china",
    "china": "china",
}


def _norm_country(value: str | None) -> str:
    """Canonical country comparison — tolerates ISO codes and the common
    'Tanzania, United Republic of' spelling variants map providers return."""
    raw = _norm_place(value)
    return _COUNTRY_ALIASES.get(raw, raw)


def _default_country_norm() -> str:
    return _norm_country(settings.DEFAULT_COUNTRY or "Tanzania")


def ensure_default_shipping(db: Session) -> None:
    """Guarantee a nationwide Xerin Express fallback exists: an active zone
    covering the whole default country plus Standard/Express methods + flat
    rates. Runs on every quote request and only fills in what is missing, so
    admin-created regional zones never block addresses they don't cover."""
    zones = db.query(ShippingZone).filter(ShippingZone.is_active.is_(True)).all()
    nationwide = next(
        (
            z
            for z in zones
            if _norm_country(z.country) == _default_country_norm()
            and not z.regions
            and not z.cities
        ),
        None,
    )
    if nationwide is None:
        nationwide = ShippingZone(
            name="Tanzania — Nationwide",
            country=settings.DEFAULT_COUNTRY or "Tanzania",
            regions=[],
            cities=[],
            is_active=True,
        )
        db.add(nationwide)
        db.flush()

    methods = {
        _norm_place(m.name): m
        for m in db.query(ShippingMethod).filter(
            ShippingMethod.carrier_name == XERIN_LOGISTICS_NAME,
            ShippingMethod.is_active.is_(True),
        )
    }
    standard = methods.get("standard")
    if standard is None:
        standard = ShippingMethod(
            name="Standard",
            description="Xerin Express standard delivery",
            carrier_name=XERIN_LOGISTICS_NAME,
            min_delivery_days=1,
            max_delivery_days=3,
        )
        db.add(standard)
    express = methods.get("express")
    if express is None:
        express = ShippingMethod(
            name="Express",
            description="Xerin Express same-day delivery",
            carrier_name=XERIN_LOGISTICS_NAME,
            min_delivery_days=0,
            max_delivery_days=1,
        )
        db.add(express)
    db.flush()

    def _ensure_rate(method: ShippingMethod, amount: Decimal) -> None:
        exists = db.query(ShippingRate.id).filter(
            ShippingRate.zone_id == nationwide.id,
            ShippingRate.method_id == method.id,
            ShippingRate.is_active.is_(True),
        ).first()
        if not exists:
            db.add(ShippingRate(
                zone_id=nationwide.id,
                method_id=method.id,
                rate_type=ShippingRateType.flat,
                base_amount=amount,
            ))

    _ensure_rate(standard, Decimal("5000"))
    _ensure_rate(express, Decimal("10000"))
    db.commit()


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return radius_km * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _route_distance_km(store: Store | None, address: Address) -> Decimal:
    """Real haversine distance when both ends have coordinates; sensible
    geography fallbacks otherwise."""
    if (
        store is not None
        and store.latitude is not None
        and store.longitude is not None
        and address.latitude is not None
        and address.longitude is not None
    ):
        return Decimal(str(round(_haversine_km(store.latitude, store.longitude, address.latitude, address.longitude), 2)))
    if store is not None and _norm_place(store.region) and _norm_place(store.region) == _norm_place(address.region):
        return Decimal("25")
    if store is not None and _norm_country(store.country) == _norm_country(address.country):
        return Decimal("120")
    return Decimal("0")


def _route_type(store: Store | None, address: Address) -> str:
    origin = _norm_country(store.country if store else None) or _default_country_norm()
    dest = _norm_country(address.country) or _default_country_norm()
    return "domestic" if origin == dest else "cross_border"


def _checkout_context(db: Session, user: User, address_id: UUID):
    """Load the customer's address + active cart and map cart sellers to their
    store origins. Returns (address, cart, {seller_id: store}, cart_subtotal)."""
    address = db.query(Address).filter(
        Address.id == address_id,
        Address.user_id == user.id,
    ).first()
    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    cart = db.query(Cart).options(
        selectinload(Cart.items).selectinload(CartItem.product)
    ).filter(Cart.user_id == user.id).first()
    if not cart or not cart.items:
        raise HTTPException(status_code=422, detail="Your cart is empty")

    seller_ids = {item.product.seller_id for item in cart.items if item.product}
    stores = {
        store.seller_id: store
        for store in db.query(Store).filter(Store.seller_id.in_(seller_ids)).all()
    } if seller_ids else {}
    sellers = {
        seller.id: seller
        for seller in db.query(Seller).filter(Seller.id.in_(seller_ids)).all()
    } if seller_ids else {}
    subtotal = sum((Decimal(item.unit_price) * item.quantity for item in cart.items), Decimal("0"))
    return address, cart, sellers, stores, subtotal


def _route_snapshots(sellers: dict, stores: dict, address: Address, billable_seller_id: UUID | None = None) -> list[dict]:
    snapshots = []
    for seller_id, seller in sellers.items():
        store = stores.get(seller_id)
        distance = _route_distance_km(store, address)
        snapshots.append({
            "seller_id": str(seller_id),
            "seller_name": seller.business_name if seller else "Xerin Store",
            "store_id": str(store.id) if store else None,
            "store_name": store.store_name if store else None,
            "origin_country": store.country if store and store.country else (settings.DEFAULT_COUNTRY or "Tanzania"),
            "route_type": _route_type(store, address),
            "pickup_location_id": str(store.id) if store else str(seller_id),
            "pickup_label": (
                ", ".join(filter(None, [store.street, store.district, store.region])) if store
                else "Seller origin"
            ) or "Seller origin",
            "distance_km": distance,
            "duration_minutes": Decimal(str(round(float(distance) / 40 * 60, 0))),
            "is_billable_reference": seller_id == billable_seller_id,
        })
    return snapshots


def _zone_serves_address(zone: ShippingZone, address: Address) -> bool:
    # A blank address country means "same as the marketplace default".
    zone_country = _norm_country(zone.country)
    address_country = _norm_country(address.country) or _default_country_norm()
    if zone_country != address_country:
        return False
    regions = {_norm_place(x) for x in (zone.regions or [])}
    cities = {_norm_place(x) for x in (zone.cities or [])}
    if regions and _norm_place(address.region) not in regions:
        return False
    if cities and _norm_place(address.city) not in cities:
        return False
    return True


def _serving_rates(db: Session, address: Address) -> list[ShippingRate]:
    ensure_default_shipping(db)
    zones = db.query(ShippingZone).filter(ShippingZone.is_active.is_(True)).all()
    zone_ids = [zone.id for zone in zones if _zone_serves_address(zone, address)]
    if not zone_ids:
        return []
    return db.query(ShippingRate).options(
        joinedload(ShippingRate.method), joinedload(ShippingRate.zone),
    ).filter(
        ShippingRate.zone_id.in_(zone_ids),
        ShippingRate.is_active.is_(True),
    ).all()


def _rate_amount(rate: ShippingRate, subtotal: Decimal, weight_kg: Decimal = Decimal("0")) -> Decimal | None:
    """Same pricing rules as order creation (_calculate_shipping). Returns None
    when the rate cannot serve this cart."""
    if not rate.method or not rate.method.is_active or not rate.zone or not rate.zone.is_active:
        return None
    if rate.min_weight_kg is not None and weight_kg < Decimal(rate.min_weight_kg):
        return None
    if rate.max_weight_kg is not None and weight_kg > Decimal(rate.max_weight_kg):
        return None
    if rate.free_shipping_threshold is not None and subtotal >= Decimal(rate.free_shipping_threshold):
        return Decimal("0.00")
    if rate.rate_type == ShippingRateType.free:
        return Decimal("0.00")
    if rate.rate_type == ShippingRateType.weight_based:
        return (Decimal(rate.base_amount) + Decimal(rate.amount_per_kg) * weight_kg).quantize(Decimal("0.01"))
    return Decimal(rate.base_amount).quantize(Decimal("0.01"))


def _farthest_seller_id(snapshots: list[dict]) -> str | None:
    if not snapshots:
        return None
    farthest = max(snapshots, key=lambda s: Decimal(str(s["distance_km"])))
    return farthest["seller_id"]


class DetectDeliveryModeRequest(BaseModel):
    address_id: UUID


class EligibleLogisticsRequest(BaseModel):
    address_id: UUID
    delivery_mode: str = Field(pattern="^(local|international)$")


class XerinExpressOptionsRequest(BaseModel):
    address_id: UUID
    delivery_mode: str = Field(pattern="^(local|international)$")


class MultiSellerPricingRequest(BaseModel):
    address_id: UUID
    logistics_company_id: UUID
    delivery_mode: str = Field(pattern="^(local|international)$")
    method_id: UUID | None = None


class CheckoutDeliveryQuoteRequest(BaseModel):
    address_id: UUID
    logistics_company_id: UUID
    rate_id: UUID
    delivery_mode: str = Field(pattern="^(local|international)$")


@router.post("/detect-delivery-mode")
def detect_delivery_mode(
    data: DetectDeliveryModeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Domestic vs cross-border detection per cart seller origin."""
    address, _cart, sellers, stores, _subtotal = _checkout_context(db, current_user, data.address_id)

    origins = []
    for seller_id in sellers:
        store = stores.get(seller_id)
        origins.append({
            "store_id": str(store.id) if store else "",
            "store_name": store.store_name if store else (sellers[seller_id].business_name if sellers.get(seller_id) else "Xerin Store"),
            "origin_country": store.country if store and store.country else (settings.DEFAULT_COUNTRY or "Tanzania"),
            "destination_country": address.country,
            "route_type": _route_type(store, address),
        })

    route_types = sorted({o["route_type"] for o in origins}) or ["domestic"]
    delivery_mode = "international" if "cross_border" in route_types else "local"

    ensure_default_shipping(db)
    zones = db.query(ShippingZone).filter(ShippingZone.is_active.is_(True)).all()
    countries = {z.country.lower() for z in zones if z.country}
    local_country = (settings.DEFAULT_COUNTRY or "Tanzania").lower()

    return {
        "address_id": str(address.id),
        "destination_country": address.country,
        "delivery_mode": delivery_mode,
        "route_types": route_types,
        "international_delivery_allowed": bool(countries - {local_country}),
        "origins": origins,
    }


@router.post("/eligible-logistics")
def eligible_logistics(
    data: EligibleLogisticsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Carriers whose active services can price this cart + address."""
    address, _cart, sellers, stores, _subtotal = _checkout_context(db, current_user, data.address_id)
    seller_count = len(sellers)
    rates = _serving_rates(db, address)

    services: dict[UUID, dict] = {}
    for rate in rates:
        method = rate.method
        if not method or not method.is_active:
            continue
        services.setdefault(method.id, {
            "method_id": str(method.id),
            "method_name": method.name,
            "service_code": method.carrier_name,
            "min_delivery_days": method.min_delivery_days,
            "max_delivery_days": method.max_delivery_days,
            "supports_cod": True,
            "supports_tracking": True,
        })

    cod_setting = db.query(SystemSetting).filter(SystemSetting.key == "cod_allowed").first()
    cod_allowed = bool(cod_setting and str(cod_setting.value).lower() in ("true", "1", "yes"))

    results, excluded = [], []
    if services:
        results.append({
            "logistics_company_id": str(XERIN_LOGISTICS_ID),
            "name": XERIN_LOGISTICS_NAME,
            "code": XERIN_LOGISTICS_CODE,
            "scope": data.delivery_mode,
            "supports_cod": cod_allowed,
            "supports_tracking": True,
            "supports_webhooks": True,
            "seller_count": seller_count,
            "covered_seller_count": seller_count,
            "route_types": sorted({_route_type(stores.get(sid), address) for sid in sellers}),
            "services": list(services.values()),
        })
    else:
        excluded.append({
            "logistics_company_id": str(XERIN_LOGISTICS_ID),
            "name": XERIN_LOGISTICS_NAME,
            "code": XERIN_LOGISTICS_CODE,
            "reason_codes": ["no_zone_coverage"],
            "reasons": ["No active shipping zone serves this address yet."],
            "uncovered_sellers": [
                sellers[sid].business_name if sellers.get(sid) else str(sid) for sid in sellers
            ],
        })

    return {
        "address_id": str(address.id),
        "delivery_mode": data.delivery_mode,
        "destination_country": address.country,
        "seller_count": seller_count,
        "total": len(results),
        "page": 1,
        "page_size": 100,
        "total_pages": 1,
        "results": results,
        "excluded_companies": excluded,
    }


@router.post("/xerin-express-options")
def xerin_express_options(
    data: XerinExpressOptionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Standard / Express delivery tiers for domestic checkout routes."""
    address, _cart, _sellers, _stores, subtotal = _checkout_context(db, current_user, data.address_id)
    if data.delivery_mode != "local":
        return []

    priced = []
    for rate in _serving_rates(db, address):
        amount = _rate_amount(rate, subtotal)
        if amount is None:
            continue
        priced.append((amount, rate))
    if not priced:
        return []

    priced.sort(key=lambda item: (item[0], item[1].method.max_delivery_days))
    standard_amount, standard_rate = priced[0]
    express_amount, express_rate = min(priced, key=lambda item: (item[1].method.max_delivery_days, item[0]))

    cod_setting = db.query(SystemSetting).filter(SystemSetting.key == "cod_allowed").first()
    cod_allowed = bool(cod_setting and str(cod_setting.value).lower() in ("true", "1", "yes"))

    def _option(tier: str, label: str, rate: ShippingRate, amount: Decimal) -> dict:
        return {
            "tier": tier,
            "label": label,
            "delivery_amount": amount,
            "currency": "TZS",
            "promised_delivery_minutes": (60 if tier == "express" else rate.method.min_delivery_days * 24 * 60),
            "logistics_company_id": str(XERIN_LOGISTICS_ID),
            "logistics_company_name": XERIN_LOGISTICS_NAME,
            "rate_id": str(rate.id),
            "method_id": str(rate.method.id),
            "supports_cod": cod_allowed,
            "supports_tracking": True,
        }

    options = [_option("standard", "Standard", standard_rate, standard_amount)]
    if express_rate.id != standard_rate.id:
        options.append(_option("express", "Express", express_rate, express_amount))
    return options


@router.post("/multi-seller-pricing")
def multi_seller_pricing(
    data: MultiSellerPricingRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Delivery price options covering every seller in the cart — one delivery
    fee billed against the farthest store route."""
    address, _cart, sellers, stores, subtotal = _checkout_context(db, current_user, data.address_id)
    if data.logistics_company_id != XERIN_LOGISTICS_ID:
        raise HTTPException(status_code=404, detail="Logistics company not found")

    snapshots = _route_snapshots(sellers, stores, address)
    billable_seller_id = _farthest_seller_id(snapshots)
    for snapshot in snapshots:
        snapshot["is_billable_reference"] = snapshot["seller_id"] == billable_seller_id
    billable_distance = max((Decimal(str(s["distance_km"])) for s in snapshots), default=Decimal("0"))

    options = []
    for rate in _serving_rates(db, address):
        if data.method_id and rate.method_id != data.method_id:
            continue
        amount = _rate_amount(rate, subtotal)
        if amount is None:
            continue
        options.append({
            "rate_id": str(rate.id),
            "method_id": str(rate.method.id),
            "method_name": rate.method.name,
            "service_code": rate.method.carrier_name,
            "logistics_company_id": str(XERIN_LOGISTICS_ID),
            "logistics_company_name": XERIN_LOGISTICS_NAME,
            "strategy": "farthest_seller",
            "rate_type": rate.rate_type.value,
            "currency": "TZS",
            "seller_count": len(sellers),
            "billable_distance_km": billable_distance,
            "billable_seller_id": billable_seller_id,
            "delivery_amount": amount,
            "min_delivery_days": rate.method.min_delivery_days,
            "max_delivery_days": rate.method.max_delivery_days,
            "supports_cod": True,
            "supports_tracking": True,
            "pricing_breakdown": {
                "base_amount": str(rate.base_amount),
                "amount_per_kg": str(rate.amount_per_kg),
                "rate_type": rate.rate_type.value,
                "free_shipping_threshold": str(rate.free_shipping_threshold) if rate.free_shipping_threshold is not None else None,
                "subtotal": str(subtotal),
            },
            "sellers": snapshots,
        })

    options.sort(key=lambda option: Decimal(str(option["delivery_amount"])))
    return {
        "address_id": str(address.id),
        "logistics_company_id": str(XERIN_LOGISTICS_ID),
        "logistics_company_name": XERIN_LOGISTICS_NAME,
        "delivery_mode": data.delivery_mode,
        "strategy": "farthest_seller",
        "seller_count": len(sellers),
        "options": options,
        "note": "One delivery fee covers all sellers — billed against the farthest store route.",
    }


@router.post("/checkout-delivery-quote")
def checkout_delivery_quote(
    data: CheckoutDeliveryQuoteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Locks a delivery price for the current cart + address. The order
    endpoint independently re-validates the same rate at submit time."""
    if data.logistics_company_id != XERIN_LOGISTICS_ID:
        raise HTTPException(status_code=404, detail="Logistics company not found")

    address, cart, sellers, stores, subtotal = _checkout_context(db, current_user, data.address_id)
    rate = db.query(ShippingRate).options(
        joinedload(ShippingRate.method), joinedload(ShippingRate.zone),
    ).filter(ShippingRate.id == data.rate_id, ShippingRate.is_active.is_(True)).first()
    if not rate or not rate.method or not rate.zone:
        raise HTTPException(status_code=409, detail="Selected shipping rate is unavailable")
    if not _zone_serves_address(rate.zone, address):
        raise HTTPException(status_code=422, detail="Shipping rate does not serve this address")

    amount = _rate_amount(rate, subtotal)
    if amount is None:
        raise HTTPException(status_code=422, detail="Shipping rate cannot price this cart")

    snapshots = _route_snapshots(sellers, stores, address)
    billable_seller_id = _farthest_seller_id(snapshots)
    for snapshot in snapshots:
        snapshot["is_billable_reference"] = snapshot["seller_id"] == billable_seller_id
    billable_distance = max((Decimal(str(s["distance_km"])) for s in snapshots), default=Decimal("0"))

    return {
        "id": str(uuid.uuid4()),
        "shipping_address_id": str(address.id),
        "logistics_company_id": str(XERIN_LOGISTICS_ID),
        "shipping_method_id": str(rate.method_id),
        "shipping_rate_id": str(rate.id),
        "delivery_mode": data.delivery_mode,
        "pricing_strategy": "farthest_seller",
        "rate_type": rate.rate_type.value,
        "currency": "TZS",
        "seller_count": len(sellers),
        "billable_distance_km": billable_distance,
        "product_subtotal": subtotal,
        "delivery_amount": amount,
        "checkout_total_before_discounts": subtotal + amount,
        "pricing_breakdown": {
            "route_types": sorted({_route_type(stores.get(sid), address) for sid in sellers}),
            "store_count": len(stores),
            "base_amount": str(rate.base_amount),
        },
        "seller_routes_snapshot": snapshots,
        "address_snapshot": {
            "country": address.country,
            "region": address.region,
            "city": address.city,
            "street": address.street,
            "latitude": address.latitude,
            "longitude": address.longitude,
        },
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=QUOTE_EXPIRY_MINUTES)).isoformat(),
    }
