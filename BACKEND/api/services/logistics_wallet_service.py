from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from api.config import settings
from api.models import (
    LogisticsPayoutAccount,
    LogisticsPayoutEvent,
    LogisticsPayoutRequest,
    LogisticsWallet,
    LogisticsWalletTransaction,
    Order,
)

MONEY = Decimal("0.01")
TERMINAL_RELEASE_STATUSES = {"rejected", "failed", "cancelled"}
ALLOWED_PAYOUT_TRANSITIONS = {
    "pending": {"approved", "rejected", "cancelled"},
    "approved": {"processing", "rejected"},
    "processing": {"completed", "failed"},
}


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def get_or_create_logistics_wallet(db: Session, company_id, currency="TZS"):
    wallet = db.query(LogisticsWallet).filter(LogisticsWallet.logistics_company_id == company_id).with_for_update().first()
    if wallet is None:
        wallet = LogisticsWallet(logistics_company_id=company_id, currency=currency)
        db.add(wallet)
        db.flush()
    if wallet.currency != currency:
        raise ValueError("Logistics wallet currency does not match the order currency")
    return wallet


def credit_order_delivery_entitlement(db: Session, *, order: Order):
    """Hold one logistics entitlement after captured online payment.

    Platform-funded shipping discounts do not reduce the carrier entitlement,
    therefore the pre-discount shipping snapshot is preferred.
    """
    if not order.logistics_company_id:
        return None
    reference = f"logistics_delivery_credit:{order.id}"
    existing = db.query(LogisticsWalletTransaction).filter(LogisticsWalletTransaction.reference == reference).first()
    if existing:
        return existing
    amount = money(order.original_shipping_amount)
    if amount <= 0:
        amount = money(order.shipping_amount)
    if amount <= 0:
        return None
    wallet = get_or_create_logistics_wallet(db, order.logistics_company_id, order.currency)
    gross_amount = amount
    debt_offset = min(money(wallet.debt_balance), amount)
    if debt_offset:
        wallet.debt_balance = money(wallet.debt_balance) - debt_offset
        amount = money(amount) - debt_offset
        db.add(LogisticsWalletTransaction(
            wallet_id=wallet.id, transaction_type="debt_recovery", amount=debt_offset,
            currency=wallet.currency, reference=f"logistics_debt_recovery:{order.id}",
            order_id=order.id, description="Prior logistics debt recovered from delivery earning",
        ))
    wallet.pending_balance = money(wallet.pending_balance) + amount
    transaction = LogisticsWalletTransaction(
        wallet_id=wallet.id,
        transaction_type="delivery_credit",
        amount=gross_amount,
        currency=wallet.currency,
        reference=reference,
        order_id=order.id,
        description="Delivery entitlement held until verified delivery",
    )
    db.add(transaction)
    db.flush()
    return transaction


def debit_order_delivery_entitlement(db: Session, *, order: Order, refund_id):
    """Reverse a carrier entitlement once, preserving active payout reserves."""
    reference = f"logistics_refund_debit:{refund_id}"
    existing = db.query(LogisticsWalletTransaction).filter(LogisticsWalletTransaction.reference == reference).first()
    if existing:
        return existing, Decimal("0.00")
    credit = db.query(LogisticsWalletTransaction).filter(
        LogisticsWalletTransaction.order_id == order.id,
        LogisticsWalletTransaction.transaction_type == "delivery_credit",
    ).first()
    if credit is None:
        return None, Decimal("0.00")
    wallet = db.query(LogisticsWallet).filter(LogisticsWallet.id == credit.wallet_id).with_for_update().one()
    already_reversed = sum((money(row.amount) for row in db.query(LogisticsWalletTransaction).filter(
        LogisticsWalletTransaction.order_id == order.id,
        LogisticsWalletTransaction.transaction_type == "refund_debit",
    ).all()), Decimal("0.00"))
    amount = money(max(Decimal("0.00"), money(credit.amount) - money(already_reversed)))
    remaining = amount
    for field in ("pending_balance", "available_balance"):
        balance = money(getattr(wallet, field))
        taken = min(balance, remaining)
        setattr(wallet, field, money(balance - taken))
        remaining = money(remaining - taken)
    if remaining:
        wallet.debt_balance = money(wallet.debt_balance) + remaining
    wallet.refunded_balance = money(wallet.refunded_balance) + amount
    transaction = LogisticsWalletTransaction(
        wallet_id=wallet.id, transaction_type="refund_debit", amount=amount,
        currency=wallet.currency, reference=reference, order_id=order.id,
        description=f"Delivery entitlement reversed for refund {refund_id}; debt created: {remaining}",
    )
    db.add(transaction)
    db.flush()
    return transaction, remaining


