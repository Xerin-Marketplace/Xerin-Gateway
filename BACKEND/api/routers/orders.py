from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.deps import get_current_user, get_db
from api.models import (
    Address,
    BrokerCommission,
    BrokerOffer,
    BrokerOfferAcceptance,
    BrokerWallet,
    BrokerWalletTransaction,
    Cart,
    CartItem,
    Coupon,
    Inventory,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentStatus,
    ProductStatus,
    Promotion,
    PromotionUsage,
    Shipment,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
    User,
)
from api.permissions import get_user_permissions, get_user_role_names, require_permission
from api.schemas import OrderCreateRequest, OrderResponse, OrderStatusUpdateRequest, PaginatedOrderResponse
from api.enums import InventoryReservationStatus, NotificationChannel, NotificationEvent
from api.services.inventory_reservations import create_reservation, release_order_reservations
from api.services.notification_service import notification_service

router = APIRouter(prefix="/orders", tags=["Orders"])

# `refunded` is intentionally absent: it is terminal state owned exclusively by
# the refund engine (Refund record + wallet debit + commission reversal + restock).
ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.pending: {OrderStatus.cancelled},
    OrderStatus.paid: {OrderStatus.processing},
    OrderStatus.processing: {OrderStatus.received_at_hub, OrderStatus.shipped, OrderStatus.cancelled},
    OrderStatus.received_at_hub: {OrderStatus.shipped, OrderStatus.cancelled},
    OrderStatus.shipped: {OrderStatus.delivered},
    OrderStatus.delivered: set(),
    OrderStatus.cancelled: set(),
    OrderStatus.refunded: set(),
}



def _normalise_place(value: str | None) -> str:
    return (value or "").strip().lower()


def _calculate_shipping(db: Session, address: Address, rate_id: UUID, subtotal: Decimal, weight_kg: Decimal):
    rate = db.query(ShippingRate).options(selectinload(ShippingRate.zone), selectinload(ShippingRate.method)).filter(
        ShippingRate.id == rate_id,
        ShippingRate.is_active.is_(True),
    ).with_for_update().first()
    if not rate or not rate.zone or not rate.method or not rate.zone.is_active or not rate.method.is_active:
        raise HTTPException(status_code=409, detail="Selected shipping rate is unavailable")
    zone = rate.zone
    if _normalise_place(zone.country) != _normalise_place(address.country):
        raise HTTPException(status_code=422, detail="Shipping rate does not serve this country")
    regions = {_normalise_place(x) for x in (zone.regions or [])}
    cities = {_normalise_place(x) for x in (zone.cities or [])}
    if regions and _normalise_place(address.region) not in regions:
        raise HTTPException(status_code=422, detail="Shipping rate does not serve this region")
    if cities and _normalise_place(address.city) not in cities:
        raise HTTPException(status_code=422, detail="Shipping rate does not serve this city")
    if rate.min_weight_kg is not None and weight_kg < Decimal(rate.min_weight_kg):
        raise HTTPException(status_code=422, detail="Shipment weight is below the selected rate minimum")
    if rate.max_weight_kg is not None and weight_kg > Decimal(rate.max_weight_kg):
        raise HTTPException(status_code=422, detail="Shipment weight exceeds the selected rate maximum")
    if rate.free_shipping_threshold is not None and subtotal >= Decimal(rate.free_shipping_threshold):
        amount = Decimal("0")
    elif rate.rate_type.value == "free":
        amount = Decimal("0")
    elif rate.rate_type.value == "weight_based":
        amount = Decimal(rate.base_amount) + Decimal(rate.amount_per_kg) * weight_kg
    else:
        amount = Decimal(rate.base_amount)
    now = datetime.now(timezone.utc)
    return rate, amount.quantize(Decimal("0.01")), now + timedelta(days=rate.method.min_delivery_days), now + timedelta(days=rate.method.max_delivery_days)

def _inventory_query(db: Session, product_id: UUID, variant_id: UUID | None):
    query = db.query(Inventory).filter(Inventory.product_id == product_id)
    return query.filter(
        Inventory.variant_id == variant_id if variant_id is not None else Inventory.variant_id.is_(None)
    )


