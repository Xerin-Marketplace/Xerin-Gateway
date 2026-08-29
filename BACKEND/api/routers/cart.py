from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from api.deps import get_current_user, get_db
from api.models import (
    Cart,
    CartItem,
    Coupon,
    Inventory,
    Product,
    ProductStatus,
    ProductVariant,
    Promotion,
    PromotionRule,
    PromotionUsage,
    User,
    Broker,
    BrokerOffer,
    BrokerOfferAcceptance,
    BrokerReferralLink,
    BrokerAttribution,
)
from api.services.fx_service import FxRateUnavailableError, convert_amount_to_tzs
from api.services.broker_risk_service import record_broker_risk
from api.schemas import (
    ApplyCartPromotionRequest,
    ApplyCouponRequest,
    CartItemCreate,
    CartItemUpdate,
    CartPromotionOffer,
    CartResponse,
    GuestCartMergeRequest,
    GuestCartMergeResponse,
)

router = APIRouter(prefix="/cart", tags=["Cart"])

ZERO = Decimal("0.00")


def _get_or_create_cart(db: Session, user_id: UUID, *, lock: bool = False) -> Cart:
    query = (
        db.query(Cart)
        .options(
            selectinload(Cart.items).selectinload(CartItem.product),
            selectinload(Cart.items).selectinload(CartItem.variant),
        )
        .filter(Cart.user_id == user_id)
    )
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
        cart = (
            db.query(Cart)
            .options(
                selectinload(Cart.items).selectinload(CartItem.product),
                selectinload(Cart.items).selectinload(CartItem.variant),
            )
            .filter(Cart.user_id == user_id)
            .first()
        )
        if cart is None:
            raise
    return cart


def _inventory_query(db: Session, product_id: UUID, variant_id: UUID | None):
    query = db.query(Inventory).filter(Inventory.product_id == product_id)
    return query.filter(
        Inventory.variant_id == variant_id
        if variant_id is not None
        else Inventory.variant_id.is_(None)
    )


def _resolve_listing_price(product: Product, variant: ProductVariant | None) -> Decimal:
    if variant is not None:
        if variant.sale_price is not None:
            return Decimal(variant.sale_price)
        if variant.price is not None:
            return Decimal(variant.price)
    if product.sale_price is not None:
        return Decimal(product.sale_price)
    return Decimal(product.price)


def _resolve_price(
    db: Session,
    product: Product,
    variant: ProductVariant | None,
) -> Decimal:
    """Return the cart/checkout unit price in canonical TZS.

    Product.price / variant.price remain listing-currency amounts. Cart money is
    always normalised to the marketplace settlement currency before arithmetic.
    """
    listing_price = _resolve_listing_price(product, variant)
    try:
        return convert_amount_to_tzs(db, listing_price, product.currency)
    except FxRateUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                f"{product.name} cannot be added to the cart because its "
                f"{(product.currency or 'TZS').upper()}/TZS exchange rate is unavailable"
            ),
        ) from exc




