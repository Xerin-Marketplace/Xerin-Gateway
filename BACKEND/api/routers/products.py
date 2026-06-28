from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_

from api.deps import get_db, get_current_user
from api.models import (
    User,
    Seller,
    SellerStatus,
    Category,
    Brand,
    Product,
    ProductStatus,
    ProductImage,
    ProductVariant,
    ProductTag,
)
from api.schemas import (
    CategoryCreate,
    CategoryResponse,
    BrandCreate,
    BrandResponse,
    ProductCreate,
    ProductUpdate,
    ProductResponse,
    ProductImageCreate,
    ProductImageResponse,
    ProductVariantCreate,
    ProductVariantResponse,
    ProductTagCreate,
    ProductTagResponse,
)

router = APIRouter(prefix="/products", tags=["Products"])


def get_my_seller(db: Session, current_user: User) -> Seller:
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must register as a seller first"
        )

    if seller.status != SellerStatus.approved:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seller account is not approved yet"
        )

    return seller


def get_seller_product(db: Session, product_id: UUID, seller_id: UUID) -> Product:
    product = db.query(Product).filter(
        Product.id == product_id,
        Product.seller_id == seller_id
    ).first()

    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Product not found or you do not own this product"
        )

    return product


# =========================
# CATEGORIES
# =========================

@router.post("/categories", response_model=CategoryResponse, status_code=status.HTTP_201_CREATED)
def create_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(Category).filter(Category.slug == data.slug).first()

    if existing:
        raise HTTPException(status_code=400, detail="Category slug already exists")

    if data.parent_id:
        parent = db.query(Category).filter(Category.id == data.parent_id).first()
        if not parent:
            raise HTTPException(status_code=404, detail="Parent category not found")

    category = Category(
        parent_id=data.parent_id,
        name=data.name,
        slug=data.slug,
    )

    db.add(category)
    db.commit()
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


# =========================
# BRANDS
# =========================

