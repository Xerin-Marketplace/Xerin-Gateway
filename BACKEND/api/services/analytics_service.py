from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.enums import PayoutStatus, RefundStatus, WalletTransactionType
from api.models import (
    MarketplaceTransaction,
    Order,
    OrderItem,
    OrderItemCommission,
    Payment,
    PaymentStatus,
    PayoutRequest,
    Product,
    Refund,
    RefundItem,
    Seller,
    SellerWallet,
    WalletTransaction,
)

ZERO = Decimal("0.00")


def money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"))


def resolve_range(start_at: datetime | None, end_at: datetime | None) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    end = end_at or now
    start = start_at or (end - timedelta(days=30))
    if start.tzinfo is None:
        start = start.replace(tzinfo=timezone.utc)
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    if start >= end:
        raise ValueError("start_at must be earlier than end_at")
    if end - start > timedelta(days=3660):
        raise ValueError("Date range cannot exceed 10 years")
    return start, end


def _scalar(db: Session, *entities, filters=()) -> tuple:
    return db.query(*entities).filter(*filters).one()


def admin_overview(db: Session, start: datetime, end: datetime) -> dict:
    order_filter = (Order.created_at >= start, Order.created_at < end)
    gross, order_count, avg_order = _scalar(
        db,
        func.coalesce(func.sum(Order.total), 0),
        func.count(Order.id),
        func.coalesce(func.avg(Order.total), 0),
        filters=order_filter,
    )
    paid_orders = db.query(func.count(func.distinct(Payment.order_id))).filter(
        Payment.status == PaymentStatus.completed,
        Payment.paid_at >= start,
        Payment.paid_at < end,
    ).scalar() or 0
    commission_gross, commission_amount, seller_net, units = _scalar(
        db,
        func.coalesce(func.sum(OrderItemCommission.gross_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.commission_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.seller_net_amount), 0),
        func.coalesce(func.sum(OrderItem.quantity), 0),
        filters=(
            OrderItemCommission.created_at >= start,
            OrderItemCommission.created_at < end,
            OrderItem.id == OrderItemCommission.order_item_id,
        ),
    )
    refunds, refunded_orders = _scalar(
        db,
        func.coalesce(func.sum(Refund.total_amount), 0),
        func.count(func.distinct(Refund.order_id)),
        filters=(Refund.status == RefundStatus.completed, Refund.completed_at >= start, Refund.completed_at < end),
    )
    payouts = db.query(func.coalesce(func.sum(PayoutRequest.amount), 0)).filter(
        PayoutRequest.status == PayoutStatus.completed,
        PayoutRequest.completed_at >= start,
        PayoutRequest.completed_at < end,
    ).scalar() or 0
    wallet = _scalar(
        db,
        func.coalesce(func.sum(SellerWallet.pending_balance), 0),
        func.coalesce(func.sum(SellerWallet.available_balance), 0),
        filters=(),
    )
    pending_payout = db.query(func.coalesce(func.sum(PayoutRequest.amount), 0)).filter(
        PayoutRequest.status.in_([PayoutStatus.pending, PayoutStatus.approved, PayoutStatus.processing])
    ).scalar() or 0
    active_sellers = db.query(func.count(Seller.id)).filter(Seller.status == "approved").scalar() or 0
    products = db.query(func.count(Product.id)).filter(Product.is_active.is_(True)).scalar() or 0
    refund_rate = (money(refunds) / money(gross) * 100) if money(gross) > 0 else ZERO
    return {
        "start_at": start,
        "end_at": end,
        "money": {
            "currency": "TZS",
            "gross_sales": money(commission_gross or gross),
            "commission_revenue": money(commission_amount),
            "seller_net_earnings": money(seller_net),
            "refunds_completed": money(refunds),
            "payouts_completed": money(payouts),
        },
        "counts": {
            "orders": int(order_count),
            "paid_orders": int(paid_orders),
            "refunded_orders": int(refunded_orders),
            "active_sellers": int(active_sellers),
            "products": int(products),
            "units_sold": int(units),
        },
        "average_order_value": money(avg_order),
        "refund_rate_percent": refund_rate.quantize(Decimal("0.01")),
        "pending_wallet_balance": money(wallet[0]),
        "available_wallet_balance": money(wallet[1]),
        "pending_payout_amount": money(pending_payout),
    }


