from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_current_user, get_db
from api.models import Inventory, Product, ProductVariant, Seller, SellerStatus, User
from api.schemas import InventoryCreate, InventoryResponse, InventoryUpdate

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _seller_for_inventory(db: Session, current_user: User) -> Seller:
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must be a seller to manage inventory")
    if seller.status != SellerStatus.approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller account is not approved")
    return seller


def _owned_product(db: Session, seller: Seller, product_id: UUID) -> Product:
    product = db.query(Product).filter(Product.id == product_id, Product.seller_id == seller.id).first()
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found or not owned by you")
    return product


def _validate_stock(quantity: int, reserved_quantity: int) -> None:
    if reserved_quantity > quantity:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="reserved_quantity cannot be greater than quantity",
        )


def _commit(db: Session, detail: str = "Inventory conflict") -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
    except Exception:
        db.rollback()
        raise


@router.post("", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED)
def create_inventory(data: InventoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = _seller_for_inventory(db, current_user)
    _owned_product(db, seller, data.product_id)
    if data.variant_id:
        variant = db.query(ProductVariant).filter(ProductVariant.id == data.variant_id, ProductVariant.product_id == data.product_id).first()
        if not variant:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product variant not found")

    if data.reserved_quantity != 0:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reserved_quantity is managed by the reservation engine")
    _validate_stock(data.quantity, 0)
    existing_query = db.query(Inventory).filter(Inventory.product_id == data.product_id)
    existing_query = existing_query.filter(Inventory.variant_id == data.variant_id) if data.variant_id else existing_query.filter(Inventory.variant_id.is_(None))
    if existing_query.first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Inventory already exists for this product and variant")

    inventory = Inventory(
        product_id=data.product_id,
        variant_id=data.variant_id,
        quantity=data.quantity,
        reserved_quantity=data.reserved_quantity,
        available_quantity=data.quantity - data.reserved_quantity,
        warehouse_location=data.warehouse_location,
        low_stock_threshold=data.low_stock_threshold,
        updated_by_id=current_user.id,
    )
    db.add(inventory)
    _commit(db, "Inventory already exists for this product and variant")
    db.refresh(inventory)
    return inventory


@router.get("/my-inventory", response_model=list[InventoryResponse])
def get_my_inventory(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = _seller_for_inventory(db, current_user)
    return db.query(Inventory).join(Product, Product.id == Inventory.product_id).filter(Product.seller_id == seller.id).order_by(Inventory.updated_at.desc().nullslast()).all()


@router.get("/product/{product_id}", response_model=InventoryResponse)
def get_product_inventory(product_id: UUID, db: Session = Depends(get_db)):
    inventory = db.query(Inventory).join(Product, Product.id == Inventory.product_id).filter(
        Inventory.product_id == product_id,
        Inventory.variant_id.is_(None),
        Product.is_active.is_(True),
    ).first()
    if not inventory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory not found")
    return inventory


@router.put("/{inventory_id}", response_model=InventoryResponse)
def update_inventory(inventory_id: UUID, data: InventoryUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = _seller_for_inventory(db, current_user)
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).with_for_update().first()
    if not inventory:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory not found")
    _owned_product(db, seller, inventory.product_id)

    new_quantity = data.quantity if data.quantity is not None else inventory.quantity
    if data.reserved_quantity is not None and data.reserved_quantity != inventory.reserved_quantity:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="reserved_quantity is managed by the reservation engine")
    new_reserved = inventory.reserved_quantity
    _validate_stock(new_quantity, new_reserved)

    inventory.quantity = new_quantity
    inventory.reserved_quantity = new_reserved
    inventory.available_quantity = new_quantity - new_reserved
    if data.warehouse_location is not None:
        inventory.warehouse_location = data.warehouse_location
    if data.low_stock_threshold is not None:
        inventory.low_stock_threshold = data.low_stock_threshold
    inventory.updated_by_id = current_user.id

    _commit(db)
    db.refresh(inventory)
    return inventory


@router.get("/low-stock", response_model=list[InventoryResponse])
def get_low_stock(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    seller = _seller_for_inventory(db, current_user)
    return db.query(Inventory).join(Product, Product.id == Inventory.product_id).filter(
        Product.seller_id == seller.id,
        Inventory.available_quantity <= Inventory.low_stock_threshold,
    ).order_by(Inventory.available_quantity.asc()).all()
