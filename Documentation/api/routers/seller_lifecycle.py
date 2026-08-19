from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.deps import get_db
from api.enums import PermissionCode, SellerOrderStatus
from api.models import (
    PayoutRequest, Product, ProductQuestion, ProductReview, Promotion, Seller, ProductStatus,
    SellerOrder, SellerOrderMessage, SellerOrderMessageAttachment,
    SellerOrderPackage, SellerOrderPackageAttachment, SellerWallet, User,
)
from api.permissions import require_permission
from api.schemas import (
    SellerDashboardResponse, SellerOrderMessageCreate, SellerOrderMessageResponse,
    PaginatedSellerOrderPackageResponse, SellerOrderPackageCreate,
    SellerOrderPackageResponse, SellerOrderPackageUpdate, SellerOrderPackageUpsert,
    SellerPricingPreviewRequest, SellerPricingPreviewResponse,
)
from api.services.seller_pricing import calculate_marketplace_price

router = APIRouter(prefix="/seller", tags=["Seller Lifecycle"])


def seller(user: User) -> Seller:
    if not user.seller_profile:
        raise HTTPException(403, "Seller profile required")
    return user.seller_profile


def owned_seller_order(db: Session, seller_id: UUID, seller_order_id: UUID) -> SellerOrder:
    row = db.query(SellerOrder).filter(
        SellerOrder.id == seller_order_id,
        SellerOrder.seller_id == seller_id,
    ).first()
    if not row:
        raise HTTPException(404, "Seller order not found")
    return row


def _ensure_package_editable(row: SellerOrder) -> None:
    if row.status not in {SellerOrderStatus.new, SellerOrderStatus.accepted, SellerOrderStatus.processing}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Package details cannot be changed after the seller order is ready to ship",
        )


def _owned_package(db: Session, row: SellerOrder, package_id: UUID) -> SellerOrderPackage:
    package = (
        db.query(SellerOrderPackage)
        .options(selectinload(SellerOrderPackage.attachments))
        .filter(
            SellerOrderPackage.id == package_id,
            SellerOrderPackage.seller_order_id == row.id,
        )
        .first()
    )
    if not package:
        raise HTTPException(404, "Package not found")
    return package


def _apply_package_values(package: SellerOrderPackage, values: dict) -> None:
    fields = {
        "package_label", "package_type", "contents_summary",
        "weight_kg", "length_cm", "width_cm", "height_cm", "package_count",
        "fragile", "keep_upright", "temperature_sensitive", "handling_instructions",
        "declared_value", "declared_currency", "notes", "is_ready",
    }
    for field in fields:
        if field in values:
            setattr(package, field, values[field])

    if "is_ready" in values:
        if values["is_ready"]:
            if package.weight_kg is None or Decimal(package.weight_kg) <= 0:
                raise HTTPException(422, "Package weight must be greater than zero before marking ready")
            now = datetime.now(timezone.utc)
            package.prepared_at = package.prepared_at or now
            package.sealed_at = package.sealed_at or now
        else:
            package.prepared_at = None
            package.sealed_at = None


def _replace_package_attachments(
    db: Session, package: SellerOrderPackage, attachment_urls: list[str] | None
) -> None:
    if attachment_urls is None:
        return
    db.query(SellerOrderPackageAttachment).filter(
        SellerOrderPackageAttachment.package_id == package.id
    ).delete(synchronize_session=False)
    for raw_url in attachment_urls:
        url = raw_url.strip()
        if url:
            db.add(SellerOrderPackageAttachment(package_id=package.id, file_url=url))


@router.post("/pricing/preview", response_model=SellerPricingPreviewResponse)
def pricing_preview(
    data: SellerPricingPreviewRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_create.value)),
):
    seller_row = seller(current_user)
    normal = calculate_marketplace_price(
        db,
        seller_base_price=data.seller_base_price,
        seller_id=seller_row.id,
        category_id=data.category_id,
        product_id=data.product_id,
    )
    customer_sale = None
    if data.seller_sale_price is not None:
        sale = calculate_marketplace_price(
            db,
            seller_base_price=data.seller_sale_price,
            seller_id=seller_row.id,
            category_id=data.category_id,
            product_id=data.product_id,
        )
        customer_sale = sale["marketplace_price"]

    return {
        "seller_base_price": normal["seller_base_price"],
        "seller_sale_price": data.seller_sale_price,
        "commission_rate": normal["commission_rate"],
        "commission_amount": normal["commission_amount"],
        "customer_price": normal["marketplace_price"],
        "customer_sale_price": customer_sale,
        "commission_scope": normal["commission_scope"],
        "currency": data.currency,
    }