def sales_series(db: Session, start: datetime, end: datetime, seller_id=None) -> list[dict]:
    period = func.date_trunc("day", OrderItemCommission.created_at)
    q = db.query(
        period.label("period"),
        func.coalesce(func.sum(OrderItemCommission.gross_amount), 0),
        func.count(func.distinct(OrderItemCommission.order_id)),
        func.coalesce(func.sum(OrderItem.quantity), 0),
    ).join(OrderItem, OrderItem.id == OrderItemCommission.order_item_id).filter(
        OrderItemCommission.created_at >= start,
        OrderItemCommission.created_at < end,
    )
    if seller_id is not None:
        q = q.filter(OrderItemCommission.seller_id == seller_id)
    rows = q.group_by(period).order_by(period).all()
    return [{"period": r[0].date().isoformat(), "amount": money(r[1]), "order_count": int(r[2]), "units": int(r[3])} for r in rows]


def seller_rankings(db: Session, start: datetime, end: datetime, limit: int = 20) -> list[dict]:
    rows = db.query(
        Seller.id,
        Seller.business_name,
        func.coalesce(func.sum(OrderItemCommission.gross_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.seller_net_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.commission_amount), 0),
        func.count(func.distinct(OrderItemCommission.order_id)),
        func.coalesce(func.sum(OrderItem.quantity), 0),
    ).join(OrderItemCommission, OrderItemCommission.seller_id == Seller.id).join(
        OrderItem, OrderItem.id == OrderItemCommission.order_item_id
    ).filter(OrderItemCommission.created_at >= start, OrderItemCommission.created_at < end).group_by(
        Seller.id, Seller.business_name
    ).order_by(func.sum(OrderItemCommission.gross_amount).desc()).limit(limit).all()
    refunds = dict(db.query(RefundItem.seller_id, func.coalesce(func.sum(RefundItem.refund_amount), 0)).join(
        Refund, Refund.id == RefundItem.refund_id
    ).filter(Refund.status == RefundStatus.completed, Refund.completed_at >= start, Refund.completed_at < end).group_by(RefundItem.seller_id).all())
    return [{"id": r[0], "name": r[1], "gross_sales": money(r[2]), "net_earnings": money(r[3]), "commission": money(r[4]), "refunds": money(refunds.get(r[0])), "order_count": int(r[5]), "units": int(r[6])} for r in rows]


def product_rankings(db: Session, start: datetime, end: datetime, seller_id=None, limit: int = 20) -> list[dict]:
    q = db.query(
        Product.id,
        Product.name,
        func.coalesce(func.sum(OrderItemCommission.gross_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.seller_net_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.commission_amount), 0),
        func.count(func.distinct(OrderItemCommission.order_id)),
        func.coalesce(func.sum(OrderItem.quantity), 0),
    ).join(OrderItem, OrderItem.product_id == Product.id).join(
        OrderItemCommission, OrderItemCommission.order_item_id == OrderItem.id
    ).filter(OrderItemCommission.created_at >= start, OrderItemCommission.created_at < end)
    if seller_id is not None:
        q = q.filter(Product.seller_id == seller_id)
    rows = q.group_by(Product.id, Product.name).order_by(func.sum(OrderItemCommission.gross_amount).desc()).limit(limit).all()
    return [{"id": r[0], "name": r[1], "gross_sales": money(r[2]), "net_earnings": money(r[3]), "commission": money(r[4]), "refunds": ZERO, "order_count": int(r[5]), "units": int(r[6])} for r in rows]


