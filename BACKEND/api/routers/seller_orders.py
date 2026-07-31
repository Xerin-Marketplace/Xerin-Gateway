from __future__ import annotations

from datetime import date, datetime, time, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, cast, func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.deps import get_db
from api.enums import PermissionCode, SellerOrderStatus, ShipmentStatus
from api.models import Order, OrderStatus, OrderStatusHistory, SellerOrder, Shipment, ShipmentTrackingEvent, User
from api.permissions import require_permission
from api.schemas import SellerOrderActionRequest, SellerOrderCancellationRequest, SellerOrderDispatchRequest, SellerOrderListResponse, SellerOrderSummaryResponse, SellerOrderView

router = APIRouter(prefix="/seller/orders", tags=["Seller Orders"])


def _seller(user: User):
    if not user.seller_profile:
        raise HTTPException(403, "Seller profile required")
    return user.seller_profile


def _query(db: Session, seller_id: UUID):
    return db.query(SellerOrder).options(
        joinedload(SellerOrder.order).joinedload(Order.user),
        joinedload(SellerOrder.order).joinedload(Order.shipping_address),
        selectinload(SellerOrder.order).selectinload(Order.items),
        selectinload(SellerOrder.order).selectinload(Order.shipments).selectinload(Shipment.items),
        selectinload(SellerOrder.order).selectinload(Order.shipments).selectinload(Shipment.tracking_events),
    ).filter(SellerOrder.seller_id == seller_id)


def _get(db: Session, seller_id: UUID, row_id: UUID, lock: bool = False):
    q = _query(db, seller_id).filter(SellerOrder.id == row_id)
    if lock:
        q = q.with_for_update()
    row = q.first()
    if not row:
        raise HTTPException(404, "Seller order not found")
    return row


def _shipment(row):
    return next((x for x in row.order.shipments if x.seller_id == row.seller_id), None)


def _serialize(row):
    order = row.order
    user = order.user
    address = order.shipping_address
    address_data = None if address is None else {
        "id": str(address.id), "label": address.label,
        "recipient_name": address.recipient_name, "recipient_phone": address.recipient_phone,
        "street": address.street, "landmark": address.landmark,
        "ward": address.ward, "district": address.district,
        "city": address.city, "region": address.region, "postal_code": address.postal_code,
        "country": address.country,
    }
    return {
        "id": row.id, "order_id": order.id, "seller_id": row.seller_id,
        "order_status": order.status, "seller_status": row.status, "currency": order.currency,
        "seller_subtotal": row.seller_subtotal, "item_count": row.item_count,
        "customer_name": f"{user.first_name or ''} {user.last_name or ''}".strip() or user.email,
        "customer_phone": user.phone, "shipping_address": address_data,
        "shipping_method_name": order.shipping_method_name, "shipping_carrier": order.shipping_carrier,
        "estimated_delivery_from": order.estimated_delivery_from, "estimated_delivery_to": order.estimated_delivery_to,
        "seller_notes": row.seller_notes, "cancellation_reason": row.cancellation_reason,
        "items": [x for x in order.items if x.seller_id == row.seller_id],
        "shipment": _shipment(row), "created_at": row.created_at, "updated_at": row.updated_at,
    }


def _commit(db):
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(409, "Seller order update conflicts with existing data") from exc


def _sync_global(db, order, user_id):
    rows = db.query(SellerOrder).filter(SellerOrder.order_id == order.id).all()
    target = None
    if rows and all(x.status == SellerOrderStatus.delivered for x in rows):
        target = OrderStatus.delivered
    elif rows and all(x.status in {SellerOrderStatus.shipped, SellerOrderStatus.delivered} for x in rows):
        target = OrderStatus.shipped
    elif order.status == OrderStatus.paid and any(x.status in {SellerOrderStatus.accepted, SellerOrderStatus.processing, SellerOrderStatus.ready_to_ship} for x in rows):
        target = OrderStatus.processing
    if target and order.status != target:
        order.status = target
        db.add(OrderStatusHistory(order_id=order.id, status=target.value, notes="Seller fulfilment status synchronized", created_by_id=user_id))


@router.get("/summary", response_model=SellerOrderSummaryResponse)
def summary(db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_read.value))):
    seller = _seller(user)
    rows = db.query(SellerOrder.status, func.count(SellerOrder.id)).filter(SellerOrder.seller_id == seller.id).group_by(SellerOrder.status).all()
    counts = dict(rows)
    money, units = db.query(func.coalesce(func.sum(SellerOrder.seller_subtotal), 0), func.coalesce(func.sum(SellerOrder.item_count), 0)).filter(SellerOrder.seller_id == seller.id).one()
    return {"total_orders": sum(counts.values()), "new_orders": counts.get(SellerOrderStatus.new, 0), "accepted_orders": counts.get(SellerOrderStatus.accepted, 0), "processing_orders": counts.get(SellerOrderStatus.processing, 0), "ready_to_ship_orders": counts.get(SellerOrderStatus.ready_to_ship, 0), "shipped_orders": counts.get(SellerOrderStatus.shipped, 0), "delivered_orders": counts.get(SellerOrderStatus.delivered, 0), "cancellation_requests": counts.get(SellerOrderStatus.cancellation_requested, 0), "gross_sales": Decimal(money), "units_sold": int(units)}


