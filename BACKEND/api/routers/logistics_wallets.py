from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.enums import LogisticsCompanyPermission, LogisticsMemberRole, PermissionCode
from api.models import LogisticsCompanyUser, LogisticsPayoutAccount, LogisticsPayoutRequest, LogisticsWallet, LogisticsWalletTransaction, User
from api.permissions import require_permission
from api.schemas import (LogisticsPayoutAccountCreate, LogisticsPayoutAccountResponse, LogisticsPayoutAccountUpdate, LogisticsPayoutAccountVerification, LogisticsPayoutAdminUpdate, LogisticsPayoutRequestCreate, LogisticsPayoutRequestResponse, LogisticsWalletAdjustmentCreate, LogisticsWalletResponse, PaginatedLogisticsPayoutResponse, PaginatedLogisticsWalletTransactionResponse)
from api.services.logistics_wallet_service import create_logistics_payout, get_or_create_logistics_wallet, money, transition_logistics_payout

router = APIRouter(prefix="/logistics/wallet", tags=["Logistics Wallets"])

ROLE_PERMISSIONS = {
    LogisticsMemberRole.company_admin: set(LogisticsCompanyPermission),
    LogisticsMemberRole.operations_manager: {LogisticsCompanyPermission.profile_manage, LogisticsCompanyPermission.dashboard_read},
    LogisticsMemberRole.viewer: {LogisticsCompanyPermission.dashboard_read},
}


def commit(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Duplicate or conflicting logistics wallet operation") from exc


def membership(db, user, permission):
    row = db.query(LogisticsCompanyUser).filter(LogisticsCompanyUser.user_id == user.id, LogisticsCompanyUser.is_active.is_(True)).first()
    if row is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Active logistics company membership required")
    permissions = set(LogisticsCompanyPermission) if row.is_primary_contact else set(ROLE_PERMISSIONS.get(row.member_role, set()))
    for value in row.permissions_json or []:
        try:
            permissions.add(LogisticsCompanyPermission(value))
        except ValueError:
            pass
    if permission not in permissions:
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"Company permission denied. Required: {permission.value}")
    return row


@router.get("/me", response_model=LogisticsWalletResponse)
def my_wallet(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.dashboard_read)
    wallet = get_or_create_logistics_wallet(db, member.logistics_company_id)
    commit(db); db.refresh(wallet); return wallet


@router.get("/me/transactions", response_model=PaginatedLogisticsWalletTransactionResponse)
def transactions(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.dashboard_read)
    wallet = get_or_create_logistics_wallet(db, member.logistics_company_id)
    query = db.query(LogisticsWalletTransaction).filter(LogisticsWalletTransaction.wallet_id == wallet.id)
    total = query.count(); rows = query.order_by(LogisticsWalletTransaction.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": 0 if total == 0 else (total+page_size-1)//page_size, "results": rows}


@router.get("/me/payout-accounts", response_model=list[LogisticsPayoutAccountResponse])
def accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.dashboard_read)
    return db.query(LogisticsPayoutAccount).filter(LogisticsPayoutAccount.logistics_company_id == member.logistics_company_id).order_by(LogisticsPayoutAccount.created_at.desc()).all()


@router.post("/me/payout-accounts", response_model=LogisticsPayoutAccountResponse, status_code=201)
def create_account(data: LogisticsPayoutAccountCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.profile_manage)
    if data.is_default:
        db.query(LogisticsPayoutAccount).filter(LogisticsPayoutAccount.logistics_company_id == member.logistics_company_id).update({LogisticsPayoutAccount.is_default: False})
    account = LogisticsPayoutAccount(logistics_company_id=member.logistics_company_id, **data.model_dump())
    db.add(account); commit(db); db.refresh(account); return account


