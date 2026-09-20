from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import Order, OrderItem, OrderStatus, Product, ProductImage, ProductRecommendation, ProductView, RecommendationEvent, SearchHistory, SearchTerm, User
from api.permissions import require_permission
from api.schemas import (
    AlsoBoughtProductItem, AlsoBoughtResponse, ProductSearchResponse, ProductViewCreate, ProductViewResponse, RecommendationListResponse,
    SearchProductItem, SearchSuggestionResponse, SellerProductPerformanceItem,
    SellerSearchAnalyticsItem, TrendingSearchItem,
)

router = APIRouter(tags=["Search & Recommendations"])


def _product_image_url(db: Session, product: Product) -> str | None:
    """Return the best usable discovery image for a product.

    Discovery cards must not depend on the relationship being pre-loaded.
    Prefer the explicit primary image, then the lowest display-order image.
    Prefer a thumbnail when one exists, otherwise use the original image URL.
    """
    images = list(product.images or [])
    if not images:
        images = (
            db.query(ProductImage)
            .filter(ProductImage.product_id == product.id)
            .order_by(
                ProductImage.is_primary.desc(),
                ProductImage.display_order.asc(),
                ProductImage.created_at.asc(),
            )
            .all()
        )

    if not images:
        return None

    images.sort(
        key=lambda image: (
            0 if image.is_primary else 1,
            image.display_order if image.display_order is not None else 0,
            image.created_at or datetime.min.replace(tzinfo=timezone.utc),
        )
    )
    for image in images:
        if image.thumbnail_url:
            return image.thumbnail_url
        if image.image_url:
            return image.image_url
    return None


def _item(db: Session, product: Product) -> SearchProductItem:
    return SearchProductItem(
        id=product.id, seller_id=product.seller_id, category_id=product.category_id,
        brand_id=product.brand_id, name=product.name, slug=product.slug, price=product.price,
        sale_price=product.sale_price, currency=product.currency,
        primary_image_url=_product_image_url(db, product),
    )


def _active_products(db: Session):
    return db.query(Product).filter(Product.is_active.is_(True), Product.status == "approved")


