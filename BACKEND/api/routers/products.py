from __future__ import annotations

from datetime import datetime, timezone
from itertools import product as cartesian_product
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.enums import PermissionCode
from api.models import (
    Brand,
    Category,
    Product,
    PaymentCurrency,
    PaymentFxRate,
    ProductImage,
    ProductOption,
    ProductOptionValue,
    ProductStatus,
    ProductTag,
    ProductVariant,
    ProductVariantValue,
    Inventory,
    MarketplaceSettings,
    Seller,
    SellerStatus,
    Store,
    User,
)
from api.permissions import require_permission
from api.schemas import (
    BrandCreate,
    BrandResponse,
    CategoryCreate,
    CategoryResponse,
    ProductCreate,
    ProductImageCreate,
    ProductImageReorderRequest,
    ProductImageResponse,
    ProductImageUpdate,
    ProductResponse,
    ProductTagCreate,
    ProductTagResponse,
    ProductUpdate,
    ProductOptionCreate,
    ProductOptionResponse,
    ProductOptionUpdate,
    ProductVariantCreate,
    ProductVariantGenerateRequest,
    ProductVariantResponse,
    ProductVariantUpdate,
)
from api.services.category_image_service import delete_category_image_files, store_category_image
from api.services.seller_pricing import apply_product_pricing, apply_variant_pricing
from api.services.inventory_catalog import inventory_configuration_errors
from api.services.product_image_service import (
    MAX_PRODUCT_IMAGES,
    delete_product_image_files,
    store_product_image,
)

router = APIRouter(prefix="/products", tags=["Products"])


def _require_active_listing_currency(db: Session, code: str) -> PaymentCurrency:
    normalized = (code or "TZS").strip().upper()
    currency = (
        db.query(PaymentCurrency)
        .filter(PaymentCurrency.code == normalized, PaymentCurrency.is_active.is_(True))
        .first()
    )
    if currency is None:
        raise HTTPException(
            status_code=422,
            detail=f"Currency {normalized} is not enabled for product listings",
        )
    return currency


def _commit(db: Session, *, conflict_detail: str = "Database conflict") -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_detail) from exc
    except Exception:
        db.rollback()
        raise


def get_my_seller(db: Session, current_user: User, *, require_approved: bool = True) -> Seller:
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must register as a seller first")
    if require_approved and seller.status != SellerStatus.approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller account is not approved")
    return seller


def get_seller_product(db: Session, product_id: UUID, seller_id: UUID) -> Product:
    product = db.query(Product).filter(Product.id == product_id, Product.seller_id == seller_id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or not owned by you")
    return product


def _ensure_editable(product: Product) -> None:
    if product.status == ProductStatus.pending_review:
        raise HTTPException(status_code=409, detail="Product is under review. Wait for the review result before editing it")


def _next_display_order(db: Session, product_id: UUID) -> int:
    latest = (
        db.query(ProductImage)
        .filter(ProductImage.product_id == product_id)
        .order_by(ProductImage.display_order.desc())
        .first()
    )
    return (latest.display_order + 1) if latest else 0


def _make_primary(db: Session, product_id: UUID, image_id: UUID) -> None:
    db.query(ProductImage).filter(ProductImage.product_id == product_id).update(
        {"is_primary": False}, synchronize_session=False
    )
    db.query(ProductImage).filter(
        ProductImage.product_id == product_id,
        ProductImage.id == image_id,
    ).update({"is_primary": True}, synchronize_session=False)


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("can_create_product_categories")),
):
    del current_user
    if db.query(Category).filter(Category.slug == data.slug).first():
        raise HTTPException(status_code=409, detail="Category slug already exists")
    if data.parent_id and not db.query(Category).filter(Category.id == data.parent_id).first():
        raise HTTPException(status_code=404, detail="Parent category not found")
    category = Category(parent_id=data.parent_id, name=data.name, slug=data.slug)
    db.add(category)
    _commit(db, conflict_detail="Category name or slug conflicts with an existing category")
    db.refresh(category)
    return category