@router.patch("/me/payout-accounts/{account_id}", response_model=LogisticsPayoutAccountResponse)
def update_account(account_id: UUID, data: LogisticsPayoutAccountUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.profile_manage)
    account = db.query(LogisticsPayoutAccount).filter(LogisticsPayoutAccount.id == account_id, LogisticsPayoutAccount.logistics_company_id == member.logistics_company_id).first()
    if account is None: raise HTTPException(404, "Payout account not found")
    changes = data.model_dump(exclude_unset=True)
    if any(key in changes for key in {"provider", "account_name", "account_number", "currency"}):
        changes.update(verification_status="pending", verified_at=None, verification_note=None)
    if changes.get("is_default"):
        db.query(LogisticsPayoutAccount).filter(LogisticsPayoutAccount.logistics_company_id == member.logistics_company_id).update({LogisticsPayoutAccount.is_default: False})
    for key, value in changes.items(): setattr(account, key, value)
    commit(db); db.refresh(account); return account


@router.post("/me/payouts", response_model=LogisticsPayoutRequestResponse, status_code=201)
def request_payout(data: LogisticsPayoutRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.profile_manage)
    try: payout = create_logistics_payout(db, company_id=member.logistics_company_id, account_id=data.payout_account_id, amount=data.amount, note=data.note)
    except ValueError as exc: db.rollback(); raise HTTPException(409, str(exc)) from exc
    commit(db); db.refresh(payout); return payout


@router.get("/me/payouts", response_model=PaginatedLogisticsPayoutResponse)
def payouts(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.dashboard_read)
    query = db.query(LogisticsPayoutRequest).filter(LogisticsPayoutRequest.logistics_company_id == member.logistics_company_id)
    total=query.count(); rows=query.order_by(LogisticsPayoutRequest.requested_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":0 if total==0 else (total+page_size-1)//page_size,"results":rows}


@router.post("/me/payouts/{payout_id}/cancel", response_model=LogisticsPayoutRequestResponse)
def cancel(payout_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    member = membership(db, current_user, LogisticsCompanyPermission.profile_manage)
    payout = db.query(LogisticsPayoutRequest).filter(LogisticsPayoutRequest.id == payout_id, LogisticsPayoutRequest.logistics_company_id == member.logistics_company_id).with_for_update().first()
    if payout is None: raise HTTPException(404, "Payout request not found")
    try: transition_logistics_payout(db, payout, "cancelled", user_id=current_user.id, note="Cancelled by logistics company")
    except ValueError as exc: raise HTTPException(409, str(exc)) from exc
    commit(db); db.refresh(payout); return payout


@router.patch("/admin/payout-accounts/{account_id}/verification", response_model=LogisticsPayoutAccountResponse)
def verify_account(account_id: UUID, data: LogisticsPayoutAccountVerification, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.payouts_approve.value))):
    account = db.query(LogisticsPayoutAccount).filter(LogisticsPayoutAccount.id == account_id).first()
    if account is None: raise HTTPException(404, "Payout account not found")
    account.verification_status=data.status; account.verification_note=data.note; account.verified_at=datetime.now(timezone.utc) if data.status == "verified" else None
    commit(db); db.refresh(account); return account


@router.patch("/admin/payouts/{payout_id}", response_model=LogisticsPayoutRequestResponse)
def update_payout(payout_id: UUID, data: LogisticsPayoutAdminUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.payouts_approve.value))):
    payout=db.query(LogisticsPayoutRequest).filter(LogisticsPayoutRequest.id==payout_id).with_for_update().first()
    if payout is None: raise HTTPException(404,"Payout request not found")
    try: transition_logistics_payout(db,payout,data.status,user_id=current_user.id,note=data.note,provider_reference=data.provider_reference)
    except ValueError as exc: raise HTTPException(409,str(exc)) from exc
    commit(db); db.refresh(payout); return payout


@router.post("/admin/wallets/{company_id}/adjustments", response_model=LogisticsWalletResponse)
def adjust(company_id: UUID, data: LogisticsWalletAdjustmentCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.wallet_adjust.value))):
    wallet=get_or_create_logistics_wallet(db,company_id); amount=money(data.amount)
    if money(wallet.available_balance)+amount < 0: raise HTTPException(409,"Adjustment would make available balance negative")
    wallet.available_balance=money(wallet.available_balance)+amount
    db.add(LogisticsWalletTransaction(wallet_id=wallet.id,transaction_type="adjustment",amount=abs(amount),currency=wallet.currency,reference=f"logistics_adjustment:{uuid4()}",description=data.reason))
    commit(db); db.refresh(wallet); return wallet
