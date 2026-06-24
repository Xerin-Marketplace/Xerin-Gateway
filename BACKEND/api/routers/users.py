from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from uuid import UUID

from api.deps import get_db, get_current_user
from api.models import User, Address
from api.schemas import UserResponse, UpdateUserRequest, AddressCreate, AddressResponse

router = APIRouter(tags=["Users"])


@router.get("/users/me", response_model=UserResponse)
def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/users/me", response_model=UserResponse)
def update_me(
    data: UpdateUserRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)

    return current_user


@router.post("/addresses", response_model=AddressResponse)
def create_address(
    data: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if data.is_default:
        db.query(Address).filter(Address.user_id == current_user.id).update(
            {"is_default": False}
        )

    address = Address(user_id=current_user.id, **data.model_dump())

    db.add(address)
    db.commit()
    db.refresh(address)

    return address


@router.get("/addresses", response_model=list[AddressResponse])
def get_addresses(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    return db.query(Address).filter(Address.user_id == current_user.id).all()


@router.patch("/addresses/{address_id}", response_model=AddressResponse)
def update_address(
    address_id: UUID,
    data: AddressCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    address = (
        db.query(Address)
        .filter(Address.id == address_id, Address.user_id == current_user.id)
        .first()
    )

    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    if data.is_default:
        db.query(Address).filter(Address.user_id == current_user.id).update(
            {"is_default": False}
        )

    for key, value in data.model_dump().items():
        setattr(address, key, value)

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
        .filter(Address.id == address_id, Address.user_id == current_user.id)
        .first()
    )

    if not address:
        raise HTTPException(status_code=404, detail="Address not found")

    db.delete(address)
    db.commit()

    return {"message": "Address deleted successfully"}