def seller_overview(db: Session, seller_id, start: datetime, end: datetime) -> dict:
    gross, commission, net, orders, units = _scalar(
        db,
        func.coalesce(func.sum(OrderItemCommission.gross_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.commission_amount), 0),
        func.coalesce(func.sum(OrderItemCommission.seller_net_amount), 0),
        func.count(func.distinct(OrderItemCommission.order_id)),
        func.coalesce(func.sum(OrderItem.quantity), 0),
        filters=(OrderItemCommission.seller_id == seller_id, OrderItemCommission.created_at >= start, OrderItemCommission.created_at < end, OrderItem.id == OrderItemCommission.order_item_id),
    )
    refunds = db.query(func.coalesce(func.sum(RefundItem.refund_amount), 0)).join(Refund, Refund.id == RefundItem.refund_id).filter(
        RefundItem.seller_id == seller_id, Refund.status == RefundStatus.completed, Refund.completed_at >= start, Refund.completed_at < end
    ).scalar() or 0
    wallet = db.query(SellerWallet).filter(SellerWallet.seller_id == seller_id).first()
    return {
        "start_at": start, "end_at": end,
        "money": {"currency": wallet.currency if wallet else "TZS", "gross_sales": money(gross), "commission_revenue": money(commission), "seller_net_earnings": money(net), "refunds_completed": money(refunds), "payouts_completed": money(wallet.paid_out_balance if wallet else 0)},
        "counts": {"orders": int(orders), "paid_orders": int(orders), "refunded_orders": 0, "active_sellers": 1, "products": db.query(func.count(Product.id)).filter(Product.seller_id == seller_id).scalar() or 0, "units_sold": int(units)},
        "average_order_value": money(net / orders if orders else 0), "refund_rate_percent": money(refunds / gross * 100 if gross else 0),
        "pending_wallet_balance": money(wallet.pending_balance if wallet else 0), "available_wallet_balance": money(wallet.available_balance if wallet else 0), "pending_payout_amount": money(wallet.reserved_balance if wallet else 0),
    }


def reconciliation(db: Session, start: datetime, end: datetime) -> dict:
    payments = db.query(func.coalesce(func.sum(Payment.amount), 0)).filter(Payment.status == PaymentStatus.completed, Payment.paid_at >= start, Payment.paid_at < end).scalar() or 0
    order_totals = db.query(func.coalesce(func.sum(Order.total), 0)).filter(Order.created_at >= start, Order.created_at < end, Order.status != "cancelled").scalar() or 0
    gross, commission, net = _scalar(db, func.coalesce(func.sum(OrderItemCommission.gross_amount),0), func.coalesce(func.sum(OrderItemCommission.commission_amount),0), func.coalesce(func.sum(OrderItemCommission.seller_net_amount),0), filters=(OrderItemCommission.created_at>=start, OrderItemCommission.created_at<end))
    refunds = db.query(func.coalesce(func.sum(Refund.total_amount),0)).filter(Refund.status==RefundStatus.completed, Refund.completed_at>=start, Refund.completed_at<end).scalar() or 0
    credits = db.query(func.coalesce(func.sum(WalletTransaction.amount),0)).filter(WalletTransaction.transaction_type==WalletTransactionType.sale_credit, WalletTransaction.created_at>=start, WalletTransaction.created_at<end).scalar() or 0
    payouts = db.query(func.coalesce(func.sum(PayoutRequest.amount),0)).filter(PayoutRequest.status==PayoutStatus.completed, PayoutRequest.completed_at>=start, PayoutRequest.completed_at<end).scalar() or 0
    d1=money(payments)-money(order_totals); d2=money(gross)-(money(commission)+money(net)); d3=money(net)-money(credits)
    return {"currency":"TZS","completed_payments":money(payments),"order_totals":money(order_totals),"commission_gross":money(gross),"commission_revenue":money(commission),"seller_net_earnings":money(net),"completed_refunds":money(refunds),"wallet_sale_credits":money(credits),"completed_payouts":money(payouts),"payment_order_difference":d1,"commission_split_difference":d2,"seller_credit_difference":d3,"is_balanced":abs(d1)<=Decimal('0.01') and abs(d2)<=Decimal('0.01') and abs(d3)<=Decimal('0.01')}