def _lock_broker_attribution(db: Session, *, user: User, product: Product, referral_code: str, unit_price: Decimal) -> BrokerAttribution:
    now = datetime.now(timezone.utc)
    link = db.query(BrokerReferralLink).filter(BrokerReferralLink.referral_code == referral_code.strip(), BrokerReferralLink.is_active.is_(True)).first()
    if not link or link.product_id != product.id:
        raise HTTPException(status_code=422, detail="Broker referral code is invalid for this product")
    offer = db.query(BrokerOffer).filter(BrokerOffer.id == link.offer_id, BrokerOffer.is_active.is_(True)).first()
    acceptance = db.query(BrokerOfferAcceptance).filter(BrokerOfferAcceptance.id == link.acceptance_id, BrokerOfferAcceptance.is_active.is_(True)).first()
    if not offer or not acceptance or offer.starts_at > now or (offer.ends_at is not None and offer.ends_at <= now):
        raise HTTPException(status_code=409, detail="Broker referral is no longer active")
    broker = db.query(Broker).filter(Broker.id == link.broker_id).first()
    if not broker:
        raise HTTPException(status_code=409, detail="Broker referral is unavailable")
    if broker.user_id == user.id:
        record_broker_risk(
            db, event_type="self_referral", severity="critical", broker_id=broker.id, user_id=user.id,
            resource_type="product", resource_id=str(product.id),
            details={"referral_link_id": str(link.id), "offer_id": str(offer.id)},
        )
        # No cart mutation has happened yet; persist the security evidence before rejecting.
        db.commit()
        raise HTTPException(status_code=422, detail="A Broker cannot earn commission from their own purchase")

    # Different accounts that reuse the Broker's email/phone are not auto-banned,
    # but they are flagged for admin review. This avoids false positives for shared
    # households while still surfacing likely multi-account self-referral abuse.
    broker_user = db.query(User).filter(User.id == broker.user_id).first()
    same_email = bool(broker_user and broker_user.email and user.email and broker_user.email.strip().lower() == user.email.strip().lower())
    same_phone = bool(broker_user and broker_user.phone and user.phone and broker_user.phone.strip() == user.phone.strip())
    if same_email or same_phone:
        record_broker_risk(
            db, event_type="related_account_referral", severity="high", broker_id=broker.id, user_id=user.id,
            resource_type="product", resource_id=str(product.id),
            details={"same_email": same_email, "same_phone": same_phone, "referral_link_id": str(link.id)},
        )
    if offer.max_attributed_sales is not None and offer.attributed_sales_count >= offer.max_attributed_sales:
        raise HTTPException(status_code=409, detail="Broker campaign has reached its sales limit")
    value = Decimal(str(offer.commission_value))
    amount = value if offer.commission_type == "fixed" else (unit_price * value / Decimal("100"))
    amount = max(ZERO, amount).quantize(Decimal("0.01"))
    attribution = BrokerAttribution(
        referral_link_id=link.id, offer_id=offer.id, broker_id=broker.id, product_id=product.id, user_id=user.id,
        commission_type=offer.commission_type, commission_value=value, commission_amount_per_unit=amount, status="locked",
    )
    db.add(attribution); db.flush()
    return attribution

def _subtotal(cart: Cart) -> Decimal:
    return sum(
        (Decimal(item.unit_price) * item.quantity for item in cart.items),
        ZERO,
    )


def _validate_coupon(coupon: Coupon, subtotal: Decimal) -> Decimal:
    now = datetime.now(timezone.utc)
    if not coupon.is_active:
        raise HTTPException(status_code=400, detail="Coupon is inactive")
    if coupon.valid_from and now < coupon.valid_from:
        raise HTTPException(status_code=400, detail="Coupon is not valid yet")
    if coupon.valid_until and now > coupon.valid_until:
        raise HTTPException(status_code=400, detail="Coupon has expired")
    if coupon.usage_limit is not None and coupon.usage_count >= coupon.usage_limit:
        raise HTTPException(
            status_code=400,
            detail="Coupon usage limit has been reached",
        )
    if (
        coupon.minimum_order_amount is not None
        and subtotal < Decimal(coupon.minimum_order_amount)
    ):
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
        raise HTTPException(
            status_code=500,
            detail="Coupon configuration is invalid",
        )

    return min(discount, subtotal).quantize(Decimal("0.01"))


def _active_promotion_query(db: Session):
    now = datetime.now(timezone.utc)
    return db.query(Promotion).filter(
        Promotion.is_active.is_(True),
        (Promotion.starts_at.is_(None) | (Promotion.starts_at <= now)),
        (Promotion.ends_at.is_(None) | (Promotion.ends_at >= now)),
        (
            Promotion.usage_limit.is_(None)
            | (Promotion.usage_count < Promotion.usage_limit)
        ),
    )


def _promotion_customer_limit(
    db: Session,
    promotion: Promotion,
    user_id: UUID,
) -> None:
    if promotion.usage_per_customer is None:
        return

    used = (
        db.query(PromotionUsage)
        .filter(
            PromotionUsage.promotion_id == promotion.id,
            PromotionUsage.user_id == user_id,
        )
        .count()
    )
    if used >= promotion.usage_per_customer:
        raise HTTPException(
            status_code=422,
            detail="You have reached the usage limit for this promotion",
        )


def _promotion_matches_item(
    promotion: Promotion,
    item: CartItem,
) -> bool:
    product = item.product

    # A seller-funded promotion never leaks to another seller's products.
    if getattr(product, "listing_owner_type", "seller") == "broker":
        raise HTTPException(status_code=409, detail="Broker-owned product checkout is not enabled until the Broker fulfillment phase is activated")

    if promotion.seller_id is not None and product.seller_id != promotion.seller_id:
        return False

    targeting_rules = [
        rule
        for rule in promotion.rules
        if rule.rule_type in {"product", "category", "store"}
    ]

    # No explicit product/category/store rule means seller-wide promotion.
    if not targeting_rules:
        return True

    for rule in targeting_rules:
        if rule.rule_type == "product" and rule.product_id == product.id:
            return True
        if rule.rule_type == "category" and rule.category_id == product.category_id:
            return True

        # Store rules can be added once storefront identity is present directly
        # on each cart item. Do not guess store membership here.
    return False


