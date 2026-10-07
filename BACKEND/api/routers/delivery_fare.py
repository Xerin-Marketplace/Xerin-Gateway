from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import DeliveryFare, DeliveryZone, SurgePricing, User
from api.permissions import require_permission
from api.schemas import (
    DeliveryFareCreate,
    DeliveryFareResponse,
    DeliveryFareUpdate,
    DeliveryZoneCreate,
    DeliveryZoneResponse,
    DeliveryZoneUpdate,
    FareCalculationRequest,
    FareCalculationResponse,
    SurgePricingCreate,
    SurgePricingResponse,
    SurgePricingUpdate,
)
from api.services.delivery_fare_service import calculate_fare

router = APIRouter(tags=["Delivery Fare Management"])


# =========================================================
# DELIVERY ZONES
# =========================================================

@router.get("/delivery-zones", response_model=list[DeliveryZoneResponse])
def list_zones(
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.delivery_zone_read.value)),
):
    q = db.query(DeliveryZone)
    if is_active is not None:
        q = q.filter(DeliveryZone.is_active == is_active)
    return q.order_by(DeliveryZone.name).all()


@router.post("/delivery-zones", response_model=DeliveryZoneResponse, status_code=status.HTTP_201_CREATED)
def create_zone(
    data: DeliveryZoneCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.delivery_zone_manage.value)),
):
    zone = DeliveryZone(**data.model_dump())
    db.add(zone)
    try:
        db.commit()
        db.refresh(zone)
        return zone
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, f"Zone '{data.name}' already exists") from exc


@router.put("/delivery-zones/{zone_id}", response_model=DeliveryZoneResponse)
def update_zone(
    zone_id: UUID,
    data: DeliveryZoneUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.delivery_zone_manage.value)),
):
    zone = db.query(DeliveryZone).filter(DeliveryZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, "Zone not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(zone, key, value)
    db.commit()
    db.refresh(zone)
    return zone


@router.delete("/delivery-zones/{zone_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_zone(
    zone_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.delivery_zone_manage.value)),
):
    zone = db.query(DeliveryZone).filter(DeliveryZone.id == zone_id).first()
    if not zone:
        raise HTTPException(404, "Zone not found")
    db.delete(zone)
    db.commit()


# =========================================================
# DELIVERY FARES
# =========================================================

@router.get("/delivery-fares", response_model=list[DeliveryFareResponse])
def list_fares(
    zone_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.delivery_fare_read.value)),
):
    q = db.query(DeliveryFare)
    if zone_id:
        q = q.filter(DeliveryFare.zone_id == zone_id)
    if is_active is not None:
        q = q.filter(DeliveryFare.is_active == is_active)
    return q.order_by(DeliveryFare.zone_id, DeliveryFare.fare_type, DeliveryFare.vehicle_type).all()


@router.post("/delivery-fares", response_model=DeliveryFareResponse, status_code=status.HTTP_201_CREATED)
def create_fare(
    data: DeliveryFareCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.delivery_fare_manage.value)),
):
    zone = db.query(DeliveryZone).filter(DeliveryZone.id == data.zone_id).first()
    if not zone:
        raise HTTPException(404, "Zone not found")
    fare = DeliveryFare(**data.model_dump())
    db.add(fare)
    db.commit()
    db.refresh(fare)
    return fare


@router.put("/delivery-fares/{fare_id}", response_model=DeliveryFareResponse)
def update_fare(
    fare_id: UUID,
    data: DeliveryFareUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.delivery_fare_manage.value)),
):
    fare = db.query(DeliveryFare).filter(DeliveryFare.id == fare_id).first()
    if not fare:
        raise HTTPException(404, "Fare configuration not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(fare, key, value)
    db.commit()
    db.refresh(fare)
    return fare


@router.delete("/delivery-fares/{fare_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_fare(
    fare_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.delivery_fare_manage.value)),
):
    fare = db.query(DeliveryFare).filter(DeliveryFare.id == fare_id).first()
    if not fare:
        raise HTTPException(404, "Fare configuration not found")
    db.delete(fare)
    db.commit()


# =========================================================
# SURGE PRICING
# =========================================================

@router.get("/surge-pricings", response_model=list[SurgePricingResponse])
def list_surge_pricings(
    zone_id: UUID | None = Query(None),
    is_active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.surge_pricing_read.value)),
):
    q = db.query(SurgePricing)
    if zone_id:
        q = q.filter(SurgePricing.zone_id == zone_id)
    if is_active is not None:
        q = q.filter(SurgePricing.is_active == is_active)
    return q.order_by(SurgePricing.created_at.desc()).all()


@router.post("/surge-pricings", response_model=SurgePricingResponse, status_code=status.HTTP_201_CREATED)
def create_surge_pricing(
    data: SurgePricingCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.surge_pricing_manage.value)),
):
    surge = SurgePricing(**data.model_dump())
    db.add(surge)
    db.commit()
    db.refresh(surge)
    return surge


@router.put("/surge-pricings/{surge_id}", response_model=SurgePricingResponse)
def update_surge_pricing(
    surge_id: UUID,
    data: SurgePricingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.surge_pricing_manage.value)),
):
    surge = db.query(SurgePricing).filter(SurgePricing.id == surge_id).first()
    if not surge:
        raise HTTPException(404, "Surge pricing not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(surge, key, value)
    db.commit()
    db.refresh(surge)
    return surge


@router.delete("/surge-pricings/{surge_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_surge_pricing(
    surge_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.surge_pricing_manage.value)),
):
    surge = db.query(SurgePricing).filter(SurgePricing.id == surge_id).first()
    if not surge:
        raise HTTPException(404, "Surge pricing not found")
    db.delete(surge)
    db.commit()


# =========================================================
# FARE CALCULATION
# =========================================================

@router.post("/delivery-fares/calculate", response_model=FareCalculationResponse)
def calculate_delivery_fare(
    data: FareCalculationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.delivery_fare_read.value)),
):
    """Calculate delivery fare based on distance, zone, surge pricing, and additional fees."""
    return calculate_fare(db, data)
