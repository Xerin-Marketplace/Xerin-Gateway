from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.models import (
    User,
    Inventory,
    Product,
    ProductVariant,
    Seller,
)
from api.schemas import (
    InventoryCreate,
    InventoryUpdate,
    InventoryResponse,
)
from api.permissions import require_permission

router = APIRouter(prefix="/inventory", tags=["Inventory"])


def _ensure_seller_owns_product(db: Session, current_user: User, product_id: UUID) -> Seller:
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=403, detail="You must be a seller to manage inventory")

    product = db.query(Product).filter(Product.id == product_id).first()
    if not product or product.seller_id != seller.id:
        raise HTTPException(status_code=403, detail="You do not own this product")

    return seller


@router.post("", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED)
def create_inventory(
    data: InventoryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _ensure_seller_owns_product(db, current_user, data.product_id)

    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")

    if data.variant_id:
        variant = db.query(ProductVariant).filter(
            ProductVariant.id == data.variant_id,
            ProductVariant.product_id == data.product_id,
        ).first()
        if not variant:
            raise HTTPException(status_code=404, detail="Product variant not found")

    existing = db.query(Inventory).filter(
        Inventory.product_id == data.product_id,
        Inventory.variant_id == data.variant_id,
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Inventory record already exists for this product/variant")

    available = data.quantity - data.reserved_quantity
    inventory = Inventory(
        product_id=data.product_id,
        variant_id=data.variant_id,
        quantity=data.quantity,
        reserved_quantity=data.reserved_quantity,
        available_quantity=available,
        warehouse_location=data.warehouse_location,
        low_stock_threshold=data.low_stock_threshold,
        updated_by_id=current_user.id,
    )
    db.add(inventory)
    db.commit()
    db.refresh(inventory)
    return inventory


@router.get("/my-inventory", response_model=list[InventoryResponse])
def get_my_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=403, detail="You must be a seller to view inventory")

    return db.query(Inventory).join(Product).filter(Product.seller_id == seller.id).all()


@router.get("/product/{product_id}", response_model=InventoryResponse)
def get_product_inventory(
    product_id: UUID,
    db: Session = Depends(get_db),
):
    inventory = db.query(Inventory).filter(
        Inventory.product_id == product_id,
        Inventory.variant_id.is_(None),
    ).first()

    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    return inventory


@router.put("/{inventory_id}", response_model=InventoryResponse)
def update_inventory(
    inventory_id: UUID,
    data: InventoryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inventory = db.query(Inventory).filter(Inventory.id == inventory_id).first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory not found")

    _ensure_seller_owns_product(db, current_user, inventory.product_id)

    if data.quantity is not None:
        inventory.quantity = data.quantity
    if data.reserved_quantity is not None:
        inventory.reserved_quantity = data.reserved_quantity
    if data.warehouse_location is not None:
        inventory.warehouse_location = data.warehouse_location
    if data.low_stock_threshold is not None:
        inventory.low_stock_threshold = data.low_stock_threshold

    inventory.available_quantity = inventory.quantity - inventory.reserved_quantity
    inventory.updated_by_id = current_user.id

    db.commit()
    db.refresh(inventory)
    return inventory


@router.get("/low-stock", response_model=list[InventoryResponse])
def get_low_stock(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
    if not seller:
        raise HTTPException(status_code=403, detail="You must be a seller to view inventory")

    return db.query(Inventory).join(Product).filter(
        Product.seller_id == seller.id,
        Inventory.available_quantity <= Inventory.low_stock_threshold,
    ).all()
