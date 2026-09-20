from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any
from sqlalchemy.orm import Session

from api.config import settings
from api.models import BrokerRiskEvent, BrokerWallet


def fingerprint_ip(ip_address: str | None) -> str | None:
    if not ip_address:
        return None
    secret = str(getattr(settings, "SECRET_KEY", "xerin-broker-risk"))
    return hashlib.sha256(f"{secret}:{ip_address.strip()}".encode("utf-8")).hexdigest()


def record_broker_risk(
    db: Session,
    *,
    event_type: str,
    severity: str = "warning",
    broker_id=None,
    user_id=None,
    ip_hash: str | None = None,
    resource_type: str | None = None,
    resource_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> BrokerRiskEvent:
    event = BrokerRiskEvent(
        broker_id=broker_id,
        user_id=user_id,
        event_type=event_type,
        severity=severity,
        status="open",
        ip_hash=ip_hash,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details or {},
    )
    db.add(event)
    db.flush()
    return event


def freeze_broker_wallet(db: Session, *, broker_id, frozen: bool) -> BrokerWallet | None:
    wallet = db.query(BrokerWallet).filter(BrokerWallet.broker_id == broker_id).with_for_update().first()
    if wallet is not None:
        wallet.is_frozen = bool(frozen)
        db.flush()
    return wallet


def resolve_broker_risk(db: Session, event: BrokerRiskEvent, *, resolved_by_id, note: str | None = None) -> BrokerRiskEvent:
    event.status = "resolved"
    event.resolved_by_id = resolved_by_id
    event.resolved_at = datetime.now(timezone.utc)
    if note:
        details = dict(event.details or {})
        details["resolution_note"] = note
        event.details = details
    db.flush()
    return event