@router.post("/categories/with-image", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
async def create_category_with_image(
    name: str = Form(...),
    slug: str = Form(...),
    parent_id: UUID | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("can_create_product_categories")),
):
    del current_user
    if db.query(Category).filter(Category.slug == slug).first():
        raise HTTPException(status_code=409, detail="Category slug already exists")
    if parent_id and not db.query(Category).filter(Category.id == parent_id).first():
        raise HTTPException(status_code=404, detail="Parent category not found")

    category = Category(parent_id=parent_id, name=name.strip(), slug=slug.strip())
    db.add(category)
    db.flush()

    try:
        if image is not None and image.filename:
            stored = await store_category_image(image, category_id=category.id)
            category.image_url = stored.image_url
            category.thumbnail_url = stored.thumbnail_url
            category.image_storage_key = stored.storage_key
        _commit(db, conflict_detail="Category name or slug conflicts with an existing category")
    except Exception:
        db.rollback()
        if category.image_storage_key:
            delete_category_image_files(category.image_storage_key)
        raise

    db.refresh(category)
    return category


@router.post("/categories/{category_id}/image", response_model=CategoryResponse)
async def upload_category_image(
    category_id: UUID,
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("can_create_product_categories")),
):
    del current_user
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    old_storage_key = category.image_storage_key
    stored = await store_category_image(image, category_id=category.id)
    category.image_url = stored.image_url
    category.thumbnail_url = stored.thumbnail_url
    category.image_storage_key = stored.storage_key
    _commit(db)
    if old_storage_key and old_storage_key != stored.storage_key:
        delete_category_image_files(old_storage_key)
    db.refresh(category)
    return category


@router.delete("/categories/{category_id}/image", response_model=CategoryResponse)
def remove_category_image(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("can_create_product_categories")),
):
    del current_user
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    storage_key = category.image_storage_key
    category.image_url = None
    category.thumbnail_url = None
    category.image_storage_key = None
    _commit(db)
    delete_category_image_files(storage_key)
    db.refresh(category)
    return category


@router.get("/categories", response_model=list[CategoryResponse])
def get_categories(db: Session = Depends(get_db)):
    return db.query(Category).order_by(Category.name.asc()).all()


@router.get("/categories/{category_id}", response_model=CategoryResponse)
def get_category(category_id: UUID, db: Session = Depends(get_db)):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/brands", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
def create_brand(
    data: BrandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("can_create_brands")),
):
    del current_user
    if db.query(Brand).filter(Brand.slug == data.slug).first():
        raise HTTPException(status_code=409, detail="Brand slug already exists")
    brand = Brand(name=data.name, slug=data.slug)
    db.add(brand)
    _commit(db, conflict_detail="Brand name or slug conflicts with an existing brand")
    db.refresh(brand)
    return brand


@router.get("/brands", response_model=list[BrandResponse])
def get_brands(db: Session = Depends(get_db)):
    return db.query(Brand).order_by(Brand.name.asc()).all()


@router.get("/brands/{brand_id}", response_model=BrandResponse)
def get_brand(brand_id: UUID, db: Session = Depends(get_db)):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    return brand


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_create.value)),
):
    seller = get_my_seller(db, current_user)
    store = db.query(Store).filter(Store.id == data.store_id, Store.seller_id == seller.id).first()
    if not store:
        raise HTTPException(status_code=404, detail="Store not found or not owned by you")
    if not db.query(Category).filter(Category.id == data.category_id).first():
        raise HTTPException(status_code=404, detail="Category not found")
    if data.brand_id and not db.query(Brand).filter(Brand.id == data.brand_id).first():
        raise HTTPException(status_code=404, detail="Brand not found")
    if db.query(Product).filter(Product.sku == data.sku).first():
        raise HTTPException(status_code=409, detail="Product SKU already exists")
    if db.query(Product).filter(Product.slug == data.slug).first():
        raise HTTPException(status_code=409, detail="Product slug already exists")

    listing_currency = _require_active_listing_currency(db, data.currency)

    product = Product(
        seller_id=seller.id,
        store_id=store.id,
        category_id=data.category_id,
        brand_id=data.brand_id,
        sku=data.sku,
        name=data.name,
        slug=data.slug,
        description=data.description,
        seller_base_price=data.price,
        seller_sale_price=data.sale_price,
        price=data.price,  # replaced below by pricing engine
        sale_price=data.sale_price,
        currency=listing_currency.code,
        weight=data.weight,
        status=ProductStatus.draft,
        is_active=True,
    )
    db.add(product)
    db.flush()
    apply_product_pricing(db, product, data.price, data.sale_price)
    _commit(db, conflict_detail="Product SKU or slug already exists")
    db.refresh(product)
    return product