@router.get("/dashboard", response_model=SellerDashboardResponse)
def dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_dashboard_read.value)),
):
    s = seller(current_user)
    wallet = db.query(SellerWallet).filter(SellerWallet.seller_id == s.id).first()

    products_total = db.query(Product).filter(Product.seller_id == s.id).count()
    products_approved = db.query(Product).filter(Product.seller_id == s.id, Product.status == ProductStatus.approved).count()
    products_pending = db.query(Product).filter(Product.seller_id == s.id, Product.status == ProductStatus.pending_review).count()
    active_promotions = db.query(Promotion).filter(Promotion.seller_id == s.id, Promotion.is_active.is_(True)).count()

    orders_total = db.query(SellerOrder).filter(SellerOrder.seller_id == s.id).count()
    orders_new = db.query(SellerOrder).filter(SellerOrder.seller_id == s.id, SellerOrder.status == SellerOrderStatus.new).count()
    orders_processing = db.query(SellerOrder).filter(
        SellerOrder.seller_id == s.id,
        SellerOrder.status.in_([SellerOrderStatus.accepted, SellerOrderStatus.processing]),
    ).count()
    orders_ready = db.query(SellerOrder).filter(SellerOrder.seller_id == s.id, SellerOrder.status == SellerOrderStatus.ready_to_ship).count()

    rating_avg, review_count = db.query(
        func.coalesce(func.avg(ProductReview.rating), 0),
        func.count(ProductReview.id),
    ).filter(ProductReview.seller_id == s.id).one()

    unanswered = (
        db.query(ProductQuestion)
        .join(Product, ProductQuestion.product_id == Product.id)
        .filter(Product.seller_id == s.id, ProductQuestion.answer_count == 0)
        .count()
    )

    pending_payouts = db.query(PayoutRequest).filter(
        PayoutRequest.seller_id == s.id,
        PayoutRequest.status.in_(["pending", "approved", "processing"]),
    ).count()

    return {
        "products_total": products_total,
        "products_approved": products_approved,
        "products_pending_review": products_pending,
        "active_promotions": active_promotions,
        "orders_total": orders_total,
        "orders_new": orders_new,
        "orders_processing": orders_processing,
        "orders_ready_to_ship": orders_ready,
        "wallet_currency": wallet.currency if wallet else "TZS",
        "wallet_pending": wallet.pending_balance if wallet else Decimal("0"),
        "wallet_available": wallet.available_balance if wallet else Decimal("0"),
        "wallet_reserved": wallet.reserved_balance if wallet else Decimal("0"),
        "pending_payouts": pending_payouts,
        "rating_average": Decimal(rating_avg).quantize(Decimal("0.01")),
        "review_count": int(review_count),
        "unanswered_questions": unanswered,
    }


@router.get("/orders/{seller_order_id}/messages", response_model=list[SellerOrderMessageResponse])
def messages(
    seller_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_order_chat_read.value)),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    return (
        db.query(SellerOrderMessage)
        .options(selectinload(SellerOrderMessage.attachments))
        .filter(SellerOrderMessage.seller_order_id == row.id)
        .order_by(SellerOrderMessage.created_at.asc())
        .all()
    )


@router.post("/orders/{seller_order_id}/messages", response_model=SellerOrderMessageResponse, status_code=201)
def send_message(
    seller_order_id: UUID,
    data: SellerOrderMessageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_order_chat_write.value)),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    message = SellerOrderMessage(
        seller_order_id=row.id,
        sender_user_id=current_user.id,
        sender_role_label="seller",
        message=data.message.strip(),
        is_internal=data.is_internal,
    )
    db.add(message)
    db.flush()
    for url in data.attachment_urls:
        db.add(SellerOrderMessageAttachment(message_id=message.id, file_url=url))
    db.commit()
    return (
        db.query(SellerOrderMessage)
        .options(selectinload(SellerOrderMessage.attachments))
        .filter(SellerOrderMessage.id == message.id)
        .one()
    )


