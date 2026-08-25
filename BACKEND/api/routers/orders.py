from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import String, cast, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, selectinload

from api.config import settings
from api.deps import get_current_user, get_db
from api.models import (
    Address,
    Cart,
    CartItem,
    Coupon,
    CheckoutDeliveryQuote,
    EscrowHold,
    Inventory,
    LogisticsCompany,
    MarketplaceSettings,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentStatus,
    ProductStatus,
    Promotion,
    PromotionRule,
    PromotionUsage,
    SellerOrder,
    Shipment,
    ShipmentPickupProof,
    ShippingMethod,
    ShippingRate,
    ShippingZone,
    User,
)
from api.permissions import get_user_permissions, get_user_role_names, require_permission
from api.schemas import (
    AdminOrderResponse,
    CustomerEscrowApprovalRequest,
    CustomerEscrowSummary,
    CustomerOrderDetailResponse,
    CustomerOrderTrackingResponse,
    PaginatedCustomerTrackingEventResponse,
    OrderCreateRequest,
    PaginatedPickupProofResponse,
    PickupProofProblemRequest,
    PickupProofResponse,
    OrderResponse,
    OrderWorkflowResponse,
    OrderStatusUpdateRequest,
    PaginatedAdminOrderResponse,
    PaginatedOrderResponse,
)
from api.enums import InventoryReservationStatus, ShipmentStatus
from api.services.eligible_logistics import EligibleLogisticsError, detect_cart_delivery_mode
from api.services.fx_service import FxRateUnavailableError, convert_amount_to_tzs
from api.services.inventory_reservations import create_reservation, release_order_reservations
from api.services.escrow_service import order_escrow_summary, release_order_escrow
from api.services.customer_shipment_tracking import (
    CustomerShipmentTrackingError,
    get_customer_order_tracking,
    get_customer_shipment_tracking_events,
)
from api.services.pickup_proof_service import (
    PickupProofError,
    approve_pickup_proof,
    auto_approve_if_expired,
    dispute_pickup_proof,
)
from api.services.checkout_delivery_quote import (
    CheckoutDeliveryQuoteError,
    get_usable_checkout_delivery_quote,
)
from api.services.order_workflow import build_order_workflow, reconcile_order_workflow
from api.services.order_invoice import build_order_invoice_pdf

router = APIRouter(prefix="/orders", tags=["Orders"])

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.pending: {OrderStatus.cancelled},
    OrderStatus.paid: {OrderStatus.processing, OrderStatus.refunded},
    OrderStatus.processing: {OrderStatus.shipped, OrderStatus.cancelled, OrderStatus.refunded},
    OrderStatus.shipped: {OrderStatus.delivered},
    OrderStatus.delivered: {OrderStatus.refunded},
    OrderStatus.cancelled: set(),
    OrderStatus.refunded: set(),
}



def _customer_payment_status(order: Order) -> str | None:
    payments = list(getattr(order, "payments", []) or [])
    if not payments:
        return None

    priority = {
        "completed": 6,
        "processing": 5,
        "pending": 4,
        "refunded": 3,
        "cancelled": 2,
        "failed": 1,
    }

    def value_of(payment):
        raw = payment.status
        return raw.value if hasattr(raw, "value") else str(raw)

    return max(
        (value_of(payment) for payment in payments),
        key=lambda value: priority.get(value, 0),
    )


def _page_count(total: int, page_size: int) -> int:
    return (total + page_size - 1) // page_size if total else 0


def _normalise_place(value: str | None) -> str:
    return (value or "").strip().lower()


def _is_tanzania(value: str | None) -> bool:
    return _normalise_place(value) in {
        "tanzania",
        "united republic of tanzania",
        "tz",
    }


def _validate_delivery_mode(
    db: Session,
    address: Address,
    delivery_mode: str,
    *,
    user_id: UUID,
) -> MarketplaceSettings | None:
    settings_row = (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.singleton_key == 1)
        .first()
    )
    try:
        detected = detect_cart_delivery_mode(
            db, user_id=user_id, address_id=address.id
        )
    except EligibleLogisticsError as exc:
        detail = {"code": exc.code, "message": exc.message}
        detail.update(exc.extra)
        raise HTTPException(status_code=exc.status_code, detail=detail) from exc

    if delivery_mode != detected["delivery_mode"]:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "delivery_mode_mismatch",
                "message": f"Delivery mode is automatically {detected['delivery_mode']} for the selected address and cart stores.",
            },
        )

    if detected["delivery_mode"] == "international" and not (
        settings_row and settings_row.international_delivery_allowed
    ):
        raise HTTPException(
            status_code=409,
            detail="International delivery is not enabled for the marketplace",
        )
    return settings_row


def _promotion_matches_order_item(
    promotion: Promotion,
    product,
) -> bool:
    if promotion.seller_id is not None and product.seller_id != promotion.seller_id:
        return False

    target_rules = [
        rule
        for rule in promotion.rules
        if rule.rule_type in {"product", "category"}
    ]

    if not target_rules:
        return True

    return any(
        (
            rule.rule_type == "product"
            and rule.product_id == product.id
        )
        or (
            rule.rule_type == "category"
            and rule.category_id == product.category_id
        )
        for rule in target_rules
    )