def _promotion_eligible_items(
    promotion: Promotion,
    cart: Cart,
) -> list[CartItem]:
    return [
        item
        for item in cart.items
        if _promotion_matches_item(promotion, item)
    ]


def _validate_minimum_quantity(
    promotion: Promotion,
    eligible_items: list[CartItem],
) -> None:
    quantity_rules = [
        rule
        for rule in promotion.rules
        if rule.rule_type == "minimum_quantity"
    ]
    if not quantity_rules:
        return

    total_quantity = sum(item.quantity for item in eligible_items)

    for rule in quantity_rules:
        raw = rule.value or {}
        minimum = raw.get("quantity") or raw.get("minimum_quantity")
        if minimum is None:
            continue
        try:
            minimum_int = int(minimum)
        except (TypeError, ValueError):
            continue
        if total_quantity < minimum_int:
            raise HTTPException(
                status_code=422,
                detail=f"Promotion requires at least {minimum_int} eligible items",
            )


def _promotion_preview(
    db: Session,
    promotion: Promotion,
    cart: Cart,
    user_id: UUID,
) -> tuple[Decimal, Decimal]:
    _promotion_customer_limit(db, promotion, user_id)

    eligible_items = _promotion_eligible_items(promotion, cart)
    if not eligible_items:
        raise HTTPException(
            status_code=422,
            detail="This promotion does not apply to products in your cart",
        )

    _validate_minimum_quantity(promotion, eligible_items)

    eligible_subtotal = sum(
        (Decimal(item.unit_price) * item.quantity for item in eligible_items),
        ZERO,
    ).quantize(Decimal("0.01"))

    if (
        promotion.minimum_order_amount is not None
        and eligible_subtotal < Decimal(promotion.minimum_order_amount)
    ):
        raise HTTPException(
            status_code=422,
            detail=f"Promotion requires an eligible subtotal of {promotion.minimum_order_amount}",
        )

    if promotion.promotion_type == "percentage":
        discount = (
            eligible_subtotal
            * Decimal(promotion.discount_value)
            / Decimal("100")
        )
    elif promotion.promotion_type == "fixed_amount":
        discount = Decimal(promotion.discount_value)
    elif promotion.promotion_type == "free_shipping":
        # Shipping is selected in Customer Phase 4. Persisting this promotion
        # now allows Phase 4/5 to apply its shipping benefit.
        discount = ZERO
    elif promotion.promotion_type == "buy_x_get_y":
        raise HTTPException(
            status_code=422,
            detail="Buy X Get Y requires item-level offer configuration and is not available in cart yet",
        )
    else:
        raise HTTPException(
            status_code=422,
            detail="This promotion type is not supported in the customer cart yet",
        )

    if promotion.maximum_discount_amount is not None:
        discount = min(discount, Decimal(promotion.maximum_discount_amount))

    discount = max(ZERO, min(discount, eligible_subtotal)).quantize(
        Decimal("0.01")
    )
    return eligible_subtotal, discount


def _promotion_payload(
    promotion: Promotion,
    eligible_subtotal: Decimal,
    discount_amount: Decimal,
) -> dict:
    return {
        "promotion_id": promotion.id,
        "code": promotion.code,
        "name": promotion.name,
        "promotion_type": promotion.promotion_type,
        "funding_source": promotion.funding_source,
        "eligible_subtotal": eligible_subtotal,
        "discount_amount": discount_amount,
        "seller_id": promotion.seller_id,
        "stackable": promotion.stackable,
    }


