from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from api.models import PaymentCurrency, PaymentFxRate

SETTLEMENT_CURRENCY = "TZS"
MONEY = Decimal("0.01")


class FxRateUnavailableError(Exception):
    """Raised when a requested listing currency cannot be converted to TZS."""


@dataclass(frozen=True)
class FxConversion:
    original_amount: Decimal
    original_currency: str
    settlement_amount: Decimal
    settlement_currency: str
    rate: Decimal
    rate_id: object | None
    effective_at: datetime | None
    source: str | None


def money(value: Decimal | int | float | str) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _normalise_currency(currency: str | None) -> str:
    return (currency or SETTLEMENT_CURRENCY).strip().upper()


def get_active_listing_rate(
    db: Session,
    currency: str,
    *,
    at: datetime | None = None,
) -> PaymentFxRate | None:
    code = _normalise_currency(currency)
    if code == SETTLEMENT_CURRENCY:
        return None

    at = at or datetime.now(timezone.utc)

    currency_row = (
        db.query(PaymentCurrency)
        .filter(
            PaymentCurrency.code == code,
            PaymentCurrency.is_active.is_(True),
        )
        .first()
    )
    if currency_row is None:
        raise FxRateUnavailableError(
            f"Currency {code} is not active for marketplace pricing"
        )

    rate = (
        db.query(PaymentFxRate)
        .filter(
            PaymentFxRate.base_currency == code,
            PaymentFxRate.quote_currency == SETTLEMENT_CURRENCY,
            PaymentFxRate.is_active.is_(True),
            PaymentFxRate.effective_at <= at,
        )
        .order_by(PaymentFxRate.effective_at.desc(), PaymentFxRate.created_at.desc())
        .first()
    )
    if rate is None:
        raise FxRateUnavailableError(
            f"No active {code}/{SETTLEMENT_CURRENCY} exchange rate is configured"
        )
    return rate


def convert_to_tzs(
    db: Session,
    amount: Decimal | int | float | str,
    currency: str | None,
    *,
    at: datetime | None = None,
) -> FxConversion:
    source_amount = Decimal(str(amount))
    code = _normalise_currency(currency)

    if code == SETTLEMENT_CURRENCY:
        return FxConversion(
            original_amount=source_amount,
            original_currency=SETTLEMENT_CURRENCY,
            settlement_amount=money(source_amount),
            settlement_currency=SETTLEMENT_CURRENCY,
            rate=Decimal("1"),
            rate_id=None,
            effective_at=None,
            source="Settlement currency",
        )

    rate = get_active_listing_rate(db, code, at=at)
    settlement = money(source_amount * Decimal(rate.rate))
    return FxConversion(
        original_amount=source_amount,
        original_currency=code,
        settlement_amount=settlement,
        settlement_currency=SETTLEMENT_CURRENCY,
        rate=Decimal(rate.rate),
        rate_id=rate.id,
        effective_at=rate.effective_at,
        source=rate.source,
    )


def convert_amount_to_tzs(
    db: Session,
    amount: Decimal | int | float | str,
    currency: str | None,
    *,
    at: datetime | None = None,
) -> Decimal:
    return convert_to_tzs(db, amount, currency, at=at).settlement_amount