def _validate_promotion_usage(
    db: Session,
    promotion: Promotion,
    user_id: UUID,
) -> None:
    now = datetime.now(timezone.utc)

    if not promotion.is_active:
        raise HTTPException(status_code=409, detail="Promotion is inactive")
    if promotion.starts_at and now < promotion.starts_at:
        raise HTTPException(status_code=409, detail="Promotion is not valid yet")
    if promotion.ends_at and now > promotion.ends_at:
        raise HTTPException(status_code=409, detail="Promotion has expired")
    if (
        promotion.usage_limit is not None
        and promotion.usage_count >= promotion.usage_limit
    ):
        raise HTTPException(
            status_code=409,
            detail="Promotion usage limit has been reached",
        )

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
            raise HTTPException(
                status_code=409,
                detail="You have reached the usage limit for this promotion",
            )


def _prepare_product_promotion(
    db: Session,
    cart: Cart,
    prepared_items: list[dict],
    user_id: UUID,
    requested_code: str | None,
) -> tuple[Promotion | None, Decimal]:
    cart_code = (cart.promotion_code or "").strip().upper() or None
    request_code = (requested_code or "").strip().upper() or None

    if request_code and cart_code and request_code != cart_code:
        raise HTTPException(
            status_code=409,
            detail="Cart promotion changed. Refresh checkout and try again",
        )

    code = request_code or cart_code
    if not code:
        return None, Decimal("0.00")

    promotion = (
        db.query(Promotion)
        .options(selectinload(Promotion.rules))
        .filter(Promotion.code == code)
        .with_for_update()
        .first()
    )
    if not promotion:
        raise HTTPException(
            status_code=404,
            detail="Promotion is no longer available",
        )

    _validate_promotion_usage(db, promotion, user_id)

    eligible = [
        item
        for item in prepared_items
        if _promotion_matches_order_item(
            promotion,
            item["cart_item"].product,
        )
    ]
    if not eligible:
        raise HTTPException(
            status_code=409,
            detail="Promotion no longer applies to this cart",
        )

    eligible_subtotal = sum(
        (item["line_total"] for item in eligible),
        Decimal("0.00"),
    )

    if (
        promotion.minimum_order_amount is not None
        and eligible_subtotal < Decimal(promotion.minimum_order_amount)
    ):
        raise HTTPException(
            status_code=409,
            detail="Promotion minimum order amount is no longer satisfied",
        )

    if promotion.promotion_type == "free_shipping":
        product_discount = Decimal("0.00")
    elif promotion.promotion_type == "percentage":
        product_discount = (
            eligible_subtotal
            * Decimal(promotion.discount_value)
            / Decimal("100")
        )
    elif promotion.promotion_type == "fixed_amount":
        product_discount = Decimal(promotion.discount_value)
    else:
        raise HTTPException(
            status_code=409,
            detail="Promotion type is not supported at checkout",
        )

    if promotion.maximum_discount_amount is not None:
        product_discount = min(
            product_discount,
            Decimal(promotion.maximum_discount_amount),
        )

    product_discount = max(
        Decimal("0.00"),
        min(product_discount, eligible_subtotal),
    ).quantize(Decimal("0.01"))

    # Pro-rate the seller-funded product discount across eligible lines.
    remaining = product_discount
    for index, item in enumerate(eligible):
        if product_discount <= 0:
            allocation = Decimal("0.00")
        elif index == len(eligible) - 1:
            allocation = remaining
        else:
            allocation = (
                product_discount
                * item["line_total"]
                / eligible_subtotal
            ).quantize(Decimal("0.01"))
            allocation = min(allocation, remaining)

        item["promotion_discount_amount"] = allocation
        item["customer_total"] = item["line_total"] - allocation
        remaining -= allocation

    return promotion, product_discount


def _free_shipping_applies(
    promotion: Promotion | None,
    prepared_items: list[dict],
) -> bool:
    if not promotion or promotion.promotion_type != "free_shipping":
        return False

    # Full-order free shipping is seller-funded, so every item in the order
    # must be eligible. This prevents one seller from funding another seller's
    # delivery.
    return all(
        _promotion_matches_order_item(
            promotion,
            item["cart_item"].product,
        )
        for item in prepared_items
    )


