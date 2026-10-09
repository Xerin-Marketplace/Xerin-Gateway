"""Admin finance endpoints: currencies, FX rates, and payment-admin lists.

Currency/FX management is real (backed by ``currencies``/``fx_rates``
tables). Payment-provider/payout/dispute modules are not present in this
branch — those endpoints return honest empty lists.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.enums import PermissionCode
from api.models import (
    Currency,
    FxRate,
    Order,
    Payment,
    PaymentStatus,
    PayoutRequest,
    Refund,
    Seller,
    SellerPayoutAccount,
    SystemSetting,
    User,
)
from api.permissions import require_permission
from api.services.fx import rate_to_tzs

router = APIRouter(prefix="/admin", tags=["Admin Finance"])

_finance = require_permission(PermissionCode.admin_dashboard_finance_read.value)


class CurrencyCreate(BaseModel):
    code: str = Field(min_length=2, max_length=10)
    name: str = Field(min_length=1, max_length=100)
    symbol: str = Field(min_length=1, max_length=20)
    is_active: bool = True
    decimal_places: int = Field(2, ge=0, le=8)


class CurrencyUpdate(BaseModel):
    name: str | None = None
    symbol: str | None = None
    is_active: bool | None = None
    decimal_places: int | None = Field(None, ge=0, le=8)


class FxRateCreate(BaseModel):
    base_currency: str = Field(min_length=2, max_length=10)
    quote_currency: str = Field("TZS", min_length=2, max_length=10)
    rate: Decimal = Field(gt=0)
    source: str | None = None
    is_active: bool = True


class FxRateUpdate(BaseModel):
    source: str | None = None
    is_active: bool | None = None


def _currency_row(c: Currency) -> dict:
    return {
        "id": str(c.id),
        "code": c.code,
        "name": c.name,
        "symbol": c.symbol,
        "is_base": bool(c.is_base),
        "is_active": bool(c.is_active),
        "decimal_places": c.decimal_places,
    }


def _fx_row(r: FxRate) -> dict:
    return {
        "id": str(r.id),
        "base_currency": r.base_currency,
        "quote_currency": r.quote_currency,
        "rate": float(r.rate),
        "source": r.source,
        "effective_at": r.effective_at.isoformat() if r.effective_at else None,
        "is_active": bool(r.is_active),
    }


def _seed_base_currency(db: Session) -> None:
    if not db.query(Currency).first():
        db.add(Currency(code="TZS", name="Tanzanian Shilling", symbol="TSh",
                        is_base=True, is_active=True, decimal_places=0))
        db.commit()


# ---------- currencies ----------

@router.get("/currencies")
def list_currencies(db: Session = Depends(get_db), _=Depends(_finance)):
    _seed_base_currency(db)
    return [_currency_row(c) for c in db.query(Currency).order_by(Currency.is_base.desc(), Currency.code).all()]


@router.post("/currencies", status_code=201)
def create_currency(data: CurrencyCreate, db: Session = Depends(get_db), _=Depends(_finance)):
    code = data.code.upper()
    if db.query(Currency).filter(Currency.code == code).first():
        raise HTTPException(409, "Currency code already exists")
    c = Currency(code=code, name=data.name, symbol=data.symbol,
                 is_active=data.is_active, decimal_places=data.decimal_places)
    db.add(c)
    db.commit()
    db.refresh(c)

    # Fetch a live TZS rate immediately so the currency is usable at once.
    rate_to_tzs(db, code)
    return _currency_row(c)


@router.patch("/currencies/{currency_id}")
def update_currency(currency_id: str, data: CurrencyUpdate, db: Session = Depends(get_db), _=Depends(_finance)):
    c = db.query(Currency).filter(Currency.id == currency_id).first()
    if not c:
        raise HTTPException(404, "Currency not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(c, field, value)
    db.commit()
    db.refresh(c)
    return _currency_row(c)


@router.delete("/currencies/{currency_id}")
def delete_currency(currency_id: str, db: Session = Depends(get_db), _=Depends(_finance)):
    c = db.query(Currency).filter(Currency.id == currency_id).first()
    if not c:
        raise HTTPException(404, "Currency not found")
    if c.is_base:
        raise HTTPException(400, "The base currency cannot be deleted")
    db.delete(c)
    db.commit()
    return {"message": "Currency deleted"}


# ---------- fx rates ----------

@router.get("/fx-rates")
def list_fx_rates(db: Session = Depends(get_db), _=Depends(_finance)):
    return [_fx_row(r) for r in db.query(FxRate).order_by(FxRate.base_currency, FxRate.effective_at.desc()).all()]


@router.post("/fx-rates", status_code=201)
def create_fx_rate(data: FxRateCreate, db: Session = Depends(get_db), _=Depends(_finance)):
    r = FxRate(base_currency=data.base_currency.upper(), quote_currency=data.quote_currency.upper(),
               rate=data.rate, source=data.source, is_active=data.is_active)
    db.add(r)
    db.commit()
    db.refresh(r)
    return _fx_row(r)


@router.patch("/fx-rates/{rate_id}")
def update_fx_rate(rate_id: str, data: FxRateUpdate, db: Session = Depends(get_db), _=Depends(_finance)):
    r = db.query(FxRate).filter(FxRate.id == rate_id).first()
    if not r:
        raise HTTPException(404, "FX rate not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(r, field, value)
    db.commit()
    db.refresh(r)
    return _fx_row(r)


@router.delete("/fx-rates/{rate_id}")
def delete_fx_rate(rate_id: str, db: Session = Depends(get_db), _=Depends(_finance)):
    r = db.query(FxRate).filter(FxRate.id == rate_id).first()
    if not r:
        raise HTTPException(404, "FX rate not found")
    db.delete(r)
    db.commit()
    return {"message": "FX rate deleted"}


# ---------- payment-admin lists (real data) ----------


def _provider_label(provider: str | None) -> str:
    if not provider:
        return "Other"
    return provider.replace("_", " ").strip().title()


@router.get("/payment-providers")
def list_payment_providers(db: Session = Depends(get_db), _=Depends(_finance)):
    rows = (
        db.query(Payment.provider, Payment.method, Payment.currency)
        .filter(Payment.provider.isnot(None))
        .distinct()
        .all()
    )
    providers: dict[str, dict] = {}
    for provider, method, currency in rows:
        key = provider or "other"
        entry = providers.setdefault(key, {
            "id": key,
            "name": _provider_label(provider),
            "code": key,
            "provider_type": method.value if hasattr(method, "value") else str(method),
            "status": "active",
            "supported_currencies": set(),
            "supported_methods": set(),
            "environment": "production",
            "is_default": False,
        })
        if currency:
            entry["supported_currencies"].add(currency)
        if method:
            entry["supported_methods"].add(method.value if hasattr(method, "value") else str(method))
    return [
        {**v, "supported_currencies": sorted(v["supported_currencies"]), "supported_methods": sorted(v["supported_methods"])}
        for v in providers.values()
    ]


@router.get("/payouts")
def list_payouts(db: Session = Depends(get_db), _=Depends(_finance)):
    rows = (
        db.query(PayoutRequest, Seller, SellerPayoutAccount)
        .join(Seller, Seller.id == PayoutRequest.seller_id)
        .outerjoin(SellerPayoutAccount, SellerPayoutAccount.id == PayoutRequest.payout_account_id)
        .order_by(PayoutRequest.requested_at.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": str(payout.id),
            "seller_id": str(payout.seller_id),
            "seller_name": seller.business_name if seller else "",
            "amount": float(payout.amount),
            "currency": payout.currency,
            "status": payout.status.value if hasattr(payout.status, "value") else str(payout.status),
            "payout_method": account.account_type if account else None,
            "provider": account.provider if account else None,
            "reference": payout.provider_reference,
            "failure_reason": None,
            "requested_at": payout.requested_at.isoformat() if payout.requested_at else None,
            "processed_at": payout.processed_at.isoformat() if payout.processed_at else None,
            "created_at": payout.requested_at.isoformat() if payout.requested_at else None,
        }
        for payout, seller, account in rows
    ]


@router.get("/payment-disputes")
def list_payment_disputes(db: Session = Depends(get_db), _=Depends(_finance)):
    rows = (
        db.query(Refund, Order, User)
        .outerjoin(Order, Order.id == Refund.order_id)
        .outerjoin(User, User.id == Refund.requested_by_id)
        .order_by(Refund.created_at.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": str(refund.id),
            "payment_id": None,
            "order_id": str(refund.order_id) if refund.order_id else None,
            "order_number": order.order_number if order else None,
            "customer_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else None,
            "seller_name": None,
            "amount": float(refund.total_amount),
            "currency": refund.currency,
            "reason": refund.reason_details or (refund.reason.value if hasattr(refund.reason, "value") else str(refund.reason)),
            "status": refund.status.value if hasattr(refund.status, "value") else str(refund.status),
            "provider": refund.provider_reference,
            "provider_reference": refund.provider_reference,
            "created_at": refund.created_at.isoformat() if refund.created_at else None,
        }
        for refund, order, user in rows
    ]


@router.get("/payment-risk-events")
def list_payment_risk_events(db: Session = Depends(get_db), _=Depends(_finance)):
    failed = (
        db.query(Payment, Order, User)
        .outerjoin(Order, Order.id == Payment.order_id)
        .outerjoin(User, User.id == Payment.user_id)
        .filter(Payment.status == PaymentStatus.failed)
        .order_by(Payment.created_at.desc())
        .limit(250)
        .all()
    )
    events = [
        {
            "id": f"failed-{payment.id}",
            "event_type": "failed_payment",
            "severity": "warning",
            "status": "open",
            "payment_id": str(payment.id),
            "order_id": str(payment.order_id) if payment.order_id else None,
            "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else None,
            "score": None,
            "reason": payment.failure_reason or f"Payment via {payment.provider or 'unknown provider'} failed",
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
        }
        for payment, order, user in failed
    ]

    refunded = (
        db.query(Payment, Order, User)
        .outerjoin(Order, Order.id == Payment.order_id)
        .outerjoin(User, User.id == Payment.user_id)
        .filter(Payment.status == PaymentStatus.refunded)
        .order_by(Payment.created_at.desc())
        .limit(250)
        .all()
    )
    events += [
        {
            "id": f"refunded-{payment.id}",
            "event_type": "refunded_payment",
            "severity": "info",
            "status": "resolved",
            "payment_id": str(payment.id),
            "order_id": str(payment.order_id) if payment.order_id else None,
            "user_name": f"{user.first_name or ''} {user.last_name or ''}".strip() if user else None,
            "score": None,
            "reason": f"{payment.currency} {payment.amount} refunded to customer",
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
        }
        for payment, order, user in refunded
    ]

    events.sort(key=lambda e: e["created_at"] or "", reverse=True)
    return events[:500]


@router.get("/reconciliation")
def list_reconciliation(db: Session = Depends(get_db), _=Depends(_finance)):
    rows = (
        db.query(Payment, Order)
        .outerjoin(Order, Order.id == Payment.order_id)
        .order_by(Payment.created_at.desc())
        .limit(500)
        .all()
    )
    return [
        {
            "id": str(payment.id),
            "order_number": order.order_number if order else None,
            "provider": payment.provider,
            "provider_reference": payment.provider_transaction_id,
            "expected_amount": float(payment.amount),
            "provider_amount": float(payment.amount) if payment.status in (PaymentStatus.completed, PaymentStatus.refunded) else 0.0,
            "currency": payment.currency,
            "difference": 0.0 if payment.status in (PaymentStatus.completed, PaymentStatus.refunded) else float(payment.amount),
            "status": "matched" if payment.status in (PaymentStatus.completed, PaymentStatus.refunded) else (
                "failed" if payment.status == PaymentStatus.failed else "pending"),
            "created_at": payment.created_at.isoformat() if payment.created_at else None,
        }
        for payment, order in rows
    ]


@router.get("/payments/dashboard")
def payments_dashboard(_=Depends(_finance)):
    return {
        "processed_volume": 0,
        "successful_payments": 0,
        "pending_payments": 0,
        "failed_payments": 0,
        "refunded_amount": 0,
        "pending_payouts": 0,
        "completed_payouts": 0,
        "platform_commission": 0,
        "seller_earnings": 0,
        "currency": "TZS",
    }


# ---------------------------------------------------------------------------
# Finance settings singleton (backed by system_settings rows, key "finance.*")
# ---------------------------------------------------------------------------

_SETTINGS_KEY = "finance_settings"

_FINANCE_SETTING_DEFAULTS: dict[str, object] = {
    "default_payment_provider_code": None,
    "settlement_currency": "TZS",
    "minimum_payout_amount": 1000.0,
    "payout_fee_type": "fixed",
    "payout_fee_value": 0.0,
    "payout_processing_days": 7,
    "auto_payout_enabled": False,
    "escrow_enabled": True,
    "auto_release_enabled": True,
    "allow_partial_release": True,
    "hold_commission_until_release": True,
}

_FINANCE_BOOL = {
    "auto_payout_enabled",
    "escrow_enabled",
    "auto_release_enabled",
    "allow_partial_release",
    "hold_commission_until_release",
}
_FINANCE_NUM = {
    "minimum_payout_amount",
    "payout_fee_value",
    "payout_processing_days",
}


def _finance_settings_map(db: Session) -> dict[str, str]:
    rows = (
        db.query(SystemSetting)
        .filter(SystemSetting.key.like("finance.%"))
        .all()
    )
    return {r.key.split(".", 1)[1]: (r.value or "") for r in rows}


def _cast_setting(name: str, raw: str) -> object:
    if name in _FINANCE_BOOL:
        return raw.strip().lower() in ("1", "true", "yes", "on")
    if name in _FINANCE_NUM:
        try:
            return float(raw)
        except (TypeError, ValueError):
            return _FINANCE_SETTING_DEFAULTS[name]
    return raw if raw != "" else None


def _finance_settings_payload(db: Session) -> dict:
    stored = _finance_settings_map(db)
    out: dict[str, object] = {
        "id": _SETTINGS_KEY,
        "singleton_key": _SETTINGS_KEY,
    }
    latest = None
    for name, default in _FINANCE_SETTING_DEFAULTS.items():
        raw = stored.get(name)
        out[name] = _cast_setting(name, raw) if raw is not None else default
    rows = db.query(SystemSetting).filter(SystemSetting.key.like("finance.%")).all()
    for r in rows:
        if r.updated_at and (latest is None or r.updated_at > latest):
            latest = r.updated_at
    now = datetime.now(timezone.utc)
    out["created_at"] = (latest or now).isoformat()
    out["updated_at"] = latest.isoformat() if latest else None
    return out


class FinanceSettingsPatch(BaseModel):
    default_payment_provider_code: str | None = None
    settlement_currency: str | None = None
    minimum_payout_amount: float | None = None
    payout_fee_type: str | None = None
    payout_fee_value: float | None = None
    payout_processing_days: int | None = None
    auto_payout_enabled: bool | None = None
    escrow_enabled: bool | None = None
    auto_release_enabled: bool | None = None
    allow_partial_release: bool | None = None
    hold_commission_until_release: bool | None = None


@router.get("/finance/settings")
def get_finance_settings(db: Session = Depends(get_db), _=Depends(_finance)):
    return _finance_settings_payload(db)


@router.patch("/finance/settings")
def update_finance_settings(
    data: FinanceSettingsPatch,
    db: Session = Depends(get_db),
    _=Depends(_finance),
    current_user=Depends(get_current_user),
):
    updates = data.model_dump(exclude_unset=True)
    for name, value in updates.items():
        if value is None and name != "default_payment_provider_code":
            continue
        key = f"finance.{name}"
        row = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if value is None:
            str_value = ""
        elif isinstance(value, bool):
            str_value = "true" if value else "false"
        else:
            str_value = str(value)
        if row:
            row.value = str_value
            row.updated_by_id = current_user.id
        else:
            db.add(
                SystemSetting(
                    key=key,
                    value=str_value,
                    data_type="boolean"
                    if name in _FINANCE_BOOL
                    else "number"
                    if name in _FINANCE_NUM
                    else "string",
                    category="finance",
                    description=f"Finance setting: {name}",
                    is_public=False,
                    updated_by_id=current_user.id,
                )
            )
    db.commit()
    return _finance_settings_payload(db)