def _cart_payload(
    db: Session,
    cart: Cart,
    *,
    user_id: UUID,
    validation_messages: list[str] | None = None,
) -> dict:
    subtotal = _subtotal(cart)
    coupon_discount = ZERO
    promotion_discount = ZERO
    promotion_payload = None

    if cart.promotion_code:
        promotion = (
            _active_promotion_query(db)
            .options(selectinload(Promotion.rules))
            .filter(Promotion.code == cart.promotion_code)
            .first()
        )
        if promotion:
            try:
                eligible_subtotal, promotion_discount = _promotion_preview(
                    db,
                    promotion,
                    cart,
                    user_id,
                )
                promotion_payload = _promotion_payload(
                    promotion,
                    eligible_subtotal,
                    promotion_discount,
                )
            except HTTPException:
                # Cart viewing should recover from a promotion that became
                # expired, exhausted or ineligible after quantity changes.
                cart.promotion_code = None
                db.flush()
        else:
            cart.promotion_code = None
            db.flush()

    if cart.coupon_code:
        coupon = db.query(Coupon).filter(Coupon.code == cart.coupon_code).first()
        if coupon:
            try:
                coupon_discount = _validate_coupon(coupon, subtotal)
            except HTTPException:
                cart.coupon_code = None
                db.flush()
        else:
            cart.coupon_code = None
            db.flush()

    combined_discount = min(
        subtotal,
        coupon_discount + promotion_discount,
    ).quantize(Decimal("0.01"))

    return {
        "id": cart.id,
        "user_id": cart.user_id,
        "coupon_code": cart.coupon_code,
        "promotion_code": cart.promotion_code,
        "promotion": promotion_payload,
        "items": cart.items,
        "subtotal": subtotal.quantize(Decimal("0.01")),
        "coupon_discount_amount": coupon_discount,
        "promotion_discount_amount": promotion_discount,
        "discount_amount": combined_discount,
        "total": max(ZERO, subtotal - combined_discount).quantize(
            Decimal("0.01")
        ),
        "currency": "TZS",
        "validation_messages": validation_messages or [],
    }


def _cart_or_error(db: Session, user_id: UUID, *, lock: bool = False) -> Cart:
    return _get_or_create_cart(db, user_id, lock=lock)


@router.get("", response_model=CartResponse)
def get_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _cart_or_error(db, current_user.id)
    payload = _cart_payload(db, cart, user_id=current_user.id)
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
        if (
            not product
            or not product.is_active
            or product.status != ProductStatus.approved
        ):
            raise HTTPException(
                status_code=404,
                detail="Product is not available",
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
            if not variant or not variant.is_active:
                raise HTTPException(
                    status_code=404,
                    detail="Product variant not found or inactive",
                )

        inventory = (
            _inventory_query(db, product.id, data.variant_id)
            .with_for_update()
            .first()
        )
        if not inventory:
            raise HTTPException(
                status_code=409,
                detail="Inventory is not configured for this item",
            )

        cart = _cart_or_error(db, current_user.id, lock=True)
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

        requested_quantity = data.quantity + (
            existing.quantity if existing else 0
        )
        if requested_quantity > inventory.available_quantity:
            raise HTTPException(status_code=409, detail="Insufficient stock")

        unit_price = _resolve_price(db, product, variant)
        attribution = None
        if data.broker_referral_code and (existing is None or existing.broker_attribution_id is None):
            attribution = _lock_broker_attribution(db, user=current_user, product=product, referral_code=data.broker_referral_code, unit_price=unit_price)
        if existing:
            existing.quantity = requested_quantity
            existing.unit_price = unit_price
            if existing.broker_attribution_id is None and attribution is not None:
                existing.broker_attribution_id = attribution.id
        else:
            db.add(
                CartItem(
                    cart_id=cart.id,
                    product_id=product.id,
                    variant_id=data.variant_id,
                    quantity=data.quantity,
                    unit_price=unit_price,
                    broker_attribution_id=attribution.id if attribution is not None else None,
                )
            )

        db.flush()
        db.expire(cart, ["items"])
        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This item is already in the cart",
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update cart",
        ) from exc


