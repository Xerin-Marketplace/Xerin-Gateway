from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import cast, or_, String
from sqlalchemy.orm import Session, selectinload

from api.deps import get_db
from api.enums import PermissionCode
from api.models import (
    EscrowEvent,
    EscrowHold,
    FinanceSettings,
    PaymentCurrency,
    PaymentFxRate,
    PaymentProviderConfig,
    Order,
    User,
)
from api.permissions import require_permission
from api.services.escrow_service import release_escrow_hold_funds
from api.services.finance_lifecycle import order_finance_lifecycle
from api.schemas import (
    EscrowHoldResponse,
    EscrowReleaseRequest,
    EscrowStatusUpdate,
    FinanceSettingsResponse,
    FinanceSettingsUpdate,
    FxConversionRequest,
    FxConversionResponse,
    PaginatedEscrowHoldResponse,
    OrderFinanceLifecycleResponse,
)

router = APIRouter(prefix="/admin/finance", tags=["Admin Finance"])


@router.get("/orders/{order_id}/lifecycle", response_model=OrderFinanceLifecycleResponse)
def get_order_finance_lifecycle(
    order_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.finance_reports_read.value)),
):
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(404, "Order not found")
    return order_finance_lifecycle(db, order)


def _pages(total: int, page_size: int) -> int:
    return 0 if total == 0 else (total + page_size - 1) // page_size


def _settings(db: Session) -> FinanceSettings:
    row = db.query(FinanceSettings).filter(FinanceSettings.singleton_key == "default").first()
    if row is None:
        row = FinanceSettings(singleton_key="default")
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _validate_provider_and_currency(
    db: Session,
    *,
    provider_code: str | None,
    currency_code: str | None,
) -> None:
    if provider_code:
        provider = (
            db.query(PaymentProviderConfig)
            .filter(
                PaymentProviderConfig.code == provider_code,
                PaymentProviderConfig.status == "active",
            )
            .first()
        )
        if not provider:
            raise HTTPException(422, f"Active payment provider '{provider_code}' does not exist")

    if currency_code:
        currency = (
            db.query(PaymentCurrency)
            .filter(
                PaymentCurrency.code == currency_code,
                PaymentCurrency.is_active.is_(True),
            )
            .first()
        )
        if not currency:
            raise HTTPException(422, f"Active currency '{currency_code}' does not exist")


@router.get("/settings", response_model=FinanceSettingsResponse)
def get_finance_settings(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.finance_settings_read.value)),
):
    return _settings(db)


@router.patch("/settings", response_model=FinanceSettingsResponse)
def update_finance_settings(
    data: FinanceSettingsUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.finance_settings_manage.value)),
):
    row = _settings(db)
    values = data.model_dump(exclude_unset=True)

    provider_code = values.get("default_payment_provider_code")
    currency_code = values.get("settlement_currency")
    _validate_provider_and_currency(
        db,
        provider_code=provider_code,
        currency_code=currency_code,
    )

    if values.get("payout_fee_type") == "percentage":
        fee_value = values.get("payout_fee_value", row.payout_fee_value)
        if fee_value is not None and Decimal(fee_value) > Decimal("100"):
            raise HTTPException(422, "Percentage payout fee cannot exceed 100")

    for key, value in values.items():
        setattr(row, key, value)

    db.commit()
    db.refresh(row)
    return row


