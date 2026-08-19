from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.models import (
    Address,
    Cart,
    CartItem,
    CheckoutDeliveryQuote,
    ProductStatus,
)
from api.services.multi_seller_pricing import (
    MultiSellerPricingError,
    calculate_multi_seller_delivery_pricing,
)


MONEY = Decimal("0.01")


class CheckoutDeliveryQuoteError(Exception):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status_code: int,
        extra: dict | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.extra = extra or {}


def _money(value: Decimal) -> Decimal:
    return value.quantize(MONEY, rounding=ROUND_HALF_UP)


def current_cart_snapshot(
    db: Session,
    *,
    user_id: UUID,
) -> tuple[Decimal, str]:
    """Return current product subtotal + deterministic cart fingerprint.

    The fingerprint prevents a customer from freezing delivery for one cart and
    then changing seller/product/quantity before creating the order.
    """
    cart = (
        db.query(Cart)
        .options(
            selectinload(Cart.items).selectinload(CartItem.product),
            selectinload(Cart.items).selectinload(CartItem.variant),
        )
        .filter(Cart.user_id == user_id)
        .first()
    )
    if cart is None or not cart.items:
        raise CheckoutDeliveryQuoteError(
            "Cart is empty.",
            code="cart_empty",
            status_code=400,
        )

    rows = []
    subtotal = Decimal("0")

    for item in sorted(cart.items, key=lambda row: str(row.id)):
        product = item.product
        if (
            product is None
            or not product.is_active
            or product.status != ProductStatus.approved
        ):
            raise CheckoutDeliveryQuoteError(
                "Cart contains a product that is no longer available.",
                code="cart_product_unavailable",
                status_code=409,
            )

        unit_price = Decimal(item.unit_price)
        line_total = unit_price * Decimal(item.quantity)
        subtotal += line_total

        rows.append(
            {
                "cart_item_id": str(item.id),
                "product_id": str(item.product_id),
                "variant_id": str(item.variant_id) if item.variant_id else None,
                "seller_id": str(product.seller_id),
                "quantity": int(item.quantity),
                "unit_price": format(unit_price, "f"),
            }
        )

    raw = json.dumps(rows, sort_keys=True, separators=(",", ":")).encode("utf-8")
    fingerprint = hashlib.sha256(raw).hexdigest()
    return _money(subtotal), fingerprint


