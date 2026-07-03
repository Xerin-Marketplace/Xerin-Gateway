from uuid import UUID
from datetime import datetime, timezone
from fastapi import Query
from sqlalchemy import or_
from api.security import hash_password
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from api.models import Role, UserRole, UserStatus


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
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
    PaginatedAdminUserResponse,
    )

router = APIRouter(prefix="/admin", tags=["Admin"])

def get_or_create_role(db: Session, name: str, description: str | None = None):
    role = db.query(Role).filter(Role.name == name).first()

    if role:
        return role

    role = Role(name=name, description=description)
    db.add(role)
    db.commit()
    db.refresh(role)

    return role

def require_admin(current_user: User):
    allowed_roles = ["super_admin", "admin"]

    user_roles = [
        user_role.role.name
        for user_role in current_user.roles
    ]

    if not any(role in allowed_roles for role in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required"
        )

@router.get("/users", response_model=PaginatedAdminUserResponse)
def admin_get_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    status_filter: str | None = Query(None),
):
    require_admin(current_user)

    query = db.query(User)

    if search:
        query = query.filter(
            or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
            )
        )

    if status_filter:
        query = query.filter(User.status == status_filter)

    total = query.count()

    users = query.order_by(User.created_at.desc()) \
        .offset((page - 1) * page_size) \
        .limit(page_size) \
        .all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": users,
    }


@router.post("/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED)
def admin_create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    email = data.email.strip().lower()
    phone = data.phone.strip() if data.phone else None

    existing = db.query(User).filter(
        (User.email == email) | (User.phone == phone)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Email or phone already exists")

    user = User(
        first_name=data.first_name,
        last_name=data.last_name,
        email=email,
        phone=phone,
        password_hash=hash_password(data.password),
        status=data.status,
        is_verified=data.is_verified,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.get("/users/{user_id}", response_model=AdminUserResponse)
def admin_get_user_detail(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def admin_update_user(
    user_id: UUID,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    update_data = data.model_dump(exclude_unset=True)

    if "email" in update_data:
        email = update_data["email"].strip().lower()
        existing = db.query(User).filter(
            User.email == email,
            User.id != user.id
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

        user.email = email
        update_data.pop("email")

    if "phone" in update_data and update_data["phone"]:
        phone = update_data["phone"].strip()
        existing = db.query(User).filter(
            User.phone == phone,
            User.id != user.id
        ).first()

        if existing:
            raise HTTPException(status_code=400, detail="Phone already exists")

        user.phone = phone
        update_data.pop("phone")

    if "password" in update_data:
        user.password_hash = hash_password(update_data["password"])
        update_data.pop("password")

    for key, value in update_data.items():
        setattr(user, key, value)

    db.commit()
    db.refresh(user)

    return user


@router.delete("/users/{user_id}")
def admin_delete_user(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    if user_id == current_user.id:
        raise HTTPException(
            status_code=400,
            detail="You cannot delete your own account"
        )

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}


@router.post("/admins", response_model=AdminUserResponse)
def admin_create_admin(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    require_admin(current_user)

    email = data.email.strip().lower()
    phone = data.phone.strip() if data.phone else None

    admin_role = get_or_create_role(
        db,
        name="admin",
        description="Platform administrator"
    )

    user = db.query(User).filter(User.email == email).first()

    if not user and phone:
        user = db.query(User).filter(User.phone == phone).first()

    if user:
        existing_admin_role = db.query(UserRole).filter(
            UserRole.user_id == user.id,
            UserRole.role_id == admin_role.id
        ).first()

        if existing_admin_role:
            return user

        user.status = UserStatus.active
        user.is_verified = True

        db.add(
            UserRole(
                user_id=user.id,
                role_id=admin_role.id
            )
        )

        db.commit()
        db.refresh(user)

        return user

    user = User(
        first_name=data.first_name,
        last_name=data.last_name,
        email=email,
        phone=phone,
        password_hash=hash_password(data.password),
        status=UserStatus.active,
        is_verified=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    db.add(
        UserRole(
            user_id=user.id,
            role_id=admin_role.id
        )
    )

    db.commit()
    db.refresh(user)

    return user

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