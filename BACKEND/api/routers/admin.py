from uuid import UUID
from datetime import datetime, timezone
from fastapi import Query
from sqlalchemy import or_
from api.security import hash_password
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status, Form
from sqlalchemy.orm import Session
from api.models import Role, UserRole, UserStatus
from api.routers.email import send_email
from api.permissions import require_permission, require_all_permissions, get_user_role_names, get_user_permissions
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
    CategoryUpdate,
    CategoryResponse,
    BrandCreate,
    BrandUpdate,
    BrandResponse,
    SellerResponse,
    SellerKYCResponse,
    ProductResponse,
    AdminProductReviewDetailResponse,
    AdminCatalogSummaryResponse,
    PaginatedAdminProductResponse,
    PaginatedCategoryResponse,
    PaginatedBusinessCategoryResponse,
    PaginatedBrandResponse,
    AdminUserCreate,
    AdminUserUpdate,
    AdminUserResponse,
    PaginatedAdminUserResponse,
    PermissionResponse,
    AssignUserPermissionsRequest,
    UserPermissionsResponse,
    RolePermissionsUpdateRequest,
    RolePermissionsResponse,
    PermissionResponse,
    RoleCreateRequest,
    RoleUpdateRequest,
    UserRolesUpdateRequest,
    UserRolesResponse,
    RoleUsersResponse,
    AdminStaffCreateRequest,
    AdminStaffResponse,
    PaginatedAdminAccessUserResponse,
)

from api.models import Permission, UserPermission
from api.services.category_image_service import (
    delete_category_image_files,
    store_category_image,
)


router = APIRouter(prefix="/admin", tags=["Admin"])

SYSTEM_ROLE_NAMES = {"super_admin", "admin", "customer", "seller"}
SUPER_ADMIN_ROLE_NAME = "super_admin"


def _get_role_or_404(db: Session, role_id: UUID) -> Role:
    role = db.query(Role).filter(Role.id == role_id).first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
    return role


def _get_user_or_404(db: Session, user_id: UUID) -> User:
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


def _resolve_permissions(db: Session, permission_codes: list[str]) -> list[Permission]:
    unique_codes = list(dict.fromkeys(permission_codes))
    if not unique_codes:
        return []

    permissions = (
        db.query(Permission)
        .filter(Permission.code.in_(unique_codes))
        .all()
    )

    found = {permission.code for permission in permissions}
    invalid = sorted(set(unique_codes) - found)

    if invalid:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "One or more permission codes are invalid",
                "invalid_permission_codes": invalid,
            },
        )

    return permissions


def _page_count(total: int, page_size: int) -> int:
    return 0 if total <= 0 else (total + page_size - 1) // page_size


def _serialize_product_review(product: Product) -> dict:
    return _serialize_product_review(product)


