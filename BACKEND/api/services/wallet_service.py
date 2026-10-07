from datetime import datetime, timezone, timedelta
from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session
from api.config import settings
from api.enums import WalletTransactionType, PayoutStatus
from api.models import SellerWallet, WalletTransaction, PayoutRequest, PayoutEvent, SellerPayoutAccount
MONEY=Decimal("0.01")
def money(v): return Decimal(v).quantize(MONEY, rounding=ROUND_HALF_UP)
def get_or_create_wallet(db:Session,seller_id,currency="TZS"):
    w=db.query(SellerWallet).filter(SellerWallet.seller_id==seller_id).with_for_update().first()
    if not w:
        w=SellerWallet(seller_id=seller_id,currency=currency); db.add(w); db.flush()
    return w
def credit_sale(db:Session,*,seller_id,amount,currency,order_id,order_item_id):
    ref=f"sale_credit:{order_item_id}"
    existing=db.query(WalletTransaction).filter(WalletTransaction.reference==ref).first()
    if existing:return existing
    w=get_or_create_wallet(db,seller_id,currency); amount=money(amount)
    debt_offset=min(money(w.debt_balance), amount)
    if debt_offset:
        w.debt_balance=money(w.debt_balance)-debt_offset
        amount=money(amount)-debt_offset
    w.pending_balance=money(w.pending_balance)+amount
    tx=WalletTransaction(wallet_id=w.id,transaction_type=WalletTransactionType.sale_credit,amount=amount,currency=currency,reference=ref,order_id=order_id,order_item_id=order_item_id,eligible_at=datetime.now(timezone.utc)+timedelta(days=settings.SELLER_SETTLEMENT_DAYS),description="Seller earning pending settlement")
    db.add(tx); db.flush(); return tx
def release_eligible_funds(db:Session,limit=500):
    now=datetime.now(timezone.utc); rows=db.query(WalletTransaction).filter(WalletTransaction.transaction_type==WalletTransactionType.sale_credit,WalletTransaction.released_at.is_(None),WalletTransaction.eligible_at<=now).order_by(WalletTransaction.eligible_at).with_for_update(skip_locked=True).limit(limit).all(); count=0
    for tx in rows:
        w=db.query(SellerWallet).filter(SellerWallet.id==tx.wallet_id).with_for_update().one(); amount=money(tx.amount)
        if money(w.pending_balance)<amount: continue
        w.pending_balance=money(w.pending_balance)-amount; w.available_balance=money(w.available_balance)+amount; tx.released_at=now
        db.add(WalletTransaction(wallet_id=w.id,transaction_type=WalletTransactionType.funds_release,amount=amount,currency=w.currency,reference=f"funds_release:{tx.id}",order_id=tx.order_id,order_item_id=tx.order_item_id,released_at=now,description="Settlement funds released")); count+=1
    return count
def create_payout(db:Session,*,seller_id,payout_account_id,amount,note=None):
    w=get_or_create_wallet(db,seller_id); amount=money(amount)
    if w.is_frozen: raise ValueError("Wallet is frozen")
    if amount < money(settings.MINIMUM_PAYOUT_AMOUNT): raise ValueError("Amount is below the minimum payout")
    account=db.query(SellerPayoutAccount).filter(SellerPayoutAccount.id==payout_account_id,SellerPayoutAccount.seller_id==seller_id).first()
    if not account: raise ValueError("Payout account not found")
    if money(w.available_balance)<amount: raise ValueError("Insufficient available balance")
    w.available_balance=money(w.available_balance)-amount; w.reserved_balance=money(w.reserved_balance)+amount
    p=PayoutRequest(wallet_id=w.id,seller_id=seller_id,payout_account_id=payout_account_id,amount=amount,currency=w.currency,status=PayoutStatus.pending,seller_note=note); db.add(p); db.flush()
    db.add(PayoutEvent(payout_request_id=p.id,status=PayoutStatus.pending,note="Payout requested")); db.add(WalletTransaction(wallet_id=w.id,transaction_type=WalletTransactionType.payout_hold,amount=amount,currency=w.currency,reference=f"payout_hold:{p.id}",payout_request_id=p.id,description="Funds reserved for payout")); return p
def transition_payout(db:Session,payout,status,*,user_id=None,note=None,provider_reference=None):
    allowed={PayoutStatus.pending:{PayoutStatus.approved,PayoutStatus.rejected,PayoutStatus.cancelled},PayoutStatus.approved:{PayoutStatus.processing,PayoutStatus.rejected},PayoutStatus.processing:{PayoutStatus.completed,PayoutStatus.failed}}
    if status not in allowed.get(payout.status,set()): raise ValueError(f"Invalid payout transition: {payout.status.value} -> {status.value}")
    w=db.query(SellerWallet).filter(SellerWallet.id==payout.wallet_id).with_for_update().one(); amount=money(payout.amount); now=datetime.now(timezone.utc)
    if status==PayoutStatus.completed:
        if money(w.reserved_balance)<amount: raise ValueError("Reserved balance is inconsistent")
        w.reserved_balance=money(w.reserved_balance)-amount; w.paid_out_balance=money(w.paid_out_balance)+amount; payout.completed_at=now
        db.add(WalletTransaction(wallet_id=w.id,transaction_type=WalletTransactionType.payout_completed,amount=amount,currency=w.currency,reference=f"payout_completed:{payout.id}",payout_request_id=payout.id,description="Payout completed"))
    elif status in {PayoutStatus.rejected,PayoutStatus.failed,PayoutStatus.cancelled}:
        if money(w.reserved_balance)<amount: raise ValueError("Reserved balance is inconsistent")
        w.reserved_balance=money(w.reserved_balance)-amount; w.available_balance=money(w.available_balance)+amount
        db.add(WalletTransaction(wallet_id=w.id,transaction_type=WalletTransactionType.payout_released,amount=amount,currency=w.currency,reference=f"payout_released:{payout.id}",payout_request_id=payout.id,description="Payout hold released"))
    payout.status=status; payout.admin_note=note or payout.admin_note; payout.provider_reference=provider_reference or payout.provider_reference; payout.processed_at=now
    db.add(PayoutEvent(payout_request_id=payout.id,status=status,note=note,created_by_id=user_id)); return payout


def debit_refund(db: Session, *, seller_id, amount, currency, refund_id, refund_item_id, order_id, order_item_id):
    """Reverse seller funds safely. Any uncovered amount becomes recoverable seller debt."""
    ref=f"refund_debit:{refund_item_id}"
    existing=db.query(WalletTransaction).filter(WalletTransaction.reference==ref).first()
    if existing:
        return existing, Decimal("0.00")
    wallet=get_or_create_wallet(db,seller_id,currency)
    remaining=money(amount)
    for field in ("pending_balance", "available_balance", "reserved_balance"):
        balance=money(getattr(wallet,field))
        take=min(balance,remaining)
        setattr(wallet,field,money(balance-take))
        remaining=money(remaining-take)
        if remaining == 0:
            break
    debt=remaining
    if debt:
        wallet.debt_balance=money(wallet.debt_balance)+debt
    wallet.refunded_balance=money(wallet.refunded_balance)+money(amount)
    tx=WalletTransaction(wallet_id=wallet.id,transaction_type=WalletTransactionType.refund_debit,amount=money(amount),currency=currency,reference=ref,order_id=order_id,order_item_id=order_item_id,description=f"Seller earning reversed for refund {refund_id}; debt created: {debt}")
    db.add(tx); db.flush()
    return tx,debt