@router.put("/items/{item_id}", response_model=CartResponse)
def update_cart_item(
    item_id: UUID,
    data: CartItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        item = (
            db.query(CartItem)
            .filter(
                CartItem.id == item_id,
                CartItem.cart_id == cart.id,
            )
            .with_for_update()
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found")

        inventory = (
            _inventory_query(db, item.product_id, item.variant_id)
            .with_for_update()
            .first()
        )
        if not inventory or data.quantity > inventory.available_quantity:
            raise HTTPException(status_code=409, detail="Insufficient stock")

        item.quantity = data.quantity
        item.unit_price = _resolve_price(db, item.product, item.variant)
        db.flush()
        db.expire(cart, ["items"])
        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not update cart item",
        ) from exc


@router.delete("/items/{item_id}", response_model=CartResponse)
def remove_cart_item(
    item_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        item = (
            db.query(CartItem)
            .filter(
                CartItem.id == item_id,
                CartItem.cart_id == cart.id,
            )
            .first()
        )
        if not item:
            raise HTTPException(status_code=404, detail="Cart item not found")

        db.delete(item)
        db.flush()
        db.expire(cart, ["items"])

        if not cart.items:
            cart.coupon_code = None
            cart.promotion_code = None

        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not remove cart item",
        ) from exc


@router.delete("", response_model=CartResponse)
def clear_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        for item in list(cart.items):
            db.delete(item)

        cart.coupon_code = None
        cart.promotion_code = None
        db.flush()
        db.expire(cart, ["items"])

        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not clear cart",
        ) from exc


@router.post("/apply-coupon", response_model=CartResponse)
def apply_coupon(
    data: ApplyCouponRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        if not cart.items:
            raise HTTPException(
                status_code=400,
                detail="Cannot apply a coupon to an empty cart",
            )

        # A seller promotion explicitly decides whether it may be stacked.
        if cart.promotion_code:
            promotion = (
                _active_promotion_query(db)
                .filter(Promotion.code == cart.promotion_code)
                .first()
            )
            if promotion and not promotion.stackable:
                raise HTTPException(
                    status_code=409,
                    detail="The active seller promotion cannot be combined with a coupon",
                )

        coupon = (
            db.query(Coupon)
            .filter(Coupon.code == data.code.strip().upper())
            .with_for_update()
            .first()
        )
        if not coupon:
            raise HTTPException(status_code=404, detail="Coupon not found")

        subtotal = _subtotal(cart)
        _validate_coupon(coupon, subtotal)
        cart.coupon_code = coupon.code

        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not apply coupon",
        ) from exc


@router.delete("/coupon", response_model=CartResponse)
def remove_coupon(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        cart.coupon_code = None
        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not remove coupon",
        ) from exc


@router.get(
    "/promotions/available",
    response_model=list[CartPromotionOffer],
)
def cart_available_promotions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _cart_or_error(db, current_user.id)
    if not cart.items:
        return []

    promotions = (
        _active_promotion_query(db)
        .options(selectinload(Promotion.rules))
        .order_by(Promotion.created_at.desc())
        .limit(100)
        .all()
    )

    offers: list[dict] = []
    for promotion in promotions:
        if promotion.code is None and not promotion.automatic:
            continue

        try:
            eligible_subtotal, discount = _promotion_preview(
                db,
                promotion,
                cart,
                current_user.id,
            )
        except HTTPException:
            continue

        # Buy-X-get-Y is intentionally hidden until its item-level rule
        # configuration exists in the backend.
        if promotion.promotion_type == "buy_x_get_y":
            continue

        offers.append(
            {
                "promotion_id": promotion.id,
                "code": promotion.code,
                "name": promotion.name,
                "description": promotion.description,
                "promotion_type": promotion.promotion_type,
                "funding_source": promotion.funding_source,
                "seller_id": promotion.seller_id,
                "eligible_subtotal": eligible_subtotal,
                "discount_amount": discount,
                "total_after_discount": max(
                    ZERO,
                    eligible_subtotal - discount,
                ),
                "stackable": promotion.stackable,
                "automatic": promotion.automatic,
                "minimum_order_amount": promotion.minimum_order_amount,
                "maximum_discount_amount": promotion.maximum_discount_amount,
                "starts_at": promotion.starts_at,
                "ends_at": promotion.ends_at,
            }
        )

    return offers


@router.post("/apply-promotion", response_model=CartResponse)
def apply_cart_promotion(
    data: ApplyCartPromotionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        if not cart.items:
            raise HTTPException(
                status_code=400,
                detail="Cannot apply a promotion to an empty cart",
            )

        promotion = (
            _active_promotion_query(db)
            .options(selectinload(Promotion.rules))
            .filter(Promotion.code == data.code)
            .with_for_update()
            .first()
        )
        if not promotion:
            raise HTTPException(
                status_code=404,
                detail="Promotion code is invalid or unavailable",
            )

        _promotion_preview(db, promotion, cart, current_user.id)

        if cart.coupon_code and not promotion.stackable:
            raise HTTPException(
                status_code=409,
                detail="This seller promotion cannot be combined with the active coupon",
            )

        cart.promotion_code = promotion.code
        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not apply seller promotion",
        ) from exc


