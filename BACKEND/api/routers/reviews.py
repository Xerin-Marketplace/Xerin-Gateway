from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.enums import PermissionCode, ReviewStatus, SellerOrderStatus
from api.models import (
    OrderItem,
    Product,
    ProductReview,
    ReviewReport,
    SellerOrder,
    Store,
    StoreReview,
    User,
)
from api.permissions import require_permission
from api.schemas import (
    ReviewCreate,
    ReviewListResponse,
    ReviewModerationRequest,
    ReviewReportRequest,
    ReviewResponse,
    ReviewUpdate,
    SellerReviewReply,
    StoreReviewCreate,
)

router = APIRouter(tags=["Reviews"])


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="A review already exists for this purchase") from exc
    except Exception:
        db.rollback()
        raise


def _review_response(review: ProductReview | StoreReview) -> ReviewResponse:
    return ReviewResponse.model_validate(review)


def _recalculate_store_rating(db: Session, store_id: UUID) -> None:
    average, count = (
        db.query(func.avg(StoreReview.rating), func.count(StoreReview.id))
        .filter(StoreReview.store_id == store_id, StoreReview.status == ReviewStatus.approved)
        .one()
    )
    store = db.query(Store).filter(Store.id == store_id).first()
    if store:
        store.rating = Decimal(str(round(float(average or 0), 2)))
        store.review_count = int(count or 0)


def _ensure_delivered_seller_order(seller_order: SellerOrder) -> None:
    if seller_order.status != SellerOrderStatus.delivered:
        raise HTTPException(status_code=409, detail="Reviews are allowed only after delivery")


@router.post("/products/{product_id}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_product_review(
    product_id: UUID,
    data: ReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.reviews_create.value)),
):
    item = (
        db.query(OrderItem)
        .join(OrderItem.order)
        .filter(OrderItem.id == data.order_item_id, OrderItem.product_id == product_id)
        .first()
    )
    if not item or item.order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Purchased order item not found")
    seller_order = (
        db.query(SellerOrder)
        .filter(SellerOrder.order_id == item.order_id, SellerOrder.seller_id == item.seller_id)
        .first()
    )
    if not seller_order:
        raise HTTPException(status_code=409, detail="Seller order is unavailable")
    _ensure_delivered_seller_order(seller_order)

    review = ProductReview(
        product_id=product_id,
        order_item_id=item.id,
        customer_id=current_user.id,
        seller_id=item.seller_id,
        rating=data.rating,
        title=data.title,
        comment=data.comment,
        verified_purchase=True,
        status=ReviewStatus.pending,
    )
    db.add(review)
    _commit(db)
    db.refresh(review)
    return _review_response(review)


@router.get("/products/{product_id}/reviews", response_model=ReviewListResponse)
def list_product_reviews(
    product_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = db.query(ProductReview).filter(
        ProductReview.product_id == product_id,
        ProductReview.status == ReviewStatus.approved,
    )
    total = query.count()
    average = db.query(func.avg(ProductReview.rating)).filter(
        ProductReview.product_id == product_id,
        ProductReview.status == ReviewStatus.approved,
    ).scalar() or 0
    rows = query.order_by(ProductReview.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ReviewListResponse(total=total, page=page, page_size=page_size, average_rating=Decimal(str(round(float(average), 2))), results=[_review_response(row) for row in rows])


@router.patch("/reviews/{review_id}", response_model=ReviewResponse)
def update_product_review(
    review_id: UUID,
    data: ReviewUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.reviews_update.value)),
):
    review = db.query(ProductReview).filter(ProductReview.id == review_id, ProductReview.customer_id == current_user.id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(review, field, value)
    review.status = ReviewStatus.pending
    _commit(db)
    db.refresh(review)
    return _review_response(review)


@router.delete("/reviews/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product_review(
    review_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.reviews_delete.value)),
):
    review = db.query(ProductReview).filter(ProductReview.id == review_id, ProductReview.customer_id == current_user.id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.delete(review)
    _commit(db)


@router.post("/stores/{slug}/reviews", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
def create_store_review(
    slug: str,
    data: StoreReviewCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.reviews_create.value)),
):
    store = db.query(Store).filter(Store.slug == slug).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    seller_order = db.query(SellerOrder).join(SellerOrder.order).filter(
        SellerOrder.id == data.seller_order_id,
        SellerOrder.seller_id == store.seller_id,
    ).first()
    if not seller_order or seller_order.order.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Purchased seller order not found")
    _ensure_delivered_seller_order(seller_order)
    review = StoreReview(
        store_id=store.id,
        seller_order_id=seller_order.id,
        customer_id=current_user.id,
        rating=data.rating,
        title=data.title,
        comment=data.comment,
        verified_purchase=True,
        status=ReviewStatus.pending,
    )
    db.add(review)
    _commit(db)
    db.refresh(review)
    return _review_response(review)


