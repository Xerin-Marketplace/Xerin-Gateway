from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.deps import get_current_user, get_db
from api.enums import PermissionCode, ShippingRateType
from api.models import Address, ShippingMethod, ShippingRate, ShippingZone, User
from api.permissions import require_permission
from api.schemas import (
    ShippingMethodCreate, ShippingMethodResponse, ShippingMethodUpdate,
    ShippingQuoteOption, ShippingQuoteRequest, ShippingRateCreate, ShippingRateResponse,
    ShippingZoneCreate, ShippingZoneResponse, ShippingZoneUpdate,
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
