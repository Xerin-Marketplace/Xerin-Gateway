from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import String, case, cast, func, or_
from sqlalchemy.orm import Session, selectinload

from api.deps import get_db
from api.enums import PermissionCode, PayoutStatus, RefundStatus
from api.models import (
    AuditLog,
    CommissionRule,
    Order,
    OrderItemCommission,
    Payment,
    PaymentCountry,
    PaymentCurrency,
    PaymentDispute,
    PaymentFxRate,
    PaymentMethod,
    PaymentProviderConfig,
    PaymentReconciliationRecord,
    PaymentRiskEvent,
    PaymentStatus,
    PaymentTransaction,
    PayoutRequest,
    Refund,
    Seller,
    User,
)
from api.permissions import require_permission
from api.schemas import (
    PaymentCountryCreate,
    PaymentCountryUpdate,
    PaymentCurrencyCreate,
    PaymentCurrencyUpdate,
    PaymentDisputeUpdate,
    PaymentFxRateCreate,
    PaymentProviderCreate,
    PaymentProviderUpdate,
    PaymentReconciliationUpdate,
    PaymentRiskUpdate,
)

router = APIRouter(prefix="/admin", tags=["Payment Administration"])


def _pages(total: int, page_size: int) -> int:
    return 0 if total <= 0 else (total + page_size - 1) // page_size


def _page(query, page: int, page_size: int):
    total = query.count()
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    return total, rows


def _status_value(value) -> str:
    return value.value if hasattr(value, "value") else str(value)


def _payment_row(payment: Payment) -> dict:
    user = payment.user
    order = payment.order
    return {
        "id": str(payment.id),
        "order_id": str(payment.order_id),
        "order_number": getattr(order, "order_number", None) or str(payment.order_id)[:8].upper(),
        "user_id": str(payment.user_id),
        "customer_name": " ".join(filter(None, [getattr(user, "first_name", None), getattr(user, "last_name", None)])) or getattr(user, "email", None) or "Customer",
        "customer_email": getattr(user, "email", None),
        "amount": float(payment.amount),
        "currency": payment.currency,
        "method": _status_value(payment.method),
        "provider": payment.provider,
        "status": _status_value(payment.status),
        "reference": payment.provider_transaction_id or str(payment.id),
        "failure_reason": payment.failure_reason,
        "paid_at": payment.paid_at,
        "transaction_count": len(payment.transactions or []),
        "created_at": payment.created_at,
        "updated_at": payment.updated_at,
    }


@router.get("/payments/dashboard")
def payments_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.payments_dashboard.value)),
):
    completed = db.query(Payment).filter(Payment.status == PaymentStatus.completed)
    refunded = db.query(Refund).filter(Refund.status == RefundStatus.completed)
    payout_completed = db.query(PayoutRequest).filter(PayoutRequest.status == PayoutStatus.completed)
    payout_pending = db.query(PayoutRequest).filter(PayoutRequest.status.in_([PayoutStatus.pending, PayoutStatus.approved, PayoutStatus.processing]))

    processed_volume = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.status == PaymentStatus.completed).scalar() or 0
    refunded_amount = db.query(func.coalesce(func.sum(Refund.total_amount), 0)).filter(Refund.status == RefundStatus.completed).scalar() or 0
    commission = db.query(func.coalesce(func.sum(OrderItemCommission.commission_amount), 0)).scalar() or 0
    seller_earnings = db.query(func.coalesce(func.sum(OrderItemCommission.seller_net_amount), 0)).scalar() or 0
    currency = db.query(Payment.currency).filter(Payment.status == PaymentStatus.completed).first()

    return {
        "processed_volume": float(processed_volume),
        "successful_payments": completed.count(),
        "pending_payments": db.query(Payment).filter(Payment.status.in_([PaymentStatus.pending, PaymentStatus.processing])).count(),
        "failed_payments": db.query(Payment).filter(Payment.status == PaymentStatus.failed).count(),
        "refunded_amount": float(refunded_amount),
        "pending_payouts": payout_pending.count(),
        "completed_payouts": payout_completed.count(),
        "platform_commission": float(commission),
        "seller_earnings": float(seller_earnings),
        "currency": currency[0] if currency else "TZS",
    }


