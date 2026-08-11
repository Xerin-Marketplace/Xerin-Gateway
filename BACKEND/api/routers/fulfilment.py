from __future__ import annotations

import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload

from api.deps import get_current_user, get_db
from api.enums import (
    InboundShipmentStatus,
    InventoryAdjustmentType,
    PickListStatus,
    PermissionCode,
    PutawayTaskStatus,
    SellerStatus,
    WarehouseInventoryMovementType,
    WarehouseStatus,
)
from api.models import (
    InboundShipment,
    InboundShipmentItem,
    Packaging,
    PickList,
    PickListItem,
    Product,
    ProductVariant,
    PutawayTask,
    Seller,
    SellerOrder,
    SellerOrderStatus,
    User,
    Warehouse,
    WarehouseBin,
    WarehouseInventory,
    WarehouseInventoryMovement,
)
from api.permissions import require_permission
from api.schemas import (
    AdminFulfilmentDashboardResponse,
    InboundItemCreate,
    InboundItemResponse,
    InboundShipmentCreate,
    InboundShipmentResponse,
    InboundShipmentUpdate,
    InventoryAdjustRequest,
    InventoryThresholdUpdate,
    PackPickListRequest,
    PackagingCreate,
    PackagingResponse,
    PackagingUpdate,
    PickItemRequest,
    PickListAssignRequest,
    PickListCancelRequest,
    PickListItemResponse,
    PickListResponse,
    PickListStatusUpdate,
    PutawayAssignRequest,
    PutawayCompleteRequest,
    PutawaySkipRequest,
    PutawayTaskResponse,
    ReceiveInboundRequest,
    SellerFulfilmentDashboardResponse,
    WarehouseBinCreate,
    WarehouseBinResponse,
    WarehouseCreate,
    WarehouseInventoryResponse,
    WarehouseResponse,
    WarehouseUpdate,
)

router = APIRouter(prefix="/fulfilment", tags=["Fulfilment"])


# =========================================================
# HELPERS
# =========================================================

def _commit(db: Session, detail: str = "Operation conflict") -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail) from exc
    except Exception:
        db.rollback()
        raise


def _get_warehouse(db: Session, warehouse_id: UUID) -> Warehouse:
    wh = db.get(Warehouse, warehouse_id)
    if not wh:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse not found")
    return wh


def _get_inbound(db: Session, inbound_id: UUID) -> InboundShipment:
    shipment = db.get(InboundShipment, inbound_id)
    if not shipment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbound shipment not found")
    return shipment


def _get_picklist(db: Session, picklist_id: UUID) -> PickList:
    pl = db.get(PickList, picklist_id)
    if not pl:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pick list not found")
    return pl


def _get_seller(db: Session, user: User) -> Seller:
    seller = db.query(Seller).filter(Seller.user_id == user.id).first()
    if not seller:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You must be a seller")
    if seller.status != SellerStatus.approved:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller account is not approved")
    return seller


def _is_admin(user: User, db: Session) -> bool:
    from api.permissions import get_user_role_names, SUPER_ADMIN_ROLE
    roles = get_user_role_names(user)
    if SUPER_ADMIN_ROLE in roles:
        return True
    return "admin" in roles


def _generate_reference(db: Session, prefix: str, model_cls) -> str:
    year = datetime.datetime.now(datetime.timezone.utc).year
    prefix_str = f"{prefix}-{year}-"
    count = db.query(model_cls).filter(model_cls.reference.like(f"{prefix_str}%")).count()
    return f"{prefix_str}{count + 1:04d}"


def _warehouse_to_response(wh: Warehouse) -> WarehouseResponse:
    return WarehouseResponse(
        id=wh.id,
        name=wh.name,
        code=wh.code,
        country=wh.country,
        region=wh.region,
        district=wh.district,
        ward=wh.ward,
        street=wh.street,
        latitude=wh.latitude,
        longitude=wh.longitude,
        total_capacity=wh.total_capacity,
        used_capacity=wh.used_capacity,
        status=wh.status,
        created_at=wh.created_at,
        updated_at=wh.updated_at,
    )


def _inbound_to_response(ship: InboundShipment, db: Session) -> InboundShipmentResponse:
    seller_name = None
    if ship.seller:
        seller_name = ship.seller.business_name
    warehouse_name = ship.warehouse.name if ship.warehouse else None
    total_items = len(ship.items) if ship.items else 0
    total_quantity = sum(i.expected_quantity for i in ship.items) if ship.items else 0
    return InboundShipmentResponse(
        id=ship.id,
        reference=ship.reference,
        seller_id=ship.seller_id,
        seller_name=seller_name,
        warehouse_id=ship.warehouse_id,
        warehouse_name=warehouse_name,
        status=ship.status,
        expected_arrival_at=ship.expected_arrival_at,
        received_at=ship.received_at,
        completed_at=ship.completed_at,
        total_items=total_items,
        total_quantity=total_quantity,
        notes=ship.notes,
        created_at=ship.created_at,
        updated_at=ship.updated_at,
    )


