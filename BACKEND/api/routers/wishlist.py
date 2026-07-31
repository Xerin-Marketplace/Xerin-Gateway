from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.deps import get_db
from api.enums import PermissionCode, StoreStatus
from api.models import (
    FavoriteStore,
    Inventory,
    Product,
    ProductImage,
    ProductStatus,
    Seller,
    Store,
    User,
    WishlistProduct,
)
from api.permissions import require_permission
from api.schemas import (
    FavoriteStoreItemResponse,
    FavoriteStoreListResponse,
    WishlistMutationResponse,
    WishlistProductItemResponse,
    WishlistProductListResponse,
    WishlistSummaryResponse,
)

router = APIRouter(prefix="/wishlist", tags=["Wishlist"] )


def _commit(db: Session, duplicate_detail: str | None = None) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=duplicate_detail or "Wishlist conflict") from exc
    except Exception:
        db.rollback()
        raise


def _product_is_public(product: Product) -> bool:
    return product.status == ProductStatus.approved and bool(product.is_active)


def _primary_image(product: Product) -> str | None:
    images = sorted(product.images or [], key=lambda image: (not bool(getattr(image, "is_primary", False)), getattr(image, "display_order", 0)))
    if not images:
        return None
    return images[0].thumbnail_url or images[0].image_url


def _product_stock(db: Session, product_id: UUID) -> int:
    return int(db.query(func.coalesce(func.sum(Inventory.available_quantity), 0)).filter(Inventory.product_id == product_id).scalar() or 0)


def _product_item(db: Session, row: WishlistProduct) -> WishlistProductItemResponse:
    product = row.product
    store = product.seller.store if product.seller else None
    available = _product_is_public(product) and (store is None or (store.status == StoreStatus.active and store.accept_orders and not store.vacation_mode))
    return WishlistProductItemResponse(
        wishlist_id=row.id,
        product_id=product.id,
        name=product.name,
        slug=product.slug,
        sku=product.sku,
        price=Decimal(product.price),
        sale_price=Decimal(product.sale_price) if product.sale_price is not None else None,
        currency=product.currency,
        primary_image_url=_primary_image(product),
        store_name=store.store_name if store else None,
        store_slug=store.slug if store else None,
        is_available=available,
        is_in_stock=_product_stock(db, product.id) > 0,
        created_at=row.created_at,
    )


def _store_item(row: FavoriteStore) -> FavoriteStoreItemResponse:
    store = row.store
    return FavoriteStoreItemResponse(
        favorite_id=row.id,
        store_id=store.id,
        store_name=store.store_name,
        slug=store.slug,
        logo_url=store.logo_url,
        banner_url=store.banner_url,
        rating=Decimal(store.rating or 0),
        review_count=store.review_count or 0,
        followers_count=store.followers_count or 0,
        is_available=store.status == StoreStatus.active and store.accept_orders and not store.vacation_mode,
        created_at=row.created_at,
    )


@router.post("/products/{product_id}", response_model=WishlistMutationResponse, status_code=status.HTTP_201_CREATED)
def add_product_to_wishlist(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_manage.value)),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or not _product_is_public(product):
        raise HTTPException(status_code=404, detail="Available product not found")
    db.add(WishlistProduct(user_id=current_user.id, product_id=product.id))
    _commit(db, "Product is already in your wishlist")
    return WishlistMutationResponse(message="Product added to wishlist")


@router.delete("/products/{product_id}", response_model=WishlistMutationResponse)
def remove_product_from_wishlist(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_manage.value)),
):
    row = db.query(WishlistProduct).filter(WishlistProduct.user_id == current_user.id, WishlistProduct.product_id == product_id).first()
    if not row:
        raise HTTPException(status_code=404, detail="Wishlist product not found")
    db.delete(row)
    _commit(db)
    return WishlistMutationResponse(message="Product removed from wishlist")


@router.get("/products", response_model=WishlistProductListResponse)
def list_wishlist_products(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_read.value)),
):
    query = db.query(WishlistProduct).options(
        joinedload(WishlistProduct.product).joinedload(Product.images),
        joinedload(WishlistProduct.product).joinedload(Product.seller).joinedload(Seller.store),
    ).filter(WishlistProduct.user_id == current_user.id)
    total = query.count()
    rows = query.order_by(WishlistProduct.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return WishlistProductListResponse(total=total, page=page, page_size=page_size, results=[_product_item(db, row) for row in rows])


@router.post("/stores/{store_slug}", response_model=WishlistMutationResponse, status_code=status.HTTP_201_CREATED)
def add_favorite_store(
    store_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_manage.value)),
):
    store = db.query(Store).filter(Store.slug == store_slug, Store.status == StoreStatus.active).with_for_update().first()
    if not store:
        raise HTTPException(status_code=404, detail="Active store not found")
    db.add(FavoriteStore(user_id=current_user.id, store_id=store.id))
    store.followers_count = (store.followers_count or 0) + 1
    _commit(db, "Store is already in your favorites")
    return WishlistMutationResponse(message="Store added to favorites")


@router.delete("/stores/{store_slug}", response_model=WishlistMutationResponse)
def remove_favorite_store(
    store_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_manage.value)),
):
    row = db.query(FavoriteStore).join(Store).filter(FavoriteStore.user_id == current_user.id, Store.slug == store_slug).with_for_update().first()
    if not row:
        raise HTTPException(status_code=404, detail="Favorite store not found")
    store = row.store
    db.delete(row)
    store.followers_count = max(0, (store.followers_count or 0) - 1)
    _commit(db)
    return WishlistMutationResponse(message="Store removed from favorites")


@router.get("/stores", response_model=FavoriteStoreListResponse)
def list_favorite_stores(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_read.value)),
):
    query = db.query(FavoriteStore).options(joinedload(FavoriteStore.store)).filter(FavoriteStore.user_id == current_user.id)
    total = query.count()
    rows = query.order_by(FavoriteStore.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return FavoriteStoreListResponse(total=total, page=page, page_size=page_size, results=[_store_item(row) for row in rows])


@router.get("/summary", response_model=WishlistSummaryResponse)
def wishlist_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_read.value)),
):
    product_count = db.query(func.count(WishlistProduct.id)).filter(WishlistProduct.user_id == current_user.id).scalar() or 0
    store_count = db.query(func.count(FavoriteStore.id)).filter(FavoriteStore.user_id == current_user.id).scalar() or 0
    return WishlistSummaryResponse(product_count=int(product_count), favorite_store_count=int(store_count))


@router.delete("/clear", response_model=WishlistMutationResponse)
def clear_wishlist(
    include_stores: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.wishlist_manage.value)),
):
    db.query(WishlistProduct).filter(WishlistProduct.user_id == current_user.id).delete(synchronize_session=False)
    if include_stores:
        rows = db.query(FavoriteStore).options(joinedload(FavoriteStore.store)).filter(FavoriteStore.user_id == current_user.id).all()
        for row in rows:
            row.store.followers_count = max(0, (row.store.followers_count or 0) - 1)
            db.delete(row)
    _commit(db)
    return WishlistMutationResponse(message="Wishlist cleared")
