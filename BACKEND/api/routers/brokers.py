import io
import re
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional

from api.config import settings
from api.deps import get_db, get_current_user
from api.enums import PermissionCode
from decimal import Decimal

from fastapi import Header
from api.models import (
    Broker,
    BrokerKycDocument,
    BrokerProduct,
    BrokerProductImage,
    BrokerStatus,
    BrokerWallet,
    BrokerWalletTransaction,
    BrokerOffer,
    BrokerOfferAcceptance,
    BrokerReferralClick,
    BrokerCommission,
    BrokerPayoutAccount,
    BrokerPayoutRequest,
    BrokerRiskEvent,
    Brand,
    Category,
    PayoutStatus,
    Product,
    ProductStatus,
    User,
)
from api.services.product_image_service import delete_product_image_files, store_product_image
from api.permissions import require_permission
from api.schemas import canonical_account_number
from api.services.notification_service import notification_service
from api.enums import NotificationChannel, NotificationEvent

router = APIRouter(prefix="/brokers", tags=["Brokers"])

REQUIRED_KYC_DOCS = ["national_id", "profile_photo", "selfie"]
ALLOWED_DOC_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}


def _empty_page(page: int, page_size: int) -> dict:
    return {
        "total": 0,
        "page": page,
        "page_size": page_size,
        "total_pages": 0,
        "results": [],
    }


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
        "avatar_url": getattr(u, "avatar_url", None),
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


def _log_risk_event(
    db: Session,
    broker: Broker,
    event_type: str,
    severity: str = "warning",
    resource_type: str | None = None,
    resource_id=None,
    details: dict | None = None,
) -> None:
    db.add(BrokerRiskEvent(
        broker_id=broker.id,
        user_id=broker.user_id,
        event_type=event_type,
        severity=severity,
        resource_type=resource_type,
        resource_id=resource_id,
        details=details,
    ))