@router.get("", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None, max_length=200),
    category_id: UUID | None = Query(default=None),
    brand_id: UUID | None = Query(default=None),
    seller_id: UUID | None = Query(default=None),
    store_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(Product).filter(Product.is_active.is_(True), Product.status == ProductStatus.approved)
    if search and search.strip():
        term = search.strip()
        query = query.filter(or_(Product.name.ilike(f"%{term}%"), Product.description.ilike(f"%{term}%"), Product.sku.ilike(f"%{term}%")))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if brand_id:
        query = query.filter(Product.brand_id == brand_id)
    if seller_id:
        query = query.filter(Product.seller_id == seller_id)
    if store_id:
        query = query.filter(Product.store_id == store_id)
    return query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/my-products", response_model=list[ProductResponse])
def get_my_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_read.value)),
    product_status: ProductStatus | None = Query(default=None, alias="status"),
    store_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    seller = get_my_seller(db, current_user, require_approved=False)
    query = db.query(Product).filter(Product.seller_id == seller.id)
    if product_status:
        query = query.filter(Product.status == product_status)
    if store_id:
        store = db.query(Store).filter(Store.id == store_id, Store.seller_id == seller.id).first()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found or not owned by you")
        query = query.filter(Product.store_id == store_id)
    return query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/my-products/{product_id}", response_model=ProductResponse)
def get_my_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_read.value)),
):
    seller = get_my_seller(db, current_user, require_approved=False)
    return get_seller_product(db, product_id, seller.id)


@router.post("/{product_id}/submit", response_model=ProductResponse)
def submit_product_for_review(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_submit.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    if product.status not in {ProductStatus.draft, ProductStatus.rejected}:
        raise HTTPException(status_code=409, detail="Only draft or rejected products can be submitted")
    image_count = db.query(ProductImage).filter(ProductImage.product_id == product.id).count()
    if image_count < 1:
        raise HTTPException(status_code=400, detail="Upload at least one product image before submitting for review")
    inventory_errors = inventory_configuration_errors(db, product)
    if inventory_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "Product inventory is not ready for review",
                "errors": inventory_errors,
            },
        )
    if not db.query(ProductImage).filter(ProductImage.product_id == product.id, ProductImage.is_primary.is_(True)).first():
        first = db.query(ProductImage).filter(ProductImage.product_id == product.id).order_by(ProductImage.display_order.asc()).first()
        if first:
            first.is_primary = True
    submitted_at = datetime.now(timezone.utc)
    settings = (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.singleton_key == 1)
        .first()
    )
    auto_approve = bool(settings and settings.auto_approve_products)

    product.rejection_reason = None
    product.submitted_at = submitted_at
    if auto_approve:
        # All normal submission validation above still runs. Auto approval only
        # changes the final moderation state after the product is valid.
        product.status = ProductStatus.approved
        product.approved_at = submitted_at
        product.approved_by_user_id = None
        product.approval_method = "automatic"
    else:
        product.status = ProductStatus.pending_review
        product.approved_at = None
        product.approved_by_user_id = None
        product.approval_method = None
    _commit(db)
    db.refresh(product)
    return product


@router.get("/listing-currencies")
def get_listing_currencies(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_read.value)),
):
    """Currencies the administrator currently allows sellers to use for product listings."""
    rows = (
        db.query(PaymentCurrency)
        .filter(PaymentCurrency.is_active.is_(True))
        .order_by(PaymentCurrency.is_base.desc(), PaymentCurrency.code.asc())
        .all()
    )
    return [
        {
            "id": str(row.id),
            "code": row.code,
            "name": row.name,
            "symbol": row.symbol,
            "decimal_places": row.decimal_places,
            "is_base": row.is_base,
        }
        for row in rows
    ]


