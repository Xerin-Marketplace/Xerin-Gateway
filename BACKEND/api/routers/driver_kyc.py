from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import DriverDocumentStatus, DriverVerificationStatus, PermissionCode
from api.models import Driver, DriverDocument, DriverKYC, User
from api.permissions import require_permission
from api.schemas import (
    DriverDocumentCreate,
    DriverDocumentResponse,
    DriverDocumentReviewRequest,
    DriverDocumentUpdate,
    DriverKYCCreate,
    DriverKYCResponse,
    DriverKYCReviewRequest,
    DriverKYCUpdate,
)

router = APIRouter(tags=["Driver KYC"])


def _get_driver_or_404(db: Session, driver_id: UUID) -> Driver:
    driver = db.query(Driver).filter(Driver.id == driver_id).first()
    if not driver:
        raise HTTPException(404, "Driver not found")
    return driver


# =========================================================
# DRIVER KYC ENDPOINTS
# =========================================================

@router.get("/drivers/{driver_id}/kyc", response_model=DriverKYCResponse)
def get_driver_kyc(
    driver_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.driver_kyc_read.value)),
):
    driver = _get_driver_or_404(db, driver_id)
    if not driver.kyc:
        raise HTTPException(404, "KYC not submitted yet")
    return driver.kyc


@router.post("/drivers/{driver_id}/kyc", response_model=DriverKYCResponse, status_code=status.HTTP_201_CREATED)
def submit_driver_kyc(
    driver_id: UUID,
    data: DriverKYCCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_manage.value)),
):
    driver = _get_driver_or_404(db, driver_id)
    if driver.kyc:
        raise HTTPException(409, "KYC already submitted. Use PUT to update.")
    kyc = DriverKYC(
        driver_id=driver_id,
        submitted_at=datetime.now(timezone.utc),
        **data.model_dump(),
    )
    db.add(kyc)
    db.commit()
    db.refresh(kyc)
    return kyc


@router.put("/drivers/{driver_id}/kyc", response_model=DriverKYCResponse)
def update_driver_kyc(
    driver_id: UUID,
    data: DriverKYCUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_manage.value)),
):
    driver = _get_driver_or_404(db, driver_id)
    if not driver.kyc:
        raise HTTPException(404, "KYC not submitted yet")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(driver.kyc, key, value)
    db.commit()
    db.refresh(driver.kyc)
    return driver.kyc


@router.post("/drivers/{driver_id}/kyc/review", response_model=DriverKYCResponse)
def review_driver_kyc(
    driver_id: UUID,
    data: DriverKYCReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_review.value)),
):
    driver = _get_driver_or_404(db, driver_id)
    if not driver.kyc:
        raise HTTPException(404, "KYC not submitted yet")

    now = datetime.now(timezone.utc)
    if data.is_approved:
        driver.kyc.is_verified = True
        driver.kyc.verified_at = now
        driver.kyc.verified_by_id = current_user.id
        driver.kyc.rejection_reason = None
        driver.verification_status = DriverVerificationStatus.verified
        driver.approved_at = now
    else:
        driver.kyc.is_verified = False
        driver.kyc.verified_at = now
        driver.kyc.verified_by_id = current_user.id
        driver.kyc.rejection_reason = data.rejection_reason
        driver.verification_status = DriverVerificationStatus.rejected

    db.commit()
    db.refresh(driver.kyc)
    return driver.kyc


@router.post("/drivers/{driver_id}/kyc/resubmit", response_model=DriverKYCResponse)
def resubmit_driver_kyc(
    driver_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_manage.value)),
):
    """Reset KYC to pending for re-verification after updates."""
    driver = _get_driver_or_404(db, driver_id)
    if not driver.kyc:
        raise HTTPException(404, "KYC not submitted yet")
    driver.kyc.is_verified = False
    driver.kyc.verified_at = None
    driver.kyc.verified_by_id = None
    driver.kyc.rejection_reason = None
    driver.kyc.submitted_at = datetime.now(timezone.utc)
    driver.verification_status = DriverVerificationStatus.pending
    db.commit()
    db.refresh(driver.kyc)
    return driver.kyc


# =========================================================
# DRIVER DOCUMENT ENDPOINTS
# =========================================================

@router.get("/drivers/{driver_id}/documents", response_model=list[DriverDocumentResponse])
def list_driver_documents(
    driver_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.driver_kyc_read.value)),
):
    _get_driver_or_404(db, driver_id)
    return db.query(DriverDocument).filter(DriverDocument.driver_id == driver_id).order_by(DriverDocument.created_at.desc()).all()


@router.post("/drivers/{driver_id}/documents", response_model=DriverDocumentResponse, status_code=status.HTTP_201_CREATED)
def add_driver_document(
    driver_id: UUID,
    data: DriverDocumentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_manage.value)),
):
    _get_driver_or_404(db, driver_id)
    doc = DriverDocument(driver_id=driver_id, **data.model_dump())
    db.add(doc)
    db.commit()
    db.refresh(doc)
    return doc


@router.put("/drivers/{driver_id}/documents/{document_id}", response_model=DriverDocumentResponse)
def update_driver_document(
    driver_id: UUID,
    document_id: UUID,
    data: DriverDocumentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_manage.value)),
):
    doc = db.query(DriverDocument).filter(DriverDocument.id == document_id, DriverDocument.driver_id == driver_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(doc, key, value)
    db.commit()
    db.refresh(doc)
    return doc


@router.delete("/drivers/{driver_id}/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_driver_document(
    driver_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_manage.value)),
):
    doc = db.query(DriverDocument).filter(DriverDocument.id == document_id, DriverDocument.driver_id == driver_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    db.delete(doc)
    db.commit()


@router.post("/drivers/{driver_id}/documents/{document_id}/review", response_model=DriverDocumentResponse)
def review_driver_document(
    driver_id: UUID,
    document_id: UUID,
    data: DriverDocumentReviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.driver_kyc_review.value)),
):
    doc = db.query(DriverDocument).filter(DriverDocument.id == document_id, DriverDocument.driver_id == driver_id).first()
    if not doc:
        raise HTTPException(404, "Document not found")
    now = datetime.now(timezone.utc)
    if data.is_approved:
        doc.status = DriverDocumentStatus.approved
        doc.verified_at = now
        doc.verified_by_id = current_user.id
        doc.rejection_reason = None
    else:
        doc.status = DriverDocumentStatus.rejected
        doc.verified_at = now
        doc.verified_by_id = current_user.id
        doc.rejection_reason = data.rejection_reason
    db.commit()
    db.refresh(doc)
    return doc


# =========================================================
# ADMIN: LIST ALL PENDING KYC / DOCUMENTS
# =========================================================

@router.get("/admin/driver-kyc/pending", response_model=list[DriverKYCResponse])
def list_pending_kyc(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.driver_kyc_read.value)),
):
    return db.query(DriverKYC).filter(DriverKYC.is_verified.is_(False), DriverKYC.submitted_at.is_not(None)).order_by(DriverKYC.submitted_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


@router.get("/admin/driver-kyc/all", response_model=list[DriverKYCResponse])
def list_all_kyc(
    verified: bool | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.driver_kyc_read.value)),
):
    q = db.query(DriverKYC)
    if verified is not None:
        q = q.filter(DriverKYC.is_verified == verified)
    return q.order_by(DriverKYC.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()


@router.get("/admin/driver-documents/pending", response_model=list[DriverDocumentResponse])
def list_pending_documents(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.driver_kyc_read.value)),
):
    return db.query(DriverDocument).filter(DriverDocument.status == DriverDocumentStatus.pending).order_by(DriverDocument.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