def create_checkout_delivery_quote(
    db: Session,
    *,
    user_id: UUID,
    address_id: UUID,
    logistics_company_id: UUID,
    rate_id: UUID,
    delivery_mode: str,
) -> CheckoutDeliveryQuote:
    subtotal, cart_fingerprint = current_cart_snapshot(db, user_id=user_id)

    try:
        pricing = calculate_multi_seller_delivery_pricing(
            db,
            user_id=user_id,
            address_id=address_id,
            logistics_company_id=logistics_company_id,
            delivery_mode=delivery_mode,
            method_id=None,
        )
    except MultiSellerPricingError as exc:
        raise CheckoutDeliveryQuoteError(
            exc.message,
            code=exc.code,
            status_code=exc.status_code,
            extra=exc.extra,
        ) from exc

    selected = next(
        (option for option in pricing["options"] if option["rate_id"] == rate_id),
        None,
    )
    if selected is None:
        raise CheckoutDeliveryQuoteError(
            "Selected delivery rate is no longer available for this cart.",
            code="delivery_rate_not_available",
            status_code=409,
            extra={"rate_id": str(rate_id)},
        )

    address = db.get(Address, address_id)
    if address is None or address.user_id != user_id:
        raise CheckoutDeliveryQuoteError(
            "Delivery address not found.",
            code="delivery_address_not_found",
            status_code=404,
        )

    delivery_amount = _money(Decimal(selected["delivery_amount"]))
    total_before_discounts = _money(subtotal + delivery_amount)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(
        minutes=max(1, settings.CHECKOUT_DELIVERY_QUOTE_TTL_MINUTES)
    )

    snapshot = CheckoutDeliveryQuote(
        user_id=user_id,
        shipping_address_id=address.id,
        logistics_company_id=logistics_company_id,
        shipping_method_id=selected["method_id"],
        shipping_rate_id=selected["rate_id"],
        delivery_mode=delivery_mode,
        pricing_strategy=(
            selected["strategy"].value
            if hasattr(selected["strategy"], "value")
            else str(selected["strategy"])
        ),
        rate_type=(
            selected["rate_type"].value
            if hasattr(selected["rate_type"], "value")
            else str(selected["rate_type"])
        ),
        currency=selected["currency"],
        seller_count=selected["seller_count"],
        billable_distance_km=selected["billable_distance_km"],
        billable_seller_id=selected["billable_seller_id"],
        product_subtotal=subtotal,
        delivery_amount=delivery_amount,
        checkout_total_before_discounts=total_before_discounts,
        cart_fingerprint=cart_fingerprint,
        pricing_breakdown={
            key: (
                format(value, "f")
                if isinstance(value, Decimal)
                else value
            )
            for key, value in selected["pricing_breakdown"].items()
        },
        seller_routes_snapshot=[
            {
                key: (
                    str(value)
                    if isinstance(value, UUID)
                    else format(value, "f")
                    if isinstance(value, Decimal)
                    else value
                )
                for key, value in row.items()
            }
            for row in selected["sellers"]
        ],
        address_snapshot={
            "address_id": str(address.id),
            "formatted_address": address.formatted_address,
            "country": address.country,
            "region": address.region,
            "district": address.district,
            "ward": address.ward,
            "city": address.city,
            "street": address.street,
            "landmark": address.landmark,
            "postal_code": address.postal_code,
            "latitude": (
                format(Decimal(address.latitude), "f")
                if address.latitude is not None
                else None
            ),
            "longitude": (
                format(Decimal(address.longitude), "f")
                if address.longitude is not None
                else None
            ),
            "recipient_name": address.recipient_name,
            "recipient_phone": address.recipient_phone,
            "delivery_instructions": address.delivery_instructions,
        },
        expires_at=expires_at,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def get_usable_checkout_delivery_quote(
    db: Session,
    *,
    quote_id: UUID,
    user_id: UUID,
    shipping_address_id: UUID,
    delivery_mode: str,
    lock: bool = False,
) -> CheckoutDeliveryQuote:
    query = db.query(CheckoutDeliveryQuote).filter(
        CheckoutDeliveryQuote.id == quote_id,
        CheckoutDeliveryQuote.user_id == user_id,
    )
    if lock:
        query = query.with_for_update()
    quote = query.first()

    if quote is None:
        raise CheckoutDeliveryQuoteError(
            "Checkout delivery quote not found.",
            code="checkout_delivery_quote_not_found",
            status_code=404,
        )

    now = datetime.now(timezone.utc)
    if quote.used_at is not None:
        raise CheckoutDeliveryQuoteError(
            "Checkout delivery quote has already been used.",
            code="checkout_delivery_quote_used",
            status_code=409,
        )
    if quote.expires_at <= now:
        raise CheckoutDeliveryQuoteError(
            "Checkout delivery quote has expired. Recalculate delivery.",
            code="checkout_delivery_quote_expired",
            status_code=409,
        )
    if quote.shipping_address_id != shipping_address_id:
        raise CheckoutDeliveryQuoteError(
            "Checkout delivery quote belongs to a different delivery address.",
            code="checkout_delivery_quote_address_mismatch",
            status_code=409,
        )
    if quote.delivery_mode != delivery_mode:
        raise CheckoutDeliveryQuoteError(
            "Checkout delivery quote belongs to a different delivery mode.",
            code="checkout_delivery_quote_mode_mismatch",
            status_code=409,
        )

    subtotal, fingerprint = current_cart_snapshot(db, user_id=user_id)
    if fingerprint != quote.cart_fingerprint or subtotal != Decimal(quote.product_subtotal):
        raise CheckoutDeliveryQuoteError(
            "Cart changed after the delivery quote was created. Recalculate delivery.",
            code="checkout_delivery_quote_cart_changed",
            status_code=409,
        )

    return quote