@router.get("/display-currencies")
def get_display_currencies(db: Session = Depends(get_db)):
    """Public active display currencies with their current conversion rate to TZS.

    `rate_to_tzs` means: 1 unit of the currency equals X TZS.
    TZS always has a rate of 1. Currencies without a current active TZS rate
    are omitted so buyers can never select an unconvertible display currency.
    """
    now = datetime.now(timezone.utc)
    currencies = (
        db.query(PaymentCurrency)
        .filter(PaymentCurrency.is_active.is_(True))
        .order_by(PaymentCurrency.is_base.desc(), PaymentCurrency.code.asc())
        .all()
    )
    result = []
    for currency in currencies:
        code = currency.code.upper().strip()
        if code == "TZS":
            rate_to_tzs = 1
            rate_source = "settlement"
            effective_at = now
        else:
            fx = (
                db.query(PaymentFxRate)
                .filter(
                    PaymentFxRate.base_currency == code,
                    PaymentFxRate.quote_currency == "TZS",
                    PaymentFxRate.is_active.is_(True),
                    PaymentFxRate.effective_at <= now,
                )
                .order_by(PaymentFxRate.effective_at.desc())
                .first()
            )
            if fx is None:
                continue
            rate_to_tzs = fx.rate
            rate_source = fx.source
            effective_at = fx.effective_at
        result.append(
            {
                "id": str(currency.id),
                "code": code,
                "name": currency.name,
                "symbol": currency.symbol,
                "decimal_places": currency.decimal_places,
                "is_base": currency.is_base,
                "rate_to_tzs": str(rate_to_tzs),
                "rate_source": rate_source,
                "effective_at": effective_at,
            }
        )
    return result


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_update.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    update_data = data.model_dump(exclude_unset=True)

    if "store_id" in update_data:
        store = db.query(Store).filter(Store.id == update_data["store_id"], Store.seller_id == seller.id).first()
        if not store:
            raise HTTPException(status_code=404, detail="Store not found or not owned by you")
    if "category_id" in update_data and not db.query(Category).filter(Category.id == update_data["category_id"]).first():
        raise HTTPException(status_code=404, detail="Category not found")
    if update_data.get("brand_id") and not db.query(Brand).filter(Brand.id == update_data["brand_id"]).first():
        raise HTTPException(status_code=404, detail="Brand not found")
    if "sku" in update_data and db.query(Product).filter(Product.sku == update_data["sku"], Product.id != product.id).first():
        raise HTTPException(status_code=409, detail="SKU already exists")
    if "slug" in update_data and db.query(Product).filter(Product.slug == update_data["slug"], Product.id != product.id).first():
        raise HTTPException(status_code=409, detail="Slug already exists")
    if "currency" in update_data:
        update_data["currency"] = _require_active_listing_currency(db, update_data["currency"]).code

    for key, value in update_data.items():
        setattr(product, key, value)
    product.status = ProductStatus.draft
    product.rejection_reason = None
    product.submitted_at = None
    product.approved_at = None
    product.approved_by_user_id = None
    # Incoming `price` / `sale_price` are seller-entered base values.
    base_price = data.price if data.price is not None else product.seller_base_price
    base_sale = data.sale_price if "sale_price" in data.model_fields_set else product.seller_sale_price
    if base_price is not None:
        apply_product_pricing(db, product, base_price, base_sale)
    _commit(db, conflict_detail="Product SKU or slug already exists")
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_delete.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    if product.status == ProductStatus.pending_review:
        raise HTTPException(status_code=409, detail="A product under review cannot be archived")
    product.is_active = False
    product.status = ProductStatus.inactive
    _commit(db)
    return {"message": "Product archived successfully"}


