from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import case, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.deps import get_db
from api.enums import InventoryMovementType, PermissionCode
from api.models import Inventory, InventoryMovement, Product, ProductVariant, User
from api.permissions import require_permission
from api.schemas import (
    SellerInventoryAdjustmentRequest,
    SellerInventoryConfigureRequest,
    SellerInventoryItemResponse,
    SellerInventoryListResponse,
    SellerInventoryMovementResponse,
    SellerInventoryRestockRequest,
    SellerInventorySettingsUpdate,
    SellerInventorySummaryResponse,
)

router = APIRouter(prefix="/seller/inventory", tags=["Seller Inventory"])


def _seller(user: User):
    if not user.seller_profile:
        raise HTTPException(status_code=403, detail="Seller profile required")
    return user.seller_profile


def _base_query(db: Session, seller_id: UUID):
    return (
        db.query(Inventory)
        .join(Product, Product.id == Inventory.product_id)
        .outerjoin(ProductVariant, ProductVariant.id == Inventory.variant_id)
        .options(joinedload(Inventory.product), joinedload(Inventory.variant))
        .filter(Product.seller_id == seller_id)
    )


def _get_owned(db: Session, seller_id: UUID, inventory_id: UUID, lock: bool = False) -> Inventory:
    query = _base_query(db, seller_id).filter(Inventory.id == inventory_id)
    if lock:
        query = query.with_for_update()
    inventory = query.first()
    if not inventory:
        raise HTTPException(status_code=404, detail="Inventory record not found")
    return inventory


def _price(inventory: Inventory) -> Decimal:
    product = inventory.product
    variant = inventory.variant
    value = None
    if variant is not None:
        value = variant.sale_price if variant.sale_price is not None else variant.price
    if value is None:
        value = product.sale_price if product.sale_price is not None else product.price
    return Decimal(value or 0)


def _serialize(inventory: Inventory) -> SellerInventoryItemResponse:
    unit_price = _price(inventory)
    return SellerInventoryItemResponse(
        inventory_id=inventory.id,
        product_id=inventory.product_id,
        product_name=inventory.product.name,
        product_sku=inventory.product.sku,
        variant_id=inventory.variant_id,
        variant_name=inventory.variant.variant_name if inventory.variant else None,
        variant_sku=inventory.variant.sku if inventory.variant else None,
        quantity=inventory.quantity,
        reserved_quantity=inventory.reserved_quantity,
        available_quantity=inventory.available_quantity,
        low_stock_threshold=inventory.low_stock_threshold or 0,
        warehouse_location=inventory.warehouse_location,
        restock_date=inventory.restock_date,
        unit_price=unit_price,
        inventory_value=unit_price * inventory.quantity,
        is_low_stock=inventory.available_quantity <= (inventory.low_stock_threshold or 0),
        is_out_of_stock=inventory.available_quantity == 0,
        updated_at=inventory.updated_at,
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Inventory update conflict") from exc
    except Exception:
        db.rollback()
        raise


def _record_movement(
    db: Session,
    inventory: Inventory,
    movement_type: InventoryMovementType,
    adjustment: int,
    before_quantity: int,
    user_id: UUID,
    reference: str | None = None,
    note: str | None = None,
) -> InventoryMovement:
    movement = InventoryMovement(
        inventory_id=inventory.id,
        movement_type=movement_type,
        quantity=abs(adjustment),
        before_quantity=before_quantity,
        after_quantity=inventory.quantity,
        reference=reference,
        note=note,
        created_by_id=user_id,
    )
    db.add(movement)
    return movement


@router.post(
    "/configure",
    response_model=SellerInventoryItemResponse,
    status_code=status.HTTP_201_CREATED,
)
def configure_inventory(
    data: SellerInventoryConfigureRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_permission(PermissionCode.seller_inventory_manage.value)
    ),
):
    """Create the seller-owned opening stock row for a product or variant."""

    seller = _seller(current_user)

    product = (
        db.query(Product)
        .filter(
            Product.id == data.product_id,
            Product.seller_id == seller.id,
        )
        .first()
    )
    if not product:
        raise HTTPException(
            status_code=404,
            detail="Product not found or not owned by you",
        )

    variant = None
    if data.variant_id is not None:
        variant = (
            db.query(ProductVariant)
            .filter(
                ProductVariant.id == data.variant_id,
                ProductVariant.product_id == product.id,
            )
            .first()
        )
        if not variant:
            raise HTTPException(
                status_code=404,
                detail="Product variant not found",
            )

    existing_query = db.query(Inventory).filter(
        Inventory.product_id == product.id
    )
    existing_query = existing_query.filter(
        Inventory.variant_id == variant.id
        if variant is not None
        else Inventory.variant_id.is_(None)
    )
    existing = existing_query.first()

    if existing:
        raise HTTPException(
            status_code=409,
            detail=(
                "Inventory is already configured for this "
                + ("variant" if variant is not None else "product")
                + ". Use the Inventory page to adjust or restock it."
            ),
        )

    inventory = Inventory(
        product_id=product.id,
        variant_id=variant.id if variant is not None else None,
        quantity=data.quantity,
        reserved_quantity=0,
        available_quantity=data.quantity,
        warehouse_location=(
            data.warehouse_location.strip()
            if data.warehouse_location
            else None
        ),
        low_stock_threshold=data.low_stock_threshold,
        restock_date=data.restock_date,
        updated_by_id=current_user.id,
    )
    db.add(inventory)
    db.flush()

    if data.quantity > 0:
        _record_movement(
            db,
            inventory,
            InventoryMovementType.restock,
            data.quantity,
            0,
            current_user.id,
            reference="opening_stock",
            note="Opening stock configured by seller",
        )

    _commit(db)

    # Reload relationships required by SellerInventoryItemResponse.
    inventory = _get_owned(db, seller.id, inventory.id)
    return _serialize(inventory)


