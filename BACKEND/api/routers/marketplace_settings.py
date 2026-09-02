from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import CommissionRuleType, CommissionScope, PermissionCode
from api.models import Category, CommissionRule, MarketplaceSettings, Product, Seller, User, XerinDomesticServiceStandard
from api.permissions import require_permission
from api.schemas import (
    CommissionPricingPreviewRequest,
    CommissionPricingPreviewResponse,
    CommissionRuleCreate,
    CommissionRuleResponse,
    CommissionRuleUpdate,
    MarketplaceSettingsResponse,
    MarketplaceSettingsUpdate,
    PaginatedCommissionRuleResponse,
    XerinDomesticServiceStandardCreate, XerinDomesticServiceStandardResponse,
)
from api.services.commission_engine import resolve_commission_rule_for_targets

router = APIRouter(prefix="/admin/marketplace-settings", tags=["Admin Marketplace Settings"])
MONEY = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return Decimal(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _page_count(total: int, page_size: int) -> int:
    return 0 if total <= 0 else (total + page_size - 1) // page_size


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Marketplace setting or commission rule conflicts with existing data") from exc


def _get_settings(db: Session) -> MarketplaceSettings | None:
    return db.query(MarketplaceSettings).filter(MarketplaceSettings.singleton_key == 1).first()


def _settings_payload(settings: MarketplaceSettings | None) -> dict:
    if settings is None:
        return {
            "id": None,
            "escrow_release_hours": None,
            "dispute_period_hours": None,
            "seller_release_grace_hours": 144,
            "allow_customer_early_acceptance": True,
            "cod_allowed": None,
            "international_delivery_allowed": None,
            "auto_approve_products": False,
            "auto_verify_seller_payout_accounts": False,
            "configured": False,
            "updated_by_id": None,
            "created_at": None,
            "updated_at": None,
        }
    return {
        "id": settings.id,
        "escrow_release_hours": settings.escrow_release_hours,
        "dispute_period_hours": settings.dispute_period_hours,
        "seller_release_grace_hours": settings.seller_release_grace_hours,
        "allow_customer_early_acceptance": bool(settings.allow_customer_early_acceptance),
        "cod_allowed": settings.cod_allowed,
        "international_delivery_allowed": settings.international_delivery_allowed,
        "auto_approve_products": bool(settings.auto_approve_products),
        "auto_verify_seller_payout_accounts": bool(settings.auto_verify_seller_payout_accounts),
        "configured": all(
            value is not None
            for value in (
                settings.escrow_release_hours,
                settings.dispute_period_hours,
                settings.seller_release_grace_hours,
                settings.cod_allowed,
                settings.international_delivery_allowed,
            )
        ),
        "updated_by_id": settings.updated_by_id,
        "created_at": settings.created_at,
        "updated_at": settings.updated_at,
    }


def _validate_rule_target(db: Session, data: CommissionRuleCreate) -> None:
    if data.scope == CommissionScope.seller:
        if not db.query(Seller.id).filter(Seller.id == data.seller_id).first():
            raise HTTPException(status_code=404, detail="Seller not found")
    elif data.scope == CommissionScope.category:
        if not db.query(Category.id).filter(Category.id == data.category_id).first():
            raise HTTPException(status_code=404, detail="Product category not found")
    elif data.scope == CommissionScope.product:
        if not db.query(Product.id).filter(Product.id == data.product_id).first():
            raise HTTPException(status_code=404, detail="Product not found")


@router.get("", response_model=MarketplaceSettingsResponse)
def get_marketplace_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.marketplace_settings_read.value)),
):
    return _settings_payload(_get_settings(db))


@router.put("", response_model=MarketplaceSettingsResponse)
def save_marketplace_settings(
    data: MarketplaceSettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.marketplace_settings_manage.value)),
):
    settings = _get_settings(db)
    if settings is None:
        settings = MarketplaceSettings(**data.model_dump(), updated_by_id=current_user.id)
        db.add(settings)
    else:
        for key, value in data.model_dump().items():
            setattr(settings, key, value)
        settings.updated_by_id = current_user.id
        settings.updated_at = datetime.now(timezone.utc)
    _commit(db)
    db.refresh(settings)
    return _settings_payload(settings)