@router.post("/{product_id}/images/upload", response_model=list[ProductImageResponse], status_code=status.HTTP_201_CREATED)
async def upload_product_images(
    product_id: UUID,
    files: list[UploadFile] = File(..., description="One to ten JPEG, PNG or WEBP product images"),
    alt_text: str | None = Form(default=None, max_length=255),
    make_first_primary: bool = Form(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_product_images_manage.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    if not files:
        raise HTTPException(status_code=400, detail="At least one image is required")
    existing_count = db.query(ProductImage).filter(ProductImage.product_id == product.id).count()
    if existing_count + len(files) > MAX_PRODUCT_IMAGES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PRODUCT_IMAGES} images allowed per product")

    created: list[ProductImage] = []
    saved_keys: list[tuple[str, str]] = []
    order = _next_display_order(db, product.id)
    try:
        for index, file in enumerate(files):
            stored = await store_product_image(file, seller_id=seller.id, product_id=product.id)
            saved_keys.append((stored.storage_key, stored.thumbnail_url))
            image = ProductImage(
                product_id=product.id,
                image_url=stored.image_url,
                thumbnail_url=stored.thumbnail_url,
                storage_key=stored.storage_key,
                original_filename=stored.original_filename,
                mime_type=stored.mime_type,
                file_size=stored.file_size,
                width=stored.width,
                height=stored.height,
                alt_text=alt_text or product.name,
                display_order=order + index,
                is_primary=(existing_count == 0 and index == 0 and make_first_primary),
                uploaded_by_user_id=current_user.id,
            )
            db.add(image)
            created.append(image)
        _commit(db)
    except Exception:
        db.rollback()
        for storage_key, thumbnail_url in saved_keys:
            delete_product_image_files(storage_key, thumbnail_url)
        raise

    for image in created:
        db.refresh(image)
    return created


@router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED, deprecated=True)
def add_product_image_url(
    product_id: UUID,
    data: ProductImageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_product_images_manage.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    if db.query(ProductImage).filter(ProductImage.product_id == product.id).count() >= MAX_PRODUCT_IMAGES:
        raise HTTPException(status_code=400, detail=f"Maximum {MAX_PRODUCT_IMAGES} images allowed per product")
    image = ProductImage(
        product_id=product.id,
        image_url=data.image_url,
        is_primary=data.is_primary,
        alt_text=data.alt_text or product.name,
        display_order=data.display_order,
        uploaded_by_user_id=current_user.id,
    )
    db.add(image)
    db.flush()
    if data.is_primary:
        _make_primary(db, product.id, image.id)
    elif not db.query(ProductImage).filter(ProductImage.product_id == product.id, ProductImage.is_primary.is_(True)).first():
        image.is_primary = True
    _commit(db)
    db.refresh(image)
    return image


@router.get("/{product_id}/images", response_model=list[ProductImageResponse])
def get_product_images(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db.query(ProductImage).filter(ProductImage.product_id == product_id).order_by(ProductImage.display_order.asc(), ProductImage.created_at.asc()).all()


@router.get("/my-products/{product_id}/images", response_model=list[ProductImageResponse])
def get_my_product_images(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_read.value)),
):
    seller = get_my_seller(db, current_user, require_approved=False)
    product = get_seller_product(db, product_id, seller.id)
    return db.query(ProductImage).filter(ProductImage.product_id == product.id).order_by(ProductImage.display_order.asc(), ProductImage.created_at.asc()).all()