def _serialize_risk_event(event: BrokerRiskEvent) -> dict:
    return {
        "id": str(event.id),
        "broker_id": str(event.broker_id),
        "user_id": str(event.user_id) if event.user_id else None,
        "event_type": event.event_type,
        "severity": event.severity,
        "status": event.status,
        "resource_type": event.resource_type,
        "resource_id": str(event.resource_id) if event.resource_id else None,
        "details": event.details,
        "resolved_by_id": str(event.resolved_by_id) if event.resolved_by_id else None,
        "resolved_at": event.resolved_at.isoformat() if event.resolved_at else None,
        "created_at": event.created_at.isoformat() if event.created_at else None,
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
    try:
        notification_service.notify(
            db=db,
            user_id=broker.user_id,
            event=NotificationEvent.kyc_submitted,
            title="Verification under review",
            message="We received your Winga verification documents. Our team is reviewing them now.",
            data={"account_label": "Winga"},
            action_url="/broker/kyc",
            channels=[NotificationChannel.in_app, NotificationChannel.email],
        )
    except Exception:
        pass
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
    try:
        notification_service.notify(
            db=db,
            user_id=broker.user_id,
            event=NotificationEvent.kyc_approved,
            title="Your account is verified",
            message="Congratulations! Your Winga verification has been approved. You can now use all Winga features on Xerin Marketplace.",
            data={"account_label": "Winga"},
            action_url="/broker",
            channels=[
                NotificationChannel.in_app,
                NotificationChannel.email,
                NotificationChannel.sms,
            ],
        )
    except Exception:
        pass
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
    _log_risk_event(db, broker, "kyc_rejected", "info", details={"reason": data.reason})
    db.commit()
    try:
        notification_service.notify(
            db=db,
            user_id=broker.user_id,
            event=NotificationEvent.kyc_rejected,
            title="Verification update",
            message=f"Your Winga verification was not approved. Reason: {data.reason}",
            data={"account_label": "Winga", "reason": data.reason or ""},
            action_url="/broker/kyc",
            channels=[
                NotificationChannel.in_app,
                NotificationChannel.email,
                NotificationChannel.sms,
            ],
        )
    except Exception:
        pass
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
    _log_risk_event(db, broker, "broker_suspended", "critical", details={"reason": data.reason})
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


# ---------------------------------------------------------------------------
# Broker products — brokers list products for admin approval + marketplace sale.
# ---------------------------------------------------------------------------

MAX_BROKER_PRODUCT_IMAGES = 10


def _get_approved_broker(db: Session, user: User) -> Broker:
    broker = _get_my_broker(db, user)
    if broker.status != BrokerStatus.approved:
        raise HTTPException(
            status_code=403,
            detail="Your broker account must be approved before managing products",
        )
    return broker


def _get_broker_product(db: Session, broker: Broker, product_id: uuid.UUID) -> BrokerProduct:
    product = (
        db.query(BrokerProduct)
        .filter(BrokerProduct.id == product_id, BrokerProduct.broker_id == broker.id)
        .first()
    )
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


def _serialize_broker_product_image(img: BrokerProductImage) -> dict:
    return {
        "id": str(img.id),
        "product_id": str(img.product_id),
        "image_url": img.image_url,
        "thumbnail_url": img.thumbnail_url,
        "is_primary": img.is_primary,
        "display_order": img.display_order,
        "created_at": img.created_at.isoformat() if img.created_at else None,
    }


def _serialize_broker_product(product: BrokerProduct) -> dict:
    seconds_remaining = None
    if product.listing_expires_at:
        delta = (product.listing_expires_at - datetime.now(timezone.utc)).total_seconds()
        seconds_remaining = max(0, int(delta))
    return {
        "id": str(product.id),
        "seller_id": str(product.seller_id) if product.seller_id else None,
        "store_id": str(product.store_id) if product.store_id else None,
        "broker_id": str(product.broker_id),
        "listing_owner_type": "broker",
        "category_id": str(product.category_id),
        "brand_id": str(product.brand_id) if product.brand_id else None,
        "sku": product.sku,
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "price": str(product.price),
        "sale_price": str(product.sale_price) if product.sale_price is not None else None,
        "currency": product.currency,
        "weight": str(product.weight) if product.weight is not None else None,
        "status": product.status.value if isinstance(product.status, ProductStatus) else str(product.status),
        "rejection_reason": product.rejection_reason,
        "is_active": product.is_active,
        "listing_expires_at": product.listing_expires_at.isoformat() if product.listing_expires_at else None,
        "listing_expired_at": product.listing_expired_at.isoformat() if product.listing_expired_at else None,
        "fulfillment_location": product.fulfillment_location,
        "images": [_serialize_broker_product_image(img) for img in product.images],
        "quantity": product.quantity,
        "reserved_quantity": product.reserved_quantity,
        "available_quantity": max(0, (product.quantity or 0) - (product.reserved_quantity or 0)),
        "seconds_remaining": seconds_remaining,
        "created_at": product.created_at.isoformat() if product.created_at else None,
    }


def _product_slug(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "product"
    return f"{base}-{uuid.uuid4().hex[:8]}"


class BrokerProductCreateRequest(BaseModel):
    category_id: uuid.UUID
    brand_id: uuid.UUID | None = None
    name: str = Field(min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal = Field(gt=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="TZS", max_length=10)
    weight: Decimal | None = Field(default=None, ge=0)
    quantity: int = Field(default=0, ge=0)
    fulfillment_location: str = Field(min_length=2, max_length=255)


class BrokerProductUpdateRequest(BaseModel):
    category_id: uuid.UUID | None = None
    brand_id: uuid.UUID | None = None
    name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    price: Decimal | None = Field(default=None, gt=0)
    sale_price: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, max_length=10)
    weight: Decimal | None = Field(default=None, ge=0)
    quantity: int | None = Field(default=None, ge=0)
    fulfillment_location: str | None = Field(default=None, min_length=2, max_length=255)


def _validate_category_brand(db: Session, category_id, brand_id) -> None:
    if not db.query(Category).filter(Category.id == category_id).first():
        raise HTTPException(status_code=404, detail="Category not found")
    if brand_id and not db.query(Brand).filter(Brand.id == brand_id).first():
        raise HTTPException(status_code=404, detail="Brand not found")


@router.get("/products")
def broker_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    products = (
        db.query(BrokerProduct)
        .filter(BrokerProduct.broker_id == broker.id)
        .order_by(BrokerProduct.created_at.desc())
        .all()
    )
    now = datetime.now(timezone.utc)
    dirty = False
    for product in products:
        if product.listing_expires_at and product.listing_expires_at <= now and not product.listing_expired_at:
            product.listing_expired_at = now
            product.is_active = False
            dirty = True
    if dirty:
        db.commit()
    return [_serialize_broker_product(p) for p in products]


@router.post("/products", status_code=201)
def broker_create_product(
    data: BrokerProductCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_approved_broker(db, current_user)
    _validate_category_brand(db, data.category_id, data.brand_id)

    product = BrokerProduct(
        broker_id=broker.id,
        category_id=data.category_id,
        brand_id=data.brand_id,
        sku=f"BRK-{broker.broker_code}-{uuid.uuid4().hex[:6].upper()}",
        name=data.name.strip(),
        slug=_product_slug(data.name),
        description=data.description,
        price=data.price,
        sale_price=data.sale_price,
        currency=data.currency or "TZS",
        weight=data.weight,
        status=ProductStatus.draft,
        is_active=True,
        fulfillment_location=data.fulfillment_location.strip(),
        quantity=data.quantity,
        reserved_quantity=0,
    )
    db.add(product)
    db.commit()
    db.refresh(product)
    return _serialize_broker_product(product)


@router.patch("/products/{product_id}")
def broker_update_product(
    product_id: uuid.UUID,
    data: BrokerProductUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    product = _get_broker_product(db, broker, product_id)
    if product.status not in (ProductStatus.draft, ProductStatus.rejected):
        raise HTTPException(status_code=409, detail="Only draft or rejected products can be edited")

    updates = data.model_dump(exclude_unset=True)
    category_id = updates.get("category_id", product.category_id)
    brand_id = updates.get("brand_id", product.brand_id)
    _validate_category_brand(db, category_id, brand_id)

    for key, value in updates.items():
        setattr(product, key, value)
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return _serialize_broker_product(product)


@router.post("/products/{product_id}/images", status_code=201)
async def broker_upload_product_images(
    product_id: uuid.UUID,
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_approved_broker(db, current_user)
    product = _get_broker_product(db, broker, product_id)

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")
    existing_count = (
        db.query(BrokerProductImage)
        .filter(BrokerProductImage.product_id == product.id)
        .count()
    )
    if existing_count + len(files) > MAX_BROKER_PRODUCT_IMAGES:
        raise HTTPException(
            status_code=400,
            detail=f"A product can have at most {MAX_BROKER_PRODUCT_IMAGES} images",
        )

    saved_keys: list[tuple[str, str | None]] = []
    created: list[BrokerProductImage] = []
    try:
        for index, file in enumerate(files):
            stored = await store_product_image(file, seller_id=broker.id, product_id=product.id)
            saved_keys.append((stored.storage_key, stored.thumbnail_url))
            image = BrokerProductImage(
                product_id=product.id,
                image_url=stored.image_url,
                thumbnail_url=stored.thumbnail_url,
                storage_key=stored.storage_key,
                original_filename=stored.original_filename,
                mime_type=stored.mime_type,
                file_size=stored.file_size,
                width=stored.width,
                height=stored.height,
                display_order=existing_count + index,
                is_primary=existing_count == 0 and index == 0,
                uploaded_by_user_id=current_user.id,
            )
            db.add(image)
            created.append(image)
        db.commit()
    except Exception:
        db.rollback()
        for storage_key, thumbnail_url in saved_keys:
            delete_product_image_files(storage_key, thumbnail_url)
        raise

    for image in created:
        db.refresh(image)
    return [_serialize_broker_product_image(img) for img in created]


@router.delete("/products/{product_id}/images/{image_id}")
def broker_delete_product_image(
    product_id: uuid.UUID,
    image_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    product = _get_broker_product(db, broker, product_id)
    image = (
        db.query(BrokerProductImage)
        .filter(BrokerProductImage.id == image_id, BrokerProductImage.product_id == product.id)
        .first()
    )
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    delete_product_image_files(image.storage_key, image.thumbnail_url)
    db.delete(image)
    db.commit()
    return {"deleted": True}


@router.post("/products/{product_id}/publish")
def broker_publish_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_approved_broker(db, current_user)
    product = _get_broker_product(db, broker, product_id)

    # Re-list: an approved listing whose 24h window lapsed goes live again
    # directly — it already passed review, so no second approval needed.
    if product.status == ProductStatus.approved and product.listing_expired_at:
        product.is_active = True
        product.listing_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        product.listing_expired_at = None
        product.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(product)
        return _serialize_broker_product(product)

    if product.status not in (ProductStatus.draft, ProductStatus.rejected):
        raise HTTPException(status_code=409, detail="Only draft or rejected products can be submitted")
    if not product.images:
        raise HTTPException(status_code=400, detail="Add at least one image before publishing")

    product.status = ProductStatus.pending_review
    product.rejection_reason = None
    product.is_active = True
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return _serialize_broker_product(product)


@router.delete("/products/{product_id}")
def broker_archive_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    product = _get_broker_product(db, broker, product_id)
    product.is_active = False
    product.status = ProductStatus.inactive
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"archived": True}


# Admin review of broker products — list / approve / reject.


CATALOG_VIEW = require_permission(PermissionCode.admin_catalog_read.value)
CATALOG_APPROVE = require_permission(PermissionCode.can_approve_products.value)
CATALOG_REJECT = require_permission(PermissionCode.can_reject_products.value)


@router.get("/admin/products")
def admin_list_broker_products(
    status: str | None = Query(default=None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(CATALOG_VIEW),
):
    query = db.query(BrokerProduct).order_by(BrokerProduct.created_at.desc())
    if status:
        try:
            query = query.filter(BrokerProduct.status == ProductStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status filter")
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "items": [_serialize_broker_product(p) for p in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def _admin_get_broker_product(db: Session, product_id: uuid.UUID) -> BrokerProduct:
    product = db.query(BrokerProduct).filter(BrokerProduct.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.post("/admin/products/{product_id}/approve")
def admin_approve_broker_product(
    product_id: uuid.UUID,
    db: Session = Depends(get_db),
    _: User = Depends(CATALOG_APPROVE),
):
    product = _admin_get_broker_product(db, product_id)
    if product.status != ProductStatus.pending_review:
        raise HTTPException(status_code=409, detail="Only products pending review can be approved")
    if not product.images:
        raise HTTPException(status_code=400, detail="A product must have at least one image before approval")

    product.status = ProductStatus.approved
    product.rejection_reason = None
    product.is_active = True
    product.listing_expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
    product.listing_expired_at = None
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return _serialize_broker_product(product)


class BrokerProductRejectRequest(BaseModel):
    reason: str = Field(min_length=2, max_length=1000)


@router.post("/admin/products/{product_id}/reject")
def admin_reject_broker_product(
    product_id: uuid.UUID,
    data: BrokerProductRejectRequest,
    db: Session = Depends(get_db),
    _: User = Depends(CATALOG_REJECT),
):
    product = _admin_get_broker_product(db, product_id)
    if product.status != ProductStatus.pending_review:
        raise HTTPException(status_code=409, detail="Only products pending review can be rejected")

    product.status = ProductStatus.rejected
    product.rejection_reason = data.reason.strip()
    product.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(product)
    return _serialize_broker_product(product)


# ---------------------------------------------------------------------------
# Earning engine — offers, referral links, click tracking, commissions.
# ---------------------------------------------------------------------------

def _referral_code(broker: Broker) -> str:
    seed = uuid.uuid4().hex.upper()
    return f"{broker.broker_code[:4]}{seed[:6]}".replace("O", "0").replace("I", "1")


def _product_card(product: Product) -> dict:
    images = sorted(product.images or [], key=lambda i: i.display_order)
    return {
        "id": str(product.id),
        "seller_id": str(product.seller_id),
        "category_id": str(product.category_id),
        "brand_id": str(product.brand_id) if product.brand_id else None,
        "sku": product.sku,
        "name": product.name,
        "slug": product.slug,
        "description": product.description,
        "price": str(product.price),
        "sale_price": str(product.sale_price) if product.sale_price is not None else None,
        "currency": product.currency,
        "weight": str(product.weight) if product.weight is not None else None,
        "status": product.status.value if isinstance(product.status, ProductStatus) else str(product.status),
        "rejection_reason": product.rejection_reason,
        "is_active": product.is_active,
        "primary_image_url": images[0].image_url if images else None,
        "images": [
            {
                "id": str(img.id),
                "product_id": str(img.product_id),
                "image_url": img.image_url,
                "thumbnail_url": img.thumbnail_url,
                "is_primary": img.is_primary,
                "display_order": img.display_order,
                "alt_text": img.alt_text,
            }
            for img in images
        ],
        "created_at": product.created_at.isoformat() if product.created_at else None,
    }


def _offer_reward_per_unit(offer: BrokerOffer, product: Product | None = None) -> Decimal:
    if offer.commission_type == "percentage" and product is not None:
        base = Decimal(product.sale_price if product.sale_price is not None else product.price)
        return (base * Decimal(offer.commission_value) / Decimal("100")).quantize(Decimal("0.01"))
    return Decimal(offer.commission_value).quantize(Decimal("0.01"))


def _serialize_offer(offer: BrokerOffer) -> dict:
    product = offer.product
    reward = _offer_reward_per_unit(offer, product)
    price = Decimal(product.sale_price if product.sale_price is not None else product.price) if product else Decimal("0")
    return {
        "id": str(offer.id),
        "product_id": str(offer.product_id),
        "seller_id": str(offer.seller_id),
        "commission_type": offer.commission_type,
        "commission_value": str(offer.commission_value),
        "max_attributed_sales": offer.max_attributed_sales,
        "attributed_sales_count": offer.attributed_sales_count,
        "starts_at": offer.starts_at.isoformat() if offer.starts_at else None,
        "ends_at": offer.ends_at.isoformat() if offer.ends_at else None,
        "is_active": offer.is_active,
        "created_at": offer.created_at.isoformat() if offer.created_at else None,
        "accepted_brokers_count": sum(1 for a in (offer.acceptances or []) if a.is_active),
        "estimated_reward_per_unit": str(reward),
        "estimated_seller_net_per_unit": str((price - reward).quantize(Decimal("0.01"))) if product else "0",
    }


def _offer_available(offer: BrokerOffer) -> bool:
    now = datetime.now(timezone.utc)
    if not offer.is_active:
        return False
    if offer.starts_at and offer.starts_at > now:
        return False
    if offer.ends_at and offer.ends_at <= now:
        return False
    if offer.max_attributed_sales is not None and offer.attributed_sales_count >= offer.max_attributed_sales:
        return False
    return True


def _opportunity_payload(db: Session, broker: Broker, offer: BrokerOffer) -> dict:
    acceptance = (
        db.query(BrokerOfferAcceptance)
        .filter(
            BrokerOfferAcceptance.offer_id == offer.id,
            BrokerOfferAcceptance.broker_id == broker.id,
            BrokerOfferAcceptance.is_active.is_(True),
        )
        .first()
    )
    product = offer.product
    return {
        "offer": _serialize_offer(offer),
        "product": _product_card(product) if product else None,
        "available_quantity": 0,
        "already_accepted": acceptance is not None,
    }


@router.get("/opportunities")
def broker_opportunities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    offers = (
        db.query(BrokerOffer)
        .join(Product, Product.id == BrokerOffer.product_id)
        .filter(BrokerOffer.is_active.is_(True), Product.status == ProductStatus.approved, Product.is_active.is_(True))
        .order_by(BrokerOffer.created_at.desc())
        .all()
    )
    return [_opportunity_payload(db, broker, offer) for offer in offers if _offer_available(offer)]


@router.get("/accepted-opportunities")
def broker_accepted_opportunities(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    acceptances = (
        db.query(BrokerOfferAcceptance)
        .filter(BrokerOfferAcceptance.broker_id == broker.id, BrokerOfferAcceptance.is_active.is_(True))
        .all()
    )
    return [_opportunity_payload(db, broker, a.offer) for a in acceptances if a.offer]


@router.post("/opportunities/{offer_id}/accept", status_code=201)
def broker_accept_opportunity(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_approved_broker(db, current_user)
    offer = db.query(BrokerOffer).filter(BrokerOffer.id == offer_id).first()
    if not offer or not _offer_available(offer):
        raise HTTPException(status_code=404, detail="Offer not available")

    acceptance = (
        db.query(BrokerOfferAcceptance)
        .filter(BrokerOfferAcceptance.offer_id == offer.id, BrokerOfferAcceptance.broker_id == broker.id)
        .first()
    )
    if acceptance:
        if acceptance.is_active:
            raise HTTPException(status_code=409, detail="Offer already accepted")
        acceptance.is_active = True
        acceptance.stopped_at = None
    else:
        acceptance = BrokerOfferAcceptance(
            offer_id=offer.id,
            broker_id=broker.id,
            referral_code=_referral_code(broker),
            is_active=True,
        )
        db.add(acceptance)
    db.commit()
    db.refresh(acceptance)
    return {
        "id": str(acceptance.id),
        "offer_id": str(acceptance.offer_id),
        "broker_id": str(acceptance.broker_id),
        "is_active": acceptance.is_active,
        "accepted_at": acceptance.accepted_at.isoformat() if acceptance.accepted_at else None,
        "stopped_at": acceptance.stopped_at.isoformat() if acceptance.stopped_at else None,
    }


@router.delete("/opportunities/{offer_id}/accept")
def broker_stop_opportunity(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    acceptance = (
        db.query(BrokerOfferAcceptance)
        .filter(BrokerOfferAcceptance.offer_id == offer_id, BrokerOfferAcceptance.broker_id == broker.id)
        .first()
    )
    if not acceptance or not acceptance.is_active:
        raise HTTPException(status_code=404, detail="Acceptance not found")
    acceptance.is_active = False
    acceptance.stopped_at = datetime.now(timezone.utc)
    db.commit()
    return {"stopped": True}


@router.get("/opportunities/{offer_id}/referral")
def broker_referral_link(
    offer_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_approved_broker(db, current_user)
    offer = db.query(BrokerOffer).filter(BrokerOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    acceptance = (
        db.query(BrokerOfferAcceptance)
        .filter(BrokerOfferAcceptance.offer_id == offer.id, BrokerOfferAcceptance.broker_id == broker.id, BrokerOfferAcceptance.is_active.is_(True))
        .first()
    )
    if not acceptance:
        acceptance = BrokerOfferAcceptance(
            offer_id=offer.id,
            broker_id=broker.id,
            referral_code=_referral_code(broker),
            is_active=True,
        )
        db.add(acceptance)
        db.commit()
        db.refresh(acceptance)
    product = offer.product
    slug_or_id = product.slug if product and product.slug else str(offer.product_id)
    return {
        "id": str(acceptance.id),
        "acceptance_id": str(acceptance.id),
        "offer_id": str(offer.id),
        "broker_id": str(broker.id),
        "product_id": str(offer.product_id),
        "referral_code": acceptance.referral_code,
        "is_active": acceptance.is_active,
        "created_at": acceptance.accepted_at.isoformat() if acceptance.accepted_at else None,
        "share_path": f"/products/{slug_or_id}?ref={acceptance.referral_code}",
    }


class ReferralClickIn(BaseModel):
    product_id: uuid.UUID
    visitor_key: str = Field(min_length=4, max_length=80)
    source: Optional[str] = Field(default=None, max_length=60)


@router.post("/referrals/{referral_code}/click")
def track_referral_click(
    referral_code: str,
    data: ReferralClickIn,
    db: Session = Depends(get_db),
):
    acceptance = (
        db.query(BrokerOfferAcceptance)
        .filter(BrokerOfferAcceptance.referral_code == referral_code, BrokerOfferAcceptance.is_active.is_(True))
        .first()
    )
    if not acceptance:
        raise HTTPException(status_code=404, detail="Referral code not found")
    click = BrokerReferralClick(
        acceptance_id=acceptance.id,
        offer_id=acceptance.offer_id,
        broker_id=acceptance.broker_id,
        product_id=data.product_id,
        referral_code=referral_code,
        visitor_key=data.visitor_key,
        source=data.source,
    )
    db.add(click)
    db.commit()
    return {"tracked": True}


def _serialize_commission(c: BrokerCommission) -> dict:
    return {
        "id": str(c.id),
        "broker_id": str(c.broker_id),
        "order_id": str(c.order_id),
        "order_item_id": str(c.order_item_id),
        "broker_offer_id": str(c.broker_offer_id) if c.broker_offer_id else None,
        "broker_attribution_id": str(c.broker_attribution_id) if c.broker_attribution_id else None,
        "escrow_hold_id": str(c.escrow_hold_id) if c.escrow_hold_id else None,
        "currency": c.currency,
        "amount": str(c.amount),
        "reversed_amount": str(c.reversed_amount),
        "net_amount": str(c.net_amount),
        "status": c.status,
        "available_at": c.available_at.isoformat() if c.available_at else None,
        "reversed_at": c.reversed_at.isoformat() if c.reversed_at else None,
        "reference": c.reference,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }


@router.get("/commissions")
def broker_commissions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    query = db.query(BrokerCommission).filter(BrokerCommission.broker_id == broker.id)
    total = query.count()
    rows = query.order_by(BrokerCommission.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "results": [_serialize_commission(c) for c in rows],
    }


@router.get("/commissions/summary")
def broker_commission_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    rows = db.query(BrokerCommission).filter(BrokerCommission.broker_id == broker.id).all()
    pending = sum(Decimal(c.amount) - Decimal(c.reversed_amount) for c in rows if c.status == "pending")
    available = sum(Decimal(c.amount) - Decimal(c.reversed_amount) for c in rows if c.status in ("available", "partially_reversed"))
    reversed_total = sum(Decimal(c.reversed_amount) for c in rows)
    lifetime = sum(Decimal(c.amount) for c in rows)
    return {
        "currency": rows[0].currency if rows else "TZS",
        "pending_amount": str(pending),
        "available_amount": str(available),
        "reversed_amount": str(reversed_total),
        "lifetime_commission": str(lifetime),
        "total_records": len(rows),
    }


# Admin — create and manage earnable offers on seller products.


class AdminOfferCreateIn(BaseModel):
    product_id: uuid.UUID
    commission_type: str = Field(pattern="^(fixed|percentage)$")
    commission_value: Decimal = Field(gt=0)
    max_attributed_sales: int | None = Field(default=None, ge=1)
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class AdminOfferUpdateIn(BaseModel):
    commission_value: Decimal | None = Field(default=None, gt=0)
    max_attributed_sales: int | None = Field(default=None, ge=1)
    ends_at: datetime | None = None
    is_active: bool | None = None


@router.get("/admin/offers")
def admin_list_offers(
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_VIEW),
):
    offers = db.query(BrokerOffer).order_by(BrokerOffer.created_at.desc()).all()
    return [_serialize_offer(o) for o in offers]


@router.post("/admin/offers", status_code=201)
def admin_create_offer(
    data: AdminOfferCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if product.status != ProductStatus.approved or not product.is_active:
        raise HTTPException(status_code=409, detail="Offers can only be created on approved live products")
    if data.commission_type == "percentage" and data.commission_value > 100:
        raise HTTPException(status_code=422, detail="Percentage commission cannot exceed 100")

    existing = db.query(BrokerOffer).filter(BrokerOffer.product_id == product.id, BrokerOffer.is_active.is_(True)).first()
    if existing:
        raise HTTPException(status_code=409, detail="An active offer already exists for this product")

    offer = BrokerOffer(
        product_id=product.id,
        seller_id=product.seller_id,
        commission_type=data.commission_type,
        commission_value=data.commission_value,
        max_attributed_sales=data.max_attributed_sales,
        starts_at=data.starts_at or datetime.now(timezone.utc),
        ends_at=data.ends_at,
        is_active=True,
    )
    db.add(offer)
    db.commit()
    db.refresh(offer)
    return _serialize_offer(offer)


@router.patch("/admin/offers/{offer_id}")
def admin_update_offer(
    offer_id: uuid.UUID,
    data: AdminOfferUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_APPROVE),
):
    offer = db.query(BrokerOffer).filter(BrokerOffer.id == offer_id).first()
    if not offer:
        raise HTTPException(status_code=404, detail="Offer not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(offer, key, value)
    offer.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(offer)
    return _serialize_offer(offer)


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
        # Self-service payout accounts are trusted — the owner chose them.
        existing.verification_status = "verified"
        existing.verification_note = None
        existing.verified_at = datetime.now(timezone.utc)
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
        verification_status="verified",
        verified_at=datetime.now(timezone.utc),
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
        account.verification_status = "verified"
        account.verified_at = datetime.now(timezone.utc)
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
    _log_risk_event(db, broker, "payout_cancelled", "warning", resource_type="payout", resource_id=payout.id, details={"amount": str(payout.amount)})
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
        broker = db.query(Broker).filter(Broker.id == payout.broker_id).first()
        if broker:
            _log_risk_event(db, broker, f"payout_{new_status.value}", "high", resource_type="payout", resource_id=payout.id, details={"amount": str(payout.amount), "note": data.note})

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
    _log_risk_event(
        db, broker,
        "wallet_frozen" if data.frozen else "wallet_unfrozen",
        "high" if data.frozen else "info",
        details={"reason": data.reason},
    )
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
    broker = _get_my_broker(db, current_user)
    wallet = _wallet_for(db, broker)
    since = datetime.now(timezone.utc) - timedelta(days=days)

    clicks_q = db.query(BrokerReferralClick).filter(
        BrokerReferralClick.broker_id == broker.id,
        BrokerReferralClick.created_at >= since,
    )
    total_clicks = clicks_q.count()
    unique_visitors = db.query(func.count(func.distinct(BrokerReferralClick.visitor_key))).filter(
        BrokerReferralClick.broker_id == broker.id,
        BrokerReferralClick.created_at >= since,
    ).scalar() or 0

    commissions = db.query(BrokerCommission).filter(
        BrokerCommission.broker_id == broker.id,
        BrokerCommission.created_at >= since,
    ).all()
    attributed_orders = len({str(c.order_id) for c in commissions})
    successful_sales = sum(1 for c in commissions if c.status in ("available", "partially_reversed"))
    refunded_sales = sum(1 for c in commissions if c.status == "reversed")
    pending_earnings = sum(Decimal(c.amount) - Decimal(c.reversed_amount) for c in commissions if c.status == "pending")
    available_earnings = sum(Decimal(c.amount) - Decimal(c.reversed_amount) for c in commissions if c.status in ("available", "partially_reversed"))
    lifetime_earnings = sum(Decimal(c.amount) for c in commissions)
    conversion = (Decimal(attributed_orders) / Decimal(total_clicks) * 100).quantize(Decimal("0.1")) if total_clicks else Decimal("0")

    promoting = db.query(BrokerOfferAcceptance).filter(
        BrokerOfferAcceptance.broker_id == broker.id,
        BrokerOfferAcceptance.is_active.is_(True),
    ).count()
    opportunities = db.query(BrokerOffer).filter(BrokerOffer.is_active.is_(True)).count()

    own = db.query(BrokerProduct).filter(BrokerProduct.broker_id == broker.id).all()
    now = datetime.now(timezone.utc)
    active = sum(1 for p in own if p.is_active and p.status == ProductStatus.approved)
    expired = sum(1 for p in own if p.listing_expired_at or (p.listing_expires_at and p.listing_expires_at <= now))
    drafts = sum(1 for p in own if p.status in (ProductStatus.draft, ProductStatus.rejected))

    return {
        "currency": wallet.currency,
        "period_days": days,
        "total_clicks": total_clicks,
        "unique_visitors": unique_visitors,
        "attributed_customers": attributed_orders,
        "attributed_orders": attributed_orders,
        "successful_sales": successful_sales,
        "refunded_sales": refunded_sales,
        "conversion_rate": str(conversion),
        "pending_earnings": str(pending_earnings),
        "available_earnings": str(available_earnings),
        "lifetime_earnings": str(lifetime_earnings),
        "wallet_available": str(wallet.available_balance),
        "wallet_pending": str(wallet.pending_balance),
        "wallet_paid_out": str(wallet.paid_out_balance),
        "currently_promoting": promoting,
        "available_opportunities": opportunities,
        "own_products_active": active,
        "own_products_expired": expired,
        "own_products_draft": drafts,
    }


@router.get("/analytics/campaigns")
def broker_campaign_analytics(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    broker = _get_my_broker(db, current_user)
    acceptances = (
        db.query(BrokerOfferAcceptance)
        .filter(BrokerOfferAcceptance.broker_id == broker.id)
        .order_by(BrokerOfferAcceptance.accepted_at.desc())
        .all()
    )
    total = len(acceptances)
    sliced = acceptances[(page - 1) * page_size: page * page_size]

    results = []
    for a in sliced:
        offer = a.offer
        product = offer.product if offer else None
        clicks = db.query(BrokerReferralClick).filter(BrokerReferralClick.acceptance_id == a.id).count()
        visitors = db.query(func.count(func.distinct(BrokerReferralClick.visitor_key))).filter(
            BrokerReferralClick.acceptance_id == a.id
        ).scalar() or 0
        commissions = db.query(BrokerCommission).filter(BrokerCommission.broker_attribution_id == a.id).all()
        orders = len({str(c.order_id) for c in commissions})
        sales = sum(1 for c in commissions if c.status in ("available", "partially_reversed"))
        gross = sum(Decimal(c.amount) for c in commissions)
        reversed_total = sum(Decimal(c.reversed_amount) for c in commissions)
        conversion = (Decimal(orders) / Decimal(clicks) * 100).quantize(Decimal("0.1")) if clicks else Decimal("0")
        results.append({
            "offer_id": str(a.offer_id),
            "product_id": str(offer.product_id) if offer else None,
            "product_name": product.name if product else "",
            "referral_code": a.referral_code,
            "is_active": a.is_active,
            "accepted_at": a.accepted_at.isoformat() if a.accepted_at else None,
            "clicks": clicks,
            "unique_visitors": visitors,
            "attributed_customers": orders,
            "attributed_orders": orders,
            "successful_sales": sales,
            "conversion_rate": str(conversion),
            "gross_commission": str(gross),
            "reversed_commission": str(reversed_total),
            "net_commission": str(gross - reversed_total),
        })

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "results": results,
    }


@router.get("/admin/security/risk-events")
def admin_risk_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
    _: User = Depends(ADMIN_VIEW),
):
    query = db.query(BrokerRiskEvent).order_by(BrokerRiskEvent.created_at.desc())
    if status:
        query = query.filter(BrokerRiskEvent.status == status)
    total = query.count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": max(1, -(-total // page_size)),
        "results": [_serialize_risk_event(e) for e in items],
    }


class RiskEventResolveIn(BaseModel):
    note: Optional[str] = None


@router.patch("/admin/security/risk-events/{event_id}/resolve")
def admin_resolve_risk_event(
    event_id: str,
    data: RiskEventResolveIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(ADMIN_APPROVE),
):
    event = db.query(BrokerRiskEvent).filter(BrokerRiskEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="Risk event not found")
    if event.status == "resolved":
        raise HTTPException(status_code=409, detail="Event already resolved")
    event.status = "resolved"
    event.resolution_note = data.note
    event.resolved_by_id = current_user.id
    event.resolved_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(event)
    return _serialize_risk_event(event)
