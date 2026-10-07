"""Live FX rate fetching with DB caching.

Admin enables a currency; the backend automatically fetches the TZS rate
from a free public FX feed and caches it in ``fx_rates`` (refreshed when
the cached rate is older than 24h). If the feed is unreachable, the last
known rate is reused.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging

import requests
from sqlalchemy.orm import Session

from api.models import FxRate

logger = logging.getLogger(__name__)

FX_API_URL = "https://open.er-api.com/v6/latest/TZS"
CACHE_MAX_AGE = timedelta(hours=24)
TIMEOUT_SECONDS = 10


def _fetch_tzs_rates() -> dict[str, float]:
    resp = requests.get(FX_API_URL, timeout=TIMEOUT_SECONDS)
    resp.raise_for_status()
    data = resp.json()
    rates = data.get("rates")
    if not isinstance(rates, dict):
        raise ValueError("FX feed returned no rates")
    return rates


def _latest_rate(db: Session, code: str) -> FxRate | None:
    return (
        db.query(FxRate)
        .filter(FxRate.base_currency == code, FxRate.is_active.is_(True))
        .order_by(FxRate.effective_at.desc())
        .first()
    )


def rate_to_tzs(db: Session, code: str) -> Decimal | None:
    """Return 1 <code> = rate TZS. Refreshes from the live feed when stale."""
    cached = _latest_rate(db, code)
    fresh = cached and cached.effective_at and (
        cached.effective_at
        if cached.effective_at.tzinfo
        else cached.effective_at.replace(tzinfo=timezone.utc)
    ) > datetime.now(timezone.utc) - CACHE_MAX_AGE

    if fresh:
        return Decimal(str(cached.rate))

    try:
        rates = _fetch_tzs_rates()
    except Exception as exc:  # feed down — keep last known rate
        logger.warning("FX feed unavailable for %s: %s", code, exc)
        return Decimal(str(cached.rate)) if cached else None

    units = rates.get(code.upper())
    if not units or units <= 0:
        return Decimal(str(cached.rate)) if cached else None

    rate = Decimal(str(1.0 / float(units)))  # units = code per 1 TZS
    db.add(FxRate(base_currency=code.upper(), quote_currency="TZS",
                  rate=rate, source="open.er-api.com"))
    db.commit()
    return rate
