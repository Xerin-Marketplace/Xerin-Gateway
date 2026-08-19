"""Immutable whole-order financial reconciliation snapshots."""

import hashlib
import json
from decimal import Decimal

from sqlalchemy.orm import Session

from api.enums import MarketplaceTransactionType, PaymentStatus, RefundStatus, WalletTransactionType
from api.models import (
    EscrowHold, FinancialReconciliationEvent, FinancialReconciliationRecord,
    LogisticsWalletTransaction, MarketplaceTransaction, Order,
    OrderItemCommission, Payment, Refund, WalletTransaction,
)

MONEY = Decimal("0.01")


def money(value):
    return Decimal(value or 0).quantize(MONEY)


def total(rows, attribute="amount"):
    return money(sum((money(getattr(row, attribute)) for row in rows), Decimal("0.00")))


def build_order_snapshot(db: Session, order: Order):
    payments = db.query(Payment).filter(Payment.order_id == order.id, Payment.status == PaymentStatus.completed).all()
    commissions = db.query(OrderItemCommission).filter(OrderItemCommission.order_id == order.id).all()
    holds = db.query(EscrowHold).filter(EscrowHold.order_id == order.id).all()
    refunds = db.query(Refund).filter(Refund.order_id == order.id, Refund.status == RefundStatus.completed).all()
    seller_rows = db.query(WalletTransaction).filter(WalletTransaction.order_id == order.id).all()
    logistics_rows = db.query(LogisticsWalletTransaction).filter(LogisticsWalletTransaction.order_id == order.id).all()
    marketplace_rows = db.query(MarketplaceTransaction).filter(MarketplaceTransaction.order_id == order.id).all()

    seller_credits = [row for row in seller_rows if row.transaction_type == WalletTransactionType.sale_credit]
    seller_refunds = [row for row in seller_rows if row.transaction_type == WalletTransactionType.refund_debit]
    seller_debt_recoveries = [row for row in seller_rows if row.reference.startswith("debt_recovery:")]
    logistics_credits = [row for row in logistics_rows if row.transaction_type == "delivery_credit"]
    logistics_refunds = [row for row in logistics_rows if row.transaction_type == "refund_debit"]
    commission_reversals = [row for row in marketplace_rows if row.transaction_type == MarketplaceTransactionType.commission_reversal]

    values = {
        "order_total": money(order.total),
        "captured_payment_total": total(payments),
        "seller_entitlement_total": total(commissions, "seller_net_amount"),
        "seller_credit_total": total(seller_credits),
        "seller_refund_debit_total": total(seller_refunds),
        "seller_debt_recovery_total": total(seller_debt_recoveries),
        "commission_total": total(commissions, "commission_amount"),
        "commission_reversal_total": total(commission_reversals),
        "escrow_gross_total": total(holds, "gross_amount"),
        "escrow_released_total": total(holds, "released_amount"),
        "escrow_refunded_total": total(holds, "refunded_amount"),
        "customer_refund_total": total(refunds, "total_amount"),
        "logistics_entitlement_total": total(logistics_credits),
        "logistics_refund_debit_total": total(logistics_refunds),
    }
    findings = []
    if payments and values["captured_payment_total"] != values["order_total"]:
        findings.append("Captured payment total does not equal the order total")
    if payments and len(commissions) != len(order.items):
        findings.append("Commission snapshot count does not equal order item count")
    if values["seller_credit_total"] + values["seller_debt_recovery_total"] != values["seller_entitlement_total"]:
        findings.append("Seller wallet credits do not equal seller commission entitlements")
    if values["commission_reversal_total"] > values["commission_total"]:
        findings.append("Commission reversals exceed original commission")
    if values["seller_refund_debit_total"] > values["seller_entitlement_total"]:
        findings.append("Seller refund debits exceed seller entitlement")
    if values["escrow_released_total"] + values["escrow_refunded_total"] > values["escrow_gross_total"]:
        findings.append("Escrow is over-settled")
    if values["logistics_refund_debit_total"] > values["logistics_entitlement_total"]:
        findings.append("Logistics reversals exceed delivery entitlement")
    for refund in refunds:
        if any(item.processed_at is None for item in refund.items):
            findings.append(f"Completed refund {refund.id} contains an unprocessed item")

    snapshot = {"order_id": str(order.id), "currency": order.currency, **{key: str(value) for key, value in values.items()},
        "counts": {"payments": len(payments), "commissions": len(commissions), "escrow_holds": len(holds), "refunds": len(refunds), "seller_transactions": len(seller_rows), "logistics_transactions": len(logistics_rows)}}
    return snapshot, findings


def create_reconciliation(db: Session, *, order: Order, idempotency_key: str, user_id=None):
    existing = db.query(FinancialReconciliationRecord).filter(FinancialReconciliationRecord.idempotency_key == idempotency_key).first()
    if existing:
        if existing.order_id != order.id:
            raise ValueError("Idempotency key belongs to another order")
        return existing
    snapshot, findings = build_order_snapshot(db, order)
    canonical = json.dumps({"snapshot": snapshot, "findings": findings}, sort_keys=True, separators=(",", ":"))
    record = FinancialReconciliationRecord(order_id=order.id, idempotency_key=idempotency_key, currency=order.currency,
        status="exception" if findings else "balanced", snapshot=snapshot, findings=findings,
        snapshot_hash=hashlib.sha256(canonical.encode()).hexdigest(), created_by_id=user_id)
    db.add(record); db.flush()
    db.add(FinancialReconciliationEvent(reconciliation_id=record.id, action="created", note="Immutable reconciliation snapshot created", created_by_id=user_id))
    return record


def add_resolution_event(db: Session, *, record, action: str, note: str, user_id=None):
    event = FinancialReconciliationEvent(record=record, action=action, note=note, created_by_id=user_id)
    db.add(event); db.flush(); return event
