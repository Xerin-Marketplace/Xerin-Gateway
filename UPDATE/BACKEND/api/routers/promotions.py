
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import Campaign, CampaignPromotion, Promotion, PromotionRule, Seller, User
from api.permissions import require_permission
from api.schemas import (
    CampaignCreate, CampaignResponse, PromotionApplyRequest, PromotionApplyResponse,
    PromotionCreate, PromotionResponse, PromotionUpdate,
)

router = APIRouter(tags=["Promotions"])


def _seller(user: User) -> Seller:
    if not user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    return user.seller_profile


def _active(query):
    now = datetime.now(timezone.utc)
    return query.filter(
        Promotion.is_active.is_(True),
        (Promotion.starts_at.is_(None) | (Promotion.starts_at <= now)),
        (Promotion.ends_at.is_(None) | (Promotion.ends_at >= now)),
        (Promotion.usage_limit.is_(None) | (Promotion.usage_count < Promotion.usage_limit)),
    )


def _discount(promotion: Promotion, subtotal: Decimal) -> Decimal:
    if promotion.minimum_order_amount is not None and subtotal < promotion.minimum_order_amount:
        raise HTTPException(status_code=422, detail="Minimum order amount not reached")
    if promotion.promotion_type == "percentage":
        amount = subtotal * promotion.discount_value / Decimal("100")
    elif promotion.promotion_type == "fixed_amount":
        amount = promotion.discount_value
    elif promotion.promotion_type == "free_shipping":
        amount = Decimal("0")
    else:
        amount = promotion.discount_value
    if promotion.maximum_discount_amount is not None:
        amount = min(amount, promotion.maximum_discount_amount)
    return max(Decimal("0"), min(amount, subtotal)).quantize(Decimal("0.01"))


@router.get("/promotions/available", response_model=list[PromotionResponse])
def available_promotions(db: Session = Depends(get_db)):
    return _active(db.query(Promotion)).order_by(Promotion.created_at.desc()).all()


@router.post("/promotions/apply", response_model=PromotionApplyResponse)
def apply_promotion(data: PromotionApplyRequest, db: Session = Depends(get_db)):
    promotion = _active(db.query(Promotion).filter(Promotion.code == data.code)).first()
    if not promotion:
        raise HTTPException(status_code=404, detail="Promotion code is invalid or unavailable")
    discount = _discount(promotion, data.subtotal)
    return PromotionApplyResponse(
        promotion_id=promotion.id, code=promotion.code, subtotal=data.subtotal,
        discount_amount=discount, total_after_discount=data.subtotal - discount,
        promotion_type=promotion.promotion_type,
    )


@router.get("/seller/promotions", response_model=list[PromotionResponse])
def seller_promotions(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.promotions_read.value))):
    seller = _seller(current_user)
    return db.query(Promotion).filter(Promotion.seller_id == seller.id).order_by(Promotion.created_at.desc()).all()


@router.post("/seller/promotions", response_model=PromotionResponse, status_code=status.HTTP_201_CREATED)
def create_seller_promotion(data: PromotionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.promotions_create.value))):
    seller = _seller(current_user)
    promotion = Promotion(**data.model_dump(exclude={"rules"}), seller_id=seller.id, created_by_id=current_user.id)
    db.add(promotion)
    try:
        db.flush()
        for rule in data.rules:
            db.add(PromotionRule(promotion_id=promotion.id, **rule.model_dump()))
        db.commit(); db.refresh(promotion); return promotion
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Promotion code already exists") from exc


@router.patch("/seller/promotions/{promotion_id}", response_model=PromotionResponse)
def update_seller_promotion(promotion_id: UUID, data: PromotionUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.promotions_update.value))):
    seller = _seller(current_user)
    promotion = db.query(Promotion).filter(Promotion.id == promotion_id, Promotion.seller_id == seller.id).first()
    if not promotion: raise HTTPException(status_code=404, detail="Promotion not found")
    for key, value in data.model_dump(exclude_unset=True).items(): setattr(promotion, key, value)
    db.commit(); db.refresh(promotion); return promotion


@router.delete("/seller/promotions/{promotion_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_seller_promotion(promotion_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.promotions_delete.value))):
    seller = _seller(current_user)
    promotion = db.query(Promotion).filter(Promotion.id == promotion_id, Promotion.seller_id == seller.id).first()
    if not promotion: raise HTTPException(status_code=404, detail="Promotion not found")
    if promotion.usage_count: promotion.is_active = False
    else: db.delete(promotion)
    db.commit()


@router.get("/campaigns", response_model=list[CampaignResponse])
def list_campaigns(active_only: bool = Query(True), db: Session = Depends(get_db)):
    query = db.query(Campaign)
    if active_only:
        now = datetime.now(timezone.utc)
        query = query.filter(Campaign.is_active.is_(True), (Campaign.starts_at.is_(None) | (Campaign.starts_at <= now)), (Campaign.ends_at.is_(None) | (Campaign.ends_at >= now)))
    return query.order_by(Campaign.created_at.desc()).all()


@router.post("/admin/campaigns", response_model=CampaignResponse, status_code=status.HTTP_201_CREATED)
def create_campaign(data: CampaignCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.campaigns_manage.value))):
    campaign = Campaign(**data.model_dump(exclude={"promotion_ids"}), created_by_id=current_user.id)
    db.add(campaign)
    try:
        db.flush()
        for promotion_id in data.promotion_ids:
            if not db.query(Promotion.id).filter(Promotion.id == promotion_id).first():
                raise HTTPException(status_code=422, detail=f"Unknown promotion: {promotion_id}")
            db.add(CampaignPromotion(campaign_id=campaign.id, promotion_id=promotion_id))
        db.commit(); db.refresh(campaign); return campaign
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Campaign slug already exists") from exc