@router.post("/fx/convert", response_model=FxConversionResponse)
def convert_currency(
    data: FxConversionRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.currencies_read.value)),
):
    if data.from_currency == data.to_currency:
        return FxConversionResponse(
            from_currency=data.from_currency,
            to_currency=data.to_currency,
            original_amount=data.amount,
            converted_amount=data.amount,
            rate=Decimal("1"),
            rate_source="same-currency",
            effective_at=data.at or datetime.now(timezone.utc),
        )

    at = data.at or datetime.now(timezone.utc)

    direct = (
        db.query(PaymentFxRate)
        .filter(
            PaymentFxRate.base_currency == data.from_currency,
            PaymentFxRate.quote_currency == data.to_currency,
            PaymentFxRate.is_active.is_(True),
            PaymentFxRate.effective_at <= at,
        )
        .order_by(PaymentFxRate.effective_at.desc())
        .first()
    )

    if direct:
        rate = Decimal(direct.rate)
        source = direct.source
        effective_at = direct.effective_at
    else:
        inverse = (
            db.query(PaymentFxRate)
            .filter(
                PaymentFxRate.base_currency == data.to_currency,
                PaymentFxRate.quote_currency == data.from_currency,
                PaymentFxRate.is_active.is_(True),
                PaymentFxRate.effective_at <= at,
            )
            .order_by(PaymentFxRate.effective_at.desc())
            .first()
        )
        if not inverse:
            raise HTTPException(
                404,
                f"No active FX rate available for {data.from_currency}/{data.to_currency}",
            )
        rate = Decimal("1") / Decimal(inverse.rate)
        source = inverse.source
        effective_at = inverse.effective_at

    converted = (Decimal(data.amount) * rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    return FxConversionResponse(
        from_currency=data.from_currency,
        to_currency=data.to_currency,
        original_amount=data.amount,
        converted_amount=converted,
        rate=rate,
        rate_source=source,
        effective_at=effective_at,
    )


@router.get("/escrow-holds", response_model=PaginatedEscrowHoldResponse)
def list_escrow_holds(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    status_filter: str | None = Query(None, alias="status"),
    currency: str | None = Query(None, max_length=10),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.escrow_read.value)),
):
    query = db.query(EscrowHold)

    if status_filter and status_filter != "all":
        query = query.filter(EscrowHold.status == status_filter)

    if currency:
        query = query.filter(EscrowHold.currency == currency.upper().strip())

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                EscrowHold.reference.ilike(pattern),
                cast(EscrowHold.order_id, String).ilike(pattern),
                cast(EscrowHold.payment_id, String).ilike(pattern),
                cast(EscrowHold.seller_id, String).ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.order_by(EscrowHold.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _pages(total, page_size),
        "results": rows,
    }


@router.get("/escrow-holds/{hold_id}", response_model=EscrowHoldResponse)
def get_escrow_hold(
    hold_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.escrow_read.value)),
):
    hold = (
        db.query(EscrowHold)
        .options(selectinload(EscrowHold.events))
        .filter(EscrowHold.id == hold_id)
        .first()
    )
    if not hold:
        raise HTTPException(404, "Escrow hold not found")
    return hold


@router.post("/escrow-holds/{hold_id}/dispute", response_model=EscrowHoldResponse)
def dispute_escrow_hold(
    hold_id: UUID,
    data: EscrowStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.escrow_manage.value)),
):
    hold = db.query(EscrowHold).filter(EscrowHold.id == hold_id).with_for_update().first()
    if not hold:
        raise HTTPException(404, "Escrow hold not found")
    if hold.status not in {"held", "release_pending"}:
        raise HTTPException(409, f"Escrow hold cannot be disputed from status {hold.status}")

    hold.status = "disputed"
    hold.disputed_at = datetime.now(timezone.utc)
    db.add(
        EscrowEvent(
            escrow_hold_id=hold.id,
            event_type="disputed",
            note=data.note,
            created_by_id=current_user.id,
        )
    )
    db.commit()
    db.refresh(hold)
    return hold


@router.post("/escrow-holds/{hold_id}/release", response_model=EscrowHoldResponse)
def release_escrow_hold(
    hold_id: UUID,
    data: EscrowReleaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.escrow_release.value)),
):
    hold = (
        db.query(EscrowHold)
        .filter(EscrowHold.id == hold_id)
        .with_for_update()
        .first()
    )
    if not hold:
        raise HTTPException(404, "Escrow hold not found")
    try:
        release_escrow_hold_funds(
            db,
            hold=hold,
            amount=Decimal(data.amount) if data.amount is not None else None,
            note=data.note,
            created_by_id=current_user.id,
            event_type="admin_released",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(409, str(exc)) from exc
    db.commit()
    db.refresh(hold)
    return hold
