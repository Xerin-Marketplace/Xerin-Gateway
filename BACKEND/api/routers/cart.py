from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from api.deps import get_current_user, get_db
from api.models import Cart, CartItem, Coupon, Inventory, Product, ProductStatus, ProductVariant, Promotion, User
from api.schemas import ApplyCouponRequest, CartItemCreate, CartItemUpdate, CartResponse, PromotionResponse

router = APIRouter(prefix="/cart", tags=["Cart"])


def _get_or_create_cart(db: Session, user_id: UUID, *, lock: bool = False) -> Cart:
    query = db.query(Cart).options(
        selectinload(Cart.items).selectinload(CartItem.product),
        selectinload(Cart.items).selectinload(CartItem.variant),
    ).filter(Cart.user_id == user_id)
    if lock:
        query = query.with_for_update()
    cart = query.first()
    if cart:
        return cart

    cart = Cart(user_id=user_id)
    db.add(cart)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        cart = db.query(Cart).filter(Cart.user_id == user_id).first()
        if cart is None:
            raise
    return cart


def _inventory_query(db: Session, product_id: UUID, variant_id: UUID | None):
    query = db.query(Inventory).filter(Inventory.product_id == product_id)
    return query.filter(
        Inventory.variant_id == variant_id if variant_id is not None else Inventory.variant_id.is_(None)
    )


def _resolve_price(product: Product, variant: ProductVariant | None) -> Decimal:
    if variant is not None:
        if variant.sale_price is not None:
            return Decimal(variant.sale_price)
        if variant.price is not None:
            return Decimal(variant.price)
    if product.sale_price is not None:
        return Decimal(product.sale_price)
    return Decimal(product.price)


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
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order amount is {coupon.minimum_order_amount}",
        )

    if coupon.discount_type == "percentage":
        discount = subtotal * (Decimal(coupon.discount_value) / Decimal("100"))
        if coupon.maximum_discount_amount is not None:
            discount = min(discount, Decimal(coupon.maximum_discount_amount))
    elif coupon.discount_type == "fixed_amount":
        discount = Decimal(coupon.discount_value)
    else:
        raise HTTPException(status_code=500, detail="Coupon configuration is invalid")
    return min(discount, subtotal)


def _active_promotions(query):
    now = datetime.now(timezone.utc)
    return query.filter(
        Promotion.is_active.is_(True),
        (Promotion.starts_at.is_(None) | (Promotion.starts_at <= now)),
        (Promotion.ends_at.is_(None) | (Promotion.ends_at >= now)),
        (Promotion.usage_limit.is_(None) | (Promotion.usage_count < Promotion.usage_limit)),
    )


def _validate_promotion(promotion: Promotion, subtotal: Decimal) -> Decimal:
    if promotion.minimum_order_amount is not None and subtotal < Decimal(promotion.minimum_order_amount):
        raise HTTPException(
            status_code=400,
            detail=f"Minimum order amount is {promotion.minimum_order_amount}",
        )
    if promotion.promotion_type == "percentage":
        discount = subtotal * (Decimal(promotion.discount_value) / Decimal("100"))
    elif promotion.promotion_type == "fixed_amount":
        discount = Decimal(promotion.discount_value)
    elif promotion.promotion_type == "free_shipping":
        discount = Decimal("0.00")
    else:
        discount = Decimal(promotion.discount_value)
    if promotion.maximum_discount_amount is not None:
        discount = min(discount, Decimal(promotion.maximum_discount_amount))
    return min(discount, subtotal)


def _cart_payload(db: Session, cart: Cart) -> dict:
    subtotal = sum((Decimal(item.unit_price) * item.quantity for item in cart.items), Decimal("0.00"))
    coupon_discount = Decimal("0.00")
    promotion_discount = Decimal("0.00")
    promotion_summary = None

    if cart.coupon_code:
        coupon = db.query(Coupon).filter(Coupon.code == cart.coupon_code).first()
        if coupon:
            try:
                coupon_discount = _validate_coupon(coupon, subtotal)
            except HTTPException:
                # An expired/deactivated coupon must not break cart viewing.
                cart.coupon_code = None
                db.flush()
        else:
            cart.coupon_code = None
            db.flush()

    if cart.promotion_code:
        promotion = db.query(Promotion).filter(Promotion.code == cart.promotion_code).first()
        if promotion:
            try:
                promotion_discount = _validate_promotion(promotion, subtotal)
                promotion_summary = {
                    "id": str(promotion.id),
                    "name": promotion.name,
                    "code": promotion.code,
                    "promotion_type": promotion.promotion_type,
                    "discount_value": str(promotion.discount_value),
                }
            except HTTPException:
                cart.promotion_code = None
                db.flush()
        else:
            cart.promotion_code = None
            db.flush()

    discount = coupon_discount + promotion_discount
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "promotion_code": cart.promotion_code,
        "promotion": promotion_summary,
        "items": cart.items,
        "subtotal": subtotal,
        "coupon_discount_amount": coupon_discount,
        "promotion_discount_amount": promotion_discount,
        "discount_amount": discount,
        "total": subtotal - discount,
    }


