from uuid import UUID
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.models import User, Coupon
from api.schemas import CouponCreate, CouponUpdate, CouponResponse
from api.permissions import require_permission

router = APIRouter(prefix="/coupons", tags=["Coupons"])


@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    data: CouponCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:write")),
):
    existing = db.query(Coupon).filter(Coupon.code == data.code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Coupon code already exists")

    if data.discount_type not in ("percentage", "fixed_amount"):
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'fixed_amount'")

    coupon = Coupon(
        code=data.code,
        description=data.description,
        discount_type=data.discount_type,
        discount_value=data.discount_value,
        minimum_order_amount=data.minimum_order_amount,
        maximum_discount_amount=data.maximum_discount_amount,
        usage_limit=data.usage_limit,
        valid_from=data.valid_from,
        valid_until=data.valid_until,
        is_active=data.is_active,
        created_by_id=current_user.id,
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return coupon


@router.get("", response_model=list[CouponResponse])
def list_coupons(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Coupon)
    if active_only:
        now = datetime.now(timezone.utc)
        query = query.filter(
            Coupon.is_active == True,
            (Coupon.valid_from.is_(None) | (Coupon.valid_from <= now)),
            (Coupon.valid_until.is_(None) | (Coupon.valid_until >= now)),
        )
    return query.order_by(Coupon.created_at.desc()).all()


@router.get("/{coupon_id}", response_model=CouponResponse)
def get_coupon(
    coupon_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


@router.put("/{coupon_id}", response_model=CouponResponse)
def update_coupon(
    coupon_id: UUID,
    data: CouponUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:write")),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    if data.discount_type is not None and data.discount_type not in ("percentage", "fixed_amount"):
        raise HTTPException(status_code=400, detail="discount_type must be 'percentage' or 'fixed_amount'")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(coupon, field, value)

    db.commit()
    db.refresh(coupon)
    return coupon


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(
    coupon_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:write")),
):
    coupon = db.query(Coupon).filter(Coupon.id == coupon_id).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    db.delete(coupon)
    db.commit()
    return None