def _serialize_staff_user(db: Session, user: User) -> dict:
    return {
        "id": user.id,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "phone": user.phone,
        "status": user.status.value if hasattr(user.status, "value") else str(user.status),
        "is_verified": user.is_verified,
        "created_at": user.created_at,
        "roles": sorted(get_user_role_names(user)),
        "permissions": sorted(get_user_permissions(db, user)),
    }



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

    user_roles = [user_role.role.name for user_role in current_user.roles]

    if not any(role in allowed_roles for role in user_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required"
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

    users = (
        query.order_by(User.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": users,
    }


@router.get("/access-users", response_model=PaginatedAdminAccessUserResponse)
def admin_get_access_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_view_users.value)
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    status_filter: str | None = Query(None),
    role_filter: str | None = Query(None, max_length=50),
):
    """Server-side paginated user access listing for the RBAC workspace."""
    query = db.query(User)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                User.first_name.ilike(term),
                User.last_name.ilike(term),
                User.email.ilike(term),
                User.phone.ilike(term),
                User.roles.any(UserRole.role.has(Role.name.ilike(term))),
            )
        )

    if status_filter:
        query = query.filter(User.status == status_filter)

    if role_filter:
        query = query.filter(
            User.roles.any(UserRole.role.has(Role.name == role_filter))
        )

    total = query.count()
    users = (
        query.order_by(User.created_at.desc(), User.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    if not users:
        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "results": [],
        }

    user_ids = [user.id for user in users]

    role_rows = (
        db.query(UserRole.user_id, Role.id, Role.name)
        .join(Role, Role.id == UserRole.role_id)
        .filter(UserRole.user_id.in_(user_ids))
        .all()
    )

    role_names_by_user: dict[UUID, list[str]] = {user_id: [] for user_id in user_ids}
    role_ids_by_user: dict[UUID, list[UUID]] = {user_id: [] for user_id in user_ids}
    all_role_ids: set[UUID] = set()

    for user_id, role_id, role_name in role_rows:
        role_names_by_user[user_id].append(role_name)
        role_ids_by_user[user_id].append(role_id)
        all_role_ids.add(role_id)

    role_permissions: dict[UUID, set[str]] = {}
    if all_role_ids:
        permission_rows = (
            db.query(RolePermission.role_id, Permission.code)
            .join(Permission, Permission.id == RolePermission.permission_id)
            .filter(RolePermission.role_id.in_(all_role_ids))
            .all()
        )
        for role_id, code in permission_rows:
            role_permissions.setdefault(role_id, set()).add(code)

    direct_permissions: dict[UUID, set[str]] = {user_id: set() for user_id in user_ids}
    direct_rows = (
        db.query(UserPermission.user_id, Permission.code)
        .join(Permission, Permission.id == UserPermission.permission_id)
        .filter(UserPermission.user_id.in_(user_ids))
        .all()
    )
    for user_id, code in direct_rows:
        direct_permissions[user_id].add(code)

    results = []
    for user in users:
        effective = set(direct_permissions.get(user.id, set()))
        for role_id in role_ids_by_user.get(user.id, []):
            effective.update(role_permissions.get(role_id, set()))

        results.append(
            {
                "id": user.id,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "email": user.email,
                "phone": user.phone,
                "status": user.status.value if hasattr(user.status, "value") else str(user.status),
                "is_verified": user.is_verified,
                "created_at": user.created_at,
                "roles": sorted(role_names_by_user.get(user.id, [])),
                "role_ids": role_ids_by_user.get(user.id, []),
                "permissions": sorted(effective),
            }
        )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": results,
    }


@router.post(
    "/users", response_model=AdminUserResponse, status_code=status.HTTP_201_CREATED
)
def admin_create_user(
    data: AdminUserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_create_users.value)
    ),
):

    email = data.email.strip().lower()
    phone = data.phone.strip() if data.phone else None

    existing = (
        db.query(User).filter((User.email == email) | (User.phone == phone)).first()
    )

    if existing:
        raise HTTPException(
            status_code=400, detail="Email or phone already exists .Please sign in"
        )

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
        existing = (
            db.query(User).filter(User.email == email, User.id != user.id).first()
        )

        if existing:
            raise HTTPException(status_code=400, detail="Email already exists")

        user.email = email
        update_data.pop("email")

    if "phone" in update_data and update_data["phone"]:
        phone = update_data["phone"].strip()
        existing = (
            db.query(User).filter(User.phone == phone, User.id != user.id).first()
        )

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
            status_code=400, detail="You cannot delete your own account"
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


