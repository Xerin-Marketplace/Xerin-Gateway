from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter,Depends,HTTPException,status,Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from api.deps import get_db,get_current_user
from api.permissions import require_permission
from api.enums import PermissionCode,PayoutStatus,WalletTransactionType
from api.models import User,SellerWallet,WalletTransaction,PayoutRequest,PayoutEvent,SellerPayoutAccount,FinanceSettings
from api.schemas import SellerWalletResponse,WalletTransactionResponse,PayoutRequestCreate,PayoutRequestResponse,PayoutAdminUpdate,WalletAdjustmentCreate,PaginatedWalletTransactionResponse,PaginatedPayoutRequestResponse
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
@router.get("/me/transactions",response_model=PaginatedWalletTransactionResponse)
def my_transactions(
    page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
    db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_read.value))
):
    w=get_or_create_wallet(db,seller(current_user).id)
    q=db.query(WalletTransaction).filter(WalletTransaction.wallet_id==w.id)
    total=q.count(); rows=q.order_by(WalletTransaction.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":0 if total==0 else (total+page_size-1)//page_size,"results":rows}
@router.post("/me/payouts",response_model=PayoutRequestResponse,status_code=201)
def request_payout(data:PayoutRequestCreate,db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_payout.value))):
    seller_row=seller(current_user)
    account=db.query(SellerPayoutAccount).filter(
        SellerPayoutAccount.id==data.payout_account_id,
        SellerPayoutAccount.seller_id==seller_row.id,
        SellerPayoutAccount.is_active.is_(True),
    ).first()
    if not account: raise HTTPException(404,"Active payout account not found")
    if account.verification_status!="verified": raise HTTPException(409,"Payout account must be verified before requesting payout")
    finance=db.query(FinanceSettings).filter(FinanceSettings.singleton_key=="default").first()
    if finance and data.amount < finance.minimum_payout_amount:
        raise HTTPException(409,f"Minimum payout amount is {finance.minimum_payout_amount} {finance.settlement_currency}")
    try:p=create_payout(db,seller_id=seller_row.id,payout_account_id=data.payout_account_id,amount=data.amount,note=data.note)
    except ValueError as e: db.rollback(); raise HTTPException(409,str(e))
    commit(db); db.refresh(p); return p
@router.get("/me/payouts",response_model=PaginatedPayoutRequestResponse)
def my_payouts(
    page:int=Query(1,ge=1),page_size:int=Query(20,ge=1,le=100),
    db:Session=Depends(get_db),current_user:User=Depends(require_permission(PermissionCode.wallet_read.value))
):
    q=db.query(PayoutRequest).filter(PayoutRequest.seller_id==seller(current_user).id)
    total=q.count(); rows=q.order_by(PayoutRequest.requested_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":0 if total==0 else (total+page_size-1)//page_size,"results":rows}
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
