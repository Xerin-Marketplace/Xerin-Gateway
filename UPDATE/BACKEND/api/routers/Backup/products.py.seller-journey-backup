from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
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
    ProductImageResponse,
    ProductResponse,
    ProductTagCreate,
    ProductTagResponse,
    ProductUpdate,
    ProductVariantCreate,
    ProductVariantResponse,
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


@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("can_create_product_categories")),
):
    del current_user
    if db.query(Category).filter(Category.slug == data.slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category slug already exists")
    if data.parent_id and not db.query(Category).filter(Category.id == data.parent_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Parent category not found")

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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    return category


@router.post("/brands", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
def create_brand(
    data: BrandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("can_create_brands")),
):
    del current_user
    if db.query(Brand).filter(Brand.slug == data.slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Brand slug already exists")
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
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    return brand


@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)
    if not db.query(Category).filter(Category.id == data.category_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if data.brand_id and not db.query(Brand).filter(Brand.id == data.brand_id).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    if db.query(Product).filter(Product.sku == data.sku).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product SKU already exists")
    if db.query(Product).filter(Product.slug == data.slug).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product slug already exists")

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
        status=ProductStatus.pending_review,
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
    if search:
        term = search.strip()
        if term:
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
    current_user: User = Depends(get_current_user),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    seller = get_my_seller(db, current_user, require_approved=False)
    return db.query(Product).filter(Product.seller_id == seller.id).order_by(Product.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    update_data = data.model_dump(exclude_unset=True)

    if "category_id" in update_data and not db.query(Category).filter(Category.id == update_data["category_id"]).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    if update_data.get("brand_id") and not db.query(Brand).filter(Brand.id == update_data["brand_id"]).first():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Brand not found")
    if "sku" in update_data and db.query(Product).filter(Product.sku == update_data["sku"], Product.id != product.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="SKU already exists")
    if "slug" in update_data and db.query(Product).filter(Product.slug == update_data["slug"], Product.id != product.id).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Slug already exists")

    for key, value in update_data.items():
        setattr(product, key, value)
    product.status = ProductStatus.pending_review
    product.rejection_reason = None
    _commit(db, conflict_detail="Product SKU or slug already exists")
    db.refresh(product)
    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    product.is_active = False
    _commit(db)
    return {"message": "Product deactivated successfully"}


@router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED)
def add_product_image(product_id: UUID, data: ProductImageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    if db.query(ProductImage).filter(ProductImage.product_id == product.id).count() >= 10:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Maximum 10 images allowed per product")
    if data.is_primary:
        db.query(ProductImage).filter(ProductImage.product_id == product.id).update({"is_primary": False}, synchronize_session=False)
    image = ProductImage(product_id=product.id, image_url=data.image_url, is_primary=data.is_primary)
    db.add(image)
    _commit(db)
    db.refresh(image)
    return image


@router.get("/{product_id}/images", response_model=list[ProductImageResponse])
def get_product_images(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return db.query(ProductImage).filter(ProductImage.product_id == product_id).order_by(ProductImage.created_at.asc()).all()


@router.delete("/{product_id}/images/{image_id}")
def delete_product_image(product_id: UUID, image_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    image = db.query(ProductImage).filter(ProductImage.id == image_id, ProductImage.product_id == product.id).first()
    if not image:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")
    db.delete(image)
    _commit(db)
    return {"message": "Product image deleted successfully"}


@router.post("/{product_id}/variants", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED)
def add_product_variant(product_id: UUID, data: ProductVariantCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    if db.query(ProductVariant).filter(ProductVariant.sku == data.sku).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Variant SKU already exists")
    variant = ProductVariant(product_id=product.id, variant_name=data.variant_name, sku=data.sku, price=data.price, attributes=data.attributes)
    db.add(variant)
    _commit(db, conflict_detail="Variant SKU already exists")
    db.refresh(variant)
    return variant


@router.get("/{product_id}/variants", response_model=list[ProductVariantResponse])
def get_product_variants(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return db.query(ProductVariant).filter(ProductVariant.product_id == product_id).order_by(ProductVariant.created_at.asc()).all()


@router.delete("/{product_id}/variants/{variant_id}")
def delete_product_variant(product_id: UUID, variant_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id, ProductVariant.product_id == product.id).first()
    if not variant:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    db.delete(variant)
    _commit(db, conflict_detail="Variant cannot be deleted because it is already referenced")
    return {"message": "Product variant deleted successfully"}


@router.post("/{product_id}/tags", response_model=ProductTagResponse, status_code=status.HTTP_201_CREATED)
def add_product_tag(product_id: UUID, data: ProductTagCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    normalized_tag = data.tag.lower().strip()
    existing = db.query(ProductTag).filter(ProductTag.product_id == product.id, ProductTag.tag == normalized_tag).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Tag already exists on this product")
    tag = ProductTag(product_id=product.id, tag=normalized_tag)
    db.add(tag)
    _commit(db)
    db.refresh(tag)
    return tag


@router.get("/{product_id}/tags", response_model=list[ProductTagResponse])
def get_product_tags(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id, Product.is_active.is_(True), Product.status == ProductStatus.approved).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return db.query(ProductTag).filter(ProductTag.product_id == product_id).all()


@router.delete("/{product_id}/tags/{tag_id}")
def delete_product_tag(product_id: UUID, tag_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = get_my_seller(db, current_user)
    product = get_seller_product(db, product_id, seller.id)
    tag = db.query(ProductTag).filter(ProductTag.id == tag_id, ProductTag.product_id == product.id).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
    db.delete(tag)
    _commit(db)
    return {"message": "Product tag deleted successfully"}
