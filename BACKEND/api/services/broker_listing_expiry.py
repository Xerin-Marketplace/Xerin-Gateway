from __future__ import annotations

from datetime import datetime, timezone
from sqlalchemy.orm import Session

from api.models import Product, ProductStatus


def expire_broker_listings(db: Session, *, broker_id=None) -> int:
    now = datetime.now(timezone.utc)
    query = db.query(Product).filter(
        Product.listing_owner_type == "broker",
        Product.is_active.is_(True),
        Product.status == ProductStatus.approved,
        Product.listing_expires_at.isnot(None),
        Product.listing_expires_at <= now,
    )
    if broker_id is not None:
        query = query.filter(Product.broker_id == broker_id)
    rows = query.all()
    for row in rows:
        row.is_active = False
        row.status = ProductStatus.inactive
        row.listing_expired_at = now
    if rows:
        db.commit()
    return len(rows)