@router.get("/payments")
def admin_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    status_filter: str | None = None,
    provider: str | None = None,
    currency: str | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.payments_read.value)),
):
    q = db.query(Payment).join(User, Payment.user_id == User.id).join(Order, Payment.order_id == Order.id)
    if status_filter and status_filter != "all":
        try:
            q = q.filter(Payment.status == PaymentStatus(status_filter))
        except ValueError as exc:
            raise HTTPException(400, "Invalid payment status") from exc
    if provider:
        q = q.filter(Payment.provider.ilike(provider))
    if currency:
        q = q.filter(Payment.currency == currency.upper())
    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        q = q.filter(or_(
            cast(Payment.id, String).ilike(pattern),
            Payment.provider_transaction_id.ilike(pattern),
            Payment.provider.ilike(pattern),
            User.first_name.ilike(pattern), User.last_name.ilike(pattern), User.email.ilike(pattern),
            cast(Order.id, String).ilike(pattern),
        ))
    total = q.count()
    rows = q.options(selectinload(Payment.user), selectinload(Payment.order), selectinload(Payment.transactions)).order_by(Payment.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _pages(total, page_size), "results": [_payment_row(x) for x in rows]}


@router.get("/payment-methods")
def payment_methods(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.payment_methods_read.value)),
):
    rows = db.query(Payment.method, Payment.provider, Payment.currency, func.count(Payment.id), func.sum(case((Payment.status == PaymentStatus.completed, 1), else_=0)), func.sum(case((Payment.status == PaymentStatus.failed, 1), else_=0)), func.coalesce(func.sum(Payment.amount), 0)).group_by(Payment.method, Payment.provider, Payment.currency).all()
    return [{"method": _status_value(r[0]), "provider": r[1] or "direct", "currency": r[2], "transactions": int(r[3] or 0), "completed": int(r[4] or 0), "failed": int(r[5] or 0), "volume": float(r[6] or 0)} for r in rows]


@router.get("/refunds")
def admin_refunds(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = None, status_filter: str | None = None,
    db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.refunds_read.value)),
):
    q = db.query(Refund).join(Order, Refund.order_id == Order.id).join(User, Refund.requested_by_id == User.id)
    if status_filter and status_filter != "all":
        try: q = q.filter(Refund.status == RefundStatus(status_filter))
        except ValueError as exc: raise HTTPException(400, "Invalid refund status") from exc
    if search:
        pattern=f"%{search.strip()}%"; q=q.filter(or_(cast(Refund.id,String).ilike(pattern),cast(Refund.order_id,String).ilike(pattern),User.email.ilike(pattern),Refund.provider_reference.ilike(pattern),Refund.reason_details.ilike(pattern)))
    total=q.count(); rows=q.options(selectinload(Refund.order),selectinload(Refund.requested_by)).order_by(Refund.requested_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    results=[]
    for r in rows:
        results.append({"id":str(r.id),"order_id":str(r.order_id),"order_number":getattr(r.order,"order_number",None) or str(r.order_id)[:8].upper(),"user_id":str(r.requested_by_id),"customer_name":" ".join(filter(None,[r.requested_by.first_name,r.requested_by.last_name])) or r.requested_by.email,"customer_email":r.requested_by.email,"amount":float(r.total_amount),"currency":r.currency,"method":"refund","provider":None,"status":_status_value(r.status),"reference":r.provider_reference or str(r.id),"failure_reason":None,"paid_at":r.completed_at,"transaction_count":len(r.events or []),"created_at":r.requested_at,"updated_at":r.completed_at or r.processed_at or r.reviewed_at})
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":results}


@router.get("/failed-payments")
def failed_payments(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payments_read.value))):
    q=db.query(Payment).join(User,Payment.user_id==User.id).join(Order,Payment.order_id==Order.id).filter(Payment.status==PaymentStatus.failed)
    if search:
        pattern=f"%{search.strip()}%"; q=q.filter(or_(Payment.failure_reason.ilike(pattern),Payment.provider_transaction_id.ilike(pattern),User.email.ilike(pattern),Payment.provider.ilike(pattern)))
    total=q.count(); rows=q.options(selectinload(Payment.user),selectinload(Payment.order),selectinload(Payment.transactions)).order_by(Payment.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[_payment_row(x) for x in rows]}


