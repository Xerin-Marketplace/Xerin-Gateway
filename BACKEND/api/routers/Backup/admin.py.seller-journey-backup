from uuid import UUID
from datetime import datetime, timezone
from fastapi import Query
from sqlalchemy import or_
from api.security import hash_password
from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from api.models import Role, UserRole, UserStatus
from api.routers.email import send_email
from api.permissions import require_permission
from api.enums import PermissionCode
from api.models import Permission, RolePermission
from api.schemas import *
from api.schemas import RoleResponse

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
    PermissionResponse,
    AssignUserPermissionsRequest,
    UserPermissionsResponse,
    RolePermissionsUpdateRequest,
    RolePermissionsResponse,
    PermissionResponse
)

from api.models import Permission, UserPermission


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
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_users.value)
),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None),
    status_filter: str | None = Query(None),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_create_users.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_users.value)
),
):
     

    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


@router.patch("/users/{user_id}", response_model=AdminUserResponse)
def admin_update_user(
    user_id: UUID,
    data: AdminUserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_update_users.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_delete_users.value)
),
):
     

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

def send_admin_notification_email(
    user: User,
    password: str | None,
    is_new_user: bool,
):
    if is_new_user:
        body = f"""
Hello {user.first_name},

You have been created as an Admin on XERIM Marketplace.

Login Details:
Email: {user.email}
Password: {password}

Please login and change your password immediately.

Regards,
XERIM Marketplace Team
"""
    else:
        body = f"""
Hello {user.first_name},

Your existing XERIM Marketplace account has been upgraded to Admin.

Login Details:
Email: {user.email}
Password: Use your existing password.

Regards,
XERIM Marketplace Team
"""

    send_email(
        to=user.email,
        subject="XERIM Marketplace Admin Access",
        body=body,
    )

@router.post("/admins", response_model=AdminUserResponse)
def admin_create_admin(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_create_admin_users.value)
),
):

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

        if not existing_admin_role:
            user.status = UserStatus.active
            user.is_verified = True

            db.add(UserRole(user_id=user.id, role_id=admin_role.id))
            db.commit()
            db.refresh(user)

        try:
            send_admin_notification_email(
                user=user,
                password=None,
                is_new_user=False,
            )
        except Exception as e:
            print("Failed to send admin email:", e)

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

    db.add(UserRole(user_id=user.id, role_id=admin_role.id))
    db.commit()
    db.refresh(user)

    try:
        send_admin_notification_email(
            user=user,
            password=data.password,
            is_new_user=True,
        )
    except Exception as e:
        print("Failed to send admin email:", e)

    return user


@router.get("/permissions", response_model=list[PermissionResponse])
def get_all_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    return db.query(Permission).order_by(Permission.code.asc()).all()