def _create_status_history(
    db: Session,
    order: Order,
    status_value: OrderStatus,
    notes: str | None,
    user_id: UUID | None,
) -> None:
    db.add(OrderStatusHistory(
        order_id=order.id,
        status=status_value.value,
        notes=notes,
        created_by_id=user_id,
    ))


def _validate_coupon(coupon: Coupon, subtotal: Decimal) -> Decimal:
    now = datetime.now(timezone.utc)
    if not coupon.is_active:
        raise HTTPException(status_code=400, detail="Coupon is inactive")
    if coupon.valid_from and now < coupon.valid_from:
        raise HTTPException(status_code=400, detail="Coupon is not valid yet")
    if coupon.valid_until and now > coupon.valid_until:
        raise HTTPException(status_code=400, detail="Coupon has expired")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise HTTPException(status_code=400, detail="Coupon usage limit has been reached")
    if coupon.minimum_order_amount is not None and subtotal < Decimal(coupon.minimum_order_amount):
        raise HTTPException(status_code=400, detail=f"Minimum order amount is {coupon.minimum_order_amount}")

    if coupon.discount_type == "percentage":
        discount = subtotal * (Decimal(coupon.discount_value) / Decimal("100"))
        if coupon.maximum_discount_amount is not None:
            discount = min(discount, Decimal(coupon.maximum_discount_amount))
    elif coupon.discount_type == "fixed_amount":
        discount = Decimal(coupon.discount_value)
    else:
        raise HTTPException(status_code=500, detail="Coupon configuration is invalid")
    return min(discount, subtotal)


def _validate_promotion(db: Session, promotion: Promotion, subtotal: Decimal, user_id: UUID) -> Decimal:
    """Validate a promotion for an order and return its discount.

    Mirrors the cart preview rules plus the per-customer and global usage
    limits that only the server can enforce.
    """
    now = datetime.now(timezone.utc)
    if not promotion.is_active:
        raise HTTPException(status_code=400, detail="Promotion is not available")
    if promotion.starts_at and now < promotion.starts_at:
        raise HTTPException(status_code=400, detail="Promotion has not started yet")
    if promotion.ends_at and now > promotion.ends_at:
        raise HTTPException(status_code=400, detail="Promotion has ended")
    if promotion.usage_limit is not None and promotion.usage_count >= promotion.usage_limit:
        raise HTTPException(status_code=400, detail="Promotion usage limit has been reached")
    if promotion.usage_per_customer is not None:
        used = (
            db.query(PromotionUsage)
            .filter(
                PromotionUsage.promotion_id == promotion.id,
                PromotionUsage.user_id == user_id,
            )
            .count()
        )
        if used >= promotion.usage_per_customer:
            raise HTTPException(status_code=400, detail="You have already used this promotion")
    if promotion.minimum_order_amount is not None and subtotal < Decimal(promotion.minimum_order_amount):
        raise HTTPException(status_code=400, detail=f"Minimum order amount is {promotion.minimum_order_amount}")

    if promotion.promotion_type == "percentage":
        discount = subtotal * (Decimal(promotion.discount_value) / Decimal("100"))
    elif promotion.promotion_type == "free_shipping":
        discount = Decimal("0.00")
    else:
        discount = Decimal(promotion.discount_value)
    if promotion.maximum_discount_amount is not None:
        discount = min(discount, Decimal(promotion.maximum_discount_amount))
    return max(Decimal("0"), min(discount, subtotal))


def _generate_order_number(db: Session, order: Order) -> str:
    """Generate a commercial order reference: XM-YYMMDD-NNNNN.

    Uses a dedicated Postgres sequence — count-based generation races under
    concurrency and collides on the unique constraint.
    """
    created = order.created_at or datetime.now(timezone.utc)
    yy = str(created.year)[2:]
    mm = str(created.month).zfill(2)
    dd = str(created.day).zfill(2)
    db.execute(text("CREATE SEQUENCE IF NOT EXISTS order_number_seq"))
    seq_val = db.execute(text("SELECT nextval('order_number_seq')")).scalar()
    return f"XM-{yy}{mm}{dd}-{seq_val:05d}"


def _release_reserved_inventory(db: Session, order: Order) -> None:
    release_order_reservations(db, order, target_status=InventoryReservationStatus.cancelled)