@router.post(
    "/staff",
    response_model=AdminStaffResponse,
    status_code=status.HTTP_201_CREATED,
)
def admin_create_staff_account(
    data: AdminStaffCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_all_permissions(
            PermissionCode.can_create_users.value,
            PermissionCode.can_assign_permissions.value,
        )
    ),
):
    email = data.email.strip().lower()
    phone = data.phone.strip() if data.phone else None

    duplicate_query = db.query(User).filter(User.email == email)
    if phone:
        duplicate_query = db.query(User).filter(
            or_(User.email == email, User.phone == phone)
        )

    if duplicate_query.first():
        raise HTTPException(
            status_code=409,
            detail="A user with this email or phone already exists",
        )

    roles = (
        db.query(Role)
        .filter(Role.id.in_(data.role_ids))
        .all()
    )

    found_ids = {role.id for role in roles}
    missing_ids = [role_id for role_id in data.role_ids if role_id not in found_ids]
    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "One or more role IDs are invalid",
                "invalid_role_ids": [str(role_id) for role_id in missing_ids],
            },
        )

    actor_roles = get_user_role_names(current_user)
    if (
        any(role.name == SUPER_ADMIN_ROLE_NAME for role in roles)
        and SUPER_ADMIN_ROLE_NAME not in actor_roles
    ):
        raise HTTPException(
            status_code=403,
            detail="Only a super_admin can create another super_admin account",
        )

    try:
        user_status = UserStatus(data.status)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid user status: {data.status}",
        ) from exc

    user = User(
        first_name=data.first_name.strip(),
        last_name=data.last_name.strip(),
        email=email,
        phone=phone,
        password_hash=hash_password(data.password),
        status=user_status,
        is_verified=data.is_verified,
    )

    db.add(user)
    db.flush()

    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))

    db.commit()
    db.refresh(user)

    return _serialize_staff_user(db, user)


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
        db, name="admin", description="Platform administrator"
    )

    user = db.query(User).filter(User.email == email).first()

    if not user and phone:
        user = db.query(User).filter(User.phone == phone).first()

    if user:
        existing_admin_role = (
            db.query(UserRole)
            .filter(UserRole.user_id == user.id, UserRole.role_id == admin_role.id)
            .first()
        )

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

    direct_permissions = (
        db.query(UserPermission).filter(UserPermission.user_id == user.id).all()
    )

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

    permissions = (
        db.query(Permission).filter(Permission.code.in_(data.permission_codes)).all()
    )

    if len(permissions) != len(set(data.permission_codes)):
        raise HTTPException(
            status_code=400, detail="One or more permission codes are invalid"
        )

    for permission in permissions:
        exists = (
            db.query(UserPermission)
            .filter(
                UserPermission.user_id == user.id,
                UserPermission.permission_id == permission.id,
            )
            .first()
        )

        if not exists:
            db.add(
                UserPermission(
                    user_id=user.id,
                    permission_id=permission.id,
                )
            )

    db.commit()

    db.refresh(user)

    return {
        "user_id": user.id,
        "permissions": sorted(get_user_permissions(db, user)),
    }


