from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import PermissionCode
from api.models import Address, Seller, User, UserRole
from api.permissions import require_permission
from api.schemas import (
    AddressCreate,
    AddressResponse,
    PaginatedAddressResponse,
    UpdateUserRequest,
    UserMeResponse,
    UserResponse,
)

router = APIRouter(tags=["Users"])


@router.get("/users/me", response_model=UserMeResponse)
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.view_profile.value)
    ),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()

    user_roles = db.query(UserRole).filter(
        UserRole.user_id == current_user.id
    ).all()

    roles = [user_role.role.name for user_role in user_roles]

    if "super_admin" in roles:
        account_type = "super_admin"
    elif "admin" in roles:
        account_type = "admin"
    elif seller:
        account_type = "seller"
    else:
        account_type = "customer"

    return {
        "id": current_user.id,
        "first_name": current_user.first_name,
        "last_name": current_user.last_name,
        "email": current_user.email,
        "phone": current_user.phone,
        "is_verified": current_user.is_verified,
        "status": current_user.status.value if current_user.status else None,
        "is_seller": seller is not None,
        "seller_status": seller.status.value if seller else None,
        "account_type": account_type,
        "roles": roles,
    }


@router.patch("/users/me", response_model=UserResponse)
def update_my_profile(
    data: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.update_profile.value)
    ),
):
    update_data = data.model_dump(exclude_unset=True)

    if "email" in update_data:
        email = update_data["email"].strip().lower()

        existing_email = db.query(User).filter(
            User.email == email,
            User.id != current_user.id,
        ).first()

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists",
            )

        current_user.email = email
        update_data.pop("email")

    if "phone" in update_data and update_data["phone"]:
        phone = update_data["phone"].strip()

        existing_phone = db.query(User).filter(
            User.phone == phone,
            User.id != current_user.id,
        ).first()

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already exists",
            )

        current_user.phone = phone
        update_data.pop("phone")

    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    return current_user


@router.post(
    "/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_address(
    data: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.manage_addresses.value)
    ),
):
    if data.is_default:
        db.query(Address).filter(
            Address.user_id == current_user.id
        ).update({"is_default": False})

    address = Address(
        user_id=current_user.id,
        country=data.country,
        region=data.region,
        city=data.city,
        street=data.street,
        postal_code=data.postal_code,
        is_default=data.is_default,
    )

    db.add(address)
    db.commit()
    db.refresh(address)

    return address


@router.get("/addresses", response_model=PaginatedAddressResponse)
def get_my_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.manage_addresses.value)
    ),
    page: int = Query(1, ge=1),
    page_size: int = Query(10, ge=1, le=100),
):
    query = db.query(Address).filter(Address.user_id == current_user.id)

    total = query.count()

    addresses = (
        query.order_by(Address.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": addresses,
    }


@router.patch("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: UUID,
    data: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.manage_addresses.value)
    ),
):
    address = db.query(Address).filter(
        Address.id == address_id,
        Address.user_id == current_user.id,
    ).first()

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    if data.is_default:
        db.query(Address).filter(
            Address.user_id == current_user.id,
            Address.id != address.id,
        ).update({"is_default": False})

    address.country = data.country
    address.region = data.region
    address.city = data.city
    address.street = data.street
    address.postal_code = data.postal_code
    address.is_default = data.is_default

    db.commit()
    db.refresh(address)

    return address


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.manage_addresses.value)
    ),
):
    address = db.query(Address).filter(
        Address.id == address_id,
        Address.user_id == current_user.id,
    ).first()

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    db.delete(address)
    db.commit()

    return {"message": "Address deleted successfully"}