# Provider CRUD
@router.get("/payment-providers")
def providers(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_filter:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payment_providers_read.value))):
    q=db.query(PaymentProviderConfig)
    if status_filter and status_filter!="all": q=q.filter(PaymentProviderConfig.status==status_filter)
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(PaymentProviderConfig.name.ilike(p),PaymentProviderConfig.code.ilike(p),PaymentProviderConfig.provider_type.ilike(p)))
    total,rows=_page(q.order_by(PaymentProviderConfig.is_default.desc(),PaymentProviderConfig.name.asc()),page,page_size)
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"name":x.name,"code":x.code,"provider_type":x.provider_type,"status":x.status,"supported_currencies":x.supported_currencies or [],"supported_methods":x.supported_methods or [],"environment":x.environment,"is_default":x.is_default,"created_at":x.created_at,"updated_at":x.updated_at} for x in rows]}

@router.post("/payment-providers",status_code=201)
def create_provider(data:PaymentProviderCreate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payment_providers_manage.value))):
    if db.query(PaymentProviderConfig).filter(PaymentProviderConfig.code==data.code.lower().strip()).first(): raise HTTPException(409,"Payment provider code already exists")
    if data.is_default: db.query(PaymentProviderConfig).update({PaymentProviderConfig.is_default:False})
    x=PaymentProviderConfig(**data.model_dump(),code=data.code.lower().strip());db.add(x);db.commit();db.refresh(x);return {"id":str(x.id),**data.model_dump(),"code":x.code}

@router.patch("/payment-providers/{provider_id}")
def update_provider(provider_id:UUID,data:PaymentProviderUpdate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payment_providers_manage.value))):
    x=db.query(PaymentProviderConfig).filter(PaymentProviderConfig.id==provider_id).first()
    if not x: raise HTTPException(404,"Payment provider not found")
    values=data.model_dump(exclude_unset=True)
    if values.get("is_default"): db.query(PaymentProviderConfig).filter(PaymentProviderConfig.id!=provider_id).update({PaymentProviderConfig.is_default:False})
    for k,v in values.items():setattr(x,k,v)
    db.commit();db.refresh(x);return {"id":str(x.id),"name":x.name,"code":x.code,"provider_type":x.provider_type,"status":x.status,"supported_currencies":x.supported_currencies or [],"supported_methods":x.supported_methods or [],"environment":x.environment,"is_default":x.is_default}


@router.get("/payouts")
def payouts(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_filter:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payouts_read.value))):
    q=db.query(PayoutRequest).join(Seller,PayoutRequest.seller_id==Seller.id)
    if status_filter and status_filter!="all":
        try:q=q.filter(PayoutRequest.status==PayoutStatus(status_filter))
        except ValueError as exc:raise HTTPException(400,"Invalid payout status") from exc
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(Seller.business_name.ilike(p),PayoutRequest.provider_reference.ilike(p),cast(PayoutRequest.id,String).ilike(p)))
    total=q.count();rows=q.options(selectinload(PayoutRequest.seller),selectinload(PayoutRequest.payout_account)).order_by(PayoutRequest.requested_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    result=[]
    for x in rows:
        result.append({"id":str(x.id),"seller_id":str(x.seller_id),"seller_name":x.seller.business_name,"amount":float(x.amount),"currency":x.currency,"status":_status_value(x.status),"payout_method":x.payout_account.account_type if x.payout_account else None,"provider":x.payout_account.provider if x.payout_account else None,"reference":x.provider_reference,"failure_reason":x.admin_note if x.status==PayoutStatus.failed else None,"requested_at":x.requested_at,"processed_at":x.processed_at,"created_at":x.requested_at})
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":result}


@router.get("/payment-disputes")
def disputes(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_filter:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payment_disputes_read.value))):
    q=db.query(PaymentDispute).outerjoin(Order,PaymentDispute.order_id==Order.id).outerjoin(Payment,PaymentDispute.payment_id==Payment.id).outerjoin(User,Payment.user_id==User.id)
    if status_filter and status_filter!="all":q=q.filter(PaymentDispute.status==status_filter)
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(PaymentDispute.reason.ilike(p),PaymentDispute.provider.ilike(p),PaymentDispute.provider_reference.ilike(p),User.email.ilike(p),cast(PaymentDispute.order_id,String).ilike(p)))
    total=q.count();rows=q.options(selectinload(PaymentDispute.payment).selectinload(Payment.user),selectinload(PaymentDispute.order)).order_by(PaymentDispute.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"payment_id":str(x.payment_id) if x.payment_id else None,"order_id":str(x.order_id) if x.order_id else None,"order_number":getattr(x.order,"order_number",None) if x.order else None,"customer_name":(" ".join(filter(None,[x.payment.user.first_name,x.payment.user.last_name])) if x.payment and x.payment.user else None),"seller_name":None,"amount":float(x.amount),"currency":x.currency,"reason":x.reason,"status":x.status,"provider":x.provider,"provider_reference":x.provider_reference,"created_at":x.created_at,"updated_at":x.updated_at} for x in rows]}