@router.get("/roles", response_model=list[RoleResponse])
def get_roles(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    return db.query(Role).order_by(Role.name.asc()).all()




@router.post(
    "/roles",
    response_model=RolePermissionsResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_role(
    data: RoleCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    existing = db.query(Role).filter(Role.name == data.name).first()
    if existing:
        raise HTTPException(status_code=409, detail="Role name already exists")

    if data.name == SUPER_ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=400,
            detail="The super_admin role is reserved and cannot be created manually",
        )

    permissions = _resolve_permissions(db, data.permission_codes)

    role = Role(name=data.name, description=data.description)
    db.add(role)
    db.flush()

    for permission in permissions:
        db.add(
            RolePermission(
                role_id=role.id,
                permission_id=permission.id,
            )
        )

    db.commit()
    db.refresh(role)

    return {
        "role_id": role.id,
        "role_name": role.name,
        "permissions": sorted(permission.code for permission in permissions),
    }


@router.patch("/roles/{role_id}", response_model=RoleResponse)
def update_role(
    role_id: UUID,
    data: RoleUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    role = _get_role_or_404(db, role_id)

    if role.name in SYSTEM_ROLE_NAMES:
        raise HTTPException(
            status_code=409,
            detail=f"System role '{role.name}' cannot be renamed or edited here",
        )

    update_data = data.model_dump(exclude_unset=True)

    if "name" in update_data:
        new_name = update_data["name"]

        if new_name in SYSTEM_ROLE_NAMES:
            raise HTTPException(
                status_code=400,
                detail="That role name is reserved by the system",
            )

        duplicate = (
            db.query(Role)
            .filter(Role.name == new_name, Role.id != role.id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=409, detail="Role name already exists")

        role.name = new_name

    if "description" in update_data:
        role.description = update_data["description"]

    db.commit()
    db.refresh(role)
    return role


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    role = _get_role_or_404(db, role_id)

    if role.name in SYSTEM_ROLE_NAMES:
        raise HTTPException(
            status_code=409,
            detail=f"System role '{role.name}' cannot be deleted",
        )

    assigned_count = (
        db.query(UserRole)
        .filter(UserRole.role_id == role.id)
        .count()
    )
    if assigned_count:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Role is assigned to {assigned_count} user(s). "
                "Remove the role from those users before deleting it."
            ),
        )

    db.query(RolePermission).filter(
        RolePermission.role_id == role.id
    ).delete(synchronize_session=False)

    db.delete(role)
    db.commit()

    return {"message": "Role deleted successfully"}


@router.get("/roles/{role_id}/users", response_model=RoleUsersResponse)
def get_role_users(
    role_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    role = _get_role_or_404(db, role_id)

    rows = (
        db.query(UserRole)
        .filter(UserRole.role_id == role.id)
        .all()
    )

    return {
        "role_id": role.id,
        "role_name": role.name,
        "user_ids": [row.user_id for row in rows],
    }


@router.get("/users/{user_id}/roles", response_model=UserRolesResponse)
def get_user_roles_admin(
    user_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    user = _get_user_or_404(db, user_id)

    roles = [
        user_role.role
        for user_role in user.roles
        if user_role.role is not None
    ]

    return {
        "user_id": user.id,
        "roles": roles,
    }


@router.put("/users/{user_id}/roles", response_model=UserRolesResponse)
def replace_user_roles_admin(
    user_id: UUID,
    data: UserRolesUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_assign_permissions.value)
    ),
):
    user = _get_user_or_404(db, user_id)

    roles = (
        db.query(Role)
        .filter(Role.id.in_(data.role_ids))
        .all()
        if data.role_ids
        else []
    )

    found_ids = {role.id for role in roles}
    missing_ids = [role_id for role_id in data.role_ids if role_id not in found_ids]

    if missing_ids:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "One or more role IDs are invalid",
                "invalid_role_ids": [str(role_id) for role_id in missing_ids],
            },
        )

    requested_role_names = {role.name for role in roles}
    current_actor_roles = get_user_role_names(current_user)

    if (
        SUPER_ADMIN_ROLE_NAME in requested_role_names
        and SUPER_ADMIN_ROLE_NAME not in current_actor_roles
    ):
        raise HTTPException(
            status_code=403,
            detail="Only a super_admin can assign the super_admin role",
        )

    target_current_roles = get_user_role_names(user)
    if (
        user.id == current_user.id
        and SUPER_ADMIN_ROLE_NAME in target_current_roles
        and SUPER_ADMIN_ROLE_NAME not in requested_role_names
    ):
        raise HTTPException(
            status_code=409,
            detail="You cannot remove your own super_admin role",
        )

    db.query(UserRole).filter(
        UserRole.user_id == user.id
    ).delete(synchronize_session=False)

    for role in roles:
        db.add(UserRole(user_id=user.id, role_id=role.id))

    db.commit()
    db.refresh(user)

    return {
        "user_id": user.id,
        "roles": roles,
    }


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

    rows = db.query(RolePermission).filter(RolePermission.role_id == role.id).all()

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
    role = _get_role_or_404(db, role_id)

    if role.name == SUPER_ADMIN_ROLE_NAME:
        raise HTTPException(
            status_code=409,
            detail="Super admin permissions cannot be edited",
        )

    permissions = _resolve_permissions(db, data.permission_codes)

    db.query(RolePermission).filter(RolePermission.role_id == role.id).delete()

    for permission in permissions:
        db.add(RolePermission(role_id=role.id, permission_id=permission.id))

    db.commit()

    return {
        "role_id": role.id,
        "role_name": role.name,
        "permissions": sorted(permission.code for permission in permissions),
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
    permission = db.query(Permission).filter(Permission.code == permission_code).first()

    if not permission:
        raise HTTPException(status_code=404, detail="Permission not found")

    user_permission = (
        db.query(UserPermission)
        .filter(
            UserPermission.user_id == user_id,
            UserPermission.permission_id == permission.id,
        )
        .first()
    )

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

    existing = (
        db.query(BusinessCategory).filter(BusinessCategory.slug == data.slug).first()
    )

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


@router.get(
    "/business-categories",
    response_model=list[BusinessCategoryResponse],
    summary="List public business categories",
    description=(
        "Public endpoint. Authentication is not required. "
        "Only active business categories are returned."
    ),
)
def get_business_categories(
    db: Session = Depends(get_db),
):
    """
    Return all active business categories for public consumers.

    This endpoint is intentionally public so it can be used by:
    - guest users
    - external websites
    - mobile applications
    - seller registration forms

    Create, update, and delete operations remain protected by
    administrator permissions.
    """
    return (
        db.query(BusinessCategory)
        .filter(BusinessCategory.active.is_(True))
        .order_by(BusinessCategory.name.asc())
        .all()
    )


@router.patch(
    "/business-categories/{category_id}", response_model=BusinessCategoryResponse
)
def update_business_category(
    category_id: UUID,
    data: BusinessCategoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_update_business_categories.value)
    ),
):

    category = (
        db.query(BusinessCategory).filter(BusinessCategory.id == category_id).first()
    )

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

    category = (
        db.query(BusinessCategory).filter(BusinessCategory.id == category_id).first()
    )

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