@router.get("/search/products", response_model=ProductSearchResponse)
def search_products(
    q: str = Query(default="", max_length=255),
    category_id: UUID | None = None, seller_id: UUID | None = None, brand_id: UUID | None = None,
    min_price: Decimal | None = Query(default=None, ge=0), max_price: Decimal | None = Query(default=None, ge=0),
    in_stock: bool | None = None, sort: str = Query(default="relevance", pattern="^(relevance|newest|price_asc|price_desc|popular)$"),
    page: int = Query(default=1, ge=1), page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    query = _active_products(db)
    normalized = " ".join(q.lower().split())
    if normalized:
        pattern = f"%{normalized}%"
        query = query.filter(or_(func.lower(Product.name).like(pattern), func.lower(Product.description).like(pattern), func.lower(Product.sku).like(pattern)))
    if category_id: query = query.filter(Product.category_id == category_id)
    if seller_id: query = query.filter(Product.seller_id == seller_id)
    if brand_id: query = query.filter(Product.brand_id == brand_id)
    effective_price = func.coalesce(Product.sale_price, Product.price)
    if min_price is not None: query = query.filter(effective_price >= min_price)
    if max_price is not None: query = query.filter(effective_price <= max_price)
    # Variant stock integration is intentionally left to the inventory service; active products are searchable.
    total = query.count()
    if sort == "newest": query = query.order_by(Product.created_at.desc())
    elif sort == "price_asc": query = query.order_by(effective_price.asc())
    elif sort == "price_desc": query = query.order_by(effective_price.desc())
    elif sort == "popular":
        views = db.query(ProductView.product_id, func.count(ProductView.id).label("view_count")).group_by(ProductView.product_id).subquery()
        query = query.outerjoin(views, views.c.product_id == Product.id).order_by(func.coalesce(views.c.view_count, 0).desc())
    else: query = query.order_by(Product.created_at.desc())
    rows = query.offset((page - 1) * page_size).limit(page_size).all()
    if normalized:
        term = db.query(SearchTerm).filter(SearchTerm.term == normalized).first()
        if term is None:
            term = SearchTerm(term=normalized, search_count=1, last_searched_at=datetime.now(timezone.utc)); db.add(term)
        else:
            term.search_count += 1; term.last_searched_at = datetime.now(timezone.utc)
        db.add(SearchHistory(query=q, normalized_query=normalized, filters={"category_id": str(category_id) if category_id else None, "seller_id": str(seller_id) if seller_id else None}, result_count=total))
        db.commit()
    return ProductSearchResponse(total=total, page=page, page_size=page_size, results=[_item(db, row) for row in rows])


@router.get("/search/suggestions", response_model=SearchSuggestionResponse)
def search_suggestions(q: str = Query(min_length=1, max_length=100), limit: int = Query(default=8, ge=1, le=20), db: Session = Depends(get_db)):
    normalized = " ".join(q.lower().split())
    terms = db.query(SearchTerm.term).filter(SearchTerm.term.like(f"{normalized}%")).order_by(SearchTerm.search_count.desc()).limit(limit).all()
    names = db.query(Product.name).filter(Product.is_active.is_(True), func.lower(Product.name).like(f"%{normalized}%")).limit(limit).all()
    values=[]
    for value in [row[0] for row in terms] + [row[0] for row in names]:
        if value not in values: values.append(value)
    return SearchSuggestionResponse(suggestions=values[:limit])


@router.get("/search/trending", response_model=list[TrendingSearchItem])
def trending_searches(limit: int = Query(default=10, ge=1, le=50), db: Session = Depends(get_db)):
    rows = db.query(SearchTerm).order_by(SearchTerm.search_count.desc(), SearchTerm.last_searched_at.desc()).limit(limit).all()
    return [TrendingSearchItem(term=row.term, search_count=row.search_count) for row in rows]


@router.post("/products/{product_id}/view", response_model=ProductViewResponse, status_code=status.HTTP_201_CREATED)
def record_product_view(product_id: UUID, payload: ProductViewCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.search_history_manage.value))):
    product = _active_products(db).filter(Product.id == product_id).first()
    if product is None: raise HTTPException(status_code=404, detail="Product not found")
    view = ProductView(product_id=product_id, user_id=current_user.id, session_id=payload.session_id, source=payload.source, search_query=payload.search_query)
    db.add(view); db.add(RecommendationEvent(user_id=current_user.id, product_id=product_id, event_type="view", metadata_json={"source": payload.source}))
    db.commit(); db.refresh(view); return ProductViewResponse.model_validate(view)


@router.get("/products/{product_id}/related", response_model=RecommendationListResponse)
def related_products(product_id: UUID, limit: int = Query(default=12, ge=1, le=50), db: Session = Depends(get_db)):
    product = _active_products(db).filter(Product.id == product_id).first()
    if product is None: raise HTTPException(status_code=404, detail="Product not found")
    rows = _active_products(db).filter(Product.id != product.id, or_(Product.category_id == product.category_id, Product.brand_id == product.brand_id)).order_by(Product.created_at.desc()).limit(limit).all()
    return RecommendationListResponse(total=len(rows), results=[_item(db, row) for row in rows])


