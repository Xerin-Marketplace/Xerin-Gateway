from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.models import OrderItem, Product, Seller, SellerKYCDocument, SellerStatus

BUSINESS_LICENSE_DOCUMENT_TYPE = "business_license"
LICENSE_EXPIRED_REASON = "business_license_expired"


def get_current_business_license(db: Session, seller_id: UUID) -> SellerKYCDocument | None:
    return (
        db.query(SellerKYCDocument)
        .filter(
            SellerKYCDocument.seller_id == seller_id,
            SellerKYCDocument.document_type == BUSINESS_LICENSE_DOCUMENT_TYPE,
            SellerKYCDocument.is_current.is_(True),
        )
        .order_by(SellerKYCDocument.version.desc(), SellerKYCDocument.uploaded_at.desc())
        .first()
    )


def _is_expired(document: SellerKYCDocument | None, *, today: date | None = None) -> bool:
    if document is None or document.expiry_date is None:
        return False
    return document.expiry_date < (today or date.today())


def enforce_seller_license_status(
    db: Session,
    seller: Seller,
    *,
    commit: bool = False,
) -> bool:
    """Suspend an approved seller whose current approved business licence expired.

    Legacy approved sellers with no dated business licence are not suspended here.
    Task 1 introduced licence metadata; only a real current licence with an expiry
    date can trigger the automatic hold.
    """
    if seller.status != SellerStatus.approved:
        return seller.status == SellerStatus.approved

    licence = get_current_business_license(db, seller.id)
    if (
        licence is not None
        and licence.status == "approved"
        and _is_expired(licence)
    ):
        seller.status = SellerStatus.suspended
        seller.suspension_reason = LICENSE_EXPIRED_REASON
        seller.suspended_at = datetime.now(timezone.utc)
        db.add(seller)
        if commit:
            db.commit()
            db.refresh(seller)
        else:
            db.flush()
        return False

    return True


def sweep_expired_seller_licenses(db: Session, *, commit: bool = True) -> int:
    """Idempotently suspend approved sellers whose current approved licence expired."""
    today = date.today()
    seller_ids = (
        db.query(SellerKYCDocument.seller_id)
        .filter(
            SellerKYCDocument.document_type == BUSINESS_LICENSE_DOCUMENT_TYPE,
            SellerKYCDocument.is_current.is_(True),
            SellerKYCDocument.status == "approved",
            SellerKYCDocument.expiry_date.isnot(None),
            SellerKYCDocument.expiry_date < today,
        )
        .distinct()
        .all()
    )
    ids = [row[0] for row in seller_ids]
    if not ids:
        return 0

    sellers = (
        db.query(Seller)
        .filter(
            Seller.id.in_(ids),
            Seller.status == SellerStatus.approved,
        )
        .all()
    )
    now = datetime.now(timezone.utc)
    for seller in sellers:
        seller.status = SellerStatus.suspended
        seller.suspension_reason = LICENSE_EXPIRED_REASON
        seller.suspended_at = now
        db.add(seller)

    if commit and sellers:
        db.commit()
    elif sellers:
        db.flush()
    return len(sellers)


def ensure_seller_can_sell(db: Session, seller: Seller) -> None:
    enforce_seller_license_status(db, seller)
    if seller.status != SellerStatus.approved:
        detail = {
            "code": "SELLER_UNAVAILABLE",
            "message": "This seller is temporarily unavailable for new sales.",
            "seller_id": str(seller.id),
            "reason": seller.suspension_reason or "seller_not_approved",
        }
        if seller.suspension_reason == LICENSE_EXPIRED_REASON:
            detail["code"] = "SELLER_LICENSE_EXPIRED"
            detail["message"] = (
                "This seller is temporarily unavailable because the business licence requires renewal."
            )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def ensure_product_seller_available(db: Session, product: Product) -> None:
    if product.seller_id is None:
        return
    seller = db.query(Seller).filter(Seller.id == product.seller_id).first()
    if seller is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "SELLER_UNAVAILABLE",
                "message": "This product is temporarily unavailable.",
                "product_id": str(product.id),
            },
        )
    try:
        ensure_seller_can_sell(db, seller)
    except HTTPException as exc:
        detail = dict(exc.detail) if isinstance(exc.detail, dict) else {"message": str(exc.detail)}
        detail["product_id"] = str(product.id)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc


def ensure_order_sellers_available(db: Session, order_id: UUID) -> None:
    seller_ids = [
        row[0]
        for row in (
            db.query(OrderItem.seller_id)
            .filter(OrderItem.order_id == order_id, OrderItem.seller_id.isnot(None))
            .distinct()
            .all()
        )
    ]
    for seller_id in seller_ids:
        seller = db.query(Seller).filter(Seller.id == seller_id).first()
        if seller is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"code": "SELLER_UNAVAILABLE", "message": "A seller in this order is unavailable."},
            )
        ensure_seller_can_sell(db, seller)