@router.delete("/promotion", response_model=CartResponse)
def remove_cart_promotion(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        cart.promotion_code = None
        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()
        return payload
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not remove seller promotion",
        ) from exc


@router.post("/validate", response_model=CartResponse)
def validate_cart(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = _cart_or_error(db, current_user.id, lock=True)
        messages: list[str] = []

        for item in cart.items:
            product = item.product
            if (
                not product
                or not product.is_active
                or product.status != ProductStatus.approved
            ):
                messages.append(
                    f"{getattr(product, 'name', 'A product')} is no longer available"
                )
                continue

            if item.variant_id is not None and (
                item.variant is None or not item.variant.is_active
            ):
                messages.append(
                    f"{product.name}: selected variant is no longer available"
                )
                continue

            inventory = (
                _inventory_query(db, item.product_id, item.variant_id)
                .with_for_update()
                .first()
            )
            if inventory is None:
                messages.append(
                    f"{product.name}: inventory is not configured"
                )
                continue

            if item.quantity > inventory.available_quantity:
                messages.append(
                    f"{product.name}: only {inventory.available_quantity} item(s) are currently available"
                )

            latest_price = _resolve_price(db, product, item.variant)
            if Decimal(item.unit_price) != latest_price:
                item.unit_price = latest_price
                messages.append(
                    f"{product.name}: price was refreshed to the latest marketplace price"
                )

        db.flush()
        payload = _cart_payload(
            db,
            cart,
            user_id=current_user.id,
            validation_messages=messages,
        )
        db.commit()
        return payload
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not validate cart",
        ) from exc


@router.post("/merge", response_model=GuestCartMergeResponse)
def merge_guest_cart(
    data: GuestCartMergeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cart = _cart_or_error(db, current_user.id, lock=True)
    rejected: list[dict] = []

    try:
        for incoming in data.items:
            product = (
                db.query(Product)
                .filter(Product.id == incoming.product_id)
                .first()
            )
            if (
                not product
                or not product.is_active
                or product.status != ProductStatus.approved
            ):
                rejected.append(
                    {
                        "product_id": incoming.product_id,
                        "reason": "Product is not available",
                    }
                )
                continue

            variant = None
            if incoming.variant_id is not None:
                variant = (
                    db.query(ProductVariant)
                    .filter(
                        ProductVariant.id == incoming.variant_id,
                        ProductVariant.product_id == product.id,
                        ProductVariant.is_active.is_(True),
                    )
                    .first()
                )
                if not variant:
                    rejected.append(
                        {
                            "product_id": incoming.product_id,
                            "reason": "Selected variant is not available",
                        }
                    )
                    continue

            inventory = (
                _inventory_query(
                    db,
                    incoming.product_id,
                    incoming.variant_id,
                )
                .with_for_update()
                .first()
            )
            if not inventory:
                rejected.append(
                    {
                        "product_id": incoming.product_id,
                        "reason": "Inventory is not configured",
                    }
                )
                continue

            existing_query = db.query(CartItem).filter(
                CartItem.cart_id == cart.id,
                CartItem.product_id == incoming.product_id,
            )
            existing_query = existing_query.filter(
                CartItem.variant_id == incoming.variant_id
                if incoming.variant_id is not None
                else CartItem.variant_id.is_(None)
            )
            existing = existing_query.with_for_update().first()
            new_quantity = incoming.quantity + (
                existing.quantity if existing else 0
            )

            if new_quantity > inventory.available_quantity:
                rejected.append(
                     {
                        "product_id": incoming.product_id,
                        "reason": "Insufficient stock",
                        "available_quantity": inventory.available_quantity,
                    }
                )
                continue

            latest_price = _resolve_price(db, product, variant)
            if existing:
                existing.quantity = new_quantity
                existing.unit_price = latest_price
            else:
                db.add(
                    CartItem(
                        cart_id=cart.id,
                        product_id=incoming.product_id,
                        variant_id=incoming.variant_id,
                        quantity=incoming.quantity,
                        unit_price=latest_price,
                    )
                )

        db.flush()
        db.expire(cart, ["items"])
        payload = _cart_payload(db, cart, user_id=current_user.id)
        db.commit()

        return {
            "cart": payload,
            "rejected_items": rejected,
        }
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not merge guest cart",
        ) from exc