@router.post(
    "/product-categories/with-image",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_product_category_with_image(
    name: str = Form(...),
    slug: str = Form(...),
    parent_id: UUID | None = Form(None),
    image: UploadFile | None = File(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_create_product_categories.value)
    ),
):
    del current_user
    if db.query(Category).filter(Category.slug == slug).first():
        raise HTTPException(status_code=409, detail="Product category already exists")
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
        db.commit()
    except Exception:
        db.rollback()
        if category.image_storage_key:
            delete_category_image_files(category.image_storage_key)
        raise
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


@router.patch("/product-categories/{category_id}", response_model=CategoryResponse)
def update_product_category(
    category_id: UUID, data: CategoryUpdate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.can_create_product_categories.value)),
):
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Product category not found")
    values = data.model_dump(exclude_unset=True)
    if "parent_id" in values:
        if values["parent_id"] == category.id:
            raise HTTPException(status_code=400, detail="A category cannot be its own parent")
        if values["parent_id"] and not db.query(Category).filter(Category.id == values["parent_id"]).first():
            raise HTTPException(status_code=404, detail="Parent category not found")
    if values.get("slug"):
        duplicate = db.query(Category).filter(Category.slug == values["slug"], Category.id != category.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Product category slug already exists")
    for key, value in values.items(): setattr(category, key, value)
    db.commit(); db.refresh(category); return category


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

    storage_key = category.image_storage_key
    db.delete(category)
    db.commit()
    delete_category_image_files(storage_key)

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


@router.patch("/brands/{brand_id}", response_model=BrandResponse)
def update_brand(
    brand_id: UUID, data: BrandUpdate, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.can_create_brands.value)),
):
    brand = db.query(Brand).filter(Brand.id == brand_id).first()
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    values = data.model_dump(exclude_unset=True)
    if values.get("slug"):
        duplicate = db.query(Brand).filter(Brand.slug == values["slug"], Brand.id != brand.id).first()
        if duplicate:
            raise HTTPException(status_code=409, detail="Brand slug already exists")
    for key, value in values.items(): setattr(brand, key, value)
    db.commit(); db.refresh(brand); return brand


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

    return (
        db.query(Seller)
        .filter(Seller.status.in_([SellerStatus.pending, SellerStatus.under_review]))
        .order_by(Seller.created_at.desc())
        .all()
    )


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

    return (
        db.query(SellerKYCDocument)
        .filter(SellerKYCDocument.seller_id == seller_id)
        .order_by(SellerKYCDocument.uploaded_at.desc())
        .all()
    )


