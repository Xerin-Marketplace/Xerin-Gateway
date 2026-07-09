from uuid import UUID
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.models import (
    User,
    Cart,
    CartItem,
    Product,
    ProductVariant,
    Inventory,
    Coupon,
)
from api.schemas import (
    CartItemCreate,
    CartItemUpdate,
    CartResponse,
    CartItemResponse,
    ApplyCouponRequest,
)

router = APIRouter(prefix="/cart", tags=["Cart"])


def _get_or_create_cart(db: Session, user_id: UUID) -> Cart:
    cart = db.query(Cart).filter(Cart.user_id == user_id).first()
    if not cart:
        cart = Cart(user_id=user_id)
        db.add(cart)
        db.commit()
        db.refresh(cart)
    return cart


def _resolve_price(product: Product, variant: ProductVariant | None) -> Decimal:
    if variant and variant.price is not None:
        return variant.price
    if product.sale_price is not None:
        return product.sale_price
    return product.price


def _calculate_cart_totals(db: Session, cart: Cart) -> dict:
    subtotal = Decimal("0.00")
    for item in cart.items:
        subtotal += Decimal(item.unit_price) * item.quantity

    discount_amount = Decimal("0.00")
    if cart.coupon_code:
        coupon = db.query(Coupon).filter(Coupon.code == cart.coupon_code, Coupon.is_active == True).first()
        if coupon:
            discount_amount = _apply_coupon(coupon, subtotal)

    return {
        "subtotal": subtotal,
        "discount_amount": discount_amount,
        "total": subtotal - discount_amount,
    }


def _apply_coupon(coupon: Coupon, subtotal: Decimal) -> Decimal:
    from datetime import datetime, timezone

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


@router.get("", response_model=CartResponse)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _get_or_create_cart(db, current_user.id)
    totals = _calculate_cart_totals(db, cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        **totals,
    }


@router.post("/items", response_model=CartResponse, status_code=status.HTTP_201_CREATED)
def add_cart_item(
    data: CartItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = db.query(Product).filter(Product.id == data.product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    if not product.is_active or product.status.value != "approved":
        raise HTTPException(status_code=400, detail="Product is not available for purchase")

    variant = None
    if data.variant_id:
        variant = db.query(ProductVariant).filter(
            ProductVariant.id == data.variant_id,
            ProductVariant.product_id == product.id,
        ).first()
        if not variant:
            raise HTTPException(status_code=404, detail="Product variant not found")

    inventory = db.query(Inventory).filter(
        Inventory.product_id == product.id,
        Inventory.variant_id == data.variant_id,
    ).first()

    if not inventory or inventory.available_quantity < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    cart = _get_or_create_cart(db, current_user.id)

    existing_item = db.query(CartItem).filter(
        CartItem.cart_id == cart.id,
        CartItem.product_id == data.product_id,
        CartItem.variant_id == data.variant_id,
    ).first()

    unit_price = _resolve_price(product, variant)

    if existing_item:
        new_quantity = existing_item.quantity + data.quantity
        if inventory.available_quantity < new_quantity:
            raise HTTPException(status_code=400, detail="Insufficient stock")
        existing_item.quantity = new_quantity
        existing_item.unit_price = unit_price
    else:
        new_item = CartItem(
            cart_id=cart.id,
            product_id=data.product_id,
            variant_id=data.variant_id,
            quantity=data.quantity,
            unit_price=unit_price,
        )
        db.add(new_item)

    db.commit()
    db.refresh(cart)
    totals = _calculate_cart_totals(db, cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        **totals,
    }


@router.put("/items/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: UUID,
    data: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _get_or_create_cart(db, current_user.id)
    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id,
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    inventory = db.query(Inventory).filter(
        Inventory.product_id == item.product_id,
        Inventory.variant_id == item.variant_id,
    ).first()

    if not inventory or inventory.available_quantity < data.quantity:
        raise HTTPException(status_code=400, detail="Insufficient stock")

    item.quantity = data.quantity
    db.commit()
    db.refresh(cart)
    totals = _calculate_cart_totals(db, cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        **totals,
    }


@router.delete("/items/{item_id}", response_model=CartResponse)
def remove_cart_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _get_or_create_cart(db, current_user.id)
    item = db.query(CartItem).filter(
        CartItem.id == item_id,
        CartItem.cart_id == cart.id,
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Cart item not found")

    db.delete(item)
    db.commit()
    db.refresh(cart)
    totals = _calculate_cart_totals(db, cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        **totals,
    }


@router.delete("", response_model=CartResponse)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _get_or_create_cart(db, current_user.id)
    for item in cart.items:
        db.delete(item)
    cart.coupon_code = None
    db.commit()
    db.refresh(cart)
    totals = _calculate_cart_totals(db, cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        **totals,
    }


@router.post("/apply-coupon", response_model=CartResponse)
def apply_coupon(
    data: ApplyCouponRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    coupon = db.query(Coupon).filter(Coupon.code == data.code).first()
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")

    cart = _get_or_create_cart(db, current_user.id)
    cart.coupon_code = data.code
    db.commit()
    db.refresh(cart)
    totals = _calculate_cart_totals(db, cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        **totals,
    }


@router.delete("/coupon", response_model=CartResponse)
def remove_coupon(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _get_or_create_cart(db, current_user.id)
    cart.coupon_code = None
    db.commit()
    db.refresh(cart)
    totals = _calculate_cart_totals(db, cart)
    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "items": cart.items,
        **totals,
    }