def create_logistics_payout(db: Session, *, company_id, account_id, amount, note=None):
    wallet = get_or_create_logistics_wallet(db, company_id)
    amount = money(amount)
    if wallet.is_frozen:
        raise ValueError("Logistics wallet is frozen")
    if amount < money(settings.MINIMUM_PAYOUT_AMOUNT):
        raise ValueError("Amount is below the minimum payout")
    account = db.query(LogisticsPayoutAccount).filter(
        LogisticsPayoutAccount.id == account_id,
        LogisticsPayoutAccount.logistics_company_id == company_id,
        LogisticsPayoutAccount.is_active.is_(True),
    ).first()
    if account is None:
        raise ValueError("Active payout account was not found")
    if account.verification_status != "verified":
        raise ValueError("Payout account must be verified")
    if account.currency != wallet.currency:
        raise ValueError("Payout account currency does not match the wallet")
    if money(wallet.available_balance) < amount:
        raise ValueError("Insufficient available balance")
    wallet.available_balance = money(wallet.available_balance) - amount
    wallet.reserved_balance = money(wallet.reserved_balance) + amount
    payout = LogisticsPayoutRequest(
        wallet_id=wallet.id, logistics_company_id=company_id,
        payout_account_id=account_id, amount=amount, currency=wallet.currency,
        status="pending", company_note=note,
    )
    db.add(payout)
    db.flush()
    db.add(LogisticsPayoutEvent(payout_request_id=payout.id, status="pending", note="Payout requested"))
    db.add(LogisticsWalletTransaction(
        wallet_id=wallet.id, transaction_type="payout_hold", amount=amount,
        currency=wallet.currency, reference=f"logistics_payout_hold:{payout.id}",
        payout_request_id=payout.id, description="Funds reserved for logistics payout",
    ))
    return payout


def transition_logistics_payout(db: Session, payout, new_status, *, user_id=None, note=None, provider_reference=None):
    current = str(payout.status)
    if new_status not in ALLOWED_PAYOUT_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid payout transition: {current} -> {new_status}")
    wallet = db.query(LogisticsWallet).filter(LogisticsWallet.id == payout.wallet_id).with_for_update().one()
    amount = money(payout.amount)
    now = datetime.now(timezone.utc)
    if new_status == "completed":
        if money(wallet.reserved_balance) < amount:
            raise ValueError("Reserved balance is inconsistent")
        wallet.reserved_balance = money(wallet.reserved_balance) - amount
        wallet.paid_out_balance = money(wallet.paid_out_balance) + amount
        payout.completed_at = now
        db.add(LogisticsWalletTransaction(wallet_id=wallet.id, transaction_type="payout_completed", amount=amount, currency=wallet.currency, reference=f"logistics_payout_completed:{payout.id}", payout_request_id=payout.id, description="Logistics payout completed"))
    elif new_status in TERMINAL_RELEASE_STATUSES:
        if money(wallet.reserved_balance) < amount:
            raise ValueError("Reserved balance is inconsistent")
        wallet.reserved_balance = money(wallet.reserved_balance) - amount
        wallet.available_balance = money(wallet.available_balance) + amount
        db.add(LogisticsWalletTransaction(wallet_id=wallet.id, transaction_type="payout_released", amount=amount, currency=wallet.currency, reference=f"logistics_payout_released:{payout.id}", payout_request_id=payout.id, description="Logistics payout reservation released"))
    payout.status = new_status
    payout.admin_note = note or payout.admin_note
    payout.provider_reference = provider_reference or payout.provider_reference
    payout.processed_at = now
    db.add(LogisticsPayoutEvent(payout_request_id=payout.id, status=new_status, note=note, created_by_id=user_id))
    return payout
