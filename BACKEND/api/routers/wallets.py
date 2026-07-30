from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from api.deps import get_db,get_current_user
from api.permissions import require_permission
from api.enums import PermissionCode,PayoutStatus,WalletTransactionType
from api.models import User,SellerWallet,WalletTransaction,PayoutRequest,PayoutEvent
from api.schemas import SellerWalletResponse,WalletTransactionResponse,PayoutRequestCreate,PayoutRequestResponse,PayoutAdminUpdate,WalletAdjustmentCreate
from api.services.wallet_service import get_or_create_wallet,create_payout,transition_payout,money
router=APIRouter(prefix="/wallet",tags=["Seller Wallets"] )
def seller(user):
    if not user.seller_profile: raise HTTPException(403,"Seller profile required")
    return user.seller_profile
def commit(db):
    try: db.commit()
    except IntegrityError as e: db.rollback(); raise HTTPException(409,"Duplicate or conflicting wallet operation") from e
@router.get("/me",response_model=SellerWalletResponse)
def my_wallet(db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_read.value))):
    w=get_or_create_wallet(db,seller(current_user).id); commit(db); db.refresh(w); return w
@router.get("/me/transactions",response_model=list[WalletTransactionResponse])
def my_transactions(db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_read.value))):
    w=get_or_create_wallet(db,seller(current_user).id); return db.query(WalletTransaction).filter(WalletTransaction.wallet_id==w.id).order_by(WalletTransaction.created_at.desc()).all()
@router.post("/me/payouts",response_model=PayoutRequestResponse,status_code=201)
def request_payout(data:PayoutRequestCreate,db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_payout.value))):
    try:p=create_payout(db,seller_id=seller(current_user).id,payout_account_id=data.payout_account_id,amount=data.amount,note=data.note)
    except ValueError as e: db.rollback(); raise HTTPException(409,str(e))
    commit(db); db.refresh(p); return p
@router.get("/me/payouts",response_model=list[PayoutRequestResponse])
def my_payouts(db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_read.value))):
    return db.query(PayoutRequest).filter(PayoutRequest.seller_id==seller(current_user).id).order_by(PayoutRequest.requested_at.desc()).all()
@router.post("/me/payouts/{payout_id}/cancel",response_model=PayoutRequestResponse)
def cancel_payout(payout_id:UUID,db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_payout.value))):
    p=db.query(PayoutRequest).filter(PayoutRequest.id==payout_id,PayoutRequest.seller_id==seller(current_user).id).with_for_update().first()
    if not p: raise HTTPException(404,"Payout request not found")
    try:transition_payout(db,p,PayoutStatus.cancelled,user_id=current_user.id,note="Cancelled by seller")
    except ValueError as e: raise HTTPException(409,str(e))
    commit(db); db.refresh(p); return p
@router.get("/admin/wallets",response_model=list[SellerWalletResponse])
def all_wallets(db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_manage.value))): return db.query(SellerWallet).order_by(SellerWallet.created_at.desc()).all()
@router.get("/admin/payouts",response_model=list[PayoutRequestResponse])
def all_payouts(db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_manage.value))): return db.query(PayoutRequest).order_by(PayoutRequest.requested_at.desc()).all()
@router.patch("/admin/payouts/{payout_id}",response_model=PayoutRequestResponse)
def update_payout(payout_id:UUID,data:PayoutAdminUpdate,db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_manage.value))):
    p=db.query(PayoutRequest).filter(PayoutRequest.id==payout_id).with_for_update().first()
    if not p: raise HTTPException(404,"Payout request not found")
    try:transition_payout(db,p,data.status,user_id=current_user.id,note=data.note,provider_reference=data.provider_reference)
    except ValueError as e: raise HTTPException(409,str(e))
    commit(db); db.refresh(p); return p
@router.post("/admin/wallets/{seller_id}/adjustments",response_model=SellerWalletResponse)
def adjust(seller_id:UUID,data:WalletAdjustmentCreate,db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_adjust.value))):
    w=get_or_create_wallet(db,seller_id); amount=money(data.amount)
    if money(w.available_balance)+amount<0: raise HTTPException(409,"Adjustment would make balance negative")
    w.available_balance=money(w.available_balance)+amount
    db.add(WalletTransaction(wallet_id=w.id,transaction_type=WalletTransactionType.adjustment,amount=abs(amount),currency=w.currency,reference=f"adjustment:{UUID(bytes=__import__('os').urandom(16))}",description=data.reason))
    commit(db); db.refresh(w); return w