@router.get("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
def get_user_permissions_admin(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    role_permissions = []
    for user_role in user.roles:
        for role_permission in user_role.role.role_permissions:
            role_permissions.append(role_permission.permission.code)

    direct_permissions = db.query(UserPermission).filter(
        UserPermission.user_id == user.id
    ).all()

    permissions = set(role_permissions)

    for item in direct_permissions:
        permissions.add(item.permission.code)

    return {
        "user_id": user.id,
        "permissions": list(permissions),
    }


@router.post("/users/{user_id}/permissions", response_model=UserPermissionsResponse)
def assign_permissions_to_user(
    user_id: UUID,
    data: AssignUserPermissionsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    user = db.query(User).filter(User.id == user_id).first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    permissions = db.query(Permission).filter(
        Permission.code.in_(data.permission_codes)
    ).all()

    if len(permissions) != len(set(data.permission_codes)):
        raise HTTPException(
            status_code=400,
            detail="One or more permission codes are invalid"
        )

    for permission in permissions:
        exists = db.query(UserPermission).filter(
            UserPermission.user_id == user.id,
            UserPermission.permission_id == permission.id,
        ).first()

        if not exists:
            db.add(
                UserPermission(
                    user_id=user.id,
                    permission_id=permission.id,
                )
            )

    db.commit()

    return {
        "user_id": user.id,
        "permissions": data.permission_codes,
    }
    
@router.get("/roles", response_model=list[RoleResponse])
def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    return db.query(Role).order_by(Role.name.asc()).all()


@router.get("/permissions", response_model=list[PermissionResponse])
def get_permissions(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    return db.query(Permission).order_by(Permission.code.asc()).all()


@router.get("/roles/{role_id}/permissions", response_model=RolePermissionsResponse)
def get_role_permissions(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    role = db.query(Role).filter(Role.id == role_id).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    rows = db.query(RolePermission).filter(
        RolePermission.role_id == role.id
    ).all()

    return {
        "role_id": role.id,
        "role_name": role.name,
        "permissions": [row.permission.code for row in rows],
    }


@router.put("/roles/{role_id}/permissions", response_model=RolePermissionsResponse)
def update_role_permissions(
    role_id: UUID,
    data: RolePermissionsUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    role = db.query(Role).filter(Role.id == role_id).first()

    if not role:
        raise HTTPException(status_code=404, detail="Role not found")

    if role.name == "super_admin":
        raise HTTPException(
            status_code=400,
            detail="Super admin permissions cannot be edited"
        )

    permissions = db.query(Permission).filter(
        Permission.code.in_(data.permission_codes)
    ).all()

    if len(permissions) != len(set(data.permission_codes)):
        raise HTTPException(status_code=400, detail="One or more permission codes are invalid")

    db.query(RolePermission).filter(
        RolePermission.role_id == role.id
    ).delete()

    for permission in permissions:
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))

    db.commit()

    return {
        "role_id": role.id,
        "role_name": role.name,
        "permissions": data.permission_codes,
    }    


@router.delete("/users/{user_id}/permissions/{permission_code}")
def remove_permission_from_user(
    user_id: UUID,
    permission_code: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    permission = db.query(Permission).filter(
        Permission.code == permission_code
    ).first()

    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    user_permission = db.query(UserPermission).filter(
        UserPermission.user_id == user_id,
        UserPermission.permission_id == permission.id,
    ).first()

    if not user_permission:
        raise HTTPException(status_code=404, detail="User permission not found")

    db.delete(user_permission)
    db.commit()

    return {"message": "Permission removed successfully"}

# =========================
# BUSINESS CATEGORIES
# =========================

@router.post("/business-categories", response_model=BusinessCategoryResponse)
def create_business_category(
    data: BusinessCategoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_create_business_categories.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_business_categories.value)
),
):
     

    return db.query(BusinessCategory).order_by(BusinessCategory.name.asc()).all()


@router.patch("/business-categories/{category_id}", response_model=BusinessCategoryResponse)
def update_business_category(
    category_id: UUID,
    data: BusinessCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_update_business_categories.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_delete_business_categories.value)
),
):

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_create_product_categories.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_product_categories.value)
),
):
     

    return db.query(Category).order_by(Category.name.asc()).all()


@router.delete("/product-categories/{category_id}")
def delete_product_category(
    category_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_delete_product_categories.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_create_brands.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_brands.value)
),
):
     

    return db.query(Brand).order_by(Brand.name.asc()).all()


@router.delete("/brands/{brand_id}")
def delete_brand(
    brand_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_delete_brands.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_sellers.value)
),
):
     

    return db.query(Seller).order_by(Seller.created_at.desc()).all()


@router.get("/sellers/pending", response_model=list[SellerResponse])
def get_pending_sellers(
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_pending_sellers.value)
),
):
     

    return db.query(Seller).filter(
        Seller.status == SellerStatus.under_recan_view
    ).order_by(Seller.created_at.desc()).all()


@router.get("/sellers/{seller_id}", response_model=SellerResponse)
def get_seller_detail(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_sellers.value)
),
):
     

    seller = db.query(Seller).filter(Seller.id == seller_id).first()

    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")

    return seller


@router.get("/sellers/{seller_id}/documents", response_model=list[SellerKYCResponse])
def get_seller_documents(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_seller_documents.value)
),
):
     

    return db.query(SellerKYCDocument).filter(
        SellerKYCDocument.seller_id == seller_id
    ).order_by(SellerKYCDocument.uploaded_at.desc()).all()


@router.post("/sellers/{seller_id}/approve", response_model=SellerResponse)
def approve_seller(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_approve_sellers.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_reject_sellers.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_view_products.value)
),
):
     

    return db.query(Product).filter(
        Product.status == ProductStatus.pending_recan_can_view
    ).order_by(Product.created_at.desc()).all()


@router.post("/products/{product_id}/approve", response_model=ProductResponse)
def approve_product(
    product_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
    require_permission(PermissionCode.can_approve_products.value)
),
):
     

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
    current_user: User = Depends(
    require_permission(PermissionCode.can_reject_products.value)
),
):
     

    product = db.query(Product).filter(Product.id == product_id).first()

    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    product.status = ProductStatus.rejected
    product.rejection_reason = reason
    product.is_active = False

    db.commit()
    db.refresh(product)

    return product