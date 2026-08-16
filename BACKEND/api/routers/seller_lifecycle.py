from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
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
    SellerOrderPackageResponse, SellerOrderPackageUpsert,
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
    package = db.query(SellerOrderPackage).filter(
        SellerOrderPackage.seller_order_id == row.id
    ).first()
    if package is None:
        package = SellerOrderPackage(seller_order_id=row.id)
        db.add(package)

    for field in ["weight_kg", "length_cm", "width_cm", "height_cm", "package_count", "notes", "is_ready"]:
        setattr(package, field, getattr(data, field))
    package.prepared_at = datetime.now(timezone.utc) if data.is_ready else None
    db.flush()

    if data.attachment_urls:
        db.query(SellerOrderPackageAttachment).filter(
            SellerOrderPackageAttachment.package_id == package.id
        ).delete(synchronize_session=False)
        for url in data.attachment_urls:
            db.add(SellerOrderPackageAttachment(package_id=package.id, file_url=url))

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