@router.post("/brands", response_model=BrandResponse, status_code=status.HTTP_201_CREATED)
def create_brand(
    data: BrandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    existing = db.query(Brand).filter(Brand.slug == data.slug).first()

    if existing:
        raise HTTPException(status_code=400, detail="Brand slug already exists")

    brand = Brand(
        name=data.name,
        slug=data.slug,
    )

    db.add(brand)
    db.commit()
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


# =========================
# SELLER PRODUCT CRUD
# =========================

@router.post("", response_model=ProductResponse, status_code=status.HTTP_201_CREATED)
def create_product(
    data: ProductCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = get_my_seller(db, current_user)

    category = db.query(Category).filter(Category.id == data.category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    if data.brand_id:
        brand = db.query(Brand).filter(Brand.id == data.brand_id).first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

    existing_sku = db.query(Product).filter(Product.sku == data.sku).first()
    if existing_sku:
        raise HTTPException(status_code=400, detail="Product SKU already exists")

    existing_slug = db.query(Product).filter(Product.slug == data.slug).first()
    if existing_slug:
        raise HTTPException(status_code=400, detail="Product slug already exists")

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
    db.commit()
    db.refresh(product)

    return product


@router.get("", response_model=list[ProductResponse])
def list_products(
    db: Session = Depends(get_db),
    search: str | None = Query(default=None),
    category_id: UUID | None = Query(default=None),
    brand_id: UUID | None = Query(default=None),
    seller_id: UUID | None = Query(default=None),
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
):
    query = db.query(Product).filter(
        Product.is_active == True,
        Product.status == ProductStatus.approved
    )

    if search:
        query = query.filter(
            or_(
                Product.name.ilike(f"%{search}%"),
                Product.description.ilike(f"%{search}%"),
                Product.sku.ilike(f"%{search}%"),
            )
        )

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
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    return db.query(Product).filter(
        Product.seller_id == seller.id
    ).order_by(Product.created_at.desc()).offset(skip).limit(limit).all()


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(product_id: UUID, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    return product


@router.patch("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: UUID,
    data: ProductUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    update_data = data.model_dump(exclude_unset=True)

    if "category_id" in update_data:
        category = db.query(Category).filter(Category.id == update_data["category_id"]).first()
        if not category:
            raise HTTPException(status_code=404, detail="Category not found")

    if "brand_id" in update_data and update_data["brand_id"] is not None:
        brand = db.query(Brand).filter(Brand.id == update_data["brand_id"]).first()
        if not brand:
            raise HTTPException(status_code=404, detail="Brand not found")

    if "sku" in update_data:
        existing = db.query(Product).filter(
            Product.sku == update_data["sku"],
            Product.id != product.id
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="SKU already exists")

    if "slug" in update_data:
        existing = db.query(Product).filter(
            Product.slug == update_data["slug"],
            Product.id != product.id
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Slug already exists")

    for key, value in update_data.items():
        setattr(product, key, value)

    product.status = ProductStatus.pending_review
    product.rejection_reason = None

    db.commit()
    db.refresh(product)

    return product


@router.delete("/{product_id}")
def delete_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    db.delete(product)
    db.commit()

    return {"message": "Product deleted successfully"}


# =========================
# PRODUCT IMAGES
# =========================

@router.post("/{product_id}/images", response_model=ProductImageResponse, status_code=status.HTTP_201_CREATED)
def add_product_image(
    product_id: UUID,
    data: ProductImageCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    image_count = db.query(ProductImage).filter(ProductImage.product_id == product.id).count()
    if image_count >= 10:
        raise HTTPException(status_code=400, detail="Maximum 10 images allowed per product")

    if data.is_primary:
        db.query(ProductImage).filter(
            ProductImage.product_id == product.id
        ).update({"is_primary": False})

    image = ProductImage(
        product_id=product.id,
        image_url=data.image_url,
        is_primary=data.is_primary,
    )

    db.add(image)
    db.commit()
    db.refresh(image)

    return image


@router.get("/{product_id}/images", response_model=list[ProductImageResponse])
def get_product_images(product_id: UUID, db: Session = Depends(get_db)):
    return db.query(ProductImage).filter(
        ProductImage.product_id == product_id
    ).order_by(ProductImage.created_at.asc()).all()


@router.delete("/{product_id}/images/{image_id}")
def delete_product_image(
    product_id: UUID,
    image_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    image = db.query(ProductImage).filter(
        ProductImage.id == image_id,
        ProductImage.product_id == product.id
    ).first()

    if not image:
        raise HTTPException(status_code=404, detail="Image not found")

    db.delete(image)
    db.commit()

    return {"message": "Product image deleted successfully"}


# =========================
# PRODUCT VARIANTS
# =========================

@router.post("/{product_id}/variants", response_model=ProductVariantResponse, status_code=status.HTTP_201_CREATED)
def add_product_variant(
    product_id: UUID,
    data: ProductVariantCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    existing = db.query(ProductVariant).filter(ProductVariant.sku == data.sku).first()
    if existing:
        raise HTTPException(status_code=400, detail="Variant SKU already exists")

    variant = ProductVariant(
        product_id=product.id,
        variant_name=data.variant_name,
        sku=data.sku,
        price=data.price,
        attributes=data.attributes,
    )

    db.add(variant)
    db.commit()
    db.refresh(variant)

    return variant


@router.get("/{product_id}/variants", response_model=list[ProductVariantResponse])
def get_product_variants(product_id: UUID, db: Session = Depends(get_db)):
    return db.query(ProductVariant).filter(
        ProductVariant.product_id == product_id
    ).order_by(ProductVariant.created_at.asc()).all()


@router.delete("/{product_id}/variants/{variant_id}")
def delete_product_variant(
    product_id: UUID,
    variant_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    variant = db.query(ProductVariant).filter(
        ProductVariant.id == variant_id,
        ProductVariant.product_id == product.id
    ).first()

    if not variant:
        raise HTTPException(status_code=404, detail="Variant not found")

    db.delete(variant)
    db.commit()

    return {"message": "Product variant deleted successfully"}


# =========================
# PRODUCT TAGS
# =========================

@router.post("/{product_id}/tags", response_model=ProductTagResponse, status_code=status.HTTP_201_CREATED)
def add_product_tag(
    product_id: UUID,
    data: ProductTagCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    tag = ProductTag(
        product_id=product.id,
        tag=data.tag.lower().strip(),
    )

    db.add(tag)
    db.commit()
    db.refresh(tag)

    return tag


@router.get("/{product_id}/tags", response_model=list[ProductTagResponse])
def get_product_tags(product_id: UUID, db: Session = Depends(get_db)):
    return db.query(ProductTag).filter(
        ProductTag.product_id == product_id
    ).all()


@router.delete("/{product_id}/tags/{tag_id}")
def delete_product_tag(
    product_id: UUID,
    tag_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller profile not found")

    product = get_seller_product(db, product_id, seller.id)

    tag = db.query(ProductTag).filter(
        ProductTag.id == tag_id,
        ProductTag.product_id == product.id
    ).first()

    if not tag:
        raise HTTPException(status_code=404, detail="Tag not found")

    db.delete(tag)
    db.commit()

    return {"message": "Product tag deleted successfully"}