@router.patch("/{product_id}/images/reorder", response_model=list[ProductImageResponse])
def reorder_product_images(
    product_id: UUID,
    data: ProductImageReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_product_images_manage.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    image_ids = [item.image_id for item in data.images]
    if len(set(image_ids)) != len(image_ids):
        raise HTTPException(status_code=400, detail="An image cannot appear more than once")
    images = db.query(ProductImage).filter(ProductImage.product_id == product.id, ProductImage.id.in_(image_ids)).all()
    if len(images) != len(image_ids):
        raise HTTPException(status_code=404, detail="One or more images do not belong to this product")
    by_id = {image.id: image for image in images}
    for item in data.images:
        by_id[item.image_id].display_order = item.display_order
    _commit(db)
    return db.query(ProductImage).filter(ProductImage.product_id == product.id).order_by(ProductImage.display_order.asc()).all()


@router.patch("/{product_id}/images/{image_id}", response_model=ProductImageResponse)
def update_product_image(
    product_id: UUID,
    image_id: UUID,
    data: ProductImageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_product_images_manage.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    image = db.query(ProductImage).filter(ProductImage.id == image_id, ProductImage.product_id == product.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    update_data = data.model_dump(exclude_unset=True)
    if update_data.pop("is_primary", False):
        _make_primary(db, product.id, image.id)
    for key, value in update_data.items():
        setattr(image, key, value)
    _commit(db)
    db.refresh(image)
    return image


@router.post("/{product_id}/images/{image_id}/primary", response_model=ProductImageResponse)
def set_primary_product_image(
    product_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_product_images_manage.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    image = db.query(ProductImage).filter(ProductImage.id == image_id, ProductImage.product_id == product.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    _make_primary(db, product.id, image.id)
    _commit(db)
    db.refresh(image)
    return image


@router.delete("/{product_id}/images/{image_id}")
def delete_product_image(
    product_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_product_images_manage.value)),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    image = db.query(ProductImage).filter(ProductImage.id == image_id, ProductImage.product_id == product.id).first()
    if not image:
        raise HTTPException(status_code=404, detail="Image not found")
    was_primary = image.is_primary
    storage_key = image.storage_key
    thumbnail_url = image.thumbnail_url
    db.delete(image)
    db.flush()
    if was_primary:
        next_image = db.query(ProductImage).filter(ProductImage.product_id == product.id).order_by(ProductImage.display_order.asc()).first()
        if next_image:
            next_image.is_primary = True
    _commit(db)
    delete_product_image_files(storage_key, thumbnail_url)
    return {"message": "Product image deleted successfully"}


def _variant_payload(db: Session, variant: ProductVariant) -> dict:
    inventory = db.query(Inventory).filter(Inventory.product_id == variant.product_id, Inventory.variant_id == variant.id).first()
    return {
        "id": variant.id, "product_id": variant.product_id, "variant_name": variant.variant_name,
        "sku": variant.sku, "barcode": variant.barcode, "price": variant.price,
        "sale_price": variant.sale_price, "weight": variant.weight, "image_id": variant.image_id,
        "attributes": variant.attributes, "is_active": variant.is_active,
        "stock_quantity": inventory.quantity if inventory else 0,
        "reserved_quantity": inventory.reserved_quantity if inventory else 0,
        "available_quantity": inventory.available_quantity if inventory else 0,
        "low_stock_threshold": inventory.low_stock_threshold if inventory else 10,
        "created_at": variant.created_at, "updated_at": variant.updated_at,
    }


def _validate_variant_image(db: Session, product_id: UUID, image_id: UUID | None) -> None:
    if image_id and not db.query(ProductImage).filter(ProductImage.id == image_id, ProductImage.product_id == product_id).first():
        raise HTTPException(status_code=400, detail="Variant image must belong to this product")


def _validate_option_values(db: Session, product_id: UUID, value_ids: list[UUID]) -> list[ProductOptionValue]:
    if not value_ids:
        return []
    values = db.query(ProductOptionValue).join(ProductOption).filter(ProductOption.product_id == product_id, ProductOptionValue.id.in_(value_ids)).all()
    if len(values) != len(set(value_ids)):
        raise HTTPException(status_code=400, detail="One or more option values do not belong to this product")
    option_ids = [value.option_id for value in values]
    if len(option_ids) != len(set(option_ids)):
        raise HTTPException(status_code=400, detail="Select only one value from each product option")
    return values


@router.post("/{product_id}/options", response_model=ProductOptionResponse, status_code=status.HTTP_201_CREATED)
def create_product_option(product_id: UUID, data: ProductOptionCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_product_variants_manage.value))):
    seller = get_my_seller(db, current_user); product = get_seller_product(db, product_id, seller.id); _ensure_editable(product)
    if db.query(ProductOption).filter(ProductOption.product_id == product.id, ProductOption.name.ilike(data.name.strip())).first():
        raise HTTPException(status_code=409, detail="Product option already exists")
    option = ProductOption(product_id=product.id, name=data.name.strip(), display_order=data.display_order)
    db.add(option); db.flush()
    seen=set()
    for item in data.values:
        key=item.value.strip().lower()
        if key in seen: raise HTTPException(status_code=400, detail="Option values must be unique")
        seen.add(key); db.add(ProductOptionValue(option_id=option.id, value=item.value.strip(), display_order=item.display_order))
    _commit(db, conflict_detail="Option or value already exists"); db.refresh(option); return option


@router.get("/{product_id}/options", response_model=list[ProductOptionResponse])
def get_product_options(product_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user); product = get_seller_product(db, product_id, seller.id)
    return db.query(ProductOption).filter(ProductOption.product_id == product.id).order_by(ProductOption.display_order.asc()).all()


@router.patch("/{product_id}/options/{option_id}", response_model=ProductOptionResponse)
def update_product_option(product_id: UUID, option_id: UUID, data: ProductOptionUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_product_variants_manage.value))):
    seller=get_my_seller(db,current_user); product=get_seller_product(db,product_id,seller.id); _ensure_editable(product)
    option=db.query(ProductOption).filter(ProductOption.id==option_id,ProductOption.product_id==product.id).first()
    if not option: raise HTTPException(status_code=404,detail="Product option not found")
    payload=data.model_dump(exclude_unset=True); values=payload.pop("values",None)
    for k,v in payload.items(): setattr(option,k,v.strip() if isinstance(v,str) else v)
    if values is not None:
        if db.query(ProductVariantValue).join(ProductOptionValue).filter(ProductOptionValue.option_id==option.id).first():
            raise HTTPException(status_code=409,detail="Cannot replace values after variants use this option; delete variants first")
        db.query(ProductOptionValue).filter(ProductOptionValue.option_id==option.id).delete(synchronize_session=False)
        for item in values: db.add(ProductOptionValue(option_id=option.id,value=item["value"].strip(),display_order=item.get("display_order",0)))
    _commit(db,conflict_detail="Option or value already exists"); db.refresh(option); return option