def _calculate_shipping(
    db: Session,
    address: Address,
    rate_id: UUID,
    subtotal: Decimal,
    weight_kg: Decimal,
    delivery_mode: str,
    free_shipping: bool,
):
    rate = (
        db.query(ShippingRate)
        .options(
            selectinload(ShippingRate.zone),
            selectinload(ShippingRate.method)
            .selectinload(ShippingMethod.logistics_company),
        )
        .filter(
            ShippingRate.id == rate_id,
            ShippingRate.is_active.is_(True),
        )
        .with_for_update()
        .first()
    )

    if (
        not rate
        or not rate.zone
        or not rate.method
        or not rate.zone.is_active
        or not rate.method.is_active
    ):
        raise HTTPException(
            status_code=409,
            detail="Selected shipping rate is unavailable",
        )

    zone = rate.zone
    method = rate.method
    company = method.logistics_company

    zone_scope = (
        zone.scope.value
        if hasattr(zone.scope, "value")
        else str(zone.scope)
    )
    method_scope = (
        method.scope.value
        if hasattr(method.scope, "value")
        else str(method.scope)
    )

    allowed_scopes = {delivery_mode, "both"}
    if zone_scope not in allowed_scopes or method_scope not in allowed_scopes:
        raise HTTPException(
            status_code=422,
            detail="Selected shipping service does not match the delivery type",
        )

    if company:
        company_status = (
            company.status.value
            if hasattr(company.status, "value")
            else str(company.status)
        )
        if company_status != "active":
            raise HTTPException(
                status_code=409,
                detail="Selected logistics company is unavailable",
            )

    if _normalise_place(zone.country) != _normalise_place(address.country):
        raise HTTPException(
            status_code=422,
            detail="Shipping rate does not serve this country",
        )

    regions = {_normalise_place(x) for x in (zone.regions or [])}
    cities = {_normalise_place(x) for x in (zone.cities or [])}

    if regions and _normalise_place(address.region) not in regions:
        raise HTTPException(
            status_code=422,
            detail="Shipping rate does not serve this region",
        )
    if cities and _normalise_place(address.city) not in cities:
        raise HTTPException(
            status_code=422,
            detail="Shipping rate does not serve this city",
        )

    if (
        rate.min_weight_kg is not None
        and weight_kg < Decimal(rate.min_weight_kg)
    ):
        raise HTTPException(
            status_code=422,
            detail="Shipment weight is below the selected rate minimum",
        )
    if (
        rate.max_weight_kg is not None
        and weight_kg > Decimal(rate.max_weight_kg)
    ):
        raise HTTPException(
            status_code=422,
            detail="Shipment weight exceeds the selected rate maximum",
        )

    try:
        free_shipping_threshold_tzs = (
            convert_amount_to_tzs(
                db,
                Decimal(rate.free_shipping_threshold),
                rate.currency,
            )
            if rate.free_shipping_threshold is not None
            else None
        )
    except FxRateUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Shipping rate {rate.id} cannot be converted to TZS: {exc}",
        ) from exc

    if (
        free_shipping_threshold_tzs is not None
        and subtotal >= free_shipping_threshold_tzs
    ):
        original_amount_source = Decimal("0.00")
    elif rate.rate_type.value == "free":
        original_amount_source = Decimal("0.00")
    elif rate.rate_type.value == "weight_based":
        original_amount_source = (
            Decimal(rate.base_amount)
            + Decimal(rate.amount_per_kg) * weight_kg
        )
    else:
        original_amount_source = Decimal(rate.base_amount)

    try:
        original_amount = convert_amount_to_tzs(
            db,
            original_amount_source,
            rate.currency,
        )
    except FxRateUnavailableError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Shipping rate {rate.id} cannot be converted to TZS: {exc}",
        ) from exc
    shipping_discount = (
        original_amount if free_shipping else Decimal("0.00")
    )
    shipping_amount = max(
        Decimal("0.00"),
        original_amount - shipping_discount,
    ).quantize(Decimal("0.01"))

    now = datetime.now(timezone.utc)

    return (
        rate,
        original_amount,
        shipping_discount,
        shipping_amount,
        now + timedelta(days=method.min_delivery_days),
        now + timedelta(days=method.max_delivery_days),
        company,
    )

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