@router.get("", response_model=SellerOrderListResponse)
def list_orders(seller_status: SellerOrderStatus | None = Query(None, alias="status"), search: str | None = None, date_from: date | None = None, date_to: date | None = None, page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100), db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_read.value))):
    q = _query(db, _seller(user).id)
    if seller_status is not None:
        q = q.filter(SellerOrder.status == seller_status)
    if search:
        token = f"%{search.strip()}%"
        q = q.join(Order, SellerOrder.order_id == Order.id).filter(or_(cast(Order.id, String).ilike(token), Order.notes.ilike(token)))
    if date_from:
        q = q.filter(SellerOrder.created_at >= datetime.combine(date_from, time.min, tzinfo=timezone.utc))
    if date_to:
        q = q.filter(SellerOrder.created_at <= datetime.combine(date_to, time.max, tzinfo=timezone.utc))
    total = q.count()
    rows = q.order_by(SellerOrder.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return {"total": total, "page": page, "page_size": page_size, "results": [_serialize(x) for x in rows]}


@router.get("/{seller_order_id}", response_model=SellerOrderView)
def get_order(seller_order_id: UUID, db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_read.value))):
    return _serialize(_get(db, _seller(user).id, seller_order_id))


def _transition(db, row, allowed, target, user, notes=None):
    if row.status not in allowed:
        raise HTTPException(409, f"Cannot move seller order from {row.status.value} to {target.value}")
    now = datetime.now(timezone.utc)
    row.status = target
    row.seller_notes = notes or row.seller_notes
    if target == SellerOrderStatus.accepted: row.accepted_at = now
    if target == SellerOrderStatus.processing: row.processing_at = now
    if target == SellerOrderStatus.ready_to_ship: row.ready_to_ship_at = now
    _sync_global(db, row.order, user.id)
    _commit(db)
    return _serialize(_get(db, row.seller_id, row.id))


@router.post("/{seller_order_id}/accept", response_model=SellerOrderView)
def accept(seller_order_id: UUID, data: SellerOrderActionRequest, db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_manage.value))):
    return _transition(db, _get(db, _seller(user).id, seller_order_id, True), {SellerOrderStatus.new}, SellerOrderStatus.accepted, user, data.notes)


@router.post("/{seller_order_id}/start-processing", response_model=SellerOrderView)
def start_processing(seller_order_id: UUID, data: SellerOrderActionRequest, db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_manage.value))):
    return _transition(db, _get(db, _seller(user).id, seller_order_id, True), {SellerOrderStatus.accepted}, SellerOrderStatus.processing, user, data.notes)


@router.post("/{seller_order_id}/ready-to-ship", response_model=SellerOrderView)
def ready_to_ship(seller_order_id: UUID, data: SellerOrderActionRequest, db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_manage.value))):
    row = _get(db, _seller(user).id, seller_order_id, True)
    shipment = _shipment(row)
    if not shipment:
        raise HTTPException(409, "Shipment has not been created")
    if shipment.status == ShipmentStatus.pending:
        shipment.status = ShipmentStatus.ready_for_dispatch
        db.add(ShipmentTrackingEvent(shipment_id=shipment.id, status=ShipmentStatus.ready_for_dispatch, notes=data.notes or "Seller marked order ready for dispatch", created_by_id=user.id))
    return _transition(db, row, {SellerOrderStatus.accepted, SellerOrderStatus.processing}, SellerOrderStatus.ready_to_ship, user, data.notes)


@router.post("/{seller_order_id}/dispatch", response_model=SellerOrderView)
def dispatch(seller_order_id: UUID, data: SellerOrderDispatchRequest, db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_manage.value))):
    row = _get(db, _seller(user).id, seller_order_id, True)
    if row.status != SellerOrderStatus.ready_to_ship:
        raise HTTPException(409, "Seller order must be ready to ship")
    shipment = _shipment(row)
    if not shipment:
        raise HTTPException(409, "Shipment has not been created")
    duplicate = db.query(Shipment.id).filter(Shipment.tracking_number == data.tracking_number, Shipment.id != shipment.id).first()
    if duplicate:
        raise HTTPException(409, "Tracking number is already in use")
    now = datetime.now(timezone.utc)
    shipment.carrier_name = data.carrier_name.strip()
    shipment.tracking_number = data.tracking_number.strip()
    shipment.status = ShipmentStatus.dispatched
    shipment.dispatched_at = now
    db.add(ShipmentTrackingEvent(shipment_id=shipment.id, status=ShipmentStatus.dispatched, location=data.location, notes=data.notes or (f"Tracking URL: {data.tracking_url}" if data.tracking_url else None), created_by_id=user.id))
    row.status = SellerOrderStatus.shipped
    row.shipped_at = now
    row.seller_notes = data.notes or row.seller_notes
    _sync_global(db, row.order, user.id)
    _commit(db)
    return _serialize(_get(db, row.seller_id, row.id))


@router.post("/{seller_order_id}/request-cancellation", response_model=SellerOrderView)
def request_cancellation(seller_order_id: UUID, data: SellerOrderCancellationRequest, db: Session = Depends(get_db), user: User = Depends(require_permission(PermissionCode.seller_orders_manage.value))):
    row = _get(db, _seller(user).id, seller_order_id, True)
    if row.status in {SellerOrderStatus.shipped, SellerOrderStatus.delivered, SellerOrderStatus.cancelled}:
        raise HTTPException(409, "Shipped, delivered or cancelled orders cannot request cancellation")
    row.status = SellerOrderStatus.cancellation_requested
    row.cancellation_reason = data.reason.strip()
    row.cancellation_requested_at = datetime.now(timezone.utc)
    row.seller_notes = data.notes or row.seller_notes
    _commit(db)
    return _serialize(_get(db, row.seller_id, row.id))
