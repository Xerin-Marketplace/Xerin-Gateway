from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.models import (
    User,
    Cart,
    CartItem,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    Inventory,
    Address,
    Coupon,
    Payment,
    PaymentStatus,
)
from api.schemas import (
    OrderCreateRequest,
    OrderResponse,
    OrderStatusUpdateRequest,
    PaginatedOrderResponse,
)
from api.permissions import require_permission

router = APIRouter(prefix="/orders", tags=["Orders"])


def _calculate_order_totals(cart: Cart) -> dict:
    subtotal = Decimal("0.00")
    for item in cart.items:
        subtotal += Decimal(item.unit_price) * item.quantity

    discount_amount = Decimal("0.00")
    if cart.coupon_code:
        coupon = cart.coupon_code  # placeholder; resolved in create_order

    shipping_amount = Decimal("0.00")
    tax_amount = Decimal("0.00")
    total = subtotal - discount_amount + shipping_amount + tax_amount

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "shipping_amount": shipping_amount,
        "tax_amount": tax_amount,
        "total": total,
    }


def _apply_coupon_to_subtotal(coupon: Coupon | None, subtotal: Decimal) -> Decimal:
    if not coupon:
        return Decimal("0.00")

    now = datetime.now(timezone.utc)
    if coupon.valid_from and now < coupon.valid_from:
        return Decimal("0.00")
    if coupon.valid_until and now > coupon.valid_until:
        return Decimal("0.00")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        return Decimal("0.00")
    if coupon.minimum_order_amount and subtotal < coupon.minimum_order_amount:
        return Decimal("0.00")

    if coupon.discount_type == "percentage":
        discount = subtotal * (coupon.discount_value / Decimal("100"))
        if coupon.maximum_discount_amount:
            discount = min(discount, coupon.maximum_discount_amount)
    else:
        discount = coupon.discount_value

    return min(discount, subtotal)


def _reserve_inventory(db: Session, cart: Cart) -> None:
    for item in cart.items:
        inventory = db.query(Inventory).filter(
            Inventory.product_id == item.product_id,
            Inventory.variant_id == item.variant_id,
        ).with_for_update().first()

        if not inventory or inventory.available_quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Insufficient stock for product {item.product_id}",
            )

        inventory.reserved_quantity += item.quantity
        inventory.available_quantity = inventory.quantity - inventory.reserved_quantity


def _release_inventory(db: Session, order: Order) -> None:
    for item in order.items:
        inventory = db.query(Inventory).filter(
            Inventory.product_id == item.product_id,
            Inventory.variant_id == item.variant_id,
        ).with_for_update().first()

        if inventory:
            inventory.reserved_quantity = max(0, inventory.reserved_quantity - item.quantity)
            inventory.available_quantity = inventory.quantity - inventory.reserved_quantity


def _deduct_inventory(db: Session, order: Order) -> None:
    for item in order.items:
        inventory = db.query(Inventory).filter(
            Inventory.product_id == item.product_id,
            Inventory.variant_id == item.variant_id,
        ).with_for_update().first()

        if inventory:
            inventory.quantity = max(0, inventory.quantity - item.quantity)
            inventory.reserved_quantity = max(0, inventory.reserved_quantity - item.quantity)
            inventory.available_quantity = inventory.quantity - inventory.reserved_quantity


def _create_status_history(db: Session, order: Order, status_value: str, notes: str | None, user_id: UUID | None) -> None:
    history = OrderStatusHistory(
        order_id=order.id,
        status=status_value,
        notes=notes,
        created_by_id=user_id,
    )
    db.add(history)


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = db.query(Cart).filter(Cart.user_id == current_user.id).first()
    if not cart or not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    if data.shipping_address_id:
        address = db.query(Address).filter(
            Address.id == data.shipping_address_id,
            Address.user_id == current_user.id,
        ).first()
        if not address:
            raise HTTPException(status_code=404, detail="Shipping address not found")

    # Validate stock and reserve inventory
    _reserve_inventory(db, cart)

    # Calculate totals
    subtotal = Decimal("0.00")
    for item in cart.items:
        subtotal += Decimal(item.unit_price) * item.quantity

    coupon = None
    if data.coupon_code or cart.coupon_code:
        code = data.coupon_code or cart.coupon_code
        coupon = db.query(Coupon).filter(
            Coupon.code == code,
            Coupon.is_active == True,
        ).first()

    discount_amount = _apply_coupon_to_subtotal(coupon, subtotal)
    shipping_amount = Decimal("0.00")
    tax_amount = Decimal("0.00")
    total = subtotal - discount_amount + shipping_amount + tax_amount

    order = Order(
        user_id=current_user.id,
        shipping_address_id=data.shipping_address_id,
        status=OrderStatus.pending,
        currency="TZS",
        subtotal=subtotal,
        discount_amount=discount_amount,
        shipping_amount=shipping_amount,
        tax_amount=tax_amount,
        total=total,
        coupon_code=coupon.code if coupon else None,
        notes=data.notes,
    )
    db.add(order)
    db.flush()

    for item in cart.items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            seller_id=item.product.seller_id,
            product_name=item.product.name,
            variant_name=item.variant.variant_name if item.variant else None,
            quantity=item.quantity,
            unit_price=item.unit_price,
            total_price=Decimal(item.unit_price) * item.quantity,
        )
        db.add(order_item)

    _create_status_history(db, order, OrderStatus.pending.value, "Order created", current_user.id)

    # Clear cart
    for item in cart.items:
        db.delete(item)
    cart.coupon_code = None

    if coupon:
        coupon.usage_count += 1

    db.commit()
    db.refresh(order)
    return order


@router.get("/my-orders", response_model=PaginatedOrderResponse)
def get_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": orders,
    }


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    data: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    # Only seller of any item, admin, or support can update status
    is_seller = any(item.seller_id == current_user.seller_profile.id for item in order.items if current_user.seller_profile)
    if not is_seller and current_user.id != order.user_id:
        # For buyers, only allow cancellation of pending orders
        if data.status != OrderStatus.cancelled.value or order.status != OrderStatus.pending:
            raise HTTPException(status_code=403, detail="Not authorized to update this order")

    try:
        new_status = OrderStatus(data.status)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid order status")

    # State machine guards
    if order.status == OrderStatus.delivered and new_status in (OrderStatus.cancelled,):
        raise HTTPException(status_code=400, detail="Cannot cancel a delivered order")

    if order.status == OrderStatus.cancelled:
        raise HTTPException(status_code=400, detail="Order is already cancelled")

    order.status = new_status

    if new_status == OrderStatus.cancelled:
        _release_inventory(db, order)

    if new_status == OrderStatus.paid:
        _deduct_inventory(db, order)

    _create_status_history(db, order, new_status.value, data.notes, current_user.id)

    db.commit()
    db.refresh(order)
    return order


@router.get("/admin/all", response_model=PaginatedOrderResponse)
def list_all_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("orders:read")),
):
    query = db.query(Order)
    if status:
        query = query.filter(Order.status == status)
    query = query.order_by(Order.created_at.desc())
    total = query.count()
    orders = query.offset((page - 1) * page_size).limit(page_size).all()

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "results": orders,
    }
