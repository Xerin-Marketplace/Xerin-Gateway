import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional

from api.config import settings
from api.deps import get_db, get_current_user
from api.enums import PermissionCode
from decimal import Decimal

from fastapi import Header
from api.models import (
    Broker,
    BrokerKycDocument,
    BrokerStatus,
    BrokerWallet,
    BrokerWalletTransaction,
    BrokerPayoutAccount,
    BrokerPayoutRequest,
    PayoutStatus,
    User,
)
from api.permissions import require_permission
from api.schemas import canonical_account_number

router = APIRouter(prefix="/brokers", tags=["Brokers"])

REQUIRED_KYC_DOCS = ["national_id", "profile_photo", "selfie"]
ALLOWED_DOC_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _serialize_broker(broker: Broker, user: User | None = None):
    u = user or broker.user
    return {
        "id": str(broker.id),
        "user_id": str(broker.user_id),
        "broker_code": broker.broker_code,
        "first_name": getattr(u, "first_name", None),
        "last_name": getattr(u, "last_name", None),
        "email": getattr(u, "email", None),
        "phone": getattr(u, "phone", None),
        "country": broker.country,
        "region": broker.region,
        "city": broker.city,
        "nida_number": broker.nida_number,
        "status": broker.status.value if broker.status else None,
        "approved_at": broker.approved_at.isoformat() if broker.approved_at else None,
        "rejected_at": broker.rejected_at.isoformat() if broker.rejected_at else None,
        "suspended_at": broker.suspended_at.isoformat() if broker.suspended_at else None,
        "status_reason": broker.status_reason,
        "created_at": broker.created_at.isoformat() if broker.created_at else None,
    }


def _serialize_doc(doc: BrokerKycDocument):
    return {
        "id": str(doc.id),
        "broker_id": str(doc.broker_id),
        "document_type": doc.document_type,
        "original_filename": doc.original_filename,
        "mime_type": doc.mime_type,
        "status": doc.status,
        "rejection_reason": doc.rejection_reason,
        "reviewed_at": doc.reviewed_at.isoformat() if doc.reviewed_at else None,
        "created_at": doc.created_at.isoformat() if doc.created_at else None,
    }


def _get_my_broker(db: Session, user: User) -> Broker:
    broker = db.query(Broker).filter(Broker.user_id == user.id).first()
    if broker is None:
        raise HTTPException(status_code=404, detail="No Winga profile found for this account.")
    return broker


def _kyc_status(db: Session, broker: Broker) -> dict:
    docs = db.query(BrokerKycDocument).filter(BrokerKycDocument.broker_id == broker.id).all()
    uploaded = [d.document_type for d in docs if d.status != "rejected"]
    missing = [t for t in REQUIRED_KYC_DOCS if t not in uploaded]
    approved = broker.status == BrokerStatus.approved
    return {
        "broker_status": broker.status.value if broker.status else None,
        "required_documents": REQUIRED_KYC_DOCS,
        "uploaded_documents": uploaded,
        "missing_documents": missing,
        "can_submit_for_review": not missing and broker.status in (BrokerStatus.pending_kyc, BrokerStatus.rejected),
        "can_use_broker_features": approved,
    }


class BrokerUpdateRequest(BaseModel):
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    nida_number: Optional[str] = None


