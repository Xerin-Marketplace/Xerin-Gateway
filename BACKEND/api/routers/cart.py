from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from api.deps import get_current_user, get_db
from api.models import Cart, CartItem, Coupon, Inventory, Product, ProductStatus, ProductVariant, User
from api.schemas import ApplyCouponRequest, CartItemCreate, CartItemUpdate, CartResponse

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


def _cart_payload(db: Session, cart: Cart) -> dict:
    subtotal = sum((Decimal(item.unit_price) * item.quantity for item in cart.items), Decimal("0.00"))
    discount = Decimal("0.00")
    if cart.coupon_code:
        coupon = db.query(Coupon).filter(Coupon.code == cart.coupon_code).first()
        if coupon:
            try:
                discount = _validate_coupon(coupon, subtotal)
            except HTTPException:
                # An expired/deactivated coupon must not break cart viewing.
                cart.coupon_code = None
                db.flush()
        else:
            cart.coupon_code = None
            db.flush()
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        "subtotal": subtotal,
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

        inventory = _inventory_query(db, product.id, data.variant_id).with_for_update().first()
        if not inventory:
            raise HTTPException(status_code=409, detail="Inventory is not configured for this item")

        cart = _get_or_create_cart(db, current_user.id, lock=True)
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
