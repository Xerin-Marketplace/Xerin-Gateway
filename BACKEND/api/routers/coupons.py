from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.models import Coupon, User
from api.permissions import require_permission
from api.schemas import CouponCreate, CouponResponse, CouponUpdate

router = APIRouter(prefix="/coupons", tags=["Coupons"])


def _get_coupon_or_404(db: Session, coupon_id: UUID, *, lock: bool = False) -> Coupon:
    query = db.query(Coupon).filter(Coupon.id == coupon_id)
    if lock:
        query = query.with_for_update()
    coupon = query.first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return coupon


def _validate_merged_coupon(coupon: Coupon, changes: dict) -> None:
    discount_type = changes.get("discount_type", coupon.discount_type)
    discount_value = changes.get("discount_value", coupon.discount_value)
    valid_from = changes.get("valid_from", coupon.valid_from)
    valid_until = changes.get("valid_until", coupon.valid_until)
    usage_limit = changes.get("usage_limit", coupon.usage_limit)

    if discount_type == "percentage" and discount_value > 100:
        raise HTTPException(status_code=422, detail="Percentage discount cannot exceed 100")
    if valid_from and valid_until and valid_until <= valid_from:
        raise HTTPException(status_code=422, detail="valid_until must be later than valid_from")
    if usage_limit is not None and usage_limit < coupon.usage_count:
        raise HTTPException(status_code=409, detail="usage_limit cannot be below current usage_count")


@router.post("", response_model=CouponResponse, status_code=status.HTTP_201_CREATED)
def create_coupon(
    data: CouponCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:write")),
):
    try:
        if db.query(Coupon.id).filter(Coupon.code == data.code).first():
            raise HTTPException(status_code=409, detail="Coupon code already exists")
        coupon = Coupon(**data.model_dump(), created_by_id=current_user.id)
        db.add(coupon)
        db.commit()
        db.refresh(coupon)
        return coupon
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Coupon code already exists") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create coupon") from exc


@router.get("", response_model=list[CouponResponse])
def list_coupons(
    active_only: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:read")),
):
    query = db.query(Coupon)
    if active_only:
        now = datetime.now(timezone.utc)
        query = query.filter(
            Coupon.is_active.is_(True),
            (Coupon.valid_from.is_(None) | (Coupon.valid_from <= now)),
            (Coupon.valid_until.is_(None) | (Coupon.valid_until >= now)),
            (Coupon.usage_limit.is_(None) | (Coupon.usage_count < Coupon.usage_limit)),
        )
    return query.order_by(Coupon.created_at.desc()).all()


@router.get("/{coupon_id}", response_model=CouponResponse)
def get_coupon(
    coupon_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:read")),
):
    return _get_coupon_or_404(db, coupon_id)


@router.put("/{coupon_id}", response_model=CouponResponse)
def update_coupon(
    coupon_id: UUID,
    data: CouponUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:write")),
):
    try:
        coupon = _get_coupon_or_404(db, coupon_id, lock=True)
        changes = data.model_dump(exclude_unset=True)
        _validate_merged_coupon(coupon, changes)
        for field, value in changes.items():
            setattr(coupon, field, value)
        db.commit()
        db.refresh(coupon)
        return coupon
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update coupon") from exc


@router.delete("/{coupon_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_coupon(
    coupon_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("coupons:write")),
):
    try:
        coupon = _get_coupon_or_404(db, coupon_id, lock=True)
        # Soft-delete to preserve historical order/coupon audit data.
        coupon.is_active = False
        db.commit()
        return None
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not deactivate coupon") from exc
