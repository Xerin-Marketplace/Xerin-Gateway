from __future__ import annotations

from datetime import datetime, timezone
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
    ProductImage,
    ProductStatus,
    ProductTag,
    ProductVariant,
    Seller,
    SellerStatus,
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
    ProductVariantCreate,
    ProductVariantResponse,
)
from api.services.product_image_service import (
    MAX_PRODUCT_IMAGES,
    delete_product_image_files,
    store_product_image,
)

router = APIRouter(prefix="/products", tags=["Products"])


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
    if not db.query(Category).filter(Category.id == data.category_id).first():
        raise HTTPException(status_code=404, detail="Category not found")
    if data.brand_id and not db.query(Brand).filter(Brand.id == data.brand_id).first():
        raise HTTPException(status_code=404, detail="Brand not found")
    if db.query(Product).filter(Product.sku == data.sku).first():
        raise HTTPException(status_code=409, detail="Product SKU already exists")
    if db.query(Product).filter(Product.slug == data.slug).first():
        raise HTTPException(status_code=409, detail="Product slug already exists")

    product = Product(
        seller_id=seller.id,
        category_id=data.category_id,
        brand_id=data.brand_id,
        sku=data.sku,
        name=data.name,
        slug=data.slug,
        description=data.description,
        price=data.price,
        sale_price=data.sale_price,
        currency=data.currency,
        weight=data.weight,
        status=ProductStatus.draft,
        is_active=True,
    )
    db.add(product)
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
    return query.order_by(Product.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/my-products", response_model=list[ProductResponse])
def get_my_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_products_read.value)),
    product_status: ProductStatus | None = Query(default=None, alias="status"),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    seller = get_my_seller(db, current_user, require_approved=False)
    query = db.query(Product).filter(Product.seller_id == seller.id)
    if product_status:
        query = query.filter(Product.status == product_status)
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
    if not db.query(ProductImage).filter(ProductImage.product_id == product.id, ProductImage.is_primary.is_(True)).first():
        first = db.query(ProductImage).filter(ProductImage.product_id == product.id).order_by(ProductImage.display_order.asc()).first()
        if first:
            first.is_primary = True
    product.status = ProductStatus.pending_review
    product.rejection_reason = None
    product.submitted_at = datetime.now(timezone.utc)
    _commit(db)
    db.refresh(product)
    return product


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

    if "category_id" in update_data and not db.query(Category).filter(Category.id == update_data["category_id"]).first():
        raise HTTPException(status_code=404, detail="Category not found")
    if update_data.get("brand_id") and not db.query(Brand).filter(Brand.id == update_data["brand_id"]).first():
        raise HTTPException(status_code=404, detail="Brand not found")
    if "sku" in update_data and db.query(Product).filter(Product.sku == update_data["sku"], Product.id != product.id).first():
        raise HTTPException(status_code=409, detail="SKU already exists")
    if "slug" in update_data and db.query(Product).filter(Product.slug == update_data["slug"], Product.id != product.id).first():
        raise HTTPException(status_code=409, detail="Slug already exists")

    for key, value in update_data.items():
        setattr(product, key, value)
    product.status = ProductStatus.draft
    product.rejection_reason = None
    product.submitted_at = None
    product.approved_at = None
    product.approved_by_user_id = None
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


@router.post("/{product_id}/variants", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED)
def add_product_variant(product_id: UUID, data: ProductVariantCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    if db.query(ProductVariant).filter(ProductVariant.sku == data.sku).first():
        raise HTTPException(status_code=409, detail="Variant SKU already exists")
    variant = ProductVariant(product_id=product.id, variant_name=data.variant_name, sku=data.sku, price=data.price, attributes=data.attributes)
    db.add(variant)
    _commit(db, conflict_detail="Variant SKU already exists")
    db.refresh(variant)
    return variant


@router.get("/{product_id}/variants", response_model=list[ProductVariantResponse])
def get_product_variants(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return db.query(ProductVariant).filter(ProductVariant.product_id == product_id).order_by(ProductVariant.created_at.asc()).all()


@router.delete("/{product_id}/variants/{variant_id}")
def delete_product_variant(product_id: UUID, variant_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    _ensure_editable(product)
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id, ProductVariant.product_id == product.id).first()
    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")
    db.delete(variant)
    _commit(db, conflict_detail="Variant cannot be deleted because it is already referenced")
    return {"message": "Product variant deleted successfully"}


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