@router.get("/stores/{slug}/reviews", response_model=ReviewListResponse)
def list_store_reviews(
    slug: str,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    store = db.query(Store).filter(Store.slug == slug).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    query = db.query(StoreReview).filter(StoreReview.store_id == store.id, StoreReview.status == ReviewStatus.approved)
    total = query.count()
    rows = query.order_by(StoreReview.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ReviewListResponse(total=total, page=page, page_size=page_size, average_rating=Decimal(store.rating or 0), results=[_review_response(row) for row in rows])


@router.get("/seller/reviews", response_model=ReviewListResponse)
def seller_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_reviews_read.value)),
):
    if not current_user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    seller_id = current_user.seller_profile.id
    query = db.query(ProductReview).filter(ProductReview.seller_id == seller_id)
    total = query.count()
    average = db.query(func.avg(ProductReview.rating)).filter(ProductReview.seller_id == seller_id, ProductReview.status == ReviewStatus.approved).scalar() or 0
    rows = query.order_by(ProductReview.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return ReviewListResponse(total=total, page=page, page_size=page_size, average_rating=Decimal(str(round(float(average), 2))), results=[_review_response(row) for row in rows])


@router.patch("/seller/reviews/{review_id}/reply", response_model=ReviewResponse)
def reply_to_review(
    review_id: UUID,
    data: SellerReviewReply,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_reviews_reply.value)),
):
    if not current_user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    review = db.query(ProductReview).filter(ProductReview.id == review_id, ProductReview.seller_id == current_user.seller_profile.id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.seller_reply = data.reply
    review.seller_replied_at = datetime.now(timezone.utc)
    _commit(db)
    db.refresh(review)
    return _review_response(review)


@router.post("/seller/reviews/{review_id}/report", status_code=status.HTTP_201_CREATED)
def report_review(
    review_id: UUID,
    data: ReviewReportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_reviews_report.value)),
):
    if not current_user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    review = db.query(ProductReview).filter(ProductReview.id == review_id, ProductReview.seller_id == current_user.seller_profile.id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    db.add(ReviewReport(product_review_id=review.id, reported_by_id=current_user.id, reason=data.reason, details=data.details))
    review.status = ReviewStatus.reported
    _commit(db)
    return {"reported": True, "review_id": str(review.id)}


@router.get("/admin/reviews", response_model=ReviewListResponse)
def admin_reviews(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.admin_reviews_read.value)),
):
    query = db.query(ProductReview)
    total = query.count()
    rows = query.order_by(ProductReview.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    average = db.query(func.avg(ProductReview.rating)).filter(ProductReview.status == ReviewStatus.approved).scalar() or 0
    return ReviewListResponse(total=total, page=page, page_size=page_size, average_rating=Decimal(str(round(float(average), 2))), results=[_review_response(row) for row in rows])


@router.patch("/admin/reviews/{review_id}/moderate", response_model=ReviewResponse)
def moderate_review(
    review_id: UUID,
    data: ReviewModerationRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.admin_reviews_moderate.value)),
):
    review = db.query(ProductReview).filter(ProductReview.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    review.status = data.status
    _commit(db)
    db.refresh(review)
    return _review_response(review)