def _is_privileged_order_operator(db: Session, user: User) -> bool:
    roles = get_user_role_names(user)
    if "super_admin" in roles:
        return True
    permissions = get_user_permissions(db, user)
    return "orders:write" in permissions or "can_update_orders" in permissions


def _is_order_seller(user: User, order: Order) -> bool:
    seller = user.seller_profile
    return bool(seller and any(item.seller_id == seller.id for item in order.items))


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = db.query(Cart).options(
            selectinload(Cart.items).selectinload(CartItem.product),
            selectinload(Cart.items).selectinload(CartItem.variant),
        ).filter(Cart.user_id == current_user.id).with_for_update().first()
        if not cart or not cart.items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        address = db.query(Address).filter(
            Address.id == data.shipping_address_id,
            Address.user_id == current_user.id,
        ).first()
        if not address:
            raise HTTPException(status_code=404, detail="Shipping address not found")

        subtotal = Decimal("0.00")
        prepared_items: list[dict] = []
        total_weight_kg = Decimal("0.000")
        for cart_item in cart.items:
            product = cart_item.product
            if not product or not product.is_active or product.status != ProductStatus.approved:
                raise HTTPException(status_code=409, detail=f"Product {cart_item.product_id} is no longer available")
            if cart_item.variant_id is not None and (
                cart_item.variant is None or cart_item.variant.product_id != product.id or not cart_item.variant.is_active
            ):
                raise HTTPException(status_code=409, detail=f"Variant for product {product.id} is invalid")

            inventory = _inventory_query(db, product.id, cart_item.variant_id).with_for_update().first()
            if not inventory or inventory.available_quantity < cart_item.quantity:
                raise HTTPException(status_code=409, detail=f"Insufficient stock for {product.name}")

            current_price = (
                Decimal(cart_item.variant.sale_price) if cart_item.variant is not None and cart_item.variant.sale_price is not None
                else Decimal(cart_item.variant.price) if cart_item.variant is not None and cart_item.variant.price is not None
                else Decimal(product.sale_price if product.sale_price is not None else product.price)
            )
            line_total = current_price * cart_item.quantity
            subtotal += line_total
            item_weight = cart_item.variant.weight if cart_item.variant is not None and cart_item.variant.weight is not None else product.weight
            total_weight_kg += Decimal(item_weight or 0) * cart_item.quantity
            prepared_items.append({
                "cart_item": cart_item,
                "inventory": inventory,
                "unit_price": current_price,
                "line_total": line_total,
            })

        coupon = None
        requested_code = data.coupon_code or cart.coupon_code
        discount_amount = Decimal("0.00")
        if requested_code:
            coupon = db.query(Coupon).filter(Coupon.code == requested_code).with_for_update().first()
            if not coupon:
                raise HTTPException(status_code=404, detail="Coupon not found")
            discount_amount = _validate_coupon(coupon, subtotal)

        promotion = None
        promotion_discount = Decimal("0.00")
        requested_promotion = data.promotion_code or cart.promotion_code
        if requested_promotion:
            promotion = (
                db.query(Promotion)
                .filter(Promotion.code == requested_promotion)
                .with_for_update()
                .first()
            )
            if not promotion:
                raise HTTPException(status_code=404, detail="Promotion not found")
            promotion_discount = _validate_promotion(db, promotion, subtotal, current_user.id)

        discount_amount = min(discount_amount + promotion_discount, subtotal)

        shipping_rate, shipping_amount, delivery_from, delivery_to = _calculate_shipping(db, address, data.shipping_rate_id, subtotal, total_weight_kg)
        tax_amount = Decimal("0.00")
        total = subtotal - discount_amount + shipping_amount + tax_amount

        order = Order(
            user_id=current_user.id,
            shipping_address_id=data.shipping_address_id,
            shipping_rate_id=shipping_rate.id,
            shipping_method_id=shipping_rate.method.id,
            shipping_method_name=shipping_rate.method.name,
            shipping_carrier=shipping_rate.method.carrier_name,
            estimated_delivery_from=delivery_from,
            estimated_delivery_to=delivery_to,
            status=OrderStatus.pending,
            currency="TZS",
            subtotal=subtotal,
            discount_amount=discount_amount,
            shipping_amount=shipping_amount,
            tax_amount=tax_amount,
            total=total,
            coupon_code=coupon.code if coupon else None,
            promotion_code=promotion.code if promotion else None,
            notes=data.notes,
        )
        db.add(order)
        db.flush()

        if promotion is not None:
            promotion.usage_count = (promotion.usage_count or 0) + 1
            db.add(PromotionUsage(
                promotion_id=promotion.id,
                user_id=current_user.id,
                order_id=order.id,
                discount_amount=promotion_discount,
            ))

        reservation_expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.INVENTORY_RESERVATION_MINUTES)
        for prepared in prepared_items:
            cart_item = prepared["cart_item"]
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                variant_id=cart_item.variant_id,
                seller_id=cart_item.product.seller_id,
                product_name=cart_item.product.name,
                variant_name=cart_item.variant.variant_name if cart_item.variant else None,
                quantity=cart_item.quantity,
                unit_price=prepared["unit_price"],
                total_price=prepared["line_total"],
            )
            db.add(order_item)
            db.flush()
            create_reservation(
                db, inventory=prepared["inventory"], order=order, order_item_id=order_item.id,
                user_id=current_user.id, quantity=cart_item.quantity, expires_at=reservation_expires_at,
            )

        order.order_number = _generate_order_number(db, order)

        # Broker referral attribution — commissions for items promoted via a
        # referral code stay pending until the order is delivered.
        if data.referral_code:
            acceptance = (
                db.query(BrokerOfferAcceptance)
                .filter(
                    BrokerOfferAcceptance.referral_code == data.referral_code,
                    BrokerOfferAcceptance.is_active.is_(True),
                )
                .first()
            )
            if acceptance:
                offer = db.query(BrokerOffer).filter(BrokerOffer.id == acceptance.offer_id).first()
                if offer and offer.is_active and (
                    offer.max_attributed_sales is None
                    or offer.attributed_sales_count < offer.max_attributed_sales
                ):
                    now = datetime.now(timezone.utc)
                    if (offer.starts_at is None or offer.starts_at <= now) and (
                        offer.ends_at is None or offer.ends_at > now
                    ):
                        wallet = db.query(BrokerWallet).filter(BrokerWallet.broker_id == acceptance.broker_id).first()
                        if wallet is None:
                            wallet = BrokerWallet(broker_id=acceptance.broker_id, currency=order.currency or "TZS")
                            db.add(wallet)
                            db.flush()
                        matched = False
                        order_items = db.query(OrderItem).filter(OrderItem.order_id == order.id).all()
                        for item in order_items:
                            if item.product_id != offer.product_id:
                                continue
                            unit_reward = (
                                (Decimal(item.unit_price) * Decimal(offer.commission_value) / Decimal("100"))
                                if offer.commission_type == "percentage"
                                else Decimal(offer.commission_value)
                            )
                            amount = (unit_reward * Decimal(item.quantity)).quantize(Decimal("0.01"))
                            if amount <= 0:
                                continue
                            commission = BrokerCommission(
                                broker_id=acceptance.broker_id,
                                order_id=order.id,
                                order_item_id=item.id,
                                broker_offer_id=offer.id,
                                broker_attribution_id=acceptance.id,
                                currency=order.currency or "TZS",
                                amount=amount,
                                net_amount=amount,
                                status="pending",
                                reference=f"BRC-{order.order_number}-{item.id}",
                            )
                            db.add(commission)
                            db.flush()
                            wallet.pending_balance = Decimal(wallet.pending_balance) + amount
                            db.add(BrokerWalletTransaction(
                                wallet_id=wallet.id,
                                broker_id=acceptance.broker_id,
                                commission_id=commission.id,
                                transaction_type="commission_pending",
                                amount=amount,
                                currency=commission.currency,
                                reference=commission.reference,
                                description=f"Pending commission for order {order.order_number}",
                            ))
                            matched = True
                        if matched:
                            offer.attributed_sales_count += 1

        _create_status_history(db, order, OrderStatus.pending, "Order created", current_user.id)
        if coupon:
            coupon.usage_count += 1
        for cart_item in list(cart.items):
            db.delete(cart_item)
        cart.coupon_code = None
        cart.promotion_code = None

        if settings.MONITORING_ENABLED:
            try:
                from api.services.monitoring import record_business_event
                from api.enums import AuditSeverity
                record_business_event(
                    db, action="order.created",
                    description="Order created",
                    severity=AuditSeverity.info,
                    actor_user_id=current_user.id,
                    resource_type="order", resource_id=str(order.id),
                    event_metadata={"total": str(order.total_amount)},
                )
            except Exception:
                pass

        db.commit()
        db.refresh(order)

        # Send order_placed notification to customer + admin
        try:
            notification_service.notify(
                db=db, user_id=current_user.id, event=NotificationEvent.order_placed,
                title="Order Confirmed",
                message=f"Your order {order.order_number} has been placed successfully. Total: {order.total} {order.currency}.",
                data={"order_number": order.order_number, "total": str(order.total), "currency": order.currency},
                action_url=f"/orders/{order.id}",
                channels=[NotificationChannel.in_app, NotificationChannel.sms, NotificationChannel.email],
                commit=False, dispatch=True,
            )
            notification_service.notify_admins(
                db=db, event=NotificationEvent.admin_order_alert,
                title="New Order Placed",
                message=f"Order {order.order_number} placed by {current_user.first_name} {current_user.last_name}. Total: {order.total} {order.currency}.",
                data={"order_number": order.order_number, "total": str(order.total), "currency": order.currency},
                channels=[NotificationChannel.in_app, NotificationChannel.email],
            )
        except Exception:
            pass

        return order
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not create order")