@router.get("/sellers/{seller_id}/documents/{document_id}/view")
def view_seller_document(
    seller_id: UUID,
    document_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.can_view_seller_documents.value)),
):
    document = db.query(SellerKYCDocument).filter(
        SellerKYCDocument.id == document_id,
        SellerKYCDocument.seller_id == seller_id,
    ).first()
    if not document:
        raise HTTPException(status_code=404, detail="Seller KYC document not found")

    from pathlib import Path
    import mimetypes
    from fastapi.responses import FileResponse

    upload_root = Path("uploads/kyc").resolve()
    file_path = Path(document.document_url).resolve()
    try:
        file_path.relative_to(upload_root)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail="Invalid document path") from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Document file not found")
    media_type, _ = mimetypes.guess_type(str(file_path))
    return FileResponse(path=file_path, media_type=media_type or "application/pdf", filename=file_path.name, content_disposition_type="inline")


@router.post("/sellers/{seller_id}/start-review", response_model=SellerResponse)
def start_seller_review(
    seller_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.can_view_seller_documents.value)),
):
    seller = db.query(Seller).filter(Seller.id == seller_id).first()
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    if seller.status == SellerStatus.approved:
        raise HTTPException(status_code=409, detail="Seller is already approved")

    documents = db.query(SellerKYCDocument).filter(SellerKYCDocument.seller_id == seller.id).all()
    required = {"tin", "business_profile", "business_registration"}
    uploaded = {doc.document_type for doc in documents}
    missing = sorted(required - uploaded)
    if missing:
        raise HTTPException(status_code=400, detail=f"Seller is missing documents: {missing}")

    for document in documents:
        document.status = "under_review"
        document.rejection_reason = None
    seller.status = SellerStatus.under_review
    seller.approved_at = None
    db.commit()
    db.refresh(seller)
    return seller


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

    documents = (
        db.query(SellerKYCDocument)
        .filter(SellerKYCDocument.seller_id == seller.id)
        .all()
    )

    uploaded_docs = [doc.document_type for doc in documents]

    missing = [doc for doc in required_docs if doc not in uploaded_docs]

    if missing:
        raise HTTPException(
            status_code=400, detail=f"Seller is missing documents: {missing}"
        )

    not_reviewed = [
        doc.document_type for doc in documents
        if doc.document_type in required_docs and doc.status not in {"under_review", "approved"}
    ]
    if not_reviewed:
        raise HTTPException(
            status_code=409,
            detail=f"Start review before approval. Documents not under review: {not_reviewed}",
        )

    for document in documents:
        document.status = "approved"
        document.rejection_reason = None

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

    db.query(SellerKYCDocument).filter(SellerKYCDocument.seller_id == seller.id).update(
        {
            "status": "rejected",
            "rejection_reason": reason,
        }
    )

    db.commit()
    db.refresh(seller)

    return seller


# =========================
# PRODUCT APPROVAL
# =========================


@router.get("/catalog/products", response_model=PaginatedAdminProductResponse)
def get_catalog_products_paginated(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    status_filter: str | None = Query("pending_review"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.can_view_products.value)),
):
    query = db.query(Product).join(Seller, Product.seller_id == Seller.id).join(Category, Product.category_id == Category.id).outerjoin(Brand, Product.brand_id == Brand.id)
    if status_filter and status_filter.lower() != "all":
        try:
            query = query.filter(Product.status == ProductStatus(status_filter))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"Invalid product status: {status_filter}") from exc
    term=(search or "").strip()
    if term:
        pattern=f"%{term}%"
        query=query.filter(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern), Product.slug.ilike(pattern), Product.description.ilike(pattern), Seller.business_name.ilike(pattern), Category.name.ilike(pattern), Brand.name.ilike(pattern)))
    total=query.count()
    rows=query.order_by(Product.submitted_at.desc().nullslast(), Product.created_at.desc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "total_pages": _page_count(total,page_size), "results": [_serialize_product_review(p) for p in rows]}


@router.get("/catalog/product-categories", response_model=PaginatedCategoryResponse)
def get_catalog_product_categories_paginated(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = Query(None, max_length=150),
    db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.can_view_product_categories.value)),
):
    query=db.query(Category)
    term=(search or "").strip()
    if term:
        pattern=f"%{term}%"; query=query.filter(or_(Category.name.ilike(pattern), Category.slug.ilike(pattern)))
    total=query.count(); rows=query.order_by(Category.name.asc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_page_count(total,page_size),"results":rows}