@router.get("", response_model=CartResponse)
def get_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    cart = _get_or_create_cart(db, current_user.id)
    payload = _cart_payload(db, cart)
    db.commit()
    return payload


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    data: CartItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        product = db.query(Product).filter(Product.id == data.product_id).first()
        if not product or not product.is_active or product.status != ProductStatus.approved:
            raise HTTPException(status_code=404, detail="Product is not available")

        variant = None
        if data.variant_id is not None:
            variant = db.query(ProductVariant).filter(
                ProductVariant.id == data.variant_id,
                ProductVariant.product_id == product.id,
            ).first()
            if not variant or not variant.is_active:
                raise HTTPException(status_code=404, detail="Product variant not found or inactive")

        cart = _get_or_create_cart(db, current_user.id, lock=True)

        inventory = _inventory_query(db, product.id, data.variant_id).with_for_update().first()
        if not inventory:
            raise HTTPException(status_code=409, detail="Inventory is not configured for this item")

        item_query = db.query(CartItem).filter(
            CartItem.cart_id == cart.id,
            CartItem.product_id == product.id,
        )
        item_query = item_query.filter(
            CartItem.variant_id == data.variant_id
            if data.variant_id is not None
            else CartItem.variant_id.is_(None)
        )
        existing = item_query.with_for_update().first()
        requested_quantity = data.quantity + (existing.quantity if existing else 0)
        if requested_quantity > inventory.available_quantity:
            raise HTTPException(status_code=409, detail="Insufficient stock")

        unit_price = _resolve_price(product, variant)
        if existing:
            existing.quantity = requested_quantity
            existing.unit_price = unit_price
        else:
            db.add(CartItem(
                cart_id=cart.id,
                product_id=product.id,
                variant_id=data.variant_id,
                quantity=data.quantity,
                unit_price=unit_price,
            ))
        db.flush()
        db.expire(cart, ["items"])
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="This item is already in the cart") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update cart") from exc


@router.put("/items/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: UUID,
    data: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).with_for_update().first()
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found")
        inventory = _inventory_query(db, item.product_id, item.variant_id).with_for_update().first()
        if not inventory or data.quantity > inventory.available_quantity:
            raise HTTPException(status_code=409, detail="Insufficient stock")
        item.quantity = data.quantity
        item.unit_price = _resolve_price(item.product, item.variant)
        db.flush()
        db.expire(cart, ["items"])
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update cart") from exc


@router.delete("/items/{item_id}", response_model=CartResponse)
def remove_cart_item(item_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        item = db.query(CartItem).filter(CartItem.id == item_id, CartItem.cart_id == cart.id).first()
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found")
        db.delete(item)
        db.flush()
        db.expire(cart, ["items"])
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not remove cart item") from exc


@router.delete("", response_model=CartResponse)
def clear_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        for item in list(cart.items):
            db.delete(item)
        cart.coupon_code = None
        db.flush()
        db.expire(cart, ["items"])
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not clear cart") from exc


@router.post("/apply-coupon", response_model=CartResponse)
def apply_coupon(
    data: ApplyCouponRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        if not cart.items:
            raise HTTPException(status_code=400, detail="Cannot apply a coupon to an empty cart")
        coupon = db.query(Coupon).filter(Coupon.code == data.code).with_for_update().first()
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")
        subtotal = sum((Decimal(item.unit_price) * item.quantity for item in cart.items), Decimal("0.00"))
        _validate_coupon(coupon, subtotal)
        cart.coupon_code = coupon.code
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not apply coupon") from exc


@router.delete("/coupon", response_model=CartResponse)
def remove_coupon(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        cart.coupon_code = None
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not remove coupon") from exc


@router.get("/promotions/available", response_model=list[PromotionResponse])
def available_cart_promotions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Promotions the customer can apply to their cart right now."""
    return (
        _active_promotions(db.query(Promotion))
        .filter(Promotion.code.isnot(None))
        .order_by(Promotion.created_at.desc())
        .all()
    )


@router.post("/apply-promotion", response_model=CartResponse)
def apply_promotion_to_cart(
    data: ApplyCouponRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        if not cart.items:
            raise HTTPException(status_code=400, detail="Cannot apply a promotion to an empty cart")
        promotion = (
            db.query(Promotion)
            .filter(Promotion.code == data.code)
            .with_for_update()
            .first()
        )
        if not promotion:
            raise HTTPException(status_code=404, detail="Promotion not found")
        # Reuse the active-window validation so expired/future promos fail cleanly.
        is_active = _active_promotions(
            db.query(Promotion).filter(Promotion.id == promotion.id)
        ).first()
        if not is_active:
            raise HTTPException(status_code=400, detail="Promotion is not currently active")
        subtotal = sum((Decimal(item.unit_price) * item.quantity for item in cart.items), Decimal("0.00"))
        _validate_promotion(promotion, subtotal)
        cart.promotion_code = promotion.code
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not apply promotion") from exc


@router.delete("/promotion", response_model=CartResponse)
def remove_promotion(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        cart.promotion_code = None
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not remove promotion") from exc


@router.post("/validate", response_model=CartResponse)
def validate_cart(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Re-resolve prices, drop items whose product is gone/inactive, and
    clear stale coupon/promotion codes (handled inside _cart_payload)."""
    try:
        cart = _get_or_create_cart(db, current_user.id, lock=True)
        for item in list(cart.items):
            product = item.product
            if (
                product is None
                or not product.is_active
                or product.status != ProductStatus.approved
                or item.quantity <= 0
            ):
                db.delete(item)
                continue
            resolved = _resolve_price(product, item.variant)
            if resolved != Decimal(item.unit_price):
                item.unit_price = resolved
        db.flush()
        payload = _cart_payload(db, cart)
        db.commit()
        return payload
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not validate cart") from exc