@router.get("/my-orders", response_model=PaginatedOrderResponse)
def get_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Order).options(
        selectinload(Order.seller_orders),
        selectinload(Order.shipments),
    ).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    return {
        "total": query.count(),
        "page": page,
        "page_size": page_size,
        "results": query.offset((page - 1) * page_size).limit(page_size).all(),
    }


@router.get("/admin/all", response_model=PaginatedOrderResponse)
def list_all_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_status: OrderStatus | None = Query(None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("orders:read")),
):
    query = db.query(Order).options(
        selectinload(Order.seller_orders),
        selectinload(Order.shipments),
    )
    if order_status is not None:
        query = query.filter(Order.status == order_status)
    query = query.order_by(Order.created_at.desc())
    return {
        "total": query.count(),
        "page": page,
        "page_size": page_size,
        "results": query.offset((page - 1) * page_size).limit(page_size).all(),
    }


@router.get("/ref/{order_number}", response_model=OrderResponse)
def get_order_by_ref(
    order_number: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(
            selectinload(Order.shipments).selectinload(Shipment.tracking_events),
            selectinload(Order.shipments).selectinload(Shipment.items),
            selectinload(Order.seller_orders),
        )
        .filter(Order.order_number == order_number.upper())
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_order_seller(current_user, order) and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return order


@router.get("/{order_id}/customer-detail")
def get_customer_order_detail(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Buyer-facing order detail: payments, shipping address, shipments and
    per-seller slices — everything the customer order page needs."""
    order = (
        db.query(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.payments),
            selectinload(Order.shipping_address),
            selectinload(Order.shipments).selectinload(Shipment.tracking_events),
            selectinload(Order.shipments).selectinload(Shipment.items),
            selectinload(Order.seller_orders),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_order_seller(current_user, order) and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")

    base = OrderResponse.model_validate(order).model_dump(mode="json")

    payments = sorted(order.payments, key=lambda p: str(p.created_at or ""))
    latest_payment = payments[-1] if payments else None

    address = order.shipping_address
    shipping_address = None
    if address:
        shipping_address = {
            "label": address.label,
            "recipient_name": address.recipient_name,
            "recipient_phone": address.recipient_phone,
            "country": address.country,
            "region": address.region,
            "district": address.district,
            "ward": address.ward,
            "city": address.city,
            "street": address.street,
            "landmark": address.landmark,
            "postal_code": address.postal_code,
        }

    seller_order_rows = []
    for so in sorted(order.seller_orders, key=lambda x: str(x.created_at or "")):
        seller_order_rows.append({
            "id": str(so.id),
            "seller_id": str(so.seller_id),
            "store_id": "",
            "status": so.status.value if so.status else "new",
            "seller_subtotal": float(so.seller_subtotal or 0),
            "item_count": int(so.item_count or 0),
            "accepted_at": so.accepted_at.isoformat() if so.accepted_at else None,
            "processing_at": so.processing_at.isoformat() if so.processing_at else None,
            "ready_to_ship_at": so.ready_to_ship_at.isoformat() if so.ready_to_ship_at else None,
            "shipped_at": so.shipped_at.isoformat() if so.shipped_at else None,
            "delivered_at": so.delivered_at.isoformat() if so.delivered_at else None,
            "created_at": so.created_at.isoformat() if so.created_at else None,
        })

    return {
        **base,
        "payment_status": latest_payment.status.value if latest_payment and latest_payment.status else None,
        "payments": [
            {
                "id": str(p.id),
                "amount": float(p.amount or 0),
                "currency": p.currency,
                "method": p.method.value if p.method else None,
                "provider": p.provider,
                "status": p.status.value if p.status else None,
                "provider_transaction_id": p.provider_transaction_id,
                "paid_at": p.paid_at.isoformat() if p.paid_at else None,
                "finalized_at": (
                    lambda dt: dt.isoformat() if dt else None
                )(getattr(p, "finalized_at", None) or getattr(p, "updated_at", None)),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in payments
        ],
        "shipping_address": shipping_address,
        "seller_orders": seller_order_rows,
    }


@router.get("/{order_id}/escrow")
def get_order_escrow(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Escrow is not enabled yet — return an honest not_applicable summary so
    the order page can render without a protection state."""
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_order_seller(current_user, order) and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return {
        "order_id": str(order.id),
        "currency": order.currency or "TZS",
        "status": "not_applicable",
        "hold_count": 0,
        "gross_amount": 0,
        "seller_amount": 0,
        "commission_amount": 0,
        "released_amount": 0,
        "remaining_amount": 0,
        "release_after": None,
        "delivery_verified_at": None,
        "seller_release_grace_hours": None,
        "allow_customer_early_acceptance": False,
        "can_customer_approve": False,
        "can_report_problem": False,
        "items": [],
    }


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(
            selectinload(Order.shipments).selectinload(Shipment.tracking_events),
            selectinload(Order.shipments).selectinload(Shipment.items),
            selectinload(Order.seller_orders),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_order_seller(current_user, order) and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return order


def _load_order_for_documents(db: Session, order_id: UUID, current_user: User) -> Order:
    order = (
        db.query(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.payments),
            selectinload(Order.shipping_address),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_order_seller(current_user, order) and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return order


@router.get("/{order_id}/invoice.pdf")
def get_order_invoice(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi.responses import Response
    from api.services.order_documents import build_invoice_pdf

    order = _load_order_for_documents(db, order_id, current_user)
    pdf = build_invoice_pdf(order)
    name = f"invoice-{order.order_number or str(order.id)[:8].upper()}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})


@router.get("/{order_id}/receipt.pdf")
def get_order_receipt(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from fastapi.responses import Response
    from api.services.order_documents import build_receipt_pdf

    order = _load_order_for_documents(db, order_id, current_user)
    paid = next((p for p in order.payments if p.status == PaymentStatus.completed), None)
    if not paid:
        raise HTTPException(status_code=409, detail="Receipt is available after a successful payment")
    pdf = build_receipt_pdf(order, paid)
    name = f"receipt-{order.order_number or str(order.id)[:8].upper()}.pdf"
    return Response(content=pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{name}"'})


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: UUID,
    data: OrderStatusUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")

        new_status = data.status
        is_buyer = order.user_id == current_user.id
        is_operator = _is_privileged_order_operator(db, current_user)

        if is_buyer:
            if new_status != OrderStatus.cancelled or order.status != OrderStatus.pending:
                raise HTTPException(status_code=403, detail="Buyers may only cancel pending orders")
        elif not is_operator:
            # Sellers manage their slice through /seller-orders, never the whole order.
            raise HTTPException(status_code=403, detail="Not authorized to update this order")

        # Payment callbacks own the pending -> paid transition.
        if new_status == OrderStatus.paid:
            raise HTTPException(status_code=409, detail="Paid status can only be set by a verified payment callback")
        if new_status not in ALLOWED_TRANSITIONS.get(order.status, set()):
            raise HTTPException(
                status_code=409,
                detail=f"Invalid order transition: {order.status.value} -> {new_status.value}",
            )
        if new_status in {OrderStatus.cancelled, OrderStatus.refunded}:
            completed_payment = db.query(Payment.id).filter(
                Payment.order_id == order.id,
                Payment.status == PaymentStatus.completed,
            ).first()
            if new_status == OrderStatus.cancelled and completed_payment:
                raise HTTPException(status_code=409, detail="A paid order must be refunded, not cancelled")
            if order.status in {OrderStatus.pending, OrderStatus.processing}:
                _release_reserved_inventory(db, order)

        order.status = new_status

        # Broker commission settlement — pending commissions become available
        # on delivery; cancelled/refunded orders reverse them.
        commissions = db.query(BrokerCommission).filter(BrokerCommission.order_id == order.id).all()
        if commissions and new_status in (OrderStatus.delivered, OrderStatus.cancelled, OrderStatus.refunded):
            wallets: dict[UUID, BrokerWallet] = {}
            now = datetime.now(timezone.utc)
            for commission in commissions:
                if commission.status in ("reversed", "cancelled"):
                    continue
                wallet = wallets.get(commission.broker_id)
                if wallet is None:
                    wallet = db.query(BrokerWallet).filter(BrokerWallet.broker_id == commission.broker_id).first()
                    wallets[commission.broker_id] = wallet
                if wallet is None:
                    continue
                net = Decimal(commission.amount) - Decimal(commission.reversed_amount)
                if new_status == OrderStatus.delivered and commission.status == "pending":
                    commission.status = "available"
                    commission.available_at = now
                    wallet.pending_balance = Decimal(wallet.pending_balance) - net
                    wallet.available_balance = Decimal(wallet.available_balance) + net
                    db.add(BrokerWalletTransaction(
                        wallet_id=wallet.id, broker_id=commission.broker_id,
                        commission_id=commission.id, transaction_type="commission_available",
                        amount=net, currency=commission.currency, reference=commission.reference,
                        description=f"Commission released for order {order.order_number}",
                    ))
                elif new_status in (OrderStatus.cancelled, OrderStatus.refunded):
                    was_pending = commission.status == "pending"
                    commission.status = "reversed" if new_status == OrderStatus.refunded else "cancelled"
                    commission.reversed_amount = Decimal(commission.amount)
                    commission.net_amount = Decimal("0")
                    commission.reversed_at = now
                    if was_pending:
                        wallet.pending_balance = Decimal(wallet.pending_balance) - net
                    else:
                        wallet.available_balance = Decimal(wallet.available_balance) - net
                    wallet.reversed_balance = Decimal(wallet.reversed_balance) + net
                    db.add(BrokerWalletTransaction(
                        wallet_id=wallet.id, broker_id=commission.broker_id,
                        commission_id=commission.id,
                        transaction_type="commission_reversed" if new_status == OrderStatus.refunded else "commission_cancelled",
                        amount=-net, currency=commission.currency, reference=commission.reference,
                        description=f"Commission {commission.status} for order {order.order_number}",
                    ))

        _create_status_history(db, order, new_status, data.notes, current_user.id)
        db.commit()
        db.refresh(order)

        # Send status-based notifications
        try:
            event_map = {
                OrderStatus.paid: (NotificationEvent.payment_confirmed, "Payment Confirmed", f"Payment for order {order.order_number} has been confirmed."),
                OrderStatus.processing: (NotificationEvent.order_accepted, "Order Processing", f"Your order {order.order_number} is now being processed."),
                OrderStatus.shipped: (NotificationEvent.order_dispatched, "Order Dispatched", f"Your order {order.order_number} has been dispatched."),
                OrderStatus.delivered: (NotificationEvent.order_delivered, "Order Delivered", f"Your order {order.order_number} has been delivered. Thank you for shopping with Xerin!"),
                OrderStatus.cancelled: (NotificationEvent.cancellation_requested, "Order Cancelled", f"Your order {order.order_number} has been cancelled."),
            }
            if new_status in event_map:
                ev, title, msg = event_map[new_status]
                notification_service.notify(
                    db=db, user_id=order.user_id, event=ev, title=title, message=msg,
                    data={"order_number": order.order_number, "status": new_status.value},
                    action_url=f"/orders/{order.id}",
                    channels=[NotificationChannel.in_app, NotificationChannel.sms, NotificationChannel.email],
                    commit=False, dispatch=True,
                )
                db.commit()
        except Exception:
            pass

        return order
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update order status") from exc