@router.get(
    "/orders/{seller_order_id}/packages",
    response_model=PaginatedSellerOrderPackageResponse,
)
def list_packages(
    seller_order_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=120),
    is_ready: bool | None = Query(default=None),
    package_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_packaging_manage.value)
    ),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    query = db.query(SellerOrderPackage).filter(
        SellerOrderPackage.seller_order_id == row.id
    )

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            SellerOrderPackage.package_label.ilike(term)
            | SellerOrderPackage.contents_summary.ilike(term)
            | SellerOrderPackage.notes.ilike(term)
        )
    if is_ready is not None:
        query = query.filter(SellerOrderPackage.is_ready.is_(is_ready))
    if package_type:
        query = query.filter(SellerOrderPackage.package_type == package_type.strip().lower())

    total = query.count()
    packages = (
        query.options(selectinload(SellerOrderPackage.attachments))
        .order_by(SellerOrderPackage.created_at.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": 0 if total == 0 else (total + page_size - 1) // page_size,
        "results": packages,
    }


@router.post(
    "/orders/{seller_order_id}/packages",
    response_model=SellerOrderPackageResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_package(
    seller_order_id: UUID,
    data: SellerOrderPackageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_packaging_manage.value)
    ),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    _ensure_package_editable(row)

    values = data.model_dump(exclude={"attachment_urls"})
    package = SellerOrderPackage(seller_order_id=row.id)
    _apply_package_values(package, values)
    db.add(package)
    db.flush()
    _replace_package_attachments(db, package, data.attachment_urls)
    db.commit()
    return _owned_package(db, row, package.id)


@router.get(
    "/orders/{seller_order_id}/packages/{package_id}",
    response_model=SellerOrderPackageResponse,
)
def get_package(
    seller_order_id: UUID,
    package_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_packaging_manage.value)
    ),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    return _owned_package(db, row, package_id)


@router.patch(
    "/orders/{seller_order_id}/packages/{package_id}",
    response_model=SellerOrderPackageResponse,
)
def update_package(
    seller_order_id: UUID,
    package_id: UUID,
    data: SellerOrderPackageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_packaging_manage.value)
    ),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    _ensure_package_editable(row)
    package = _owned_package(db, row, package_id)

    values = data.model_dump(exclude_unset=True, exclude={"attachment_urls"})
    _apply_package_values(package, values)
    if "attachment_urls" in data.model_fields_set:
        _replace_package_attachments(db, package, data.attachment_urls)

    db.commit()
    return _owned_package(db, row, package.id)


@router.delete(
    "/orders/{seller_order_id}/packages/{package_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_package(
    seller_order_id: UUID,
    package_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_packaging_manage.value)
    ),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    _ensure_package_editable(row)
    package = _owned_package(db, row, package_id)
    db.delete(package)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/orders/{seller_order_id}/package", response_model=SellerOrderPackageResponse)
def package(
    seller_order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_packaging_manage.value)),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    package = (
        db.query(SellerOrderPackage)
        .options(selectinload(SellerOrderPackage.attachments))
        .filter(SellerOrderPackage.seller_order_id == row.id)
        .first()
    )
    if not package:
        raise HTTPException(404, "Package information has not been prepared")
    return package


@router.put("/orders/{seller_order_id}/package", response_model=SellerOrderPackageResponse)
def upsert_package(
    seller_order_id: UUID,
    data: SellerOrderPackageUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_packaging_manage.value)),
):
    row = owned_seller_order(db, seller(current_user).id, seller_order_id)
    _ensure_package_editable(row)
    package = db.query(SellerOrderPackage).filter(
        SellerOrderPackage.seller_order_id == row.id
    ).order_by(SellerOrderPackage.created_at.asc()).first()
    if package is None:
        package = SellerOrderPackage(seller_order_id=row.id)
        db.add(package)

    values = data.model_dump(exclude={"attachment_urls"})
    _apply_package_values(package, values)
    db.flush()
    _replace_package_attachments(db, package, data.attachment_urls)

    db.commit()
    return (
        db.query(SellerOrderPackage)
        .options(selectinload(SellerOrderPackage.attachments))
        .filter(SellerOrderPackage.id == package.id)
        .one()
    )


@router.patch("/admin/payout-accounts/{account_id}/verification")
def verify_payout_account(
    account_id: UUID,
    status_value: str,
    provider_reference: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_payout_accounts_verify.value)),
):
    from api.models import SellerPayoutAccount
    if status_value not in {"pending", "verified", "rejected"}:
        raise HTTPException(422, "status_value must be pending, verified or rejected")
    account = db.get(SellerPayoutAccount, account_id)
    if not account:
        raise HTTPException(404, "Payout account not found")
    account.verification_status = status_value
    account.provider_reference = provider_reference
    account.verified_at = datetime.now(timezone.utc) if status_value == "verified" else None
    db.commit()
    return {"id": str(account.id), "verification_status": account.verification_status, "verified_at": account.verified_at}