@router.get("/commission-rules", response_model=PaginatedCommissionRuleResponse)
def list_commission_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    scope: CommissionScope | None = Query(None),
    active: bool | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_read.value)),
):
    query = db.query(CommissionRule)
    term = (search or "").strip()
    if term:
        query = query.filter(CommissionRule.name.ilike(f"%{term}%"))
    if scope is not None:
        query = query.filter(CommissionRule.scope == scope)
    if active is not None:
        query = query.filter(CommissionRule.is_active.is_(active))
    total = query.count()
    rows = (
        query.order_by(CommissionRule.scope.asc(), CommissionRule.priority.desc(), CommissionRule.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _page_count(total, page_size), "results": rows}


@router.post("/commission-rules", response_model=CommissionRuleResponse, status_code=status.HTTP_201_CREATED)
def create_commission_rule(
    data: CommissionRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.commissions_manage.value)),
):
    _validate_rule_target(db, data)
    rule = CommissionRule(**data.model_dump(), created_by_id=current_user.id)
    db.add(rule)
    _commit(db)
    db.refresh(rule)
    return rule


@router.patch("/commission-rules/{rule_id}", response_model=CommissionRuleResponse)
def update_commission_rule(
    rule_id: UUID,
    data: CommissionRuleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_manage.value)),
):
    rule = db.query(CommissionRule).filter(CommissionRule.id == rule_id).with_for_update().first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Commission rule not found")
    values = data.model_dump(exclude_unset=True)
    for key, value in values.items():
        setattr(rule, key, value)
    if rule.rule_type == CommissionRuleType.percentage and Decimal(rule.rate) > Decimal("100"):
        raise HTTPException(status_code=422, detail="Percentage commission cannot exceed 100")
    if rule.starts_at and rule.ends_at and rule.ends_at <= rule.starts_at:
        raise HTTPException(status_code=422, detail="ends_at must be later than starts_at")
    _commit(db)
    db.refresh(rule)
    return rule


@router.delete("/commission-rules/{rule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_commission_rule(
    rule_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_manage.value)),
):
    rule = db.query(CommissionRule).filter(CommissionRule.id == rule_id).first()
    if rule is None:
        raise HTTPException(status_code=404, detail="Commission rule not found")
    db.delete(rule)
    _commit(db)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/commission-preview", response_model=CommissionPricingPreviewResponse)
def preview_commission_price(
    data: CommissionPricingPreviewRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.commissions_read.value)),
):
    seller_id = data.seller_id
    category_id = data.category_id
    product_id = data.product_id

    if product_id is not None:
        product = db.query(Product).filter(Product.id == product_id).first()
        if product is None:
            raise HTTPException(status_code=404, detail="Product not found")
        seller_id = seller_id or product.seller_id
        category_id = category_id or product.category_id

    if seller_id is not None and not db.query(Seller.id).filter(Seller.id == seller_id).first():
        raise HTTPException(status_code=404, detail="Seller not found")
    if category_id is not None and not db.query(Category.id).filter(Category.id == category_id).first():
        raise HTTPException(status_code=404, detail="Product category not found")

    rule = resolve_commission_rule_for_targets(
        db, seller_id=seller_id, category_id=category_id, product_id=product_id
    )
    base = _money(data.seller_base_price)
    if rule is None:
        commission = Decimal("0.00")
        rate = Decimal("0")
    elif rule.rule_type == CommissionRuleType.fixed:
        rate = Decimal(rule.rate)
        commission = _money(rate)
    else:
        rate = Decimal(rule.rate)
        commission = _money(base * rate / Decimal("100"))

    return {
        "seller_base_price": base,
        "commission_rule_id": rule.id if rule else None,
        "commission_scope": rule.scope if rule else None,
        "commission_rule_type": rule.rule_type if rule else None,
        "commission_rate": rate,
        "commission_amount": commission,
        "customer_price": _money(base + commission),
        "seller_receivable_before_other_adjustments": base,
        "currency": data.currency,
    }


@router.get("/domestic-service-standards", response_model=list[XerinDomesticServiceStandardResponse])
def list_domestic_service_standards(db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.marketplace_settings_read.value))):
    return db.query(XerinDomesticServiceStandard).order_by(XerinDomesticServiceStandard.origin_region, XerinDomesticServiceStandard.destination_region, XerinDomesticServiceStandard.tier).all()

@router.post("/domestic-service-standards", response_model=XerinDomesticServiceStandardResponse, status_code=201)
def create_domestic_service_standard(data: XerinDomesticServiceStandardCreate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.marketplace_settings_manage.value))):
    row = XerinDomesticServiceStandard(**data.model_dump())
    db.add(row); _commit(db); db.refresh(row); return row

@router.patch("/domestic-service-standards/{rule_id}", response_model=XerinDomesticServiceStandardResponse)
def update_domestic_service_standard(rule_id: UUID, data: XerinDomesticServiceStandardCreate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.marketplace_settings_manage.value))):
    row = db.get(XerinDomesticServiceStandard, rule_id)
    if not row: raise HTTPException(404, "Domestic service standard not found")
    for key, value in data.model_dump().items(): setattr(row, key, value)
    _commit(db); db.refresh(row); return row