def _inbound_item_to_response(item: InboundShipmentItem, db: Session) -> InboundItemResponse:
    product_name = item.product.name if item.product else None
    if item.putaway_quantity >= item.received_quantity and item.received_quantity > 0:
        item_status = "completed"
    elif item.putaway_quantity > 0:
        item_status = "putaway_in_progress"
    elif item.received_quantity > 0:
        item_status = "received"
    else:
        item_status = "pending"
    return InboundItemResponse(
        id=item.id,
        inbound_shipment_id=item.inbound_shipment_id,
        product_id=item.product_id,
        product_name=product_name,
        variant_id=item.variant_id,
        expected_quantity=item.expected_quantity,
        received_quantity=item.received_quantity,
        putaway_quantity=item.putaway_quantity,
        status=item_status,
        condition=item.condition,
        notes=item.notes,
        created_at=item.created_at,
    )


def _picklist_to_response(pl: PickList, db: Session) -> PickListResponse:
    warehouse_name = pl.warehouse.name if pl.warehouse else None
    assigned_name = None
    if pl.assigned_user:
        assigned_name = f"{pl.assigned_user.first_name or ''} {pl.assigned_user.last_name or ''}".strip() or pl.assigned_user.email
    total_items = len(pl.items) if pl.items else 0
    total_quantity = sum(i.quantity for i in pl.items) if pl.items else 0
    return PickListResponse(
        id=pl.id,
        reference=pl.reference,
        warehouse_id=pl.warehouse_id,
        warehouse_name=warehouse_name,
        seller_order_id=pl.seller_order_id,
        status=pl.status,
        assigned_to=pl.assigned_to,
        assigned_to_name=assigned_name,
        total_items=total_items,
        total_quantity=total_quantity,
        notes=pl.notes,
        created_at=pl.created_at,
        completed_at=pl.completed_at,
    )


def _picklist_item_to_response(item: PickListItem) -> PickListItemResponse:
    product_name = item.product.name if item.product else None
    bin_label = None
    if item.bin:
        bin_label = f"{item.bin.aisle}-{item.bin.shelf}-{item.bin.bin}"
    return PickListItemResponse(
        id=item.id,
        pick_list_id=item.pick_list_id,
        product_id=item.product_id,
        product_name=product_name,
        variant_id=item.variant_id,
        warehouse_bin_id=item.warehouse_bin_id,
        bin_label=bin_label,
        quantity=item.quantity,
        picked_quantity=item.picked_quantity,
        status=item.status,
        created_at=item.created_at,
    )


def _putaway_to_response(task: PutawayTask) -> PutawayTaskResponse:
    product_name = task.product.name if task.product else None
    bin_label = None
    if task.bin:
        bin_label = f"{task.bin.aisle}-{task.bin.shelf}-{task.bin.bin}"
    assigned_name = None
    if task.assigned_user:
        assigned_name = f"{task.assigned_user.first_name or ''} {task.assigned_user.last_name or ''}".strip() or task.assigned_user.email
    return PutawayTaskResponse(
        id=task.id,
        inbound_shipment_id=task.inbound_shipment_id,
        inbound_item_id=task.inbound_item_id,
        warehouse_id=task.warehouse_id,
        warehouse_bin_id=task.warehouse_bin_id,
        bin_label=bin_label,
        product_id=task.product_id,
        product_name=product_name,
        variant_id=task.variant_id,
        quantity=task.quantity,
        putaway_quantity=task.putaway_quantity,
        assigned_to=task.assigned_to,
        assigned_to_name=assigned_name,
        status=task.status,
        notes=task.notes,
        created_at=task.created_at,
        completed_at=task.completed_at,
    )


def _wh_inv_to_response(inv: WarehouseInventory) -> WarehouseInventoryResponse:
    warehouse_name = inv.warehouse.name if inv.warehouse else None
    product_name = inv.product.name if inv.product else None
    bin_label = None
    if inv.bin:
        bin_label = f"{inv.bin.aisle}-{inv.bin.shelf}-{inv.bin.bin}"
    return WarehouseInventoryResponse(
        id=inv.id,
        warehouse_id=inv.warehouse_id,
        warehouse_name=warehouse_name,
        product_id=inv.product_id,
        product_name=product_name,
        variant_id=inv.variant_id,
        seller_id=inv.seller_id,
        quantity=inv.quantity,
        reserved_quantity=inv.reserved_quantity,
        available_quantity=inv.available_quantity,
        low_stock_threshold=inv.low_stock_threshold,
        warehouse_bin_id=inv.warehouse_bin_id,
        bin_label=bin_label,
        updated_at=inv.updated_at,
    )


# =========================================================
# 1. WAREHOUSES
# =========================================================

