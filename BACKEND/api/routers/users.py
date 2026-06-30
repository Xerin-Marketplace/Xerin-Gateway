from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID

from api.deps import get_db, get_current_user
from api.models import User, Address, Seller
from api.schemas import UserResponse, UpdateUserRequest, AddressCreate, AddressResponse


router = APIRouter(tags=["Users"])


# =========================
# USER PROFILE
# =========================

@router.get("/users/me")
def get_my_profile(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    seller = db.query(Seller).filter(
        Seller.user_id == current_user.id
    ).first()

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
        "account_type": "seller" if seller else "customer",
    }


@router.patch("/users/me", response_model=UserResponse)
def update_my_profile(
    data: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    update_data = data.model_dump(exclude_unset=True)

    if "email" in update_data:
        existing_email = db.query(User).filter(
            User.email == update_data["email"],
            User.id != current_user.id
        ).first()

        if existing_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already exists"
            )

    if "phone" in update_data:
        existing_phone = db.query(User).filter(
            User.phone == update_data["phone"],
            User.id != current_user.id
        ).first()

        if existing_phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone already exists"
            )

    for key, value in update_data.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    return current_user


# =========================
# ADDRESSES
# =========================

@router.post(
    "/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED
)
def create_address(
    data: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
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


@router.get("/addresses", response_model=list[AddressResponse])
def get_my_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    addresses = db.query(Address).filter(
        Address.user_id == current_user.id
    ).order_by(Address.created_at.desc()).all()

    return addresses


@router.patch("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: UUID,
    data: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    address = db.query(Address).filter(
        Address.id == address_id,
        Address.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    if data.is_default:
        db.query(Address).filter(
            Address.user_id == current_user.id,
            Address.id != address.id
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
    current_user: User = Depends(get_current_user)
):
    address = db.query(Address).filter(
        Address.id == address_id,
        Address.user_id == current_user.id
    ).first()

    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found"
        )

    db.delete(address)
    db.commit()

    return {
        "message": "Address deleted successfully"
    }