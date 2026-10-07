from __future__ import annotations
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from sqlalchemy import func
from sqlalchemy.orm import Session
from api.models import (User, Seller, Product, Order, Payment, Refund, ProductQuestion,
                        QuestionReport, NotificationDelivery, SearchTerm, ProductView,
                        SystemAlert)


def date_window(period: str, start_at: datetime | None, end_at: datetime | None):
    now = datetime.now(timezone.utc)
    if start_at or end_at:
        return start_at or now - timedelta(days=30), end_at or now
    days = {"today": 1, "7d": 7, "30d": 30}.get(period, 30)
    return now - timedelta(days=days), now


def _count(db: Session, model, *criteria):
    q = db.query(func.count(model.id))
    if criteria: q = q.filter(*criteria)
    return int(q.scalar() or 0)


def summary(db: Session, start: datetime, end: datetime) -> dict:
    orders = db.query(Order).filter(Order.created_at >= start, Order.created_at <= end)
    gmv = orders.with_entities(func.coalesce(func.sum(Order.total), 0)).scalar() or Decimal("0")
    return {
        "period": {"start": start, "end": end},
        "gmv": str(gmv),
        "orders": int(orders.count()),
        "customers": _count(db, User),
        "active_sellers": _count(db, Seller, Seller.status == "approved"),
        "pending_sellers": _count(db, Seller, Seller.status.in_(["pending", "under_review"])),
        "approved_products": _count(db, Product, Product.status == "approved"),
        "pending_products": _count(db, Product, Product.status == "pending_review"),
        "failed_payments": _count(db, Payment, Payment.status == "failed"),
        "pending_refunds": _count(db, Refund, Refund.status.in_(["requested", "under_review", "approved"])),
        "unresolved_question_reports": _count(db, QuestionReport, QuestionReport.resolved.is_(False)),
        "failed_notifications": _count(db, NotificationDelivery, NotificationDelivery.status == "failed"),
        "open_alerts": _count(db, SystemAlert, SystemAlert.is_resolved.is_(False)),
    }


def status_breakdown(db: Session, model, status_column, created_column, start, end):
    rows = (db.query(status_column, func.count(model.id)).filter(created_column >= start, created_column <= end)
            .group_by(status_column).all())
    return {str(getattr(status, "value", status)): int(count) for status, count in rows}


def top_searches(db: Session, limit: int = 10):
    rows = db.query(SearchTerm).order_by(SearchTerm.search_count.desc()).limit(limit).all()
    return [{"term": r.term, "search_count": r.search_count, "click_count": r.result_click_count} for r in rows]


def most_viewed(db: Session, limit: int = 10):
    rows = (db.query(ProductView.product_id, func.count(ProductView.id).label("views"))
            .group_by(ProductView.product_id).order_by(func.count(ProductView.id).desc()).limit(limit).all())
    return [{"product_id": str(pid), "views": int(views)} for pid, views in rows]