@router.get("/warehouses", response_model=list[WarehouseResponse])
def list_warehouses(
    status_filter: str | None = Query(default=None, alias="status"),
    country: str | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(Warehouse)
    if status_filter:
        q = q.filter(Warehouse.status == status_filter)
    if country:
        q = q.filter(Warehouse.country.ilike(f"%{country}%"))
    if search:
        q = q.filter(or_(Warehouse.name.ilike(f"%{search}%"), Warehouse.code.ilike(f"%{search}%")))
    items = q.order_by(Warehouse.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return [_warehouse_to_response(w) for w in items]


@router.get("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse_by_id(warehouse_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    return _warehouse_to_response(_get_warehouse(db, warehouse_id))


@router.post("/warehouses", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    data: WarehouseCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    wh = Warehouse(**data.model_dump())
    db.add(wh)
    _commit(db, "Warehouse code already exists")
    db.refresh(wh)
    return _warehouse_to_response(wh)


@router.put("/warehouses/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: UUID,
    data: WarehouseUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    wh = _get_warehouse(db, warehouse_id)
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(wh, k, v)
    _commit(db, "Warehouse code already exists")
    db.refresh(wh)
    return _warehouse_to_response(wh)


@router.delete("/warehouses/{warehouse_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_warehouse(
    warehouse_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    wh = _get_warehouse(db, warehouse_id)
    has_inventory = db.query(WarehouseInventory).filter(WarehouseInventory.warehouse_id == warehouse_id, WarehouseInventory.quantity > 0).first()
    if has_inventory:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete warehouse with active inventory")
    has_inbound = db.query(InboundShipment).filter(
        InboundShipment.warehouse_id == warehouse_id,
        InboundShipment.status.in_([InboundShipmentStatus.draft, InboundShipmentStatus.submitted, InboundShipmentStatus.in_transit]),
    ).first()
    if has_inbound:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot delete warehouse with active inbound shipments")
    db.delete(wh)
    _commit(db)
    return None


@router.get("/warehouses/{warehouse_id}/bins", response_model=list[WarehouseBinResponse])
def list_warehouse_bins(warehouse_id: UUID, db: Session = Depends(get_db), _: User = Depends(get_current_user)):
    _get_warehouse(db, warehouse_id)
    bins = db.query(WarehouseBin).filter(WarehouseBin.warehouse_id == warehouse_id).order_by(WarehouseBin.aisle, WarehouseBin.shelf, WarehouseBin.bin).all()
    return [WarehouseBinResponse.model_validate(b) for b in bins]


@router.post("/warehouses/{warehouse_id}/bins", response_model=WarehouseBinResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse_bin(
    warehouse_id: UUID,
    data: WarehouseBinCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    _get_warehouse(db, warehouse_id)
    bin_obj = WarehouseBin(warehouse_id=warehouse_id, **data.model_dump())
    db.add(bin_obj)
    _commit(db, "Bin location already exists in this warehouse")
    db.refresh(bin_obj)
    return WarehouseBinResponse.model_validate(bin_obj)


# =========================================================
# 2. INBOUND SHIPMENTS
# =========================================================

@router.get("/inbound", response_model=list[InboundShipmentResponse])
def list_inbound_shipments(
    status_filter: str | None = Query(default=None, alias="status"),
    warehouse_id: UUID | None = None,
    seller_id: UUID | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(InboundShipment).options(joinedload(InboundShipment.seller), joinedload(InboundShipment.warehouse), joinedload(InboundShipment.items))
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
        q = q.filter(InboundShipment.seller_id == seller.id)
    else:
        if seller_id:
            q = q.filter(InboundShipment.seller_id == seller_id)
    if status_filter:
        q = q.filter(InboundShipment.status == status_filter)
    if warehouse_id:
        q = q.filter(InboundShipment.warehouse_id == warehouse_id)
    if search:
        q = q.filter(InboundShipment.reference.ilike(f"%{search}%"))
    items = q.order_by(InboundShipment.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return [_inbound_to_response(s, db) for s in items]


@router.get("/inbound/{inbound_id}", response_model=InboundShipmentResponse)
def get_inbound_shipment(inbound_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _inbound_to_response(ship, db)


@router.post("/inbound", response_model=InboundShipmentResponse, status_code=status.HTTP_201_CREATED)
def create_inbound_shipment(
    data: InboundShipmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    admin = _is_admin(current_user, db)
    if admin and data.seller_id:
        seller_id = data.seller_id
    elif not admin:
        seller = _get_seller(db, current_user)
        seller_id = seller.id
    else:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="seller_id is required for admin users")

    wh = _get_warehouse(db, data.warehouse_id)
    if wh.status != WarehouseStatus.active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Warehouse is not active")

    reference = _generate_reference(db, "INB", InboundShipment)
    ship = InboundShipment(
        reference=reference,
        seller_id=seller_id,
        warehouse_id=data.warehouse_id,
        expected_arrival_at=data.expected_arrival_at,
        notes=data.notes,
        status=InboundShipmentStatus.draft,
    )
    db.add(ship)
    _commit(db, "Failed to create inbound shipment")
    db.refresh(ship)
    return _inbound_to_response(ship, db)


@router.patch("/inbound/{inbound_id}", response_model=InboundShipmentResponse)
def update_inbound_shipment(
    inbound_id: UUID,
    data: InboundShipmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if ship.status != InboundShipmentStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Inbound shipment is not editable (must be in draft status)")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(ship, k, v)
    _commit(db)
    db.refresh(ship)
    return _inbound_to_response(ship, db)


@router.post("/inbound/{inbound_id}/submit", response_model=InboundShipmentResponse)
def submit_inbound_shipment(inbound_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if ship.status != InboundShipmentStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft shipments can be submitted")
    ship.status = InboundShipmentStatus.submitted
    _commit(db)
    db.refresh(ship)
    return _inbound_to_response(ship, db)


@router.post("/inbound/{inbound_id}/cancel", response_model=InboundShipmentResponse)
def cancel_inbound_shipment(inbound_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if ship.status not in (InboundShipmentStatus.draft, InboundShipmentStatus.submitted):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only draft or submitted shipments can be cancelled")
    ship.status = InboundShipmentStatus.cancelled
    _commit(db)
    db.refresh(ship)
    return _inbound_to_response(ship, db)


@router.post("/inbound/{inbound_id}/in-transit", response_model=InboundShipmentResponse)
def mark_in_transit(inbound_id: UUID, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.inventory_manage.value))):
    ship = _get_inbound(db, inbound_id)
    if ship.status != InboundShipmentStatus.submitted:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only submitted shipments can be marked in transit")
    ship.status = InboundShipmentStatus.in_transit
    _commit(db)
    db.refresh(ship)
    return _inbound_to_response(ship, db)


@router.post("/inbound/{inbound_id}/receive", response_model=InboundShipmentResponse)
def receive_inbound_shipment(
    inbound_id: UUID,
    data: ReceiveInboundRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    ship = _get_inbound(db, inbound_id)
    if ship.status != InboundShipmentStatus.in_transit:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only in-transit shipments can be received")
    for ri in data.received_items:
        item = db.get(InboundShipmentItem, ri.inbound_item_id)
        if not item or item.inbound_shipment_id != ship.id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Inbound item {ri.inbound_item_id} not found")
        if ri.received_quantity > item.expected_quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Received quantity exceeds expected for item {ri.inbound_item_id}")
        item.received_quantity = ri.received_quantity
        item.condition = ri.condition
        item.notes = ri.notes
    ship.status = InboundShipmentStatus.received
    ship.received_at = datetime.datetime.now(datetime.timezone.utc)
    _commit(db)
    db.refresh(ship)
    return _inbound_to_response(ship, db)


# --- Inbound Items ---

@router.get("/inbound/{inbound_id}/items", response_model=list[InboundItemResponse])
def list_inbound_items(inbound_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    items = db.query(InboundShipmentItem).filter(InboundShipmentItem.inbound_shipment_id == inbound_id).all()
    return [_inbound_item_to_response(i, db) for i in items]


@router.post("/inbound/{inbound_id}/items", response_model=InboundItemResponse, status_code=status.HTTP_201_CREATED)
def add_inbound_item(
    inbound_id: UUID,
    data: InboundItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if ship.status != InboundShipmentStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Items can only be added to draft shipments")
    product = db.get(Product, data.product_id)
    if not product:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if data.variant_id:
        variant = db.get(ProductVariant, data.variant_id)
        if not variant or variant.product_id != data.product_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product variant not found")
    item = InboundShipmentItem(
        inbound_shipment_id=inbound_id,
        product_id=data.product_id,
        variant_id=data.variant_id,
        expected_quantity=data.expected_quantity,
    )
    db.add(item)
    _commit(db)
    db.refresh(item)
    return _inbound_item_to_response(item, db)


@router.patch("/inbound/{inbound_id}/items/{item_id}", response_model=InboundItemResponse)
def update_inbound_item(
    inbound_id: UUID,
    item_id: UUID,
    data: InboundItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if ship.status != InboundShipmentStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Items can only be updated in draft shipments")
    item = db.get(InboundShipmentItem, item_id)
    if not item or item.inbound_shipment_id != inbound_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbound item not found")
    item.expected_quantity = data.expected_quantity
    _commit(db)
    db.refresh(item)
    return _inbound_item_to_response(item, db)


@router.delete("/inbound/{inbound_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_inbound_item(
    inbound_id: UUID,
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ship = _get_inbound(db, inbound_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or ship.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    if ship.status != InboundShipmentStatus.draft:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Items can only be removed from draft shipments")
    item = db.get(InboundShipmentItem, item_id)
    if not item or item.inbound_shipment_id != inbound_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inbound item not found")
    db.delete(item)
    _commit(db)
    return None


# =========================================================
# 3. PUTAWAY TASKS
# =========================================================

@router.get("/putaway", response_model=list[PutawayTaskResponse])
def list_putaway_tasks(
    status_filter: str | None = Query(default=None, alias="status"),
    warehouse_id: UUID | None = None,
    inbound_shipment_id: UUID | None = None,
    assigned_to: UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    q = db.query(PutawayTask).options(
        joinedload(PutawayTask.product),
        joinedload(PutawayTask.bin),
        joinedload(PutawayTask.assigned_user),
    )
    if status_filter:
        q = q.filter(PutawayTask.status == status_filter)
    if warehouse_id:
        q = q.filter(PutawayTask.warehouse_id == warehouse_id)
    if inbound_shipment_id:
        q = q.filter(PutawayTask.inbound_shipment_id == inbound_shipment_id)
    if assigned_to:
        q = q.filter(PutawayTask.assigned_to == assigned_to)
    items = q.order_by(PutawayTask.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return [_putaway_to_response(t) for t in items]


@router.post("/putaway/{task_id}/assign", response_model=PutawayTaskResponse)
def assign_putaway_task(
    task_id: UUID,
    data: PutawayAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    task = db.get(PutawayTask, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Putaway task not found")
    task.assigned_to = data.assigned_to
    if task.status == PutawayTaskStatus.pending:
        task.status = PutawayTaskStatus.in_progress
    _commit(db)
    db.refresh(task)
    return _putaway_to_response(task)


@router.post("/putaway/{task_id}/complete", response_model=PutawayTaskResponse)
def complete_putaway_task(
    task_id: UUID,
    data: PutawayCompleteRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    task = db.get(PutawayTask, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Putaway task not found")
    if task.status in (PutawayTaskStatus.completed, PutawayTaskStatus.skipped):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task already completed or skipped")
    wh_bin = db.get(WarehouseBin, data.warehouse_bin_id)
    if not wh_bin or wh_bin.warehouse_id != task.warehouse_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Warehouse bin not found in this warehouse")

    # Update or create warehouse inventory
    inv_q = db.query(WarehouseInventory).filter(
        WarehouseInventory.warehouse_id == task.warehouse_id,
        WarehouseInventory.product_id == task.product_id,
    )
    inv_q = inv_q.filter(WarehouseInventory.variant_id == task.variant_id) if task.variant_id else inv_q.filter(WarehouseInventory.variant_id.is_(None))
    inv = inv_q.first()

    if not inv:
        seller = db.query(Seller).filter(Seller.id == db.query(Product).filter(Product.id == task.product_id).first().seller_id).first()
        inv = WarehouseInventory(
            warehouse_id=task.warehouse_id,
            product_id=task.product_id,
            variant_id=task.variant_id,
            seller_id=seller.id if seller else task.inbound_shipment.seller_id,
            quantity=0,
            reserved_quantity=0,
            available_quantity=0,
            warehouse_bin_id=wh_bin.id,
        )
        db.add(inv)

    inv.quantity += data.putaway_quantity
    inv.available_quantity = inv.quantity - inv.reserved_quantity
    inv.warehouse_bin_id = wh_bin.id

    # Record movement
    movement = WarehouseInventoryMovement(
        warehouse_inventory_id=inv.id,
        movement_type=WarehouseInventoryMovementType.inbound_putaway,
        quantity=data.putaway_quantity,
        reference_type="putaway_task",
        reference_id=task.id,
        reason=data.notes or "Putaway from inbound shipment",
        created_by_id=current_user.id,
    )
    db.add(movement)

    # Update putaway task
    task.putaway_quantity = data.putaway_quantity
    task.warehouse_bin_id = wh_bin.id
    task.status = PutawayTaskStatus.completed
    task.completed_at = datetime.datetime.now(datetime.timezone.utc)
    task.notes = data.notes

    # Update inbound item putaway_quantity
    inbound_item = task.inbound_item
    if inbound_item:
        inbound_item.putaway_quantity += data.putaway_quantity

    # Check if all items in the inbound shipment are fully putaway
    ship = task.inbound_shipment
    if ship and ship.status == InboundShipmentStatus.received:
        all_items = db.query(InboundShipmentItem).filter(InboundShipmentItem.inbound_shipment_id == ship.id).all()
        if all_items and all(i.putaway_quantity >= i.received_quantity for i in all_items):
            ship.status = InboundShipmentStatus.putaway_in_progress
            # If all putaway, mark completed
            all_putaway = all(i.putaway_quantity >= i.received_quantity for i in all_items)
            if all_putaway:
                ship.status = InboundShipmentStatus.completed
                ship.completed_at = datetime.datetime.now(datetime.timezone.utc)

    _commit(db)
    db.refresh(task)
    return _putaway_to_response(task)


@router.post("/putaway/{task_id}/skip", response_model=PutawayTaskResponse)
def skip_putaway_task(
    task_id: UUID,
    data: PutawaySkipRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    task = db.get(PutawayTask, task_id)
    if not task:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Putaway task not found")
    if task.status in (PutawayTaskStatus.completed, PutawayTaskStatus.skipped):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Task already completed or skipped")
    task.status = PutawayTaskStatus.skipped
    task.notes = data.reason
    task.completed_at = datetime.datetime.now(datetime.timezone.utc)
    _commit(db)
    db.refresh(task)
    return _putaway_to_response(task)


# =========================================================
# 4. PICK LISTS
# =========================================================

@router.get("/picklists", response_model=list[PickListResponse])
def list_pick_lists(
    status_filter: str | None = Query(default=None, alias="status"),
    warehouse_id: UUID | None = None,
    assigned_to: UUID | None = None,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(PickList).options(
        joinedload(PickList.warehouse),
        joinedload(PickList.assigned_user),
        joinedload(PickList.items),
    )
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
        seller_order_ids = db.query(SellerOrder.id).filter(SellerOrder.seller_id == seller.id).subquery()
        q = q.filter(PickList.seller_order_id.in_(seller_order_ids))
    if status_filter:
        q = q.filter(PickList.status == status_filter)
    if warehouse_id:
        q = q.filter(PickList.warehouse_id == warehouse_id)
    if assigned_to:
        q = q.filter(PickList.assigned_to == assigned_to)
    if search:
        q = q.filter(PickList.reference.ilike(f"%{search}%"))
    items = q.order_by(PickList.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return [_picklist_to_response(p, db) for p in items]


@router.get("/picklists/{picklist_id}", response_model=PickListResponse)
def get_pick_list(picklist_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pl = _get_picklist(db, picklist_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
        so = db.get(SellerOrder, pl.seller_order_id)
        if not so or so.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _picklist_to_response(pl, db)


@router.get("/picklists/{picklist_id}/items", response_model=list[PickListItemResponse])
def list_pick_list_items(picklist_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    pl = _get_picklist(db, picklist_id)
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
        so = db.get(SellerOrder, pl.seller_order_id)
        if not so or so.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    items = db.query(PickListItem).options(joinedload(PickListItem.product), joinedload(PickListItem.bin)).filter(PickListItem.pick_list_id == picklist_id).all()
    return [_picklist_item_to_response(i) for i in items]


@router.post("/picklists/{picklist_id}/assign", response_model=PickListResponse)
def assign_pick_list(
    picklist_id: UUID,
    data: PickListAssignRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pl = _get_picklist(db, picklist_id)
    if pl.status != PickListStatus.pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending pick lists can be assigned")
    pl.assigned_to = data.assigned_to
    pl.status = PickListStatus.assigned
    _commit(db)
    db.refresh(pl)
    return _picklist_to_response(pl, db)


@router.post("/picklists/{picklist_id}/start", response_model=PickListResponse)
def start_picking(
    picklist_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pl = _get_picklist(db, picklist_id)
    if pl.status != PickListStatus.assigned:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only assigned pick lists can start picking")
    pl.status = PickListStatus.in_progress
    _commit(db)
    db.refresh(pl)
    return _picklist_to_response(pl, db)


@router.post("/picklists/{picklist_id}/items/{item_id}/pick", response_model=PickListItemResponse)
def mark_item_picked(
    picklist_id: UUID,
    item_id: UUID,
    data: PickItemRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pl = _get_picklist(db, picklist_id)
    if pl.status != PickListStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick list must be in progress")
    item = db.get(PickListItem, item_id)
    if not item or item.pick_list_id != picklist_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pick list item not found")
    if data.picked_quantity > item.quantity:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Picked quantity exceeds required quantity")
    item.picked_quantity = data.picked_quantity
    item.status = "picked" if data.picked_quantity >= item.quantity else "partial"
    _commit(db)
    db.refresh(item)
    return _picklist_item_to_response(item)


@router.post("/picklists/{picklist_id}/complete-pick", response_model=PickListResponse)
def complete_picking(
    picklist_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pl = _get_picklist(db, picklist_id)
    if pl.status != PickListStatus.in_progress:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick list must be in progress")
    items = db.query(PickListItem).filter(PickListItem.pick_list_id == picklist_id).all()
    if not items:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Pick list has no items")
    incomplete = [i for i in items if i.picked_quantity < i.quantity]
    if incomplete:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Not all items have been fully picked")
    pl.status = PickListStatus.picked
    _commit(db)
    db.refresh(pl)
    return _picklist_to_response(pl, db)


@router.post("/picklists/{picklist_id}/pack", response_model=PickListResponse)
def complete_packing(
    picklist_id: UUID,
    data: PackPickListRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pl = _get_picklist(db, picklist_id)
    if pl.status != PickListStatus.picked:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only picked pick lists can be packed")
    pl.status = PickListStatus.packed
    pl.completed_at = datetime.datetime.now(datetime.timezone.utc)

    # Update seller order status to shipped
    so = db.get(SellerOrder, pl.seller_order_id)
    if so:
        so.status = SellerOrderStatus.shipped
        so.shipped_at = datetime.datetime.now(datetime.timezone.utc)

    # Deduct inventory
    items = db.query(PickListItem).filter(PickListItem.pick_list_id == picklist_id).all()
    for item in items:
        inv_q = db.query(WarehouseInventory).filter(
            WarehouseInventory.warehouse_id == pl.warehouse_id,
            WarehouseInventory.product_id == item.product_id,
        )
        inv_q = inv_q.filter(WarehouseInventory.variant_id == item.variant_id) if item.variant_id else inv_q.filter(WarehouseInventory.variant_id.is_(None))
        inv = inv_q.first()
        if inv:
            inv.quantity -= item.picked_quantity
            inv.reserved_quantity = max(0, inv.reserved_quantity - item.quantity)
            inv.available_quantity = inv.quantity - inv.reserved_quantity
            movement = WarehouseInventoryMovement(
                warehouse_inventory_id=inv.id,
                movement_type=WarehouseInventoryMovementType.outbound_pick,
                quantity=item.picked_quantity,
                reference_type="pick_list",
                reference_id=pl.id,
                reason="Outbound pick for order",
            )
            db.add(movement)

    _commit(db)
    db.refresh(pl)
    return _picklist_to_response(pl, db)


@router.post("/picklists/{picklist_id}/cancel", response_model=PickListResponse)
def cancel_pick_list(
    picklist_id: UUID,
    data: PickListCancelRequest,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pl = _get_picklist(db, picklist_id)
    if pl.status not in (PickListStatus.pending, PickListStatus.assigned):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only pending or assigned pick lists can be cancelled")
    pl.status = PickListStatus.cancelled
    pl.notes = data.reason
    pl.completed_at = datetime.datetime.now(datetime.timezone.utc)
    _commit(db)
    db.refresh(pl)
    return _picklist_to_response(pl, db)


@router.patch("/picklists/{picklist_id}/status", response_model=PickListResponse)
def update_pick_list_status(
    picklist_id: UUID,
    data: PickListStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pl = _get_picklist(db, picklist_id)
    pl.status = data.status
    if data.status in (PickListStatus.packed, PickListStatus.cancelled):
        pl.completed_at = datetime.datetime.now(datetime.timezone.utc)
    _commit(db)
    db.refresh(pl)
    return _picklist_to_response(pl, db)


# =========================================================
# 5. FBX INVENTORY (WAREHOUSE INVENTORY)
# =========================================================

@router.get("/inventory", response_model=list[WarehouseInventoryResponse])
def list_warehouse_inventory(
    warehouse_id: UUID | None = None,
    seller_id: UUID | None = None,
    product_id: UUID | None = None,
    low_stock: bool = False,
    search: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(WarehouseInventory).options(
        joinedload(WarehouseInventory.warehouse),
        joinedload(WarehouseInventory.product),
        joinedload(WarehouseInventory.bin),
    )
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Seller access required")
        q = q.filter(WarehouseInventory.seller_id == seller.id)
    else:
        if seller_id:
            q = q.filter(WarehouseInventory.seller_id == seller_id)
    if warehouse_id:
        q = q.filter(WarehouseInventory.warehouse_id == warehouse_id)
    if product_id:
        q = q.filter(WarehouseInventory.product_id == product_id)
    if low_stock:
        q = q.filter(WarehouseInventory.quantity <= WarehouseInventory.low_stock_threshold)
    if search:
        q = q.join(Product).filter(Product.name.ilike(f"%{search}%"))
    items = q.order_by(WarehouseInventory.updated_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return [_wh_inv_to_response(i) for i in items]


@router.get("/inventory/{inventory_id}", response_model=WarehouseInventoryResponse)
def get_warehouse_inventory(inventory_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    inv = db.get(WarehouseInventory, inventory_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory record not found")
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or inv.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return _wh_inv_to_response(inv)


@router.post("/inventory/{inventory_id}/adjust", response_model=WarehouseInventoryResponse)
def adjust_inventory(
    inventory_id: UUID,
    data: InventoryAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    inv = db.get(WarehouseInventory, inventory_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory record not found")
    if data.adjustment_type == InventoryAdjustmentType.increase:
        inv.quantity += data.quantity
    else:
        if inv.quantity - inv.reserved_quantity < data.quantity:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Insufficient available inventory")
        inv.quantity -= data.quantity
    inv.available_quantity = inv.quantity - inv.reserved_quantity
    movement = WarehouseInventoryMovement(
        warehouse_inventory_id=inv.id,
        movement_type=WarehouseInventoryMovementType.manual_adjustment,
        quantity=data.quantity,
        reason=data.reason,
        notes=data.notes,
        created_by_id=current_user.id,
    )
    db.add(movement)
    _commit(db)
    db.refresh(inv)
    return _wh_inv_to_response(inv)


@router.patch("/inventory/{inventory_id}", response_model=WarehouseInventoryResponse)
def update_inventory_threshold(
    inventory_id: UUID,
    data: InventoryThresholdUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    inv = db.get(WarehouseInventory, inventory_id)
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inventory record not found")
    admin = _is_admin(current_user, db)
    if not admin:
        seller = db.query(Seller).filter(Seller.user_id == current_user.id).first()
        if not seller or inv.seller_id != seller.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    inv.low_stock_threshold = data.low_stock_threshold
    _commit(db)
    db.refresh(inv)
    return _wh_inv_to_response(inv)


# =========================================================
# 6. PACKAGING
# =========================================================

@router.get("/packaging", response_model=list[PackagingResponse])
def list_packaging(
    packaging_type: str | None = Query(default=None, alias="type"),
    is_active: bool | None = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    q = db.query(Packaging)
    if packaging_type:
        q = q.filter(Packaging.packaging_type == packaging_type)
    if is_active is not None:
        q = q.filter(Packaging.is_active == is_active)
    items = q.order_by(Packaging.created_at.desc()).all()
    return [PackagingResponse.model_validate(p) for p in items]


@router.post("/packaging", response_model=PackagingResponse, status_code=status.HTTP_201_CREATED)
def create_packaging(
    data: PackagingCreate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pkg = Packaging(**data.model_dump())
    db.add(pkg)
    _commit(db)
    db.refresh(pkg)
    return PackagingResponse.model_validate(pkg)


@router.put("/packaging/{packaging_id}", response_model=PackagingResponse)
def update_packaging(
    packaging_id: UUID,
    data: PackagingUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pkg = db.get(Packaging, packaging_id)
    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Packaging not found")
    for k, v in data.model_dump(exclude_unset=True).items():
        setattr(pkg, k, v)
    _commit(db)
    db.refresh(pkg)
    return PackagingResponse.model_validate(pkg)


@router.delete("/packaging/{packaging_id}", status_code=status.HTTP_204_NO_CONTENT)
def deactivate_packaging(
    packaging_id: UUID,
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    pkg = db.get(Packaging, packaging_id)
    if not pkg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Packaging not found")
    pkg.is_active = False
    _commit(db)
    return None


# =========================================================
# 7. DASHBOARD / STATS
# =========================================================

@router.get("/dashboard", response_model=AdminFulfilmentDashboardResponse)
def admin_fulfilment_dashboard(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.inventory_manage.value)),
):
    wh_total = db.query(Warehouse).count()
    wh_active = db.query(Warehouse).filter(Warehouse.status == WarehouseStatus.active).count()
    wh_maintenance = db.query(Warehouse).filter(Warehouse.status == WarehouseStatus.maintenance).count()

    inbound_pending = db.query(InboundShipment).filter(InboundShipment.status.in_([InboundShipmentStatus.draft, InboundShipmentStatus.submitted])).count()
    inbound_transit = db.query(InboundShipment).filter(InboundShipment.status == InboundShipmentStatus.in_transit).count()
    inbound_received = db.query(InboundShipment).filter(InboundShipment.status == InboundShipmentStatus.received).count()
    inbound_completed = db.query(InboundShipment).filter(InboundShipment.status == InboundShipmentStatus.completed).count()
    inbound_cancelled = db.query(InboundShipment).filter(InboundShipment.status == InboundShipmentStatus.cancelled).count()

    pl_pending = db.query(PickList).filter(PickList.status == PickListStatus.pending).count()
    pl_in_progress = db.query(PickList).filter(PickList.status == PickListStatus.in_progress).count()
    pl_picked = db.query(PickList).filter(PickList.status == PickListStatus.picked).count()
    pl_packed = db.query(PickList).filter(PickList.status == PickListStatus.packed).count()
    pl_cancelled = db.query(PickList).filter(PickList.status == PickListStatus.cancelled).count()

    inv_total_skus = db.query(WarehouseInventory).count()
    inv_total_units = db.query(func.sum(WarehouseInventory.quantity)).scalar() or 0
    inv_low_stock = db.query(WarehouseInventory).filter(WarehouseInventory.quantity <= WarehouseInventory.low_stock_threshold, WarehouseInventory.quantity > 0).count()
    inv_out_of_stock = db.query(WarehouseInventory).filter(WarehouseInventory.quantity == 0).count()

    return AdminFulfilmentDashboardResponse(
        warehouses={"total": wh_total, "active": wh_active, "maintenance": wh_maintenance},
        inbound={"pending": inbound_pending, "in_transit": inbound_transit, "received": inbound_received, "completed": inbound_completed, "cancelled": inbound_cancelled},
        pick_lists={"pending": pl_pending, "in_progress": pl_in_progress, "picked": pl_picked, "packed": pl_packed, "cancelled": pl_cancelled},
        inventory={"total_skus": inv_total_skus, "total_units": inv_total_units, "low_stock_items": inv_low_stock, "out_of_stock_items": inv_out_of_stock},
    )


@router.get("/seller/dashboard", response_model=SellerFulfilmentDashboardResponse)
def seller_fulfilment_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    seller = _get_seller(db, current_user)

    inbound_total = db.query(InboundShipment).filter(InboundShipment.seller_id == seller.id).count()
    inbound_transit = db.query(InboundShipment).filter(InboundShipment.seller_id == seller.id, InboundShipment.status == InboundShipmentStatus.in_transit).count()
    inbound_received = db.query(InboundShipment).filter(InboundShipment.seller_id == seller.id, InboundShipment.status == InboundShipmentStatus.received).count()
    inbound_completed = db.query(InboundShipment).filter(InboundShipment.seller_id == seller.id, InboundShipment.status == InboundShipmentStatus.completed).count()

    inv_total_units = db.query(func.sum(WarehouseInventory.quantity)).filter(WarehouseInventory.seller_id == seller.id).scalar() or 0
    inv_available_units = db.query(func.sum(WarehouseInventory.available_quantity)).filter(WarehouseInventory.seller_id == seller.id).scalar() or 0
    inv_reserved_units = db.query(func.sum(WarehouseInventory.reserved_quantity)).filter(WarehouseInventory.seller_id == seller.id).scalar() or 0
    inv_low_stock = db.query(WarehouseInventory).filter(
        WarehouseInventory.seller_id == seller.id,
        WarehouseInventory.quantity <= WarehouseInventory.low_stock_threshold,
        WarehouseInventory.quantity > 0,
    ).count()

    return SellerFulfilmentDashboardResponse(
        inbound={"total": inbound_total, "in_transit": inbound_transit, "received": inbound_received, "completed": inbound_completed},
        fbx_inventory={"total_units": inv_total_units, "available_units": inv_available_units, "reserved_units": inv_reserved_units, "low_stock_items": inv_low_stock},
    )