@router.patch("/payment-disputes/{dispute_id}")
def update_dispute(dispute_id:UUID,data:PaymentDisputeUpdate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payment_disputes_manage.value))):
    x=db.query(PaymentDispute).filter(PaymentDispute.id==dispute_id).first()
    if not x:raise HTTPException(404,"Dispute not found")
    for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v)
    if x.status in {"resolved","closed"}:x.resolved_at=datetime.now(timezone.utc)
    db.commit();return {"id":str(x.id),"status":x.status}


@router.get("/payment-risk-events")
def risk_events(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_filter:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.fraud_risk_read.value))):
    q=db.query(PaymentRiskEvent).outerjoin(User,PaymentRiskEvent.user_id==User.id)
    if status_filter and status_filter!="all":q=q.filter(PaymentRiskEvent.status==status_filter)
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(PaymentRiskEvent.event_type.ilike(p),PaymentRiskEvent.reason.ilike(p),User.email.ilike(p)))
    total=q.count();rows=q.options(selectinload(PaymentRiskEvent.user)).order_by(PaymentRiskEvent.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"event_type":x.event_type,"severity":x.severity,"status":x.status,"payment_id":str(x.payment_id) if x.payment_id else None,"order_id":str(x.order_id) if x.order_id else None,"user_name":(" ".join(filter(None,[x.user.first_name,x.user.last_name])) if x.user else None),"score":float(x.score) if x.score is not None else None,"reason":x.reason,"created_at":x.created_at} for x in rows]}

@router.patch("/payment-risk-events/{event_id}")
def update_risk(event_id:UUID,data:PaymentRiskUpdate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.fraud_risk_manage.value))):
    x=db.query(PaymentRiskEvent).filter(PaymentRiskEvent.id==event_id).first()
    if not x:raise HTTPException(404,"Risk event not found")
    for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v)
    if x.status in {"resolved","closed"}:x.resolved_at=datetime.now(timezone.utc)
    db.commit();return {"id":str(x.id),"status":x.status}


@router.get("/reconciliation")
def reconciliation(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_filter:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.reconciliation_read.value))):
    q=db.query(PaymentReconciliationRecord).outerjoin(Order,PaymentReconciliationRecord.order_id==Order.id)
    if status_filter and status_filter!="all":q=q.filter(PaymentReconciliationRecord.status==status_filter)
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(PaymentReconciliationRecord.provider.ilike(p),PaymentReconciliationRecord.provider_reference.ilike(p),cast(PaymentReconciliationRecord.order_id,String).ilike(p)))
    total=q.count();rows=q.options(selectinload(PaymentReconciliationRecord.order)).order_by(PaymentReconciliationRecord.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"order_number":getattr(x.order,"order_number",None) if x.order else None,"provider":x.provider,"provider_reference":x.provider_reference,"expected_amount":float(x.expected_amount),"provider_amount":float(x.provider_amount),"currency":x.currency,"difference":float(x.difference),"status":x.status,"created_at":x.created_at} for x in rows]}

