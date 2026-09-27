import io
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from api.config import settings
from api.deps import get_db, get_current_user
from api.enums import PermissionCode
from api.models import Broker, BrokerKycDocument, BrokerStatus, User
from api.permissions import require_permission

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
# Commerce surface — the Winga earning engine (products, offers, wallet,
# payouts, analytics) is not part of this release. Return honest empty/zero
# payloads so the dashboard renders cleanly instead of 404-storming.
# ---------------------------------------------------------------------------

def _empty_page(page: int, page_size: int):
    return {"total": 0, "page": page, "page_size": page_size, "total_pages": 1, "results": []}


@router.get("/products")
def broker_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return []


@router.get("/opportunities")
def broker_opportunities(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
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
    broker = _get_my_broker(db, current_user)
    return {
        "id": str(broker.id),
        "broker_id": str(broker.id),
        "currency": "TZS",
        "pending_balance": "0",
        "available_balance": "0",
        "reserved_balance": "0",
        "paid_out_balance": "0",
        "reversed_balance": "0",
        "debt_balance": "0",
        "is_frozen": False,
        "created_at": broker.created_at.isoformat() if broker.created_at else None,
        "updated_at": broker.updated_at.isoformat() if broker.updated_at else None,
    }


@router.get("/wallet/transactions")
def broker_wallet_transactions(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return _empty_page(page, page_size)


@router.get("/payout-accounts")
def broker_payout_accounts(current_user: User = Depends(get_current_user)):
    _ = current_user
    return []


@router.get("/payouts")
def broker_payouts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return _empty_page(page, page_size)


@router.get("/analytics/overview")
def broker_analytics_overview(
    days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
):
    _ = current_user
    return {
        "currency": "TZS",
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
        "wallet_available": "0",
        "wallet_pending": "0",
        "wallet_paid_out": "0",
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


@router.get("/admin/payout-accounts")
def admin_payout_accounts(_: User = Depends(ADMIN_VIEW)):
    return []


@router.get("/admin/payouts")
def admin_payouts(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: User = Depends(ADMIN_VIEW),
):
    return _empty_page(page, page_size)


@router.get("/admin/security/risk-events")
def admin_risk_events(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    _: User = Depends(ADMIN_VIEW),
):
    return _empty_page(page, page_size)