@router.get(
    "/{order_id}/tracking",
    response_model=CustomerOrderTrackingResponse,
)
def get_my_order_tracking(
    order_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=150),
    shipment_status: ShipmentStatus | None = Query(default=None, alias="status"),
    requires_action: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_customer_order_tracking(
            db,
            order_id=order_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
            search=search,
            shipment_status=shipment_status,
            requires_action=requires_action,
        )
    except CustomerShipmentTrackingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.get(
    "/{order_id}/tracking/shipments/{shipment_id}/events",
    response_model=PaginatedCustomerTrackingEventResponse,
)
def get_my_shipment_tracking_events(
    order_id: UUID,
    shipment_id: UUID,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        return get_customer_shipment_tracking_events(
            db,
            order_id=order_id,
            shipment_id=shipment_id,
            user_id=current_user.id,
            page=page,
            page_size=page_size,
        )
    except CustomerShipmentTrackingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.get(
    "/pickup-proofs",
    response_model=PaginatedPickupProofResponse,
)
def list_my_pickup_proofs(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        db.query(ShipmentPickupProof)
        .filter(ShipmentPickupProof.customer_id == current_user.id)
    )
    if status_filter:
        if status_filter not in {"pending", "approved", "disputed", "auto_approved"}:
            raise HTTPException(422, "Invalid pickup proof status")
        query = query.filter(ShipmentPickupProof.status == status_filter)

    total = query.count()
    rows = (
        query.order_by(ShipmentPickupProof.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    for proof in rows:
        auto_approve_if_expired(db, proof, commit=False)
    db.commit()
    for proof in rows:
        db.refresh(proof)

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": (total + page_size - 1) // page_size if total else 0,
        "results": rows,
    }


@router.get(
    "/pickup-proofs/{proof_id}",
    response_model=PickupProofResponse,
)
def get_my_pickup_proof(
    proof_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proof = (
        db.query(ShipmentPickupProof)
        .filter(
            ShipmentPickupProof.id == proof_id,
            ShipmentPickupProof.customer_id == current_user.id,
        )
        .first()
    )
    if proof is None:
        raise HTTPException(404, "Pickup proof not found")
    proof = auto_approve_if_expired(db, proof)
    return proof


@router.post(
    "/pickup-proofs/{proof_id}/approve",
    response_model=PickupProofResponse,
)
def approve_my_pickup_proof(
    proof_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proof = (
        db.query(ShipmentPickupProof)
        .filter(ShipmentPickupProof.id == proof_id)
        .with_for_update()
        .first()
    )
    if proof is None or proof.customer_id != current_user.id:
        raise HTTPException(404, "Pickup proof not found")

    try:
        return approve_pickup_proof(
            db,
            proof=proof,
            customer_id=current_user.id,
        )
    except PickupProofError as exc:
        db.rollback()
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.post(
    "/pickup-proofs/{proof_id}/report-problem",
    response_model=PickupProofResponse,
)
def report_pickup_proof_problem(
    proof_id: UUID,
    data: PickupProofProblemRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    proof = (
        db.query(ShipmentPickupProof)
        .filter(ShipmentPickupProof.id == proof_id)
        .with_for_update()
        .first()
    )
    if proof is None or proof.customer_id != current_user.id:
        raise HTTPException(404, "Pickup proof not found")

    try:
        return dispute_pickup_proof(
            db,
            proof=proof,
            customer_id=current_user.id,
            reason=data.reason,
            notes=data.notes,
        )
    except PickupProofError as exc:
        db.rollback()
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@router.post("", response_model=OrderResponse, status_code=status.HTTP_201_CREATED)
def create_order(
    data: OrderCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        cart = (
            db.query(Cart)
            .options(
                selectinload(Cart.items).selectinload(CartItem.product),
                selectinload(Cart.items).selectinload(CartItem.variant),
            )
            .filter(Cart.user_id == current_user.id)
            .with_for_update()
            .first()
        )
        if not cart or not cart.items:
            raise HTTPException(status_code=400, detail="Cart is empty")

        address = (
            db.query(Address)
            .filter(
                Address.id == data.shipping_address_id,
                Address.user_id == current_user.id,
            )
            .first()
        )
        if not address:
            raise HTTPException(
                status_code=404,
                detail="Shipping address not found",
            )

        _validate_delivery_mode(db, address, data.delivery_mode, user_id=current_user.id)

        subtotal = Decimal("0.00")
        prepared_items: list[dict] = []
        total_weight_kg = Decimal("0.000")

        for cart_item in cart.items:
            product = cart_item.product
            if (
                not product
                or not product.is_active
                or product.status != ProductStatus.approved
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Product {cart_item.product_id} is no longer available",
                )

            if cart_item.variant_id is not None and (
                cart_item.variant is None
                or cart_item.variant.product_id != product.id
                or not cart_item.variant.is_active
            ):
                raise HTTPException(
                    status_code=409,
                    detail=f"Variant for product {product.id} is invalid",
                )

            inventory = (
                _inventory_query(
                    db,
                    product.id,
                    cart_item.variant_id,
                )
                .with_for_update()
                .first()
            )
            if not inventory or inventory.available_quantity < cart_item.quantity:
                raise HTTPException(
                    status_code=409,
                    detail=f"Insufficient stock for {product.name}",
                )

            listing_price = (
                Decimal(cart_item.variant.sale_price)
                if (
                    cart_item.variant is not None
                    and cart_item.variant.sale_price is not None
                )
                else Decimal(cart_item.variant.price)
                if (
                    cart_item.variant is not None
                    and cart_item.variant.price is not None
                )
                else Decimal(
                    product.sale_price
                    if product.sale_price is not None
                    else product.price
                )
            )
            try:
                current_price = convert_amount_to_tzs(
                    db,
                    listing_price,
                    product.currency,
                )
            except FxRateUnavailableError as exc:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"{product.name} cannot be checked out because its "
                        f"{(product.currency or 'TZS').upper()}/TZS exchange rate is unavailable"
                    ),
                ) from exc

            # If the cart price changed after Phase 3 validation, checkout must
            # stop instead of silently creating an order with a different total.
            if Decimal(cart_item.unit_price) != current_price:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Price changed for {product.name}. "
                        "Refresh your cart before placing the order"
                    ),
                )

            line_total = (
                current_price * cart_item.quantity
            ).quantize(Decimal("0.01"))
            subtotal += line_total

            item_weight = (
                cart_item.variant.weight
                if (
                    cart_item.variant is not None
                    and cart_item.variant.weight is not None
                )
                else product.weight
            )
            total_weight_kg += Decimal(item_weight or 0) * cart_item.quantity

            prepared_items.append(
                {
                    "cart_item": cart_item,
                    "inventory": inventory,
                    "unit_price": current_price,
                    "line_total": line_total,
                    "promotion_discount_amount": Decimal("0.00"),
                    "customer_total": line_total,
                }
            )

        subtotal = subtotal.quantize(Decimal("0.01"))

        coupon = None
        requested_coupon = (
            data.coupon_code
            or cart.coupon_code
        )
        coupon_discount = Decimal("0.00")

        if requested_coupon:
            if (
                cart.coupon_code
                and requested_coupon.strip().upper()
                != cart.coupon_code.strip().upper()
            ):
                raise HTTPException(
                    status_code=409,
                    detail="Cart coupon changed. Refresh checkout and try again",
                )

            coupon = (
                db.query(Coupon)
                .filter(
                    Coupon.code == requested_coupon.strip().upper()
                )
                .with_for_update()
                .first()
            )
            if not coupon:
                raise HTTPException(
                    status_code=404,
                    detail="Coupon not found",
                )

            coupon_discount = _validate_coupon(
                coupon,
                subtotal,
            ).quantize(Decimal("0.01"))

        promotion, promotion_discount = _prepare_product_promotion(
            db,
            cart,
            prepared_items,
            current_user.id,
            data.promotion_code,
        )

        if coupon and promotion and not promotion.stackable:
            raise HTTPException(
                status_code=409,
                detail="The selected seller promotion cannot be combined with the coupon",
            )

        free_shipping = _free_shipping_applies(
            promotion,
            prepared_items,
        )

        delivery_quote = None

        if data.delivery_quote_id is not None:
            try:
                delivery_quote = get_usable_checkout_delivery_quote(
                    db,
                    quote_id=data.delivery_quote_id,
                    user_id=current_user.id,
                    shipping_address_id=data.shipping_address_id,
            delivery_quote_id=(delivery_quote.id if delivery_quote else None),
                    delivery_mode=data.delivery_mode,
                    lock=True,
                )
            except CheckoutDeliveryQuoteError as exc:
                detail = {"code": exc.code, "message": exc.message}
                detail.update(exc.extra)
                raise HTTPException(
                    status_code=exc.status_code,
                    detail=detail,
                ) from exc

            shipping_rate = (
                db.query(ShippingRate)
                .options(
                    selectinload(ShippingRate.zone),
                    selectinload(ShippingRate.method)
                    .selectinload(ShippingMethod.logistics_company),
                )
                .filter(ShippingRate.id == delivery_quote.shipping_rate_id)
                .first()
            )
            if shipping_rate is None or shipping_rate.method is None:
                raise HTTPException(
                    status_code=409,
                    detail="Frozen delivery rate is no longer available",
                )

            logistics_company = shipping_rate.method.logistics_company
            try:
                original_shipping_amount = convert_amount_to_tzs(
                    db,
                    Decimal(delivery_quote.delivery_amount),
                    delivery_quote.currency,
                )
            except FxRateUnavailableError as exc:
                raise HTTPException(
                    status_code=409,
                    detail=f"Frozen delivery quote cannot be converted to TZS: {exc}",
                ) from exc
            shipping_discount_amount = (
                original_shipping_amount
                if free_shipping
                else Decimal("0.00")
            )
            shipping_amount = max(
                Decimal("0.00"),
                original_shipping_amount - shipping_discount_amount,
            ).quantize(Decimal("0.01"))

            now = datetime.now(timezone.utc)
            delivery_from = now + timedelta(
                days=shipping_rate.method.min_delivery_days
            )
            delivery_to = now + timedelta(
                days=shipping_rate.method.max_delivery_days
            )
        else:
            (
                shipping_rate,
                original_shipping_amount,
                shipping_discount_amount,
                shipping_amount,
                delivery_from,
                delivery_to,
                logistics_company,
            ) = _calculate_shipping(
                db,
                address,
                data.shipping_rate_id,
                subtotal,
                total_weight_kg,
                data.delivery_mode,
                free_shipping,
            )

        tax_amount = Decimal("0.00")
        combined_product_discount = min(
            subtotal,
            coupon_discount + promotion_discount,
        ).quantize(Decimal("0.01"))

        total = max(
            Decimal("0.00"),
            subtotal
            - combined_product_discount
            + shipping_amount
            + tax_amount,
        ).quantize(Decimal("0.01"))

        order = Order(
            user_id=current_user.id,
            shipping_address_id=data.shipping_address_id,
            shipping_rate_id=shipping_rate.id,
            shipping_method_id=shipping_rate.method.id,
            shipping_method_name=shipping_rate.method.name,
            shipping_carrier=(
                shipping_rate.method.carrier_name
                or (
                    logistics_company.name
                    if logistics_company
                    else None
                )
            ),
            estimated_delivery_from=delivery_from,
            estimated_delivery_to=delivery_to,
            status=OrderStatus.pending,
            currency="TZS",
            subtotal=subtotal,
            coupon_discount_amount=coupon_discount,
            promotion_discount_amount=promotion_discount,
            discount_amount=combined_product_discount,
            original_shipping_amount=original_shipping_amount,
            shipping_discount_amount=shipping_discount_amount,
            shipping_amount=shipping_amount,
            tax_amount=tax_amount,
            total=total,
            coupon_code=coupon.code if coupon else None,
            promotion_code=promotion.code if promotion else None,
            promotion_seller_id=(
                promotion.seller_id if promotion else None
            ),
            delivery_mode=data.delivery_mode,
            logistics_company_id=(
                logistics_company.id
                if logistics_company
                else None
            ),
            notes=data.notes,
        )
        db.add(order)
        db.flush()

        if delivery_quote is not None:
            delivery_quote.used_at = datetime.now(timezone.utc)

        reservation_expires_at = (
            datetime.now(timezone.utc)
            + timedelta(minutes=settings.INVENTORY_RESERVATION_MINUTES)
        )

        for prepared in prepared_items:
            cart_item = prepared["cart_item"]
            order_item = OrderItem(
                order_id=order.id,
                product_id=cart_item.product_id,
                variant_id=cart_item.variant_id,
                seller_id=cart_item.product.seller_id,
                store_id=cart_item.product.store_id,
                product_name=cart_item.product.name,
                variant_name=(
                    cart_item.variant.variant_name
                    if cart_item.variant
                    else None
                ),
                quantity=cart_item.quantity,
                unit_price=prepared["unit_price"],
                total_price=prepared["line_total"],
                promotion_discount_amount=prepared[
                    "promotion_discount_amount"
                ],
                customer_total=prepared["customer_total"],
            )
            db.add(order_item)
            db.flush()

            create_reservation(
                db,
                inventory=prepared["inventory"],
                order=order,
                order_item_id=order_item.id,
                user_id=current_user.id,
                quantity=cart_item.quantity,
                expires_at=reservation_expires_at,
            )

        _create_status_history(
            db,
            order,
            OrderStatus.pending,
            (
                "Order created; checkout amounts, promotion, "
                "coupon and logistics quote snapshotted"
            ),
            current_user.id,
        )

        if coupon:
            coupon.usage_count += 1

        if promotion:
            promotion.usage_count += 1
            db.add(
                PromotionUsage(
                    promotion_id=promotion.id,
                    user_id=current_user.id,
                    order_id=order.id,
                    # A free-shipping promotion has no product discount but its
                    # shipping benefit is still represented on the order.
                    discount_amount=(
                        promotion_discount
                        + shipping_discount_amount
                    ),
                )
            )

        for cart_item in list(cart.items):
            db.delete(cart_item)

        cart.coupon_code = None
        cart.promotion_code = None

        db.commit()
        db.refresh(order)
        return order

    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail="Could not create order",
        ) from exc

def _admin_order_payment_status(order: Order) -> str | None:
    if not order.payments:
        return None

    priority = {
        PaymentStatus.completed: 5,
        PaymentStatus.processing: 4,
        PaymentStatus.pending: 3,
        PaymentStatus.failed: 2,
        PaymentStatus.refunded: 1,
        PaymentStatus.cancelled: 0,
    }

    payment = max(
        order.payments,
        key=lambda item: priority.get(item.status, -1),
    )
    return payment.status.value if hasattr(payment.status, "value") else str(payment.status)


def _serialize_admin_order(order: Order) -> dict:
    payload = OrderResponse.model_validate(order).model_dump()

    primary_shipment = None
    if order.shipments:
        primary_shipment = sorted(
            order.shipments,
            key=lambda shipment: shipment.created_at or datetime.min.replace(tzinfo=timezone.utc),
        )[0]

    payload.update(
        {
            "payment_status": _admin_order_payment_status(order),
            "user": (
                {
                    "id": order.user.id,
                    "first_name": order.user.first_name,
                    "last_name": order.user.last_name,
                    "email": order.user.email,
                    "phone": order.user.phone,
                }
                if order.user
                else None
            ),
            "payments": [
                {
                    "id": payment.id,
                    "method": (
                        payment.method.value
                        if hasattr(payment.method, "value")
                        else str(payment.method)
                    ),
                    "status": (
                        payment.status.value
                        if hasattr(payment.status, "value")
                        else str(payment.status)
                    ),
                    "amount": payment.amount,
                    "currency": payment.currency,
                    "provider": payment.provider,
                    "transaction_reference": payment.provider_transaction_id,
                    "paid_at": payment.paid_at,
                }
                for payment in sorted(
                    order.payments,
                    key=lambda item: item.created_at or datetime.min.replace(tzinfo=timezone.utc),
                    reverse=True,
                )
            ],
            "address": (
                {
                    "country": order.shipping_address.country,
                    "region": order.shipping_address.region,
                    "city": order.shipping_address.city,
                    "street": order.shipping_address.street,
                    "postal_code": order.shipping_address.postal_code,
                }
                if order.shipping_address
                else None
            ),
            "delivery_method": order.shipping_method_name,
            "courier_name": (
                primary_shipment.carrier_name
                if primary_shipment and primary_shipment.carrier_name
                else order.shipping_carrier
            ),
            "tracking_number": (
                primary_shipment.tracking_number
                if primary_shipment
                else None
            ),
            "estimated_delivery_date": (
                primary_shipment.estimated_delivery_to
                if primary_shipment and primary_shipment.estimated_delivery_to
                else order.estimated_delivery_to
            ),
            "delivered_at": (
                primary_shipment.delivered_at
                if primary_shipment
                else None
            ),
        }
    )

    return payload


def _page_count(total: int, page_size: int) -> int:
    if total <= 0:
        return 0
    return (total + page_size - 1) // page_size


@router.get("/my-orders", response_model=PaginatedOrderResponse)
def get_my_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=150),
    order_status: OrderStatus | None = Query(None, alias="status"),
    payment_status: PaymentStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Customer order history with PostgreSQL filtering before pagination.

    Search covers order id, product name, tracking number, carrier and payment
    provider transaction reference.
    """
    query = db.query(Order).filter(Order.user_id == current_user.id)

    if order_status is not None:
        query = query.filter(Order.status == order_status)

    if payment_status is not None:
        query = query.filter(
            Order.payments.any(Payment.status == payment_status)
        )

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"
        query = query.filter(
            or_(
                cast(Order.id, String).ilike(pattern),
                Order.items.any(OrderItem.product_name.ilike(pattern)),
                Order.payments.any(
                    Payment.provider_transaction_id.ilike(pattern)
                ),
                Order.payments.any(Payment.provider.ilike(pattern)),
                Order.shipments.any(Shipment.tracking_number.ilike(pattern)),
                Order.shipments.any(Shipment.carrier_name.ilike(pattern)),
                Order.shipping_carrier.ilike(pattern),
                Order.shipping_method_name.ilike(pattern),
            )
        )

    total = query.count()
    rows = (
        query.options(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments),
            selectinload(Order.shipments)
            .selectinload(Shipment.tracking_events),
        )
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _page_count(total, page_size),
        "results": rows,
    }


@router.get("/admin/all", response_model=PaginatedAdminOrderResponse)
def list_all_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    order_status: OrderStatus | None = Query(None, alias="status"),
    search: str | None = Query(None, max_length=150),
    payment_status: PaymentStatus | None = Query(None),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("orders:read")),
):
    """
    Scalable admin order listing.

    Search is performed in PostgreSQL before LIMIT/OFFSET pagination and covers:
    order id, customer name/email/phone, product name, tracking number, courier,
    and payment provider transaction reference.
    """
    query = db.query(Order).join(User, Order.user_id == User.id)

    if order_status is not None:
        query = query.filter(Order.status == order_status)

    if payment_status is not None:
        query = query.filter(
            Order.payments.any(Payment.status == payment_status)
        )

    if date_from is not None:
        start = datetime.combine(date_from, datetime.min.time()).replace(
            tzinfo=timezone.utc
        )
        query = query.filter(Order.created_at >= start)

    if date_to is not None:
        end_exclusive = (
            datetime.combine(date_to, datetime.min.time())
            .replace(tzinfo=timezone.utc)
            + timedelta(days=1)
        )
        query = query.filter(Order.created_at < end_exclusive)

    term = (search or "").strip()
    if term:
        pattern = f"%{term}%"

        from api.models import Shipment

        query = query.filter(
            or_(
                cast(Order.id, String).ilike(pattern),
                User.first_name.ilike(pattern),
                User.last_name.ilike(pattern),
                User.email.ilike(pattern),
                User.phone.ilike(pattern),
                Order.items.any(OrderItem.product_name.ilike(pattern)),
                Order.payments.any(
                    Payment.provider_transaction_id.ilike(pattern)
                ),
                Order.payments.any(Payment.provider.ilike(pattern)),
                Order.shipments.any(Shipment.tracking_number.ilike(pattern)),
                Order.shipments.any(Shipment.carrier_name.ilike(pattern)),
                Order.shipping_carrier.ilike(pattern),
                Order.shipping_method_name.ilike(pattern),
            )
        )

    total = query.count()

    rows = (
        query.options(
            selectinload(Order.user),
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments),
            selectinload(Order.shipping_address),
            selectinload(Order.shipments),
        )
        .order_by(Order.created_at.desc(), Order.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": _page_count(total, page_size),
        "results": [_serialize_admin_order(order) for order in rows],
    }


@router.get(
    "/{order_id}/customer-detail",
    response_model=CustomerOrderDetailResponse,
)
def get_customer_order_detail(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(
            selectinload(Order.items),
            selectinload(Order.status_history),
            selectinload(Order.payments),
            selectinload(Order.shipping_address),
            selectinload(Order.shipments)
            .selectinload(Shipment.items),
            selectinload(Order.shipments)
            .selectinload(Shipment.tracking_events),
            selectinload(Order.seller_orders),
        )
        .filter(
            Order.id == order_id,
            Order.user_id == current_user.id,
        )
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "id": order.id,
        "user_id": order.user_id,
        "shipping_address_id": order.shipping_address_id,
        "shipping_rate_id": order.shipping_rate_id,
        "shipping_method_id": order.shipping_method_id,
        "shipping_method_name": order.shipping_method_name,
        "shipping_carrier": order.shipping_carrier,
        "estimated_delivery_from": order.estimated_delivery_from,
        "estimated_delivery_to": order.estimated_delivery_to,
        "status": order.status,
        "currency": order.currency,
        "subtotal": order.subtotal,
        "coupon_discount_amount": order.coupon_discount_amount,
        "promotion_discount_amount": order.promotion_discount_amount,
        "discount_amount": order.discount_amount,
        "original_shipping_amount": order.original_shipping_amount,
        "shipping_discount_amount": order.shipping_discount_amount,
        "shipping_amount": order.shipping_amount,
        "tax_amount": order.tax_amount,
        "total": order.total,
        "coupon_code": order.coupon_code,
        "promotion_code": order.promotion_code,
        "promotion_seller_id": order.promotion_seller_id,
        "delivery_mode": order.delivery_mode,
        "logistics_company_id": order.logistics_company_id,
        "notes": order.notes,
        "items": order.items,
        "status_history": order.status_history,
        "created_at": order.created_at,
        "updated_at": order.updated_at,
        "payment_status": _customer_payment_status(order),
        "payments": order.payments,
        "shipping_address": order.shipping_address,
        "shipments": order.shipments,
        "seller_orders": order.seller_orders,
    }


@router.get("/{order_id}/escrow", response_model=CustomerEscrowSummary)
def customer_order_escrow(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(
            selectinload(Order.payments),
            selectinload(Order.shipments),
        )
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order_escrow_summary(db, order)


@router.post("/{order_id}/approve-receipt", response_model=CustomerEscrowSummary)
def approve_order_receipt(
    order_id: UUID,
    data: CustomerEscrowApprovalRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(
            selectinload(Order.payments),
            selectinload(Order.shipments),
        )
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    summary = order_escrow_summary(db, order)
    if summary["status"] == "released":
        return summary
    if summary["status"] == "not_applicable":
        raise HTTPException(status_code=409, detail="This order has no online-payment escrow")
    if summary["status"] == "disputed":
        raise HTTPException(status_code=409, detail="This order is under dispute")
    if not summary["can_customer_approve"]:
        raise HTTPException(
            status_code=409,
            detail="Receipt can be approved only after all shipments are marked delivered and payment is confirmed",
        )

    try:
        release_order_escrow(
            db,
            order=order,
            created_by_id=current_user.id,
            note=data.note or "Customer confirmed successful receipt of the order",
            event_type="customer_approved",
        )
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    if order.status not in {OrderStatus.cancelled, OrderStatus.refunded}:
        order.status = OrderStatus.delivered
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                status=OrderStatus.delivered.value,
                notes="Customer approved receipt; seller escrow funds released",
                created_by_id=current_user.id,
            )
        )

    db.commit()
    db.refresh(order)
    return order_escrow_summary(db, order)




@router.get("/{order_id}/invoice.pdf")
def download_customer_invoice(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(
            selectinload(Order.items).selectinload(OrderItem.store),
            selectinload(Order.payments),
            selectinload(Order.shipping_address),
            selectinload(Order.user),
        )
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to download this invoice")

    logistics_company = None
    if order.logistics_company_id:
        logistics_company = (
            db.query(LogisticsCompany)
            .filter(LogisticsCompany.id == order.logistics_company_id)
            .first()
        )

    pdf = build_order_invoice_pdf(order, logistics_company=logistics_company)
    created = order.created_at.strftime("%Y%m%d")
    filename = f"Xerin-Invoice-{created}-{str(order.id)[:8].upper()}.pdf"
    return StreamingResponse(
        iter([pdf]),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "private, no-store",
        },
    )

@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_order_seller(current_user, order) and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this order")
    return order


@router.get("/{order_id}/workflow", response_model=OrderWorkflowResponse)
def get_order_workflow(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order_id)
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.user_id != current_user.id and not _is_order_seller(current_user, order) and not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Not authorized to view this workflow")
    return build_order_workflow(db, order)


@router.post("/{order_id}/workflow/reconcile", response_model=OrderWorkflowResponse)
def reconcile_order_workflow_endpoint(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not _is_privileged_order_operator(db, current_user):
        raise HTTPException(status_code=403, detail="Order operations permission is required")
    order = (
        db.query(Order)
        .options(selectinload(Order.items))
        .filter(Order.id == order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    try:
        return reconcile_order_workflow(db, order, actor_id=current_user.id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not reconcile order workflow") from exc


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
        is_seller = _is_order_seller(current_user, order)

        if is_buyer:
            if new_status != OrderStatus.cancelled or order.status != OrderStatus.pending:
                raise HTTPException(status_code=403, detail="Buyers may only cancel pending orders")
        elif not is_operator and not is_seller:
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
        _create_status_history(db, order, new_status, data.notes, current_user.id)
        db.commit()
        db.refresh(order)
        return order
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="Could not update order status") from exc

