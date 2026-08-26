from __future__ import annotations

from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import func
from sqlalchemy.orm import Session

from api.config import settings
from api.models import (
    BrokerCommission,
    BrokerPayoutAccount,
    BrokerPayoutEvent,
    BrokerPayoutRequest,
    BrokerWallet,
    BrokerWalletTransaction,
)

MONEY = Decimal("0.01")
ALLOWED_PAYOUT_TRANSITIONS = {
    "pending": {"approved", "rejected", "cancelled"},
    "approved": {"processing", "rejected", "cancelled"},
    "processing": {"completed", "failed"},
    "completed": set(),
    "failed": set(),
    "rejected": set(),
    "cancelled": set(),
}
RELEASE_RESERVATION_STATUSES = {"failed", "rejected", "cancelled"}


def money(value) -> Decimal:
    return Decimal(value or 0).quantize(MONEY, rounding=ROUND_HALF_UP)


def get_or_create_broker_wallet(db: Session, broker_id, currency: str = "TZS") -> BrokerWallet:
    wallet = db.query(BrokerWallet).filter(BrokerWallet.broker_id == broker_id).with_for_update().first()
    if wallet is None:
        wallet = BrokerWallet(broker_id=broker_id, currency=(currency or "TZS").upper())
        db.add(wallet)
        db.flush()
    return wallet


def _tx(db: Session, reference: str):
    return db.query(BrokerWalletTransaction).filter(BrokerWalletTransaction.reference == reference).first()


def _add_tx(db: Session, *, wallet, broker_id, tx_type, amount, reference, commission_id=None, payout_request_id=None, description=None):
    existing = _tx(db, reference)
    if existing:
        return existing
    row = BrokerWalletTransaction(
        wallet_id=wallet.id,
        broker_id=broker_id,
        commission_id=commission_id,
        payout_request_id=payout_request_id,
        transaction_type=tx_type,
        amount=money(amount),
        currency=wallet.currency,
        reference=reference,
        description=description,
    )
    db.add(row)
    db.flush()
    return row


def sync_commission_to_wallet(db: Session, commission: BrokerCommission) -> BrokerWallet:
    """Idempotently project a B5 commission into the B6 wallet ledger.

    This also backfills B5 commission rows created before the B6 migration.
    """
    wallet = get_or_create_broker_wallet(db, commission.broker_id, commission.currency)
    total = money(commission.amount)
    reversed_total = money(commission.reversed_amount)

    pending_ref = f"broker_commission_pending:{commission.id}"
    if _tx(db, pending_ref) is None:
        wallet.pending_balance = money(wallet.pending_balance) + total
        _add_tx(
            db, wallet=wallet, broker_id=commission.broker_id,
            tx_type="commission_pending", amount=total, reference=pending_ref,
            commission_id=commission.id,
            description="Broker commission received and held pending escrow release",
        )

    reversal_ref = f"broker_commission_reversal:{commission.id}"
    reversal_tx = _tx(db, reversal_ref)
    recorded_reversal = money(reversal_tx.amount) if reversal_tx else Decimal("0.00")
    reversal_delta = money(max(Decimal("0.00"), reversed_total - recorded_reversal))

    release_ref = f"broker_commission_release:{commission.id}"
    release_tx = _tx(db, release_ref)

    if reversal_delta > 0:
        if release_tx is None:
            wallet.pending_balance = max(Decimal("0.00"), money(wallet.pending_balance) - reversal_delta)
        else:
            available = money(wallet.available_balance)
            deducted = min(available, reversal_delta)
            wallet.available_balance = money(available - deducted)
            shortfall = money(reversal_delta - deducted)
            if shortfall > 0:
                wallet.debt_balance = money(wallet.debt_balance) + shortfall
        wallet.reversed_balance = money(wallet.reversed_balance) + reversal_delta
        if reversal_tx is None:
            reversal_tx = _add_tx(
                db, wallet=wallet, broker_id=commission.broker_id,
                tx_type="commission_reversal", amount=reversed_total, reference=reversal_ref,
                commission_id=commission.id,
                description="Commission reversed because of refund/cancellation",
            )
        else:
            reversal_tx.amount = reversed_total

    net = max(Decimal("0.00"), money(total - reversed_total))
    releasable = commission.available_at is not None or commission.status in {"available", "partially_reversed"}
    if releasable and release_tx is None and net > 0:
        movable = min(money(wallet.pending_balance), net)
        wallet.pending_balance = money(wallet.pending_balance) - movable
        # For a normal ledger movable == net. If a historic state is inconsistent,
        # debt is not hidden; only actually held funds are made available.
        wallet.available_balance = money(wallet.available_balance) + movable
        _add_tx(
            db, wallet=wallet, broker_id=commission.broker_id,
            tx_type="commission_release", amount=movable, reference=release_ref,
            commission_id=commission.id,
            description="Commission released from escrow into available Broker balance",
        )

    db.flush()
    return wallet


def sync_all_broker_commissions(db: Session, *, broker_id) -> BrokerWallet:
    commissions = db.query(BrokerCommission).filter(BrokerCommission.broker_id == broker_id).order_by(BrokerCommission.created_at.asc()).all()
    currency = commissions[-1].currency if commissions else "TZS"
    wallet = get_or_create_broker_wallet(db, broker_id, currency)
    for commission in commissions:
        wallet = sync_commission_to_wallet(db, commission)
    return wallet