@router.patch("/reconciliation/{record_id}")
def update_reconciliation(record_id:UUID,data:PaymentReconciliationUpdate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.reconciliation_manage.value))):
    x=db.query(PaymentReconciliationRecord).filter(PaymentReconciliationRecord.id==record_id).first()
    if not x:raise HTTPException(404,"Reconciliation record not found")
    for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v)
    if x.status in {"matched","reconciled"}:x.reconciled_at=datetime.now(timezone.utc)
    db.commit();return {"id":str(x.id),"status":x.status}


# Currency / FX CRUD. No exchange rate is hardcoded.
@router.get("/currencies")
def currencies(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.currencies_read.value))):
    q=db.query(PaymentCurrency)
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(PaymentCurrency.code.ilike(p),PaymentCurrency.name.ilike(p)))
    total,rows=_page(q.order_by(PaymentCurrency.is_base.desc(),PaymentCurrency.code.asc()),page,page_size)
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"code":x.code,"name":x.name,"symbol":x.symbol,"is_base":x.is_base,"is_active":x.is_active,"decimal_places":x.decimal_places,"created_at":x.created_at} for x in rows]}

@router.post("/currencies",status_code=201)
def create_currency(data:PaymentCurrencyCreate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.currencies_manage.value))):
    code=data.code.upper().strip()
    if db.query(PaymentCurrency).filter(PaymentCurrency.code==code).first():raise HTTPException(409,"Currency already exists")
    if data.is_base:db.query(PaymentCurrency).update({PaymentCurrency.is_base:False})
    x=PaymentCurrency(**data.model_dump(exclude={"code"}),code=code);db.add(x);db.commit();db.refresh(x);return {"id":str(x.id),"code":x.code,"name":x.name,"symbol":x.symbol,"is_base":x.is_base,"is_active":x.is_active}

@router.patch("/currencies/{currency_id}")
def update_currency(currency_id:UUID,data:PaymentCurrencyUpdate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.currencies_manage.value))):
    x=db.query(PaymentCurrency).filter(PaymentCurrency.id==currency_id).first()
    if not x:raise HTTPException(404,"Currency not found")
    values=data.model_dump(exclude_unset=True)
    if values.get("is_base"):db.query(PaymentCurrency).filter(PaymentCurrency.id!=currency_id).update({PaymentCurrency.is_base:False})
    for k,v in values.items():setattr(x,k,v)
    db.commit();return {"id":str(x.id),"code":x.code,"name":x.name,"symbol":x.symbol,"is_base":x.is_base,"is_active":x.is_active}

@router.get("/fx-rates")
def fx_rates(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.currencies_read.value))):
    q=db.query(PaymentFxRate)
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(PaymentFxRate.base_currency.ilike(p),PaymentFxRate.quote_currency.ilike(p),PaymentFxRate.source.ilike(p)))
    total,rows=_page(q.order_by(PaymentFxRate.effective_at.desc()),page,page_size)
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"base_currency":x.base_currency,"quote_currency":x.quote_currency,"rate":float(x.rate),"source":x.source,"effective_at":x.effective_at,"is_active":x.is_active} for x in rows]}

@router.post("/fx-rates",status_code=201)
def create_fx(data:PaymentFxRateCreate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.currencies_manage.value))):
    base=data.base_currency.upper().strip();quote=data.quote_currency.upper().strip()
    if base==quote:raise HTTPException(422,"Base and quote currencies must differ")
    for code in (base,quote):
        if not db.query(PaymentCurrency).filter(PaymentCurrency.code==code,PaymentCurrency.is_active.is_(True)).first():raise HTTPException(422,f"Active currency {code} does not exist")
    x=PaymentFxRate(base_currency=base,quote_currency=quote,rate=data.rate,source=data.source,effective_at=data.effective_at or datetime.now(timezone.utc),is_active=data.is_active);db.add(x);db.commit();db.refresh(x);return {"id":str(x.id),"base_currency":x.base_currency,"quote_currency":x.quote_currency,"rate":float(x.rate),"source":x.source,"effective_at":x.effective_at,"is_active":x.is_active}