@router.get("/me")
def get_my_broker(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _serialize_broker(_get_my_broker(db, current_user))


@router.patch("/me")
def update_my_broker(
    data: BrokerUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    for field in ("country", "region", "city", "nida_number"):
        value = getattr(data, field)
        if value is not None:
            setattr(broker, field, value.strip() or None)
    db.commit()
    db.refresh(broker)
    return _serialize_broker(broker)


@router.get("/kyc-status")
def kyc_status(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _kyc_status(db, _get_my_broker(db, current_user))


@router.get("/kyc-documents")
def list_kyc_documents(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _get_my_broker(db, current_user)
    docs = (
        db.query(BrokerKycDocument)
        .filter(BrokerKycDocument.broker_id == broker.id)
        .order_by(BrokerKycDocument.created_at.desc())
        .all()
    )
    return {"results": [_serialize_doc(d) for d in docs]}


@router.post("/kyc-documents")
async def upload_kyc_document(
    document_type: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    if document_type not in REQUIRED_KYC_DOCS:
        raise HTTPException(status_code=422, detail=f"document_type must be one of {REQUIRED_KYC_DOCS}")
    if broker.status in (BrokerStatus.approved, BrokerStatus.under_review):
        raise HTTPException(status_code=409, detail="Documents can only be uploaded while KYC is pending.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Document must not exceed {settings.MAX_UPLOAD_SIZE_MB} MB")

    mime = (file.content_type or "").lower()
    if mime.startswith("image/"):
        # Verify it is a real image through PIL — same pipeline as product images.
        try:
            from PIL import Image, UnidentifiedImageError

            with Image.open(io.BytesIO(raw)) as probe:
                detected = (probe.format or "").upper()
                probe.verify()
            if detected not in {"JPEG", "PNG", "WEBP"}:
                raise HTTPException(status_code=400, detail="Only JPEG, PNG or WEBP images are allowed")
            mime = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}[detected]
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(status_code=400, detail="The uploaded file is not a valid image")
        ext = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}[mime]
    elif mime == "application/pdf" and raw[:4] == b"%PDF":
        ext = ".pdf"
    else:
        raise HTTPException(status_code=400, detail="Only image files (JPEG/PNG/WEBP) or PDF are allowed")

    target_dir = settings.upload_path / "broker-kyc" / str(broker.id)
    target_dir.mkdir(parents=True, exist_ok=True)
    file_name = f"{uuid.uuid4()}{ext}"
    (target_dir / file_name).write_bytes(raw)
    stored_path = f"broker-kyc/{broker.id}/{file_name}"

    # Replace any existing doc of the same type.
    db.query(BrokerKycDocument).filter(
        BrokerKycDocument.broker_id == broker.id,
        BrokerKycDocument.document_type == document_type,
    ).delete()

    doc = BrokerKycDocument(
        broker_id=broker.id,
        document_type=document_type,
        document_path=stored_path,
        original_filename=file.filename,
        mime_type=mime,
        status="pending",
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return _serialize_doc(doc)


@router.delete("/kyc-documents/{document_id}")
def delete_kyc_document(
    document_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    doc = (
        db.query(BrokerKycDocument)
        .filter(BrokerKycDocument.id == document_id, BrokerKycDocument.broker_id == broker.id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    try:
        (settings.upload_path / doc.document_path).unlink(missing_ok=True)
    except OSError:
        pass
    db.delete(doc)
    db.commit()
    return {"message": "Document deleted"}


@router.post("/submit-kyc")
def submit_kyc(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _get_my_broker(db, current_user)
    if not broker.nida_number:
        raise HTTPException(
            status_code=422, detail="Add your national ID (NIDA) number first."
        )
    payout_accounts = (
        db.query(BrokerPayoutAccount)
        .filter(
            BrokerPayoutAccount.broker_id == broker.id,
            BrokerPayoutAccount.is_active.is_(True),
        )
        .count()
    )
    if payout_accounts == 0:
        raise HTTPException(
            status_code=422,
            detail="Add a payout account (mobile money or bank) before submitting KYC.",
        )
    status = _kyc_status(db, broker)
    if status["missing_documents"]:
        raise HTTPException(
            status_code=422,
            detail=f"Missing required documents: {', '.join(status['missing_documents'])}",
        )
    if broker.status not in (BrokerStatus.pending_kyc, BrokerStatus.rejected):
        return _serialize_broker(broker)
    broker.status = BrokerStatus.kyc_submitted
    broker.status_reason = None
    db.commit()
    db.refresh(broker)
    return _serialize_broker(broker)


# ---------------------------------------------------------------------------
# Admin endpoints — reuse the seller review permissions.
# ---------------------------------------------------------------------------

ADMIN_VIEW = require_permission(PermissionCode.can_view_sellers.value)
ADMIN_APPROVE = require_permission(PermissionCode.can_approve_sellers.value)


@router.get("/admin")
def admin_list_brokers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: Optional[str] = None,
    search: Optional[str] = None,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_VIEW),
):
    query = db.query(Broker).join(User, Broker.user_id == User.id)
    if status:
        try:
            query = query.filter(Broker.status == BrokerStatus(status))
        except ValueError:
            pass
    if search:
        like = f"%{search}%"
        query = query.filter(
            (Broker.broker_code.ilike(like))
            | (User.email.ilike(like))
            | (User.first_name.ilike(like))
            | (User.last_name.ilike(like))
        )
    total = query.count()
    rows = (
        query.order_by(Broker.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "results": [_serialize_broker(b) for b in rows],
    }


def _admin_get_broker(db: Session, broker_id: str) -> Broker:
    broker = db.query(Broker).filter(Broker.id == broker_id).first()
    if not broker:
        raise HTTPException(status_code=404, detail="Broker not found")
    return broker


@router.get("/admin/{broker_id}/documents")
def admin_list_broker_documents(
    broker_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_VIEW),
):
    broker = _admin_get_broker(db, broker_id)
    docs = db.query(BrokerKycDocument).filter(BrokerKycDocument.broker_id == broker.id).all()
    return [_serialize_doc(d) for d in docs]


@router.get("/admin/{broker_id}/documents/{doc_id}/view")
def admin_view_broker_document(
    broker_id: str,
    doc_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_VIEW),
):
    doc = (
        db.query(BrokerKycDocument)
        .filter(BrokerKycDocument.id == doc_id, BrokerKycDocument.broker_id == broker_id)
        .first()
    )
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    path = settings.upload_path / doc.document_path
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Stored file is missing")
    return FileResponse(path, media_type=doc.mime_type or "application/octet-stream")


class AdminStatusRequest(BaseModel):
    reason: Optional[str] = None


@router.post("/admin/{broker_id}/start-review")
def admin_start_review(broker_id: str, db: Session = Depends(get_db), _: User = Depends(ADMIN_APPROVE)):
    broker = _admin_get_broker(db, broker_id)
    if broker.status == BrokerStatus.kyc_submitted:
        broker.status = BrokerStatus.under_review
        db.commit()
        db.refresh(broker)
    return _serialize_broker(broker)


@router.post("/admin/{broker_id}/approve")
def admin_approve_broker(
    broker_id: str,
    data: AdminStatusRequest = AdminStatusRequest(),
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    broker = _admin_get_broker(db, broker_id)
    broker.status = BrokerStatus.approved
    broker.status_reason = data.reason
    broker.approved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(broker)
    return _serialize_broker(broker)


@router.post("/admin/{broker_id}/reject")
def admin_reject_broker(
    broker_id: str,
    data: AdminStatusRequest,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    broker = _admin_get_broker(db, broker_id)
    broker.status = BrokerStatus.rejected
    broker.status_reason = data.reason
    broker.rejected_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(broker)
    return _serialize_broker(broker)


@router.post("/admin/{broker_id}/suspend")
def admin_suspend_broker(
    broker_id: str,
    data: AdminStatusRequest,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    broker = _admin_get_broker(db, broker_id)
    broker.status = BrokerStatus.suspended
    broker.status_reason = data.reason
    broker.suspended_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(broker)
    return _serialize_broker(broker)


# ---------------------------------------------------------------------------
# Wallet & payouts — real ledger-backed implementation.
# ---------------------------------------------------------------------------

def _serialize_wallet(w: BrokerWallet) -> dict:
    f = lambda v: str(Decimal(v or 0))
    return {
        "id": str(w.id),
        "broker_id": str(w.broker_id),
        "currency": w.currency,
        "pending_balance": f(w.pending_balance),
        "available_balance": f(w.available_balance),
        "reserved_balance": f(w.reserved_balance),
        "paid_out_balance": f(w.paid_out_balance),
        "reversed_balance": f(w.reversed_balance),
        "debt_balance": f(w.debt_balance),
        "is_frozen": bool(w.is_frozen),
        "created_at": w.created_at.isoformat() if w.created_at else None,
        "updated_at": w.updated_at.isoformat() if w.updated_at else None,
    }


def _serialize_tx(t: BrokerWalletTransaction) -> dict:
    return {
        "id": str(t.id),
        "wallet_id": str(t.wallet_id),
        "broker_id": str(t.broker_id),
        "commission_id": None,
        "payout_request_id": str(t.payout_request_id) if t.payout_request_id else None,
        "transaction_type": t.transaction_type,
        "amount": str(t.amount),
        "currency": t.currency,
        "reference": t.reference,
        "description": t.description,
        "created_at": t.created_at.isoformat() if t.created_at else None,
    }


def _serialize_account(a: BrokerPayoutAccount) -> dict:
    return {
        "id": str(a.id),
        "broker_id": str(a.broker_id),
        "account_type": a.account_type,
        "provider": a.provider,
        "account_name": a.account_name,
        "account_number": a.account_number,
        "currency": a.currency,
        "is_default": bool(a.is_default),
        "is_active": bool(a.is_active),
        "verification_status": a.verification_status,
        "verification_note": a.verification_note,
        "verified_at": a.verified_at.isoformat() if a.verified_at else None,
        "created_at": a.created_at.isoformat() if a.created_at else None,
        "updated_at": a.updated_at.isoformat() if a.updated_at else None,
    }


def _serialize_payout(p: BrokerPayoutRequest) -> dict:
    return {
        "id": str(p.id),
        "wallet_id": str(p.wallet_id),
        "broker_id": str(p.broker_id),
        "payout_account_id": str(p.payout_account_id),
        "amount": str(p.amount),
        "currency": p.currency,
        "status": p.status.value if p.status else "pending",
        "provider_reference": p.provider_reference,
        "broker_note": p.broker_note,
        "admin_note": p.admin_note,
        "requested_at": p.requested_at.isoformat() if p.requested_at else None,
        "processed_at": p.processed_at.isoformat() if p.processed_at else None,
        "completed_at": p.completed_at.isoformat() if p.completed_at else None,
    }


def _wallet_for(db: Session, broker: Broker) -> BrokerWallet:
    wallet = db.query(BrokerWallet).filter(BrokerWallet.broker_id == broker.id).first()
    if wallet is None:
        wallet = BrokerWallet(broker_id=broker.id)
        db.add(wallet)
        db.commit()
        db.refresh(wallet)
    return wallet


def _ledger(db: Session, wallet: BrokerWallet, tx_type: str, amount: Decimal,
            description: str, payout_request_id=None) -> None:
    db.add(BrokerWalletTransaction(
        wallet_id=wallet.id,
        broker_id=wallet.broker_id,
        transaction_type=tx_type,
        amount=amount,
        currency=wallet.currency,
        reference=f"TX-{uuid.uuid4().hex[:10].upper()}",
        description=description,
        payout_request_id=payout_request_id,
    ))


@router.get("/products")
def broker_products(current_user: User = Depends(get_current_user)):
    _ = current_user
    return []


@router.get("/opportunities")
def broker_opportunities(current_user: User = Depends(get_current_user)):
    _ = current_user
    return []


@router.get("/accepted-opportunities")
def broker_accepted_opportunities(current_user: User = Depends(get_current_user)):
    _ = current_user
    return []


@router.get("/commissions")
def broker_commissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return _empty_page(page, page_size)


@router.get("/commissions/summary")
def broker_commission_summary(current_user: User = Depends(get_current_user)):
    _ = current_user
    return {
        "currency": "TZS",
        "pending_amount": "0",
        "available_amount": "0",
        "reversed_amount": "0",
        "lifetime_commission": "0",
        "total_records": 0,
    }


@router.get("/wallet")
def broker_wallet(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return _serialize_wallet(_wallet_for(db, _get_my_broker(db, current_user)))


@router.get("/wallet/transactions")
def broker_wallet_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = _wallet_for(db, _get_my_broker(db, current_user))
    query = db.query(BrokerWalletTransaction).filter(BrokerWalletTransaction.wallet_id == wallet.id)
    total = query.count()
    rows = query.order_by(BrokerWalletTransaction.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "results": [_serialize_tx(t) for t in rows],
    }


class PayoutAccountIn(BaseModel):
    account_type: str
    provider: str = Field(min_length=2, max_length=100)
    account_name: str = Field(min_length=2, max_length=255)
    account_number: str = Field(min_length=4, max_length=100)
    currency: str = "TZS"
    is_default: bool = False


@router.get("/payout-accounts")
def broker_payout_accounts(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    broker = _get_my_broker(db, current_user)
    rows = (
        db.query(BrokerPayoutAccount)
        .filter(BrokerPayoutAccount.broker_id == broker.id, BrokerPayoutAccount.is_active.is_(True))
        .order_by(BrokerPayoutAccount.created_at.desc())
        .all()
    )
    return [_serialize_account(a) for a in rows]


@router.post("/payout-accounts")
def broker_create_payout_account(
    data: PayoutAccountIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    if data.account_type not in ("mobile_money", "bank"):
        raise HTTPException(status_code=422, detail="account_type must be mobile_money or bank")

    canonical = canonical_account_number(data.account_number, data.account_type)
    existing = next(
        (
            a
            for a in db.query(BrokerPayoutAccount)
            .filter(BrokerPayoutAccount.broker_id == broker.id)
            .all()
            if canonical_account_number(a.account_number, a.account_type) == canonical
        ),
        None,
    )
    if existing and existing.is_active:
        raise HTTPException(
            status_code=409,
            detail="This account number is already saved on your profile.",
        )
    if existing:
        # A deactivated account with the same number exists — reactivate and
        # update it instead of creating a duplicate row.
        existing.account_type = data.account_type
        existing.provider = data.provider.strip()
        existing.account_name = data.account_name.strip()
        existing.account_number = canonical
        existing.currency = data.currency
        existing.is_active = True
        if data.is_default:
            db.query(BrokerPayoutAccount).filter(
                BrokerPayoutAccount.broker_id == broker.id
            ).update({"is_default": False})
            existing.is_default = True
        # Details may have changed — require re-verification.
        existing.verification_status = "pending"
        existing.verification_note = None
        existing.verified_at = None
        db.commit()
        db.refresh(existing)
        return _serialize_account(existing)

    if data.is_default:
        db.query(BrokerPayoutAccount).filter(
            BrokerPayoutAccount.broker_id == broker.id
        ).update({"is_default": False})

    account = BrokerPayoutAccount(
        broker_id=broker.id,
        account_type=data.account_type,
        provider=data.provider.strip(),
        account_name=data.account_name.strip(),
        account_number=canonical,
        currency=data.currency,
        is_default=data.is_default,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


class PayoutAccountPatch(BaseModel):
    account_type: Optional[str] = None
    provider: Optional[str] = None
    account_name: Optional[str] = None
    account_number: Optional[str] = None
    currency: Optional[str] = None
    is_default: Optional[bool] = None
    is_active: Optional[bool] = None


@router.patch("/payout-accounts/{account_id}")
def broker_update_payout_account(
    account_id: str,
    data: PayoutAccountPatch,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    account = db.query(BrokerPayoutAccount).filter(
        BrokerPayoutAccount.id == account_id,
        BrokerPayoutAccount.broker_id == broker.id,
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Payout account not found")
    if data.account_number is not None or data.account_type is not None:
        new_type = data.account_type or account.account_type
        canonical = canonical_account_number(
            data.account_number or account.account_number, new_type
        )
        dup = next(
            (
                a
                for a in db.query(BrokerPayoutAccount)
                .filter(
                    BrokerPayoutAccount.broker_id == broker.id,
                    BrokerPayoutAccount.id != account.id,
                    BrokerPayoutAccount.is_active.is_(True),
                )
                .all()
                if canonical_account_number(a.account_number, a.account_type) == canonical
            ),
            None,
        )
        if dup:
            raise HTTPException(
                status_code=409,
                detail="This account number is already saved on your profile.",
            )
        data.account_number = canonical
    for field in ("account_type", "provider", "account_name", "account_number", "currency"):
        value = getattr(data, field)
        if value is not None:
            setattr(account, field, value)
    if data.is_default is not None:
        account.is_default = data.is_default
    if data.is_active is not None:
        account.is_active = data.is_active
    if data.provider or data.account_number:
        account.verification_status = "pending"  # changes require re-verification
        account.verified_at = None
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


class PayoutRequestIn(BaseModel):
    payout_account_id: str
    amount: Decimal
    note: Optional[str] = None


@router.post("/payouts")
def broker_request_payout(
    data: PayoutRequestIn,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    wallet = _wallet_for(db, broker)

    if wallet.is_frozen:
        raise HTTPException(status_code=423, detail="Wallet is frozen. Contact support.")
    if data.amount <= 0:
        raise HTTPException(status_code=422, detail="Amount must be greater than zero.")
    if Decimal(wallet.available_balance or 0) < data.amount:
        raise HTTPException(status_code=422, detail="Insufficient available balance.")

    account = db.query(BrokerPayoutAccount).filter(
        BrokerPayoutAccount.id == data.payout_account_id,
        BrokerPayoutAccount.broker_id == broker.id,
        BrokerPayoutAccount.is_active.is_(True),
    ).first()
    if not account:
        raise HTTPException(status_code=404, detail="Payout account not found")
    if account.verification_status != "verified":
        raise HTTPException(status_code=422, detail="Payout account is not verified yet.")

    # Idempotency: same key replays the original request instead of double-charging.
    if idempotency_key:
        existing = db.query(BrokerPayoutRequest).filter(
            BrokerPayoutRequest.broker_id == broker.id,
            BrokerPayoutRequest.idempotency_key == idempotency_key,
        ).first()
        if existing:
            return _serialize_payout(existing)

    payout = BrokerPayoutRequest(
        wallet_id=wallet.id,
        broker_id=broker.id,
        payout_account_id=account.id,
        amount=data.amount,
        currency=wallet.currency,
        status=PayoutStatus.pending,
        broker_note=data.note,
        idempotency_key=idempotency_key,
    )
    wallet.available_balance = Decimal(wallet.available_balance) - data.amount
    wallet.reserved_balance = Decimal(wallet.reserved_balance) + data.amount
    db.add(payout)
    db.flush()
    _ledger(db, wallet, "payout_hold", data.amount,
            f"Payout request placed to {account.provider}", payout.id)
    db.commit()
    db.refresh(payout)
    return _serialize_payout(payout)


@router.get("/payouts")
def broker_payouts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    query = db.query(BrokerPayoutRequest).filter(BrokerPayoutRequest.broker_id == broker.id)
    total = query.count()
    rows = query.order_by(BrokerPayoutRequest.requested_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "results": [_serialize_payout(p) for p in rows],
    }


@router.post("/payouts/{payout_id}/cancel")
def broker_cancel_payout(
    payout_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    payout = db.query(BrokerPayoutRequest).filter(
        BrokerPayoutRequest.id == payout_id,
        BrokerPayoutRequest.broker_id == broker.id,
    ).first()
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    if payout.status not in (PayoutStatus.pending, PayoutStatus.approved):
        raise HTTPException(status_code=409, detail="Only pending payouts can be cancelled")

    wallet = _wallet_for(db, broker)
    wallet.reserved_balance = Decimal(wallet.reserved_balance) - payout.amount
    wallet.available_balance = Decimal(wallet.available_balance) + payout.amount
    payout.status = PayoutStatus.cancelled
    _ledger(db, wallet, "payout_released", payout.amount, "Payout cancelled — funds released", payout.id)
    db.commit()
    db.refresh(payout)
    return _serialize_payout(payout)


# ---- Admin payout management ----

@router.get("/admin/payout-accounts")
def admin_payout_accounts(db: Session = Depends(get_db), _: User = Depends(ADMIN_VIEW)):
    rows = db.query(BrokerPayoutAccount).order_by(BrokerPayoutAccount.created_at.desc()).all()
    return [_serialize_account(a) for a in rows]


class AdminVerifyAccountIn(BaseModel):
    status: str
    note: Optional[str] = None


@router.patch("/admin/payout-accounts/{account_id}/verification")
def admin_verify_payout_account(
    account_id: str,
    data: AdminVerifyAccountIn,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    account = db.query(BrokerPayoutAccount).filter(BrokerPayoutAccount.id == account_id).first()
    if not account:
        raise HTTPException(status_code=404, detail="Payout account not found")
    if data.status not in ("verified", "rejected", "pending"):
        raise HTTPException(status_code=422, detail="Invalid verification status")
    account.verification_status = data.status
    account.verification_note = data.note
    account.verified_at = datetime.now(timezone.utc) if data.status == "verified" else None
    db.commit()
    db.refresh(account)
    return _serialize_account(account)


@router.get("/admin/payouts")
def admin_payouts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: Optional[str] = Query(None, alias="status"),
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_VIEW),
):
    query = db.query(BrokerPayoutRequest)
    if status_filter:
        try:
            query = query.filter(BrokerPayoutRequest.status == PayoutStatus(status_filter))
        except ValueError:
            pass
    total = query.count()
    rows = query.order_by(BrokerPayoutRequest.requested_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, (total + page_size - 1) // page_size),
        "results": [_serialize_payout(p) for p in rows],
    }


class AdminPayoutUpdateIn(BaseModel):
    status: str
    provider_reference: Optional[str] = None
    note: Optional[str] = None


@router.patch("/admin/payouts/{payout_id}")
def admin_update_payout(
    payout_id: str,
    data: AdminPayoutUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    payout = db.query(BrokerPayoutRequest).filter(BrokerPayoutRequest.id == payout_id).first()
    if not payout:
        raise HTTPException(status_code=404, detail="Payout not found")
    try:
        new_status = PayoutStatus(data.status)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid status")

    now = datetime.now(timezone.utc)
    wallet = db.query(BrokerWallet).filter(BrokerWallet.id == payout.wallet_id).first()
    if not wallet:
        raise HTTPException(status_code=409, detail="Wallet missing for this payout")

    # Balance transitions — reserved funds resolve to paid_out or back to available.
    if new_status == PayoutStatus.completed and payout.status != PayoutStatus.completed:
        wallet.reserved_balance = Decimal(wallet.reserved_balance) - payout.amount
        wallet.paid_out_balance = Decimal(wallet.paid_out_balance) + payout.amount
        payout.completed_at = now
        _ledger(db, wallet, "payout_completed", payout.amount, "Payout completed", payout.id)
    elif new_status in (PayoutStatus.rejected, PayoutStatus.failed) and payout.status not in (PayoutStatus.rejected, PayoutStatus.failed, PayoutStatus.cancelled):
        wallet.reserved_balance = Decimal(wallet.reserved_balance) - payout.amount
        wallet.available_balance = Decimal(wallet.available_balance) + payout.amount
        _ledger(db, wallet, "payout_released", payout.amount, f"Payout {new_status.value} — funds released", payout.id)

    payout.status = new_status
    payout.provider_reference = data.provider_reference or payout.provider_reference
    payout.admin_note = data.note or payout.admin_note
    payout.processed_at = now
    db.commit()
    db.refresh(payout)
    return _serialize_payout(payout)


class FreezeWalletIn(BaseModel):
    frozen: bool
    reason: Optional[str] = None


@router.patch("/admin/{broker_id}/security/wallet-freeze")
def admin_freeze_wallet(
    broker_id: str,
    data: FreezeWalletIn,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    broker = _admin_get_broker(db, broker_id)
    wallet = _wallet_for(db, broker)
    wallet.is_frozen = data.frozen
    db.commit()
    db.refresh(wallet)
    return _serialize_wallet(wallet)


# ---------------------------------------------------------------------------
# Earning engine (offers, referral clicks, commissions, analytics) ships in a
# separate release — these stay honest empties so the dashboard renders.
# ---------------------------------------------------------------------------

@router.get("/analytics/overview")
def broker_analytics_overview(
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    wallet = _wallet_for(db, _get_my_broker(db, current_user))
    return {
        "currency": wallet.currency,
        "period_days": days,
        "total_clicks": 0,
        "unique_visitors": 0,
        "attributed_customers": 0,
        "attributed_orders": 0,
        "successful_sales": 0,
        "refunded_sales": 0,
        "conversion_rate": "0",
        "pending_earnings": "0",
        "available_earnings": "0",
        "lifetime_earnings": "0",
        "wallet_available": str(wallet.available_balance),
        "wallet_pending": str(wallet.pending_balance),
        "wallet_paid_out": str(wallet.paid_out_balance),
        "currently_promoting": 0,
        "available_opportunities": 0,
        "own_products_active": 0,
        "own_products_expired": 0,
        "own_products_draft": 0,
    }


@router.get("/analytics/campaigns")
def broker_campaign_analytics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return _empty_page(page, page_size)


@router.get("/admin/security/risk-events")
def admin_risk_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: User = Depends(ADMIN_VIEW),
):
    return _empty_page(page, page_size)