def create_broker_payout(db: Session, *, broker_id, payout_account_id, amount, note=None, idempotency_key=None) -> BrokerPayoutRequest:
    wallet = sync_all_broker_commissions(db, broker_id=broker_id)
    amount = money(amount)
    if wallet.is_frozen:
        raise ValueError("Broker wallet is frozen")
    minimum = money(getattr(settings, "MINIMUM_PAYOUT_AMOUNT", 0) or 0)
    if minimum > 0 and amount < minimum:
        raise ValueError(f"Amount is below the minimum payout of {minimum} {wallet.currency}")
    account = db.query(BrokerPayoutAccount).filter(
        BrokerPayoutAccount.id == payout_account_id,
        BrokerPayoutAccount.broker_id == broker_id,
        BrokerPayoutAccount.is_active.is_(True),
    ).first()
    if account is None:
        raise ValueError("Active payout account was not found")
    if account.verification_status != "verified":
        raise ValueError("Payout account must be verified")
    if account.currency.upper() != wallet.currency.upper():
        raise ValueError("Payout account currency does not match the Broker wallet")
    if money(wallet.debt_balance) > 0:
        raise ValueError("Outstanding Broker wallet debt must be cleared before payout")
    if money(wallet.available_balance) < amount:
        raise ValueError("Insufficient available balance")

    # B8 payout-abuse controls.  The wallet row is already locked, so these
    # checks are concurrency-safe across API workers.
    now = datetime.now(timezone.utc)
    open_count = db.query(BrokerPayoutRequest).filter(
        BrokerPayoutRequest.broker_id == broker_id,
        BrokerPayoutRequest.status.in_(["pending", "approved", "processing"]),
    ).count()
    if open_count >= 3:
        raise ValueError("Too many payout requests are already in progress")
    duplicate_cutoff = now - timedelta(minutes=10)
    duplicate = db.query(BrokerPayoutRequest).filter(
        BrokerPayoutRequest.broker_id == broker_id,
        BrokerPayoutRequest.payout_account_id == payout_account_id,
        BrokerPayoutRequest.amount == amount,
        BrokerPayoutRequest.requested_at >= duplicate_cutoff,
        BrokerPayoutRequest.status.in_(["pending", "approved", "processing", "completed"]),
    ).first()
    if duplicate is not None:
        raise ValueError("A matching payout was already requested recently")

    wallet.available_balance = money(wallet.available_balance) - amount
    wallet.reserved_balance = money(wallet.reserved_balance) + amount
    payout = BrokerPayoutRequest(
        wallet_id=wallet.id,
        broker_id=broker_id,
        payout_account_id=payout_account_id,
        amount=amount,
        currency=wallet.currency,
        status="pending",
        broker_note=note,
        idempotency_key=idempotency_key,
    )
    db.add(payout)
    db.flush()
    db.add(BrokerPayoutEvent(payout_request_id=payout.id, status="pending", note="Payout requested"))
    _add_tx(
        db, wallet=wallet, broker_id=broker_id, tx_type="payout_hold", amount=amount,
        reference=f"broker_payout_hold:{payout.id}", payout_request_id=payout.id,
        description="Available funds reserved for Broker payout",
    )
    return payout


def transition_broker_payout(db: Session, payout: BrokerPayoutRequest, new_status: str, *, user_id=None, note=None, provider_reference=None) -> BrokerPayoutRequest:
    current = str(payout.status)
    new_status = str(new_status)
    if new_status not in ALLOWED_PAYOUT_TRANSITIONS.get(current, set()):
        raise ValueError(f"Invalid payout transition: {current} -> {new_status}")
    wallet = db.query(BrokerWallet).filter(BrokerWallet.id == payout.wallet_id).with_for_update().one()
    amount = money(payout.amount)
    now = datetime.now(timezone.utc)

    if new_status == "completed":
        if money(wallet.reserved_balance) < amount:
            raise ValueError("Reserved Broker balance is inconsistent")
        wallet.reserved_balance = money(wallet.reserved_balance) - amount
        wallet.paid_out_balance = money(wallet.paid_out_balance) + amount
        payout.completed_at = now
        _add_tx(db, wallet=wallet, broker_id=payout.broker_id, tx_type="payout_completed", amount=amount,
                reference=f"broker_payout_completed:{payout.id}", payout_request_id=payout.id,
                description="Broker payout completed")
    elif new_status in RELEASE_RESERVATION_STATUSES:
        if money(wallet.reserved_balance) < amount:
            raise ValueError("Reserved Broker balance is inconsistent")
        wallet.reserved_balance = money(wallet.reserved_balance) - amount
        wallet.available_balance = money(wallet.available_balance) + amount
        _add_tx(db, wallet=wallet, broker_id=payout.broker_id, tx_type="payout_released", amount=amount,
                reference=f"broker_payout_released:{payout.id}", payout_request_id=payout.id,
                description="Broker payout reservation released")

    payout.status = new_status
    payout.admin_note = note or payout.admin_note
    payout.provider_reference = provider_reference or payout.provider_reference
    payout.processed_at = now
    db.add(BrokerPayoutEvent(payout_request_id=payout.id, status=new_status, note=note, created_by_id=user_id))
    db.flush()
    return payout