@router.get("/payment-countries")
def countries(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_filter:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.countries_read.value))):
    q=db.query(PaymentCountry)
    if status_filter and status_filter!="all":q=q.filter(PaymentCountry.is_active.is_(status_filter=="active"))
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(PaymentCountry.name.ilike(p),PaymentCountry.code.ilike(p),PaymentCountry.currency_code.ilike(p)))
    total,rows=_page(q.order_by(PaymentCountry.name.asc()),page,page_size)
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"code":x.code,"name":x.name,"currency_code":x.currency_code,"is_active":x.is_active,"payments_enabled":x.payments_enabled,"payouts_enabled":x.payouts_enabled} for x in rows]}

@router.post("/payment-countries",status_code=201)
def create_country(data:PaymentCountryCreate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.countries_manage.value))):
    x=PaymentCountry(**data.model_dump(),code=data.code.upper().strip(),currency_code=data.currency_code.upper().strip());db.add(x);db.commit();db.refresh(x);return {"id":str(x.id),"code":x.code,"name":x.name,"currency_code":x.currency_code,"is_active":x.is_active,"payments_enabled":x.payments_enabled,"payouts_enabled":x.payouts_enabled}

@router.patch("/payment-countries/{country_id}")
def update_country(country_id:UUID,data:PaymentCountryUpdate,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.countries_manage.value))):
    x=db.query(PaymentCountry).filter(PaymentCountry.id==country_id).first()
    if not x:raise HTTPException(404,"Country not found")
    for k,v in data.model_dump(exclude_unset=True).items():setattr(x,k,v.upper() if k=="currency_code" and isinstance(v,str) else v)
    db.commit();return {"id":str(x.id),"code":x.code,"name":x.name,"currency_code":x.currency_code,"is_active":x.is_active,"payments_enabled":x.payments_enabled,"payouts_enabled":x.payouts_enabled}


@router.get("/fees-commissions")
def fees_commissions(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,status_filter:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.commissions_read.value))):
    q=db.query(CommissionRule)
    if status_filter and status_filter!="all":q=q.filter(CommissionRule.is_active.is_(status_filter=="active"))
    if search:
        p=f"%{search.strip()}%";q=q.filter(CommissionRule.name.ilike(p))
    total,rows=_page(q.order_by(CommissionRule.priority.desc(),CommissionRule.created_at.desc()),page,page_size)
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"name":x.name,"scope":_status_value(x.scope),"rate_type":_status_value(x.rule_type),"rate_value":float(x.rate),"currency":None,"provider":None,"is_active":x.is_active} for x in rows]}


@router.get("/payment-reports")
def payment_reports(db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.finance_reports_read.value))):
    by_status=db.query(Payment.status,func.count(Payment.id),func.coalesce(func.sum(Payment.amount),0)).group_by(Payment.status).all()
    by_provider=db.query(Payment.provider,func.count(Payment.id),func.coalesce(func.sum(Payment.amount),0)).group_by(Payment.provider).all()
    return {"payments_by_status":[{"status":_status_value(x[0]),"count":int(x[1]),"amount":float(x[2])} for x in by_status],"payments_by_provider":[{"provider":x[0] or "direct","count":int(x[1]),"amount":float(x[2])} for x in by_provider]}

@router.get("/payment-audit-logs")
def payment_audit_logs(page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),search:str|None=None,db:Session=Depends(get_db),_:User=Depends(require_permission(PermissionCode.payment_audit_read.value))):
    q=db.query(AuditLog).filter(or_(AuditLog.request_path.ilike("%payment%"),AuditLog.resource_type.ilike("%payment%"),AuditLog.action.ilike("%payment%"),AuditLog.request_path.ilike("%refund%"),AuditLog.request_path.ilike("%payout%")))
    if search:
        p=f"%{search.strip()}%";q=q.filter(or_(AuditLog.action.ilike(p),AuditLog.request_path.ilike(p),AuditLog.resource_id.ilike(p),AuditLog.request_id.ilike(p)))
    total,rows=_page(q.order_by(AuditLog.created_at.desc()),page,page_size)
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_pages(total,page_size),"results":[{"id":str(x.id),"actor_user_id":str(x.actor_user_id) if x.actor_user_id else None,"action":x.action,"resource_type":x.resource_type,"resource_id":x.resource_id,"request_path":x.request_path,"response_status":x.response_status,"severity":_status_value(x.severity),"created_at":x.created_at} for x in rows]}