@router.delete("/{product_id}/options/{option_id}")
def delete_product_option(product_id: UUID, option_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_product_variants_manage.value))):
    seller=get_my_seller(db,current_user); product=get_seller_product(db,product_id,seller.id); _ensure_editable(product)
    option=db.query(ProductOption).filter(ProductOption.id==option_id,ProductOption.product_id==product.id).first()
    if not option: raise HTTPException(status_code=404,detail="Product option not found")
    if db.query(ProductVariantValue).join(ProductOptionValue).filter(ProductOptionValue.option_id==option.id).first():
        raise HTTPException(status_code=409,detail="Delete variants using this option first")
    db.delete(option); _commit(db); return {"message":"Product option deleted successfully"}


@router.post("/{product_id}/variants", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED)
def add_product_variant(product_id: UUID, data: ProductVariantCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_product_variants_manage.value))):
    seller=get_my_seller(db,current_user); product=get_seller_product(db,product_id,seller.id); _ensure_editable(product)
    _validate_variant_image(db,product.id,data.image_id); values=_validate_option_values(db,product.id,data.option_value_ids)
    if db.query(ProductVariant).filter(ProductVariant.sku==data.sku).first(): raise HTTPException(status_code=409,detail="Variant SKU already exists")
    variant=ProductVariant(product_id=product.id,variant_name=data.variant_name,sku=data.sku,barcode=data.barcode,price=data.price,sale_price=data.sale_price,weight=data.weight,image_id=data.image_id,attributes=data.attributes,is_active=data.is_active)
    db.add(variant); db.flush()
    for value in values: db.add(ProductVariantValue(variant_id=variant.id,option_value_id=value.id))
    db.add(Inventory(product_id=product.id,variant_id=variant.id,quantity=data.stock_quantity,reserved_quantity=0,available_quantity=data.stock_quantity,low_stock_threshold=data.low_stock_threshold,updated_by_id=current_user.id))
    _commit(db,conflict_detail="Variant SKU or barcode already exists"); db.refresh(variant); return _variant_payload(db,variant)


@router.post("/{product_id}/variants/generate", response_model=list[ProductVariantResponse], status_code=status.HTTP_201_CREATED)
def generate_product_variants(product_id: UUID, data: ProductVariantGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_product_variants_manage.value))):
    seller=get_my_seller(db,current_user); product=get_seller_product(db,product_id,seller.id); _ensure_editable(product)
    options=db.query(ProductOption).filter(ProductOption.product_id==product.id).order_by(ProductOption.display_order.asc()).all()
    if not options or any(not option.values for option in options): raise HTTPException(status_code=400,detail="Create options with values before generating variants")
    combinations=list(cartesian_product(*[option.values for option in options]))
    if len(combinations)>200: raise HTTPException(status_code=400,detail="A product cannot generate more than 200 variants")
    created=[]
    for index,combo in enumerate(combinations,1):
        attributes={value.option.name:value.value for value in combo}; name=" / ".join(value.value for value in combo); sku=f"{data.sku_prefix.strip().upper()}-{index:03d}"
        if db.query(ProductVariant).filter(ProductVariant.sku==sku).first(): raise HTTPException(status_code=409,detail=f"Generated SKU already exists: {sku}")
        variant=ProductVariant(product_id=product.id,variant_name=name,sku=sku,price=data.default_price,sale_price=data.default_sale_price,attributes=attributes,is_active=True)
        db.add(variant); db.flush()
        for value in combo: db.add(ProductVariantValue(variant_id=variant.id,option_value_id=value.id))
        db.add(Inventory(product_id=product.id,variant_id=variant.id,quantity=data.default_stock_quantity,reserved_quantity=0,available_quantity=data.default_stock_quantity,low_stock_threshold=data.low_stock_threshold,updated_by_id=current_user.id)); created.append(variant)
    _commit(db,conflict_detail="Generated variant conflicts with an existing record")
    return [_variant_payload(db,v) for v in created]


@router.get("/{product_id}/variants", response_model=list[ProductVariantResponse])
def get_product_variants(product_id: UUID, db: Session = Depends(get_db)):
    product=db.query(Product).filter(Product.id==product_id,Product.is_active.is_(True),Product.status==ProductStatus.approved).first()
    if not product: raise HTTPException(status_code=404,detail="Product not found")
    variants=db.query(ProductVariant).filter(ProductVariant.product_id==product_id,ProductVariant.is_active.is_(True)).order_by(ProductVariant.created_at.asc()).all()
    return [_variant_payload(db,v) for v in variants]


