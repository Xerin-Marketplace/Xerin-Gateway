from uuid import UUID, uuid4

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.enums import PermissionCode
from api.models import Address, Seller, User, UserRole, Session as UserSession, OTPRequest, UserStatus
from api.permissions import require_permission
from api.security import hash_password, verify_password
from api.services.customer_delivery_location import (
    CustomerDeliveryLocationError,
    confirm_customer_map_pin,
)
from api.schemas import (
    AddressCreate,
    AddressUpdate,
    AddressResponse,
    CustomerMapPinConfirmationRequest,
    CustomerMapPinConfirmationResponse,
    PaginatedAddressResponse,
    UpdateUserRequest,
    DeleteMyAccountRequest,
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


@router.delete("/users/me")
def delete_my_account(
    data: DeleteMyAccountRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Delete the currently authenticated user's account safely.

    The users row is retained as an anonymised tombstone so existing orders,
    payments, settlements and audit records can keep their foreign-key
    relationships. Authentication data is revoked immediately.
    """
    user = db.query(User).filter(User.id == current_user.id).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if data.confirmation.strip().upper() != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Type "DELETE" to confirm account deletion',
        )

    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect",
        )

    user_id = user.id
    deleted_marker = str(user_id).replace("-", "")
    now = datetime.now(timezone.utc)

    # Sign the account out everywhere once this transaction commits.
    db.query(UserSession).filter(
        UserSession.user_id == user_id
    ).delete(synchronize_session=False)

    # Outstanding OTPs should not survive account deletion.
    db.query(OTPRequest).filter(
        OTPRequest.user_id == user_id
    ).delete(synchronize_session=False)

    # Preserve the row for referential integrity but remove login/profile identity.
    user.first_name = "Deleted"
    user.last_name = "User"
    user.email = f"deleted-{deleted_marker}@deleted.xerin.invalid"
    user.phone = None
    user.password_hash = hash_password(
        f"deleted:{deleted_marker}:{now.timestamp()}:{uuid4()}"
    )
    user.status = UserStatus.inactive
    user.is_verified = False
    user.initial_role_choice = None
    user.initial_role_choice_completed = False
    user.last_login_at = None

    db.commit()

    return {
        "message": "Your account has been deleted successfully.",
        "deleted": True,
    }


@router.post(
    "/addresses",
    response_model=AddressResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_address(
    data: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # First active address becomes default automatically.
    active_count = (
        db.query(Address)
        .filter(
            Address.user_id == current_user.id,
            Address.is_active.is_(True),
        )
        .count()
    )
    make_default = bool(data.is_default or (data.is_active and active_count == 0))

    if make_default:
        db.query(Address).filter(
            Address.user_id == current_user.id
        ).update({"is_default": False})

    address = Address(
        user_id=current_user.id,
        label=data.label,
        recipient_name=data.recipient_name,
        recipient_phone=data.recipient_phone,
        country=data.country,
        region=data.region,
        district=data.district,
        ward=data.ward,
        city=data.city,
        street=data.street,
        landmark=data.landmark,
        postal_code=data.postal_code,
        formatted_address=data.formatted_address,
        place_id=data.place_id,
        latitude=data.latitude,
        longitude=data.longitude,
        delivery_instructions=data.delivery_instructions,
        is_default=make_default,
        is_active=data.is_active,
        # Customer/self-service location changes are not automatically verified.
        is_verified=False,
    )

    db.add(address)
    db.commit()
    db.refresh(address)
    return address


@router.get("/addresses", response_model=PaginatedAddressResponse)
def get_my_addresses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(default=None, min_length=1, max_length=150),
    is_active: bool | None = Query(default=None),
    is_default: bool | None = Query(default=None),
    delivery_ready: bool | None = Query(default=None),
):
    query = db.query(Address).filter(Address.user_id == current_user.id)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Address.label.ilike(term),
                Address.recipient_name.ilike(term),
                Address.recipient_phone.ilike(term),
                Address.formatted_address.ilike(term),
                Address.country.ilike(term),
                Address.region.ilike(term),
                Address.district.ilike(term),
                Address.ward.ilike(term),
                Address.city.ilike(term),
                Address.street.ilike(term),
                Address.landmark.ilike(term),
                Address.postal_code.ilike(term),
            )
        )

    if is_active is not None:
        query = query.filter(Address.is_active.is_(is_active))

    if is_default is not None:
        query = query.filter(Address.is_default.is_(is_default))

    if delivery_ready is True:
        query = query.filter(
            Address.is_active.is_(True),
            Address.is_verified.is_(True),
            Address.location_confirmed_at.isnot(None),
            Address.recipient_name.isnot(None),
            Address.recipient_phone.isnot(None),
            Address.latitude.isnot(None),
            Address.longitude.isnot(None),
        )
    elif delivery_ready is False:
        query = query.filter(
            or_(
                Address.is_active.is_(False),
                Address.is_verified.is_(False),
                Address.location_confirmed_at.is_(None),
                Address.recipient_name.is_(None),
                Address.recipient_phone.is_(None),
                Address.latitude.is_(None),
                Address.longitude.is_(None),
            )
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size if total else 0

    addresses = (
        query.order_by(
            Address.is_default.desc(),
            Address.created_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": addresses,
    }


@router.get("/addresses/{address_id}", response_model=AddressResponse)
def get_my_address(
    address_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = (
        db.query(Address)
        .filter(
            Address.id == address_id,
            Address.user_id == current_user.id,
        )
        .first()
    )
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
    return address


@router.patch("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: UUID,
    data: AddressUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = (
        db.query(Address)
        .filter(
            Address.id == address_id,
            Address.user_id == current_user.id,
        )
        .first()
    )
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    update_data = data.model_dump(exclude_unset=True)

    # Coordinates are an atomic pair. Do not allow one side to change alone.
    if "latitude" in update_data or "longitude" in update_data:
        next_lat = update_data.get("latitude", address.latitude)
        next_lng = update_data.get("longitude", address.longitude)
        if (next_lat is None) != (next_lng is None):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="latitude and longitude must be provided together",
            )

    # An inactive location cannot remain/become default.
    next_active = update_data.get("is_active", address.is_active)
    next_default = update_data.get("is_default", address.is_default)
    if next_default and not next_active:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="An inactive delivery address cannot be default",
        )

    if update_data.get("is_default"):
        db.query(Address).filter(
            Address.user_id == current_user.id,
            Address.id != address.id,
        ).update({"is_default": False})

    # Editing location-critical fields invalidates future verification.
    critical_location_fields = {
        "formatted_address",
        "place_id",
        "country",
        "region",
        "district",
        "ward",
        "city",
        "street",
        "latitude",
        "longitude",
    }
    if critical_location_fields.intersection(update_data):
        address.is_verified = False
        address.location_provider = None
        address.location_confirmed_at = None

    for field, value in update_data.items():
        setattr(address, field, value)

    # If the default is deactivated/unset, promote another active address.
    if not address.is_active or address.is_default is False:
        if not address.is_active:
            address.is_default = False

    db.flush()

    has_default = (
        db.query(Address)
        .filter(
            Address.user_id == current_user.id,
            Address.is_active.is_(True),
            Address.is_default.is_(True),
        )
        .count()
        > 0
    )
    if not has_default:
        fallback = (
            db.query(Address)
            .filter(
                Address.user_id == current_user.id,
                Address.is_active.is_(True),
                Address.id != address.id,
            )
            .order_by(Address.created_at.desc())
            .first()
        )
        if fallback:
            fallback.is_default = True
        elif address.is_active:
            address.is_default = True

    db.commit()
    db.refresh(address)
    return address


@router.post(
    "/addresses/{address_id}/confirm-map-pin",
    response_model=CustomerMapPinConfirmationResponse,
)
def confirm_delivery_address_map_pin(
    address_id: UUID,
    data: CustomerMapPinConfirmationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = (
        db.query(Address)
        .filter(
            Address.id == address_id,
            Address.user_id == current_user.id,
        )
        .first()
    )
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    if not address.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "inactive_delivery_address",
                "message": "Activate the delivery address before confirming its map pin.",
            },
        )

    try:
        resolved = confirm_customer_map_pin(
            db,
            address=address,
            latitude=data.latitude,
            longitude=data.longitude,
            language=data.language,
        )
    except CustomerDeliveryLocationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={
                "code": exc.code,
                "message": exc.message,
            },
        ) from exc

    return {
        "address": address,
        "resolved_location": resolved,
        "message": "Delivery map pin confirmed successfully.",
    }


@router.post("/addresses/{address_id}/default", response_model=AddressResponse)
def set_default_address(
    address_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = (
        db.query(Address)
        .filter(
            Address.id == address_id,
            Address.user_id == current_user.id,
        )
        .first()
    )
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )
    if not address.is_active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inactive delivery address cannot be set as default",
        )

    db.query(Address).filter(
        Address.user_id == current_user.id
    ).update({"is_default": False})
    address.is_default = True
    db.commit()
    db.refresh(address)
    return address


@router.delete("/addresses/{address_id}")
def delete_address(
    address_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = (
        db.query(Address)
        .filter(
            Address.id == address_id,
            Address.user_id == current_user.id,
        )
        .first()
    )
    if not address:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Address not found",
        )

    was_default = bool(address.is_default)
    db.delete(address)
    db.flush()

    if was_default:
        fallback = (
            db.query(Address)
            .filter(
                Address.user_id == current_user.id,
                Address.is_active.is_(True),
            )
            .order_by(Address.created_at.desc())
            .first()
        )
        if fallback:
            fallback.is_default = True

    db.commit()
    return {"message": "Address deleted successfully"}