@router.get("", response_model=SellerInventoryListResponse)
def list_inventory(
    search: str | None = Query(default=None, max_length=120),
    low_stock: bool | None = None,
    out_of_stock: bool | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_inventory_read.value)),
):
    seller = _seller(current_user)
    query = _base_query(db, seller.id)

    if search:
        pattern = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.name.ilike(pattern),
                Product.sku.ilike(pattern),
                ProductVariant.variant_name.ilike(pattern),
                ProductVariant.sku.ilike(pattern),
            )
        )
    if low_stock is True:
        query = query.filter(Inventory.available_quantity <= Inventory.low_stock_threshold)
    if out_of_stock is True:
        query = query.filter(Inventory.available_quantity == 0)

    total = query.count()
    rows = query.order_by(Product.name.asc(), ProductVariant.variant_name.asc().nullslast()).offset((page - 1) * page_size).limit(page_size).all()
    return SellerInventoryListResponse(total=total, page=page, page_size=page_size, results=[_serialize(row) for row in rows])


@router.get("/summary", response_model=SellerInventorySummaryResponse)
def inventory_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_inventory_read.value)),
):
    seller = _seller(current_user)
    rows = _base_query(db, seller.id).all()
    product_ids = {row.product_id for row in rows}
    return SellerInventorySummaryResponse(
        total_products=len(product_ids),
        total_variants=sum(1 for row in rows if row.variant_id is not None),
        total_stock_units=sum(row.quantity for row in rows),
        reserved_units=sum(row.reserved_quantity for row in rows),
        available_units=sum(row.available_quantity for row in rows),
        low_stock_variants=sum(1 for row in rows if row.available_quantity <= (row.low_stock_threshold or 0)),
        out_of_stock_variants=sum(1 for row in rows if row.available_quantity == 0),
        inventory_value=sum((_price(row) * row.quantity for row in rows), Decimal("0")),
    )


@router.get("/low-stock", response_model=list[SellerInventoryItemResponse])
def low_stock_inventory(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_inventory_read.value)),
):
    seller = _seller(current_user)
    rows = _base_query(db, seller.id).filter(Inventory.available_quantity <= Inventory.low_stock_threshold).order_by(Inventory.available_quantity.asc()).all()
    return [_serialize(row) for row in rows]


