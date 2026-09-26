"""Admin catalog listing endpoints.

Minimal admin catalog implementation matching the storefront contract:
paginated products/categories/brands for the admin dashboard. Fields the
live schema doesn't track here are returned as null/defaults.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from api.deps import get_db
from api.enums import PermissionCode
from api.models import (
    Brand,
    BusinessCategory,
    Category,
    Inventory,
    Product,
    Seller,
)
from api.permissions import require_permission

router = APIRouter(prefix="/admin/catalog", tags=["Admin Catalog"])
brokers_router = APIRouter(prefix="/brokers", tags=["Brokers"])


def _paginate(query, page: int, page_size: int):
    total = query.count()
    total_pages = max(1, -(-total // page_size))
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": total_pages, "results": items}


def _product_row(product: Product, quantity: int) -> dict:
    return {
        "id": str(product.id),
        "seller_id": str(product.seller_id),
        "category_id": str(product.category_id),
        "brand_id": str(product.brand_id) if product.brand_id else None,
        "sku": product.sku,
        "barcode": getattr(product, "barcode", None),
        "name": product.name,
        "slug": product.slug,
        "short_description": None,
        "description": product.description,
        "price": float(product.price or 0),
        "sale_price": float(product.sale_price) if product.sale_price is not None else None,
        "cost_price": None,
        "tax_class": None,
        "currency": product.currency or "TZS",
        "weight": float(product.weight) if product.weight is not None else None,
        "featured": False,
        "track_stock": True,
        "quantity": quantity,
        "low_stock_threshold": 10,
        "warehouse_id": None,
        "status": product.status.value if product.status else None,
        "rejection_reason": product.rejection_reason,
        "is_active": product.is_active,
        "submitted_at": product.submitted_at.isoformat() if product.submitted_at else None,
        "approved_at": product.approved_at.isoformat() if product.approved_at else None,
        "approved_by_user_id": str(product.approved_by_user_id) if product.approved_by_user_id else None,
        "approval_method": None,
        "created_at": product.created_at.isoformat() if product.created_at else None,
        "images": [
            {
                "id": str(img.id),
                "product_id": str(img.product_id),
                "image_url": img.image_url,
                "thumbnail_url": img.thumbnail_url,
                "alt_text": img.alt_text,
                "is_primary": img.is_primary,
                "display_order": img.display_order,
            }
            for img in (getattr(product, "images", None) or [])
        ],
        "seller_business_name": product.seller.business_name if product.seller else None,
        "seller_contact_email": product.seller.contact_email if product.seller else None,
        "seller_contact_phone": product.seller.contact_phone if product.seller else None,
        "category_name": product.category.name if product.category else None,
        "brand_name": product.brand.name if product.brand else None,
    }


@router.get("/products")
def list_catalog_products(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
    status_filter: str | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission(PermissionCode.can_view_products.value)),
):
    query = (
        db.query(Product)
        .options(selectinload(Product.images))
        .join(Seller, Product.seller_id == Seller.id)
        .join(Category, Product.category_id == Category.id)
        .outerjoin(Brand, Product.brand_id == Brand.id)
    )
    if status_filter:
        query = query.filter(Product.status == status_filter)
    if search:
        term = f"%{search}%"
        query = query.filter(or_(Product.name.ilike(term), Product.sku.ilike(term)))
    query = query.order_by(Product.created_at.desc())

    total = query.count()
    total_pages = max(1, -(-total // page_size))
    products = query.offset((page - 1) * page_size).limit(page_size).all()

    quantities = dict(
        db.query(Inventory.product_id, func.coalesce(func.sum(Inventory.available_quantity), 0))
        .filter(Inventory.product_id.in_([p.id for p in products]))
        .group_by(Inventory.product_id)
        .all()
    ) if products else {}

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": [_product_row(p, int(quantities.get(p.id, 0))) for p in products],
    }


@router.get("/summary")
def catalog_summary(
    db: Session = Depends(get_db),
    _=Depends(require_permission(PermissionCode.can_view_products.value)),
):
    def count(status_value: str | None = None) -> int:
        q = db.query(func.count(Product.id))
        if status_value:
            q = q.filter(Product.status == status_value)
        return q.scalar() or 0

    return {
        "total_products": count(),
        "pending_products": count("pending_review"),
        "approved_products": count("approved"),
        "rejected_products": count("rejected"),
        "product_categories": db.query(func.count(Category.id)).scalar() or 0,
        "business_categories": db.query(func.count(BusinessCategory.id)).scalar() or 0,
        "brands": db.query(func.count(Brand.id)).scalar() or 0,
    }


@router.get("/product-categories")
def list_product_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission(PermissionCode.can_view_product_categories.value)),
):
    query = db.query(Category).order_by(Category.name)
    if search:
        query = query.filter(Category.name.ilike(f"%{search}%"))
    return _paginate(query, page, page_size)


@router.get("/business-categories")
def list_business_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    active_filter: str = Query("all"),
    db: Session = Depends(get_db),
    _=Depends(require_permission(PermissionCode.can_view_business_categories.value)),
):
    query = db.query(BusinessCategory).order_by(BusinessCategory.name)
    if search:
        query = query.filter(BusinessCategory.name.ilike(f"%{search}%"))
    if active_filter == "active":
        query = query.filter(BusinessCategory.active.is_(True))
    elif active_filter == "inactive":
        query = query.filter(BusinessCategory.active.is_(False))
    return _paginate(query, page, page_size)


@router.get("/brands")
def list_brands(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _=Depends(require_permission(PermissionCode.can_view_brands.value)),
):
    query = db.query(Brand).order_by(Brand.name)
    if search:
        query = query.filter(Brand.name.ilike(f"%{search}%"))
    return _paginate(query, page, page_size)


# Brokers module is not part of this branch — return an empty page so the
# admin UI degrades cleanly instead of logging 404s.
@brokers_router.get("/admin")
def admin_list_brokers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=200),
):
    return {"total": 0, "page": page, "page_size": page_size, "total_pages": 1, "results": []}
