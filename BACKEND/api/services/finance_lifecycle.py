"""Read-only financial lifecycle reconciliation for marketplace orders."""

from decimal import Decimal
from sqlalchemy.orm import Session

from api.enums import RefundStatus, WalletTransactionType
from api.models import (
    EscrowHold,
    Order,
    OrderItemCommission,
    Payment,
    PaymentStatus,
    Refund,
    WalletTransaction,
    LogisticsWalletTransaction,
)

MONEY = Decimal("0.01")


def _money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY)


def order_finance_lifecycle(db: Session, order: Order) -> dict:
    payments = db.query(Payment).filter(Payment.order_id == order.id).all()
    commissions = db.query(OrderItemCommission).filter(OrderItemCommission.order_id == order.id).all()
    holds = db.query(EscrowHold).filter(EscrowHold.order_id == order.id).all()
    refunds = db.query(Refund).filter(Refund.order_id == order.id).all()
    wallet_rows = db.query(WalletTransaction).filter(WalletTransaction.order_id == order.id).all()
    logistics_rows = db.query(LogisticsWalletTransaction).filter(LogisticsWalletTransaction.order_id == order.id).all()

    completed_payments = [row for row in payments if row.status == PaymentStatus.completed]
    completed_refunds = [row for row in refunds if row.status == RefundStatus.completed]
    blockers: list[str] = []
    if completed_payments and len(commissions) != len(order.items):
        blockers.append("Completed payment does not have one commission snapshot per order item")
    if holds and len(holds) != len(commissions):
        blockers.append("Escrow allocation count does not match commission snapshot count")
    for hold in holds:
        if _money(hold.released_amount) + _money(hold.refunded_amount) > _money(hold.gross_amount):
            blockers.append(f"Escrow hold {hold.id} is over-settled")
    for refund in completed_refunds:
        if any(item.processed_at is None for item in refund.items):
            blockers.append(f"Completed refund {refund.id} has unprocessed items")

    payment_total = sum((_money(row.amount) for row in completed_payments), Decimal("0.00"))
    commission_total = sum((_money(row.commission_amount) for row in commissions), Decimal("0.00"))
    seller_total = sum((_money(row.seller_net_amount) for row in commissions), Decimal("0.00"))
    escrow_held = sum((_money(row.gross_amount) for row in holds), Decimal("0.00"))
    escrow_released = sum((_money(row.released_amount) for row in holds), Decimal("0.00"))
    escrow_refunded = sum((_money(row.refunded_amount) for row in holds), Decimal("0.00"))
    refund_total = sum((_money(row.total_amount) for row in completed_refunds), Decimal("0.00"))
    wallet_sale_credits = sum((_money(row.amount) for row in wallet_rows if row.transaction_type == WalletTransactionType.sale_credit), Decimal("0.00"))
    wallet_releases = sum((_money(row.amount) for row in wallet_rows if row.transaction_type == WalletTransactionType.funds_release), Decimal("0.00"))
    wallet_refunds = sum((_money(row.amount) for row in wallet_rows if row.transaction_type == WalletTransactionType.refund_debit), Decimal("0.00"))
    logistics_credits = sum((_money(row.amount) for row in logistics_rows if row.transaction_type == "delivery_credit"), Decimal("0.00"))
    logistics_refunds = sum((_money(row.amount) for row in logistics_rows if row.transaction_type == "refund_debit"), Decimal("0.00"))

    return {
        "order_id": order.id,
        "currency": order.currency,
        "order_total": _money(order.total),
        "completed_payment_total": _money(payment_total),
        "commission_total": _money(commission_total),
        "seller_net_total": _money(seller_total),
        "escrow_gross_total": _money(escrow_held),
        "escrow_released_total": _money(escrow_released),
        "escrow_refunded_total": _money(escrow_refunded),
        "completed_refund_total": _money(refund_total),
        "wallet_sale_credit_total": _money(wallet_sale_credits),
        "wallet_release_total": _money(wallet_releases),
        "wallet_refund_debit_total": _money(wallet_refunds),
        "logistics_delivery_credit_total": _money(logistics_credits),
        "logistics_refund_debit_total": _money(logistics_refunds),
        "payment_count": len(payments),
        "commission_count": len(commissions),
        "escrow_hold_count": len(holds),
        "refund_count": len(refunds),
        "wallet_transaction_count": len(wallet_rows),
        "logistics_transaction_count": len(logistics_rows),
        "balanced": not blockers,
        "blockers": blockers,
    }
