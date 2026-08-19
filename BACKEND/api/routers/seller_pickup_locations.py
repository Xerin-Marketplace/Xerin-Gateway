from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import SellerPickupLocation, User
from api.permissions import require_permission
from api.schemas import (
    SellerPickupLocationCreate,
    SellerPickupLocationListResponse,
    SellerPickupLocationResponse,
    SellerPickupLocationUpdate,
)

router = APIRouter(prefix="/seller/pickup-locations", tags=["Seller Pickup Locations"])


def _seller(user: User):
    if not user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    return user.seller_profile


def _owned(db: Session, seller_id: UUID, location_id: UUID, *, lock: bool = False) -> SellerPickupLocation:
    query = db.query(SellerPickupLocation).filter(
        SellerPickupLocation.id == location_id,
        SellerPickupLocation.seller_id == seller_id,
    )
    if lock:
        query = query.with_for_update()
    row = query.first()
    if row is None:
        raise HTTPException(status_code=404, detail="Pickup location not found")
    return row


def _clear_default(db: Session, seller_id: UUID, *, exclude_id: UUID | None = None) -> None:
    query = db.query(SellerPickupLocation).filter(
        SellerPickupLocation.seller_id == seller_id,
        SellerPickupLocation.is_default.is_(True),
    )
    if exclude_id is not None:
        query = query.filter(SellerPickupLocation.id != exclude_id)
    query.update({SellerPickupLocation.is_default: False}, synchronize_session=False)


def _promote_default_if_needed(db: Session, seller_id: UUID) -> None:
    exists = db.query(SellerPickupLocation.id).filter(
        SellerPickupLocation.seller_id == seller_id,
        SellerPickupLocation.is_default.is_(True),
        SellerPickupLocation.is_active.is_(True),
    ).first()
    if exists:
        return
    candidate = (
        db.query(SellerPickupLocation)
        .filter(
            SellerPickupLocation.seller_id == seller_id,
            SellerPickupLocation.is_active.is_(True),
        )
        .order_by(SellerPickupLocation.created_at.asc())
        .first()
    )
    if candidate:
        candidate.is_default = True


@router.get("", response_model=SellerPickupLocationListResponse)
def list_pickup_locations(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=180),
    is_active: bool | None = Query(default=None),
    is_default: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_pickup_locations_read.value)
    ),
):
    seller = _seller(current_user)
    query = db.query(SellerPickupLocation).filter(
        SellerPickupLocation.seller_id == seller.id
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                SellerPickupLocation.label.ilike(term),
                SellerPickupLocation.formatted_address.ilike(term),
                SellerPickupLocation.country.ilike(term),
                SellerPickupLocation.region.ilike(term),
                SellerPickupLocation.city.ilike(term),
                SellerPickupLocation.district.ilike(term),
                SellerPickupLocation.ward.ilike(term),
                SellerPickupLocation.street.ilike(term),
                SellerPickupLocation.landmark.ilike(term),
                SellerPickupLocation.pickup_contact_name.ilike(term),
                SellerPickupLocation.pickup_phone.ilike(term),
            )
        )

    if is_active is not None:
        query = query.filter(SellerPickupLocation.is_active == is_active)
    if is_default is not None:
        query = query.filter(SellerPickupLocation.is_default == is_default)

    total = query.count()
    rows = (
        query.order_by(
            SellerPickupLocation.is_default.desc(),
            SellerPickupLocation.is_active.desc(),
            SellerPickupLocation.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": 0 if total == 0 else (total + page_size - 1) // page_size,
        "results": rows,
    }


@router.post("", response_model=SellerPickupLocationResponse, status_code=status.HTTP_201_CREATED)
def create_pickup_location(
    data: SellerPickupLocationCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_pickup_locations_manage.value)
    ),
):
    seller = _seller(current_user)
    if data.is_default and not data.is_active:
        raise HTTPException(422, "Default pickup location must be active")

    has_active_default = db.query(SellerPickupLocation.id).filter(
        SellerPickupLocation.seller_id == seller.id,
        SellerPickupLocation.is_default.is_(True),
        SellerPickupLocation.is_active.is_(True),
    ).first() is not None

    # The first active location automatically becomes default. Inactive records
    # may exist without becoming a routing origin.
    make_default = bool(data.is_active and (data.is_default or not has_active_default))
    if make_default:
        _clear_default(db, seller.id)

    row = SellerPickupLocation(
        **data.model_dump(exclude={"is_default"}),
        seller_id=seller.id,
        is_default=make_default,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


@router.get("/{location_id}", response_model=SellerPickupLocationResponse)
def get_pickup_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_pickup_locations_read.value)
    ),
):
    seller = _seller(current_user)
    return _owned(db, seller.id, location_id)


@router.patch("/{location_id}", response_model=SellerPickupLocationResponse)
def update_pickup_location(
    location_id: UUID,
    data: SellerPickupLocationUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_pickup_locations_manage.value)
    ),
):
    seller = _seller(current_user)
    row = _owned(db, seller.id, location_id, lock=True)
    changes = data.model_dump(exclude_unset=True)

    if changes.get("is_default") is True:
        if changes.get("is_active") is False:
            raise HTTPException(422, "Default pickup location must be active")
        _clear_default(db, seller.id, exclude_id=row.id)

    if changes.get("is_active") is False and row.is_default and changes.get("is_default") is not False:
        # A disabled location cannot remain the default.
        changes["is_default"] = False

    verification_fields = {
        "formatted_address", "country", "region", "city", "district", "ward",
        "street", "landmark", "postal_code", "place_id", "latitude", "longitude",
    }
    if verification_fields.intersection(changes):
        row.is_verified = False

    for key, value in changes.items():
        setattr(row, key, value)

    db.flush()
    _promote_default_if_needed(db, seller.id)
    db.commit()
    db.refresh(row)
    return row


@router.post("/{location_id}/default", response_model=SellerPickupLocationResponse)
def set_default_pickup_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_pickup_locations_manage.value)
    ),
):
    seller = _seller(current_user)
    row = _owned(db, seller.id, location_id, lock=True)
    if not row.is_active:
        raise HTTPException(409, "Inactive pickup location cannot be the default")
    _clear_default(db, seller.id, exclude_id=row.id)
    row.is_default = True
    db.commit()
    db.refresh(row)
    return row


@router.delete("/{location_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_pickup_location(
    location_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_pickup_locations_manage.value)
    ),
):
    seller = _seller(current_user)
    row = _owned(db, seller.id, location_id, lock=True)
    was_default = bool(row.is_default)
    db.delete(row)
    db.flush()
    if was_default:
        _promote_default_if_needed(db, seller.id)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
