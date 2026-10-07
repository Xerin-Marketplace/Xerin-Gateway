"""Admin finance endpoints: currencies, FX rates, and payment-admin lists.

Currency/FX management is real (backed by ``currencies``/``fx_rates``
tables). Payment-provider/payout/dispute modules are not present in this
branch — those endpoints return honest empty lists.
"""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import Currency, FxRate
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


# ---------- payment-admin modules absent from this branch ----------

@router.get("/payment-providers")
def list_payment_providers(_=Depends(_finance)):
    return []


@router.get("/payouts")
def list_payouts(_=Depends(_finance)):
    return []


@router.get("/payment-disputes")
def list_payment_disputes(_=Depends(_finance)):
    return []


@router.get("/payment-risk-events")
def list_payment_risk_events(_=Depends(_finance)):
    return []


@router.get("/reconciliation")
def list_reconciliation(_=Depends(_finance)):
    return []


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
