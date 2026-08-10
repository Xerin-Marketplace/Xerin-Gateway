from decimal import Decimal
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from api.deps import get_db, get_current_user
from api.enums import PermissionCode
from api.models import CommissionRule, OrderItemCommission, Seller, User
from api.permissions import require_permission
from api.schemas import CommissionRuleCreate, CommissionRuleResponse, CommissionRuleUpdate, OrderItemCommissionResponse, SellerEarningsSummary

router=APIRouter(prefix="/commissions", tags=["Commissions"] )

def _commit(db):
    try: db.commit()
    except IntegrityError as exc:
        db.rollback(); raise HTTPException(status_code=409, detail="Conflicting commission rule") from exc

@router.post("/rules", response_model=CommissionRuleResponse, status_code=status.HTTP_201_CREATED)
def create_rule(data: CommissionRuleCreate, db: Session=Depends(get_db), current_user: User=Depends(require_permission(PermissionCode.commissions_write.value))):
    rule=CommissionRule(**data.model_dump(), created_by_id=current_user.id); db.add(rule); _commit(db); db.refresh(rule); return rule

@router.get("/rules", response_model=list[CommissionRuleResponse])
def list_rules(active_only: bool=False, db: Session=Depends(get_db), _: User=Depends(require_permission(PermissionCode.commissions_read.value))):
    q=db.query(CommissionRule); q=q.filter(CommissionRule.is_active.is_(True)) if active_only else q; return q.order_by(CommissionRule.scope, CommissionRule.priority.desc()).all()

@router.patch("/rules/{rule_id}", response_model=CommissionRuleResponse)
def update_rule(rule_id: UUID, data: CommissionRuleUpdate, db: Session=Depends(get_db), _: User=Depends(require_permission(PermissionCode.commissions_write.value))):
    rule=db.query(CommissionRule).filter(CommissionRule.id==rule_id).with_for_update().first()
    if not rule: raise HTTPException(status_code=404, detail="Commission rule not found")
    for k,v in data.model_dump(exclude_unset=True).items(): setattr(rule,k,v)
    if rule.rule_type.value=="percentage" and rule.rate>100: raise HTTPException(status_code=422, detail="Percentage commission cannot exceed 100")
    _commit(db); db.refresh(rule); return rule

@router.get("/orders/{order_id}", response_model=list[OrderItemCommissionResponse])
def order_commissions(order_id: UUID, db: Session=Depends(get_db), _: User=Depends(require_permission(PermissionCode.commissions_read.value))):
    return db.query(OrderItemCommission).filter(OrderItemCommission.order_id==order_id).all()

@router.get("/seller/me/summary", response_model=SellerEarningsSummary)
def my_summary(db: Session=Depends(get_db), current_user: User=Depends(get_current_user)):
    seller=db.query(Seller).filter(Seller.user_id==current_user.id).first()
    if not seller: raise HTTPException(status_code=404, detail="Seller profile not found")
    row=db.query(func.coalesce(func.sum(OrderItemCommission.gross_amount),0),func.coalesce(func.sum(OrderItemCommission.commission_amount),0),func.coalesce(func.sum(OrderItemCommission.seller_net_amount),0),func.count(OrderItemCommission.id)).filter(OrderItemCommission.seller_id==seller.id).one()
    currency=db.query(OrderItemCommission.currency).filter(OrderItemCommission.seller_id==seller.id).first()
    return SellerEarningsSummary(currency=currency[0] if currency else "TZS",gross_sales=Decimal(row[0]),commission_deducted=Decimal(row[1]),net_earnings=Decimal(row[2]),transaction_count=row[3])
