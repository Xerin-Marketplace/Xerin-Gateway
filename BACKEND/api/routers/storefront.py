from __future__ import annotations

import uuid
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from sqlalchemy import func
from sqlalchemy.orm import Session, selectinload

from api.deps import get_db
from api.enums import PermissionCode, StoreStatus
from api.models import Category, Product, ProductImage, ProductStatus, Seller, Store, User
from api.permissions import require_permission
from api.schemas import ProductResponse, StoreResponse, StoreUpdate
from api.routers.stores import (
    STORE_BANNER_DIR,
    STORE_LOGO_DIR,
    MAX_BANNER_SIZE,
    MAX_LOGO_SIZE,
    delete_old_local_file,
    generate_unique_slug,
    get_current_seller,
    get_or_create_store,
    save_store_image,
)

router = APIRouter(tags=["Seller Storefront"])


def _apply_store_update(db: Session, store: Store, data: StoreUpdate) -> Store:
    values = data.model_dump(exclude_unset=True)
    if "store_name" in values:
        name = values["store_name"].strip()
        if not name:
            raise HTTPException(status_code=400, detail="Store name cannot be empty")
        values["store_name"] = name
        values["slug"] = generate_unique_slug(db, name, store.id)
    for field, value in values.items():
        setattr(store, field, value)
    db.commit(); db.refresh(store)
    return store


@router.get("/seller/store", response_model=StoreResponse)
def get_seller_store(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_store_read.value)),
):
    return get_or_create_store(db, get_current_seller(db, current_user))


@router.patch("/seller/store", response_model=StoreResponse)
def update_seller_store(
    data: StoreUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_store_update.value)),
):
    seller = get_current_seller(db, current_user)
    return _apply_store_update(db, get_or_create_store(db, seller), data)


async def _upload_branding(file: UploadFile, image_type: str, db: Session, current_user: User) -> Store:
    seller = get_current_seller(db, current_user)
    store = get_or_create_store(db, seller)
    is_logo = image_type == "logo"
    old = store.logo_url if is_logo else store.banner_url
    url = await save_store_image(
        file=file,
        directory=STORE_LOGO_DIR if is_logo else STORE_BANNER_DIR,
        store_id=store.id,
        image_type=image_type,
        max_size=MAX_LOGO_SIZE if is_logo else MAX_BANNER_SIZE,
    )
    if is_logo: store.logo_url = url
    else: store.banner_url = url
    db.commit(); db.refresh(store); delete_old_local_file(old)
    return store


@router.post("/seller/store/logo", response_model=StoreResponse)
async def upload_seller_store_logo(
    logo: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_store_branding.value)),
):
    return await _upload_branding(logo, "logo", db, current_user)


@router.post("/seller/store/banner", response_model=StoreResponse)
async def upload_seller_store_banner(
    banner: UploadFile = File(...), db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_store_branding.value)),
):
    return await _upload_branding(banner, "banner", db, current_user)


def _public_store(db: Session, slug: str) -> Store:
    store = db.query(Store).filter(Store.slug == slug, Store.status == StoreStatus.active).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found")
    return store


@router.get("/stores/{slug}/products", response_model=list[ProductResponse])
def public_store_products(
    slug: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    category_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
):
    store = _public_store(db, slug)
    query = db.query(Product).options(selectinload(Product.images)).filter(
        Product.seller_id == store.seller_id,
        Product.status == ProductStatus.approved,
        Product.is_active.is_(True),
    )
    if category_id: query = query.filter(Product.category_id == category_id)
    return query.order_by(Product.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()


@router.get("/stores/{slug}/categories")
def public_store_categories(slug: str, db: Session = Depends(get_db)):
    store = _public_store(db, slug)
    rows = (
        db.query(Category.id, Category.name, Category.slug, func.count(Product.id).label("product_count"))
        .join(Product, Product.category_id == Category.id)
        .filter(Product.seller_id == store.seller_id, Product.status == ProductStatus.approved, Product.is_active.is_(True))
        .group_by(Category.id, Category.name, Category.slug)
        .order_by(Category.name.asc()).all()
    )
    return [{"id": r.id, "name": r.name, "slug": r.slug, "product_count": r.product_count} for r in rows]