@router.get("/history", response_model=list[SellerInventoryMovementResponse])
def inventory_history(
    inventory_id: UUID | None = None,
    movement_type: InventoryMovementType | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_inventory_read.value)),
):
    seller = _seller(current_user)
    query = (
        db.query(InventoryMovement)
        .join(Inventory, Inventory.id == InventoryMovement.inventory_id)
        .join(Product, Product.id == Inventory.product_id)
        .outerjoin(ProductVariant, ProductVariant.id == Inventory.variant_id)
        .options(joinedload(InventoryMovement.inventory).joinedload(Inventory.product), joinedload(InventoryMovement.inventory).joinedload(Inventory.variant))
        .filter(Product.seller_id == seller.id)
    )
    if inventory_id:
        query = query.filter(InventoryMovement.inventory_id == inventory_id)
    if movement_type:
        query = query.filter(InventoryMovement.movement_type == movement_type)
    rows = query.order_by(InventoryMovement.created_at.desc()).limit(limit).all()
    result = []
    for row in rows:
        inv = row.inventory
        adjustment = row.after_quantity - row.before_quantity
        result.append(SellerInventoryMovementResponse(
            id=row.id,
            inventory_id=row.inventory_id,
            product_id=inv.product_id,
            product_name=inv.product.name,
            variant_id=inv.variant_id,
            variant_name=inv.variant.variant_name if inv.variant else None,
            movement_type=row.movement_type,
            adjustment=adjustment,
            before_quantity=row.before_quantity,
            after_quantity=row.after_quantity,
            reference=row.reference,
            note=row.note,
            created_at=row.created_at,
        ))
    return result


@router.patch("/{inventory_id}", response_model=SellerInventoryItemResponse)
def update_inventory_settings(
    inventory_id: UUID,
    data: SellerInventorySettingsUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_inventory_manage.value)),
):
    seller = _seller(current_user)
    inventory = _get_owned(db, seller.id, inventory_id, lock=True)
    if data.low_stock_threshold is not None:
        inventory.low_stock_threshold = data.low_stock_threshold
    if data.warehouse_location is not None:
        inventory.warehouse_location = data.warehouse_location.strip() or None
    if data.restock_date is not None:
        inventory.restock_date = data.restock_date
    inventory.updated_by_id = current_user.id
    _commit(db)
    db.refresh(inventory)
    return _serialize(inventory)


@router.post("/{inventory_id}/adjust", response_model=SellerInventoryItemResponse)
def adjust_inventory(
    inventory_id: UUID,
    data: SellerInventoryAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_inventory_manage.value)),
):
    seller = _seller(current_user)
    inventory = _get_owned(db, seller.id, inventory_id, lock=True)
    before = inventory.quantity
    after = before + data.adjustment
    if after < inventory.reserved_quantity:
        raise HTTPException(status_code=409, detail="Stock cannot be reduced below the reserved quantity")
    if after < 0:
        raise HTTPException(status_code=422, detail="Stock cannot be negative")

    inventory.quantity = after
    inventory.available_quantity = after - inventory.reserved_quantity
    inventory.updated_by_id = current_user.id
    _record_movement(db, inventory, data.reason, data.adjustment, before, current_user.id, data.reference, data.note)
    _commit(db)
    db.refresh(inventory)
    return _serialize(inventory)


@router.post("/{inventory_id}/restock", response_model=SellerInventoryItemResponse)
def restock_inventory(
    inventory_id: UUID,
    data: SellerInventoryRestockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.seller_inventory_manage.value)),
):
    seller = _seller(current_user)
    inventory = _get_owned(db, seller.id, inventory_id, lock=True)
    before = inventory.quantity
    inventory.quantity += data.quantity
    inventory.available_quantity = inventory.quantity - inventory.reserved_quantity
    inventory.restock_date = datetime.now().astimezone()
    if data.warehouse_location is not None:
        inventory.warehouse_location = data.warehouse_location.strip() or None
    inventory.updated_by_id = current_user.id
    _record_movement(db, inventory, InventoryMovementType.restock, data.quantity, before, current_user.id, data.reference, data.note)
    _commit(db)
    db.refresh(inventory)
    return _serialize(inventory)
