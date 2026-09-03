from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from api.enums import InventoryReservationStatus
from api.models import Inventory, InventoryReservation, Order

TERMINAL_STATUSES = {
    InventoryReservationStatus.committed,
    InventoryReservationStatus.released,
    InventoryReservationStatus.expired,
    InventoryReservationStatus.cancelled,
}


def create_reservation(db: Session, *, inventory: Inventory, order: Order, order_item_id: UUID, user_id: UUID, quantity: int, expires_at: datetime) -> InventoryReservation:
    if quantity <= 0:
        raise HTTPException(status_code=422, detail="Reservation quantity must be positive")
    inventory = db.query(Inventory).filter(Inventory.id == inventory.id).with_for_update().one()
    if inventory.available_quantity < quantity:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "INSUFFICIENT_STOCK",
                "message": "This item is no longer available in the requested quantity.",
                "product_id": str(inventory.product_id),
                "variant_id": str(inventory.variant_id) if inventory.variant_id is not None else None,
                "requested_quantity": int(quantity),
                "available_quantity": int(inventory.available_quantity),
            },
        )
    existing = db.query(InventoryReservation).filter(InventoryReservation.order_item_id == order_item_id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order item already has an inventory reservation")
    inventory.reserved_quantity += quantity
    inventory.available_quantity = inventory.quantity - inventory.reserved_quantity
    reservation = InventoryReservation(inventory_id=inventory.id, order_id=order.id, order_item_id=order_item_id, user_id=user_id, quantity=quantity, status=InventoryReservationStatus.active, expires_at=expires_at)
    db.add(reservation)
    return reservation


def ensure_order_reservations_active(db: Session, order: Order) -> list[InventoryReservation]:
    now = datetime.now(timezone.utc)
    rows = db.query(InventoryReservation).filter(InventoryReservation.order_id == order.id).with_for_update().all()
    if len(rows) != len(order.items):
        raise HTTPException(status_code=409, detail="Order inventory reservations are incomplete")
    for row in rows:
        if row.status != InventoryReservationStatus.active:
            raise HTTPException(status_code=409, detail=f"Inventory reservation is {row.status.value}")
        if row.expires_at <= now:
            release_order_reservations(db, order, target_status=InventoryReservationStatus.expired)
            raise HTTPException(status_code=409, detail="Inventory reservation has expired")
    return rows


def commit_order_reservations(db: Session, order: Order) -> None:
    now = datetime.now(timezone.utc)
    rows = ensure_order_reservations_active(db, order)
    for row in rows:
        inventory = db.query(Inventory).filter(Inventory.id == row.inventory_id).with_for_update().one()
        if inventory.reserved_quantity < row.quantity or inventory.quantity < row.quantity:
            raise HTTPException(status_code=409, detail="Reserved inventory is inconsistent")
        inventory.quantity -= row.quantity
        inventory.reserved_quantity -= row.quantity
        inventory.available_quantity = inventory.quantity - inventory.reserved_quantity
        row.status = InventoryReservationStatus.committed
        row.committed_at = now


def release_order_reservations(db: Session, order: Order, *, target_status: InventoryReservationStatus = InventoryReservationStatus.released) -> int:
    if target_status not in {InventoryReservationStatus.released, InventoryReservationStatus.expired, InventoryReservationStatus.cancelled}:
        raise ValueError("Invalid release status")
    now = datetime.now(timezone.utc)
    rows = db.query(InventoryReservation).filter(InventoryReservation.order_id == order.id, InventoryReservation.status == InventoryReservationStatus.active).with_for_update().all()
    for row in rows:
        inventory = db.query(Inventory).filter(Inventory.id == row.inventory_id).with_for_update().one()
        if inventory.reserved_quantity < row.quantity:
            raise HTTPException(status_code=409, detail="Reserved inventory is inconsistent")
        inventory.reserved_quantity -= row.quantity
        inventory.available_quantity = inventory.quantity - inventory.reserved_quantity
        row.status = target_status
        row.released_at = now
    return len(rows)


def release_expired_reservations(db: Session, *, limit: int = 500) -> int:
    now = datetime.now(timezone.utc)
    rows = db.query(InventoryReservation).filter(InventoryReservation.status == InventoryReservationStatus.active, InventoryReservation.expires_at <= now).order_by(InventoryReservation.expires_at.asc()).with_for_update(skip_locked=True).limit(limit).all()
    count = 0
    for row in rows:
        inventory = db.query(Inventory).filter(Inventory.id == row.inventory_id).with_for_update().one()
        if inventory.reserved_quantity < row.quantity:
            raise RuntimeError(f"Inventory reservation inconsistency for {row.id}")
        inventory.reserved_quantity -= row.quantity
        inventory.available_quantity = inventory.quantity - inventory.reserved_quantity
        row.status = InventoryReservationStatus.expired
        row.released_at = now
        count += 1
    return count