@router.get("/catalog/business-categories", response_model=PaginatedBusinessCategoryResponse)
def get_catalog_business_categories_paginated(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = Query(None, max_length=150), active_filter: str | None = Query("all"),
    db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.can_view_business_categories.value)),
):
    query=db.query(BusinessCategory)
    if active_filter and active_filter.lower() != "all":
        if active_filter.lower() not in {"active","inactive"}: raise HTTPException(status_code=400, detail="active_filter must be one of: all, active, inactive")
        query=query.filter(BusinessCategory.active.is_(active_filter.lower()=="active"))
    term=(search or "").strip()
    if term:
        pattern=f"%{term}%"; query=query.filter(or_(BusinessCategory.name.ilike(pattern), BusinessCategory.slug.ilike(pattern), BusinessCategory.description.ilike(pattern)))
    total=query.count(); rows=query.order_by(BusinessCategory.name.asc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_page_count(total,page_size),"results":rows}


@router.get("/catalog/brands", response_model=PaginatedBrandResponse)
def get_catalog_brands_paginated(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), search: str | None = Query(None, max_length=150),
    db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.can_view_brands.value)),
):
    query=db.query(Brand)
    term=(search or "").strip()
    if term:
        pattern=f"%{term}%"; query=query.filter(or_(Brand.name.ilike(pattern), Brand.slug.ilike(pattern)))
    total=query.count(); rows=query.order_by(Brand.name.asc()).offset((page-1)*page_size).limit(page_size).all()
    return {"total":total,"page":page,"page_size":page_size,"total_pages":_page_count(total,page_size),"results":rows}


@router.get("/catalog/summary", response_model=AdminCatalogSummaryResponse)
def get_catalog_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.can_view_products.value)),
):
    return {
        "total_products": db.query(Product).count(),
        "pending_products": db.query(Product).filter(Product.status == ProductStatus.pending_review).count(),
        "approved_products": db.query(Product).filter(Product.status == ProductStatus.approved).count(),
        "rejected_products": db.query(Product).filter(Product.status == ProductStatus.rejected).count(),
        "product_categories": db.query(Category).count(),
        "business_categories": db.query(BusinessCategory).count(),
        "brands": db.query(Brand).count(),
    }


@router.get("/products/{product_id}/review", response_model=AdminProductReviewDetailResponse)
def get_product_review_detail(
    product_id: UUID, db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.can_view_products.value)),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    payload = ProductResponse.model_validate(product).model_dump()
    payload.update({
        "seller_business_name": product.seller.business_name if product.seller else None,
        "seller_contact_email": product.seller.contact_email if product.seller else None,
        "seller_contact_phone": product.seller.contact_phone if product.seller else None,
        "category_name": product.category.name if product.category else None,
        "brand_name": product.brand.name if product.brand else None,
    })
    return payload


@router.get("/products/pending", response_model=list[ProductResponse])
def get_pending_products(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.can_view_products.value)
    ),
):

    return (
        db.query(Product)
        .filter(Product.status == ProductStatus.pending_review)
        .order_by(Product.created_at.desc())
        .all()
    )


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

    if product.status != ProductStatus.pending_review:
        raise HTTPException(
            status_code=409, detail="Only products pending review can be approved"
        )
    if not product.images:
        raise HTTPException(
            status_code=400,
            detail="A product must have at least one image before approval",
        )

    product.status = ProductStatus.approved
    product.rejection_reason = None
    product.is_active = True
    product.approved_at = datetime.now(timezone.utc)
    product.approved_by_user_id = current_user.id

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

    if product.status != ProductStatus.pending_review:
        raise HTTPException(
            status_code=409, detail="Only products pending review can be rejected"
        )

    product.status = ProductStatus.rejected
    product.rejection_reason = reason.strip()
    product.is_active = True
    product.approved_at = None
    product.approved_by_user_id = None

    db.commit()
    db.refresh(product)

    return product