@router.get("/my-products/{product_id}/variants", response_model=list[ProductVariantResponse])
def get_my_product_variants(product_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_products_read.value))):
    seller=get_my_seller(db,current_user); product=get_seller_product(db,product_id,seller.id)
    return [_variant_payload(db,v) for v in db.query(ProductVariant).filter(ProductVariant.product_id==product.id).order_by(ProductVariant.created_at.asc()).all()]


@router.patch("/{product_id}/variants/{variant_id}", response_model=ProductVariantResponse)
def update_product_variant(product_id: UUID, variant_id: UUID, data: ProductVariantUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_product_variants_manage.value))):
    seller=get_my_seller(db,current_user); product=get_seller_product(db,product_id,seller.id); _ensure_editable(product)
    variant=db.query(ProductVariant).filter(ProductVariant.id==variant_id,ProductVariant.product_id==product.id).first()
    if not variant: raise HTTPException(status_code=404,detail="Variant not found")
    payload=data.model_dump(exclude_unset=True); stock=payload.pop("stock_quantity",None); threshold=payload.pop("low_stock_threshold",None)
    _validate_variant_image(db,product.id,payload.get("image_id"))
    final_price=payload.get("price",variant.price); final_sale=payload.get("sale_price",variant.sale_price)
    if final_sale is not None and final_price is not None and final_sale>final_price: raise HTTPException(status_code=422,detail="sale_price cannot exceed price")
    for k,v in payload.items(): setattr(variant,k,v)
    inventory=db.query(Inventory).filter(Inventory.product_id==product.id,Inventory.variant_id==variant.id).with_for_update().first()
    if not inventory:
        inventory=Inventory(product_id=product.id,variant_id=variant.id,quantity=0,reserved_quantity=0,available_quantity=0,updated_by_id=current_user.id); db.add(inventory)
    if stock is not None:
        if stock<inventory.reserved_quantity: raise HTTPException(status_code=409,detail="Stock cannot be below reserved quantity")
        inventory.quantity=stock; inventory.available_quantity=stock-inventory.reserved_quantity
    if threshold is not None: inventory.low_stock_threshold=threshold
    inventory.updated_by_id=current_user.id
    _commit(db,conflict_detail="Variant SKU or barcode already exists"); db.refresh(variant); return _variant_payload(db,variant)


@router.delete("/{product_id}/variants/{variant_id}")
def delete_product_variant(product_id: UUID, variant_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.seller_product_variants_manage.value))):
    seller=get_my_seller(db,current_user); product=get_seller_product(db,product_id,seller.id); _ensure_editable(product)
    variant=db.query(ProductVariant).filter(ProductVariant.id==variant_id,ProductVariant.product_id==product.id).first()
    if not variant: raise HTTPException(status_code=404,detail="Variant not found")
    inventory=db.query(Inventory).filter(Inventory.variant_id==variant.id).first()
    if inventory and inventory.reserved_quantity>0: raise HTTPException(status_code=409,detail="Variant has reserved inventory and cannot be deleted")
    db.delete(variant); _commit(db,conflict_detail="Variant cannot be deleted because it is already referenced"); return {"message":"Product variant deleted successfully"}


@router.post("/{product_id}/tags", response_model=ProductTagResponse, status_code=status.HTTP_201_CREATED)
def add_product_tag(product_id: UUID, data: ProductTagCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    normalized_tag = data.tag.lower().strip()
    existing = db.query(ProductTag).filter(ProductTag.product_id == product.id, ProductTag.tag == normalized_tag).first()
    if existing:
        raise HTTPException(status_code=409, detail="Tag already exists on this product")
    tag = ProductTag(product_id=product.id, tag=normalized_tag)
    db.add(tag)
    _commit(db)
    db.refresh(tag)
    return tag


@router.get("/{product_id}/tags", response_model=list[ProductTagResponse])
def get_product_tags(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db.query(ProductTag).filter(ProductTag.product_id == product_id).all()


@router.delete("/{product_id}/tags/{tag_id}")
def delete_product_tag(product_id: UUID, tag_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    tag = db.query(ProductTag).filter(ProductTag.id == tag_id, ProductTag.product_id == product.id).first()
    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")
    db.delete(tag)
    _commit(db)
    return {"message": "Product tag deleted successfully"}
