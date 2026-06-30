from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.models import (
    User,
    BusinessCategory,
    Category,
    Brand,
    Seller,
    SellerStatus,
    SellerKYCDocument,
    Product,
    ProductStatus,
)
from api.schemas import (
    BusinessCategoryCreate,
    BusinessCategoryUpdate,
    BusinessCategoryResponse,
    CategoryCreate,
    CategoryResponse,
    BrandCreate,
    BrandResponse,
    SellerResponse,
    SellerKYCResponse,
    ProductResponse,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


def require_admin(current_user: User):
    # Temporary admin check. Later replace with roles/RBAC.
    if current_user.email != "admin@example.com":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )


# =========================
# BUSINESS CATEGORIES
# =========================

@router.post("/business-categories", response_model=BusinessCategoryResponse)
def create_business_category(
    data: BusinessCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    existing = db.query(BusinessCategory).filter(
        BusinessCategory.slug == data.slug
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Business category already exists")

    category = BusinessCategory(
        name=data.name,
        slug=data.slug,
        description=data.description,
        active=data.active,
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.get("/business-categories", response_model=list[BusinessCategoryResponse])
def get_business_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(BusinessCategory).order_by(BusinessCategory.name.asc()).all()


@router.patch("/business-categories/{category_id}", response_model=BusinessCategoryResponse)
def update_business_category(
    category_id: UUID,
    data: BusinessCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    category = db.query(BusinessCategory).filter(
        BusinessCategory.id == category_id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Business category not found")

    update_data = data.model_dump(exclude_unset=True)

    for key, value in update_data.items():
        setattr(category, key, value)

    db.commit()
    db.refresh(category)

    return category


@router.delete("/business-categories/{category_id}")
def delete_business_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    category = db.query(BusinessCategory).filter(
        BusinessCategory.id == category_id
    ).first()

    if not category:
        raise HTTPException(status_code=404, detail="Business category not found")

    db.delete(category)
    db.commit()

    return {"message": "Business category deleted successfully"}


# =========================
# PRODUCT CATEGORIES
# =========================

@router.post("/product-categories", response_model=CategoryResponse)
def create_product_category(
    data: CategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    existing = db.query(Category).filter(Category.slug == data.slug).first()

    if existing:
        raise HTTPException(status_code=400, detail="Product category already exists")

    category = Category(
        parent_id=data.parent_id,
        name=data.name,
        slug=data.slug,
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    return category


@router.get("/product-categories", response_model=list[CategoryResponse])
def get_product_categories(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(Category).order_by(Category.name.asc()).all()


@router.delete("/product-categories/{category_id}")
def delete_product_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    category = db.query(Category).filter(Category.id == category_id).first()

    if not category:
        raise HTTPException(status_code=404, detail="Product category not found")

    db.delete(category)
    db.commit()

    return {"message": "Product category deleted successfully"}


# =========================
# BRANDS
# =========================

@router.post("/brands", response_model=BrandResponse)
def create_brand(
    data: BrandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    existing = db.query(Brand).filter(Brand.slug == data.slug).first()

    if existing:
        raise HTTPException(status_code=400, detail="Brand already exists")

    brand = Brand(name=data.name, slug=data.slug)

    db.add(brand)
    db.commit()
    db.refresh(brand)

    return brand


@router.get("/brands", response_model=list[BrandResponse])
def get_brands(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(Brand).order_by(Brand.name.asc()).all()


@router.delete("/brands/{brand_id}")
def delete_brand(
    brand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    brand = db.query(Brand).filter(Brand.id == brand_id).first()

    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")

    db.delete(brand)
    db.commit()

    return {"message": "Brand deleted successfully"}


# =========================
# SELLER VERIFICATION
# =========================

@router.get("/sellers", response_model=list[SellerResponse])
def get_all_sellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(Seller).order_by(Seller.created_at.desc()).all()


@router.get("/sellers/pending", response_model=list[SellerResponse])
def get_pending_sellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(Seller).filter(
        Seller.status == SellerStatus.under_review
    ).order_by(Seller.created_at.desc()).all()


@router.get("/sellers/{seller_id}", response_model=SellerResponse)
def get_seller_detail(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    return seller


@router.get("/sellers/{seller_id}/documents", response_model=list[SellerKYCResponse])
def get_seller_documents(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller_id
    ).order_by(SellerKYCDocument.uploaded_at.desc()).all()


@router.post("/sellers/{seller_id}/approve", response_model=SellerResponse)
def approve_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    required_docs = ["tin", "business_profile", "business_registration"]

    documents = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    ).all()

    uploaded_docs = [doc.document_type for doc in documents]

    missing = [doc for doc in required_docs if doc not in uploaded_docs]

    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Seller is missing documents: {missing}"
        )

    seller.status = SellerStatus.approved
    seller.approved_at = datetime.now(timezone.utc)

    db.commit()
    db.refresh(seller)

    return seller


@router.post("/sellers/{seller_id}/reject", response_model=SellerResponse)
def reject_seller(
    seller_id: UUID,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    seller.status = SellerStatus.rejected

    db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller.id
    ).update({
        "status": "rejected",
        "rejection_reason": reason,
    })

    db.commit()
    db.refresh(seller)

    return seller


# =========================
# PRODUCT APPROVAL
# =========================

@router.get("/products/pending", response_model=list[ProductResponse])
def get_pending_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    return db.query(Product).filter(
        Product.status == ProductStatus.pending_review
    ).order_by(Product.created_at.desc()).all()


@router.post("/products/{product_id}/approve", response_model=ProductResponse)
def approve_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.status = ProductStatus.approved
    product.rejection_reason = None
    product.is_active = True

    db.commit()
    db.refresh(product)

    return product


@router.post("/products/{product_id}/reject", response_model=ProductResponse)
def reject_product(
    product_id: UUID,
    reason: str = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.status = ProductStatus.rejected
    product.rejection_reason = reason
    product.is_active = False

    db.commit()
    db.refresh(product)

    return product