@router.get("/products/{product_id}/also-bought", response_model=AlsoBoughtResponse)
def also_bought_products(
    product_id: UUID,
    limit: int = Query(default=8, ge=1, le=24),
    db: Session = Depends(get_db),
):
    """Products genuinely purchased by customers who purchased this product.

    Only successful/non-refunded order states participate. Results are
    aggregated; no customer identity is exposed.
    """
    product = _active_products(db).filter(Product.id == product_id).first()
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    successful_statuses = (
        OrderStatus.paid,
        OrderStatus.processing,
        OrderStatus.shipped,
        OrderStatus.delivered,
    )

    buyer_ids = (
        db.query(Order.user_id.label("user_id"))
        .join(OrderItem, OrderItem.order_id == Order.id)
        .filter(
            OrderItem.product_id == product_id,
            Order.status.in_(successful_statuses),
        )
        .distinct()
        .subquery()
    )

    ranked = (
        db.query(
            OrderItem.product_id.label("product_id"),
            func.count(func.distinct(Order.user_id)).label("customer_count"),
            func.count(func.distinct(Order.id)).label("order_count"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .join(buyer_ids, buyer_ids.c.user_id == Order.user_id)
        .join(Product, Product.id == OrderItem.product_id)
        .filter(
            OrderItem.product_id != product_id,
            Order.status.in_(successful_statuses),
            Product.is_active.is_(True),
            Product.status == "approved",
        )
        .group_by(OrderItem.product_id)
        .order_by(
            desc("customer_count"),
            desc("order_count"),
            func.max(Order.created_at).desc(),
        )
        .limit(limit)
        .all()
    )

    if not ranked:
        return AlsoBoughtResponse(total=0, results=[])

    ids = [row.product_id for row in ranked]
    products_by_id = {
        row.id: row
        for row in _active_products(db).filter(Product.id.in_(ids)).all()
    }

    results: list[AlsoBoughtProductItem] = []
    for row in ranked:
        candidate = products_by_id.get(row.product_id)
        if candidate is None:
            continue
        base = _item(db, candidate)
        results.append(
            AlsoBoughtProductItem(
                **base.model_dump(),
                customer_count=int(row.customer_count or 0),
                order_count=int(row.order_count or 0),
            )
        )

    return AlsoBoughtResponse(total=len(results), results=results)


@router.get("/recommendations", response_model=RecommendationListResponse)
def recommendations(limit: int = Query(default=20, ge=1, le=50), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.recommendations_read.value))):
    ids = [row.product_id for row in db.query(ProductRecommendation).filter(ProductRecommendation.user_id == current_user.id).order_by(ProductRecommendation.score.desc()).limit(limit).all()]
    rows = _active_products(db).filter(Product.id.in_(ids)).all() if ids else []
    if not rows:
        viewed_categories = db.query(Product.category_id, func.count(ProductView.id).label("n")).join(ProductView, ProductView.product_id == Product.id).filter(ProductView.user_id == current_user.id).group_by(Product.category_id).order_by(desc("n")).limit(3).all()
        categories=[row[0] for row in viewed_categories]
        query=_active_products(db)
        if categories: query=query.filter(Product.category_id.in_(categories))
        rows=query.order_by(Product.created_at.desc()).limit(limit).all()
    return RecommendationListResponse(total=len(rows), results=[_item(db, row) for row in rows])


@router.get("/recommendations/recently-viewed", response_model=RecommendationListResponse)
def recently_viewed(limit: int = Query(default=20, ge=1, le=50), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.recommendations_read.value))):
    recent = db.query(ProductView.product_id, func.max(ProductView.created_at).label("last_viewed")).filter(ProductView.user_id == current_user.id).group_by(ProductView.product_id).order_by(desc("last_viewed")).limit(limit).all()
    ids=[row[0] for row in recent]
    by_id={row.id: row for row in _active_products(db).filter(Product.id.in_(ids)).all()} if ids else {}
    rows=[by_id[item] for item in ids if item in by_id]
    return RecommendationListResponse(total=len(rows), results=[_item(db, row) for row in rows])


@router.get("/seller/search-analytics", response_model=list[SellerSearchAnalyticsItem])
def seller_search_analytics(limit: int = Query(default=20, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_search_analytics_read.value))):
    if not current_user.seller_profile: raise HTTPException(status_code=403, detail="Seller profile required")
    rows = db.query(ProductView.search_query, func.count(ProductView.id)).join(Product, Product.id == ProductView.product_id).filter(Product.seller_id == current_user.seller_profile.id, ProductView.search_query.isnot(None)).group_by(ProductView.search_query).order_by(func.count(ProductView.id).desc()).limit(limit).all()
    return [SellerSearchAnalyticsItem(query=row[0], searches=0, product_views=row[1]) for row in rows]


@router.get("/seller/product-performance", response_model=list[SellerProductPerformanceItem])
def seller_product_performance(limit: int = Query(default=50, ge=1, le=100), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_search_analytics_read.value))):
    if not current_user.seller_profile: raise HTTPException(status_code=403, detail="Seller profile required")
    rows = db.query(Product.id, Product.name, func.count(ProductView.id)).outerjoin(ProductView, ProductView.product_id == Product.id).filter(Product.seller_id == current_user.seller_profile.id).group_by(Product.id, Product.name).order_by(func.count(ProductView.id).desc()).limit(limit).all()
    return [SellerProductPerformanceItem(product_id=row[0], product_name=row[1], views=row[2]) for row in rows]
