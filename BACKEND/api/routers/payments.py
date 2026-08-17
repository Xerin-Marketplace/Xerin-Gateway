import hmac
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from sqlalchemy import String, cast, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, joinedload, selectinload

from api.config import settings
from api.deps import get_current_user, get_db
from api.models import (
    FinanceSettings,
    LogisticsCompany,
    MarketplaceSettings,
    Order,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentTransaction,
    ShippingMethod,
    Shipment,
    ShipmentItem,
    ShipmentStatus,
    ShipmentTrackingEvent,
    SellerOrder,
    User,
)
from api.permissions import require_permission
from api.schemas import (
    AzamPayCheckoutCallbackRequest,
    AzamPayDiagnosticsResponse,
    PaymentCallbackRequest,
    PaymentInitiateRequest,
    PaymentRetryRequest,
    PaginatedPaymentResponse,
    PaymentResponse,
    NameLookupRequest,
    NameLookupResponse,
    OrderPaymentStateResponse,
)
from api.enums import InventoryReservationStatus, SellerOrderStatus
from api.services.azampay_service import AzamPayAPIError, AzamPayClient, AzamPayConfigurationError
from api.services.inventory_reservations import commit_order_reservations, ensure_order_reservations_active, release_order_reservations
from api.services.commission_engine import calculate_order_commissions
from api.services.escrow_service import create_order_escrow_holds

router = APIRouter(prefix="/payments", tags=["Payments"])

SUCCESS_STATUSES = {"success", "completed", "paid"}
FAILED_STATUSES = {"failed", "failure"}
CANCELLED_STATUSES = {"cancelled", "canceled"}


def _verify_webhook_secret(received_secret: str | None) -> None:
    configured = settings.PAYMENT_WEBHOOK_SECRET
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Payment webhook secret is not configured",
        )
    if not received_secret or not hmac.compare_digest(received_secret, configured):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid payment webhook signature")


def _record_transaction(
    db: Session,
    payment: Payment,
    transaction_type: str,
    transaction_status: str,
    amount: Decimal | None = None,
    provider_response: dict | None = None,
    *,
    idempotency_key: str | None = None,
) -> PaymentTransaction:
    tx = PaymentTransaction(
        payment_id=payment.id,
        transaction_type=transaction_type,
        status=transaction_status,
        amount=amount,
        provider_response=provider_response or {},
        idempotency_key=idempotency_key,
    )
    db.add(tx)
    return tx


def _callback_idempotency_key(
    provider: str,
    payment_id: UUID,
    transaction_id: str,
    event_status: str,
) -> str:
    """Stable DB key for provider callback replay protection."""
    return (
        f"{provider.lower().strip()}:{payment_id}:{transaction_id.strip()}:{event_status.lower().strip()}"
    )[:255]


def _callback_already_processed(db: Session, key: str) -> bool:
    return (
        db.query(PaymentTransaction.id)
        .filter(PaymentTransaction.idempotency_key == key)
        .first()
        is not None
    )


def _deduct_reserved_inventory(db: Session, order: Order) -> None:
    commit_order_reservations(db, order)



def _create_shipments_for_order(db: Session, order: Order) -> None:
    existing = {row.seller_id for row in db.query(Shipment).filter(Shipment.order_id == order.id).all()}
    grouped: dict[UUID, list] = {}
    for item in order.items:
        grouped.setdefault(item.seller_id, []).append(item)
    for seller_id, items in grouped.items():
        seller_order = db.query(SellerOrder).filter(
            SellerOrder.order_id == order.id,
            SellerOrder.seller_id == seller_id,
        ).first()
        if seller_order is None:
            db.add(SellerOrder(
                order_id=order.id,
                seller_id=seller_id,
                status=SellerOrderStatus.new,
                seller_subtotal=sum((Decimal(item.total_price) for item in items), Decimal("0.00")),
                item_count=sum(item.quantity for item in items),
            ))
        if seller_id in existing:
            continue
        shipment = Shipment(
            order_id=order.id,
            seller_id=seller_id,
            shipping_method_id=order.shipping_method_id,
            status=ShipmentStatus.pending,
            carrier_name=order.shipping_carrier,
            estimated_delivery_from=order.estimated_delivery_from,
            estimated_delivery_to=order.estimated_delivery_to,
        )
        db.add(shipment)
        db.flush()
        for item in items:
            db.add(ShipmentItem(shipment_id=shipment.id, order_item_id=item.id, quantity=item.quantity))
        db.add(ShipmentTrackingEvent(
            shipment_id=shipment.id,
            status=ShipmentStatus.pending,
            notes="Shipment created after payment confirmation",
        ))

def _commit(db: Session, *, conflict_detail: str = "Payment conflict") -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_detail) from exc
    except Exception:
        db.rollback()
        raise
    
    
@router.post(
    "/name-lookup",
    response_model=NameLookupResponse
)
def payment_name_lookup(
    data: NameLookupRequest,
):
    """
    Verify a Mobile Money account before payment/disbursement.
    """

    client = AzamPayClient()
    try:
        normalized_provider = client.normalize_mno(data.provider)
        result = client.name_lookup(
            phone_number=data.phone_number,
            provider=normalized_provider,
        )
        return {
            "success": True,
            "account_name": result.get("accountName") or result.get("data", {}).get("accountName"),
            "provider": normalized_provider,
            "phone_number": data.phone_number,
            "message": result.get("message"),
        }
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AzamPayConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except AzamPayAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail={"provider": "azampay", "message": str(exc)},
        ) from exc

def _finance_settings(db: Session) -> FinanceSettings | None:
    return (
        db.query(FinanceSettings)
        .filter(FinanceSettings.singleton_key == "default")
        .first()
    )


def _marketplace_settings(db: Session) -> MarketplaceSettings | None:
    return (
        db.query(MarketplaceSettings)
        .filter(MarketplaceSettings.singleton_key == 1)
        .first()
    )


def _escrow_release_after(db: Session) -> datetime | None:
    marketplace = _marketplace_settings(db)
    if not marketplace or not marketplace.escrow_release_hours:
        return None
    return datetime.now(timezone.utc) + timedelta(
        hours=marketplace.escrow_release_hours
    )


def _validate_cod_for_order(db: Session, order: Order) -> None:
    marketplace = _marketplace_settings(db)

    if order.delivery_mode != "local":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cash on Delivery is only available for local Tanzania delivery",
        )

    if not marketplace or not marketplace.cod_allowed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cash on Delivery is disabled by marketplace settings",
        )

    method = (
        db.query(ShippingMethod)
        .options(joinedload(ShippingMethod.logistics_company))
        .filter(ShippingMethod.id == order.shipping_method_id)
        .first()
    )
    if not method or not method.is_active or not method.supports_cod:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The selected delivery service does not support Cash on Delivery",
        )

    company = method.logistics_company
    if company:
        company_status = (
            company.status.value
            if hasattr(company.status, "value")
            else str(company.status)
        )
        if company_status != "active" or not company.supports_cod:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The selected logistics company does not support Cash on Delivery",
            )


def _finalise_online_payment(
    db: Session,
    *,
    order: Order,
    payment: Payment,
    provider_name: str,
) -> None:
    _deduct_reserved_inventory(db, order)
    _create_shipments_for_order(db, order)

    finance = _finance_settings(db)
    escrow_enabled = bool(finance is None or finance.escrow_enabled)
    release_after = _escrow_release_after(db) if escrow_enabled else None

    commission_records = calculate_order_commissions(
        db,
        order,
        settlement_eligible_at=release_after,
    )

    if escrow_enabled:
        create_order_escrow_holds(
            db,
            order=order,
            payment=payment,
            commission_records=commission_records,
            release_after=release_after,
        )

    order.status = OrderStatus.paid
    db.add(
        OrderStatusHistory(
            order_id=order.id,
            status=OrderStatus.paid.value,
            notes=(
                f"Payment confirmed via {provider_name}; "
                + (
                    "seller settlement placed in escrow"
                    if escrow_enabled
                    else "seller settlement recorded"
                )
            ),
        )
    )


@router.get(
    "/azampay/diagnostics",
    response_model=AzamPayDiagnosticsResponse,
)
def azampay_diagnostics(
    current_user: User = Depends(
        require_permission("payment_providers:read")
    ),
):
    """Safe merchant diagnostics. Never returns tokens, secrets, or API keys."""
    del current_user
    client = AzamPayClient()

    base = {
        "environment": "sandbox" if settings.AZAMPAY_SANDBOX else "live",
        "base_url": client.base_url,
        "authentication": "failed",
        "merchant_configured": False,
        "payment_partners_status": "skipped",
        "partners": [],
        "provider_names": [],
        "error_code": None,
        "error_message": None,
        "provider_status": None,
    }

    try:
        # Do not expose the token. This call only proves authentication works.
        client.get_token(force_refresh=True)
        base["authentication"] = "ok"
    except AzamPayConfigurationError as exc:
        base["error_code"] = "configuration_error"
        base["error_message"] = str(exc)
        return base
    except AzamPayAPIError as exc:
        base["error_code"] = str(
            exc.payload.get("code") or "authentication_error"
        )
        base["error_message"] = str(exc)
        base["provider_status"] = exc.status_code
        return base

    try:
        rows = client.payment_partners()
    except AzamPayAPIError as exc:
        base["payment_partners_status"] = "failed"
        base["error_code"] = str(
            exc.payload.get("code") or "payment_partners_error"
        )
        base["error_message"] = str(exc)
        base["provider_status"] = exc.status_code
        return base

    partners = [
        {
            "logo_url": row.get("logoUrl"),
            "partner_name": row.get("partnerName"),
            "provider": row.get("provider"),
            "vendor_name": row.get("vendorName"),
            "payment_vendor_id": row.get("paymentVendorId"),
            "payment_partner_id": row.get("paymentPartnerId"),
            "currency": row.get("currency"),
        }
        for row in rows
    ]

    provider_names = sorted(
        {
            str(row.get("partnerName")).strip()
            for row in rows
            if row.get("partnerName")
        }
    )

    base["payment_partners_status"] = "ok"
    base["partners"] = partners
    base["provider_names"] = provider_names
    base["merchant_configured"] = bool(rows)
    return base


def _execute_azampay_payment(
    *,
    client: AzamPayClient,
    payment: Payment,
    order: Order,
    method: PaymentMethod,
    mno_provider: str | None,
    phone_number: str | None,
    success_url: str | None,
    failure_url: str | None,
):
    if method == PaymentMethod.mobile_money:
        if not mno_provider or not phone_number:
            raise ValueError("provider and phone_number are required for mobile money")
        return client.mobile_checkout(
            amount=Decimal(order.total),
            currency=order.currency,
            phone_number=phone_number,
            provider=mno_provider,
            external_id=str(payment.id),
            additional_properties={
                "order_id": str(order.id),
                "payment_id": str(payment.id),
            },
        )
    if method == PaymentMethod.card:
        resolved_success_url = success_url or settings.AZAMPAY_CARD_SUCCESS_URL
        resolved_failure_url = failure_url or settings.AZAMPAY_CARD_FAILURE_URL
        if not resolved_success_url or not resolved_failure_url:
            raise AzamPayConfigurationError(
                "Card checkout requires success_url and failure_url, or configured defaults"
            )
        cart_items = [
            {
                "name": getattr(item, "product_name", None) or f"Order item {item.id}",
                "quantity": item.quantity,
                "price": format(Decimal(item.unit_price), "f"),
            }
            for item in order.items
        ]
        return client.card_checkout(
            amount=Decimal(order.total),
            currency=order.currency,
            external_id=payment.id.hex[:30],
            success_url=resolved_success_url,
            failure_url=resolved_failure_url,
            cart={"items": cart_items},
        )
    raise ValueError("AzamPay supports mobile_money and card methods")


def _payment_error_detail(
    *,
    code: str,
    message: str,
    payment: Payment,
    order: Order,
    retryable: bool,
    provider_status: int | None = None,
) -> dict:
    detail = {
        "code": code,
        "message": message,
        "provider": payment.provider or "azampay",
        "order_id": str(order.id),
        "payment_id": str(payment.id),
        "retryable": retryable,
    }
    if provider_status is not None:
        detail["provider_status"] = provider_status
    return detail


@router.post("/initiate", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def initiate_payment(data: PaymentInitiateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == data.order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to pay for this order")
    if order.status != OrderStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending orders can be paid")
    ensure_order_reservations_active(db, order)

    method = data.method if isinstance(data.method, PaymentMethod) else PaymentMethod(data.method)
    provider = (data.provider or ("azampay" if method in {PaymentMethod.mobile_money, PaymentMethod.card} else "")).lower().strip() or None
    if method == PaymentMethod.mobile_money and (not data.provider or not data.phone_number):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="provider and phone_number are required for mobile money")
    if method in {PaymentMethod.mobile_money, PaymentMethod.card} and provider != "azampay" and method == PaymentMethod.card:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Card payments currently support AzamPay only")

    existing = (
        db.query(Payment)
        .filter(
            Payment.order_id == order.id,
            Payment.status.in_(
                [
                    PaymentStatus.pending,
                    PaymentStatus.processing,
                    PaymentStatus.completed,
                ]
            ),
        )
        .order_by(Payment.created_at.desc())
        .with_for_update()
        .first()
    )
    if existing:
        detail = "Order is already paid" if existing.status == PaymentStatus.completed else "A payment is already in progress for this order"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    payment = Payment(
        order_id=order.id,
        user_id=current_user.id,
        amount=order.total,
        currency=order.currency,
        method=method,
        provider="azampay" if method in {PaymentMethod.mobile_money, PaymentMethod.card} else provider,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.flush()

    _record_transaction(db, payment, "initiate", PaymentStatus.pending.value, order.total, {
        "payment_reference": str(payment.id),
        "method": method.value,
        "provider": payment.provider,
        "mno": data.provider if method == PaymentMethod.mobile_money else None,
        "phone": data.phone_number,
    })

    if method == PaymentMethod.cash_on_delivery:
        _validate_cod_for_order(db, order)

        # COD has no captured digital funds yet, so no escrow hold is created.
        # Inventory is committed and seller fulfilment begins immediately.
        _deduct_reserved_inventory(db, order)
        _create_shipments_for_order(db, order)
        order.status = OrderStatus.processing

        _record_transaction(
            db,
            payment,
            "cod_authorized",
            PaymentStatus.pending.value,
            order.total,
            {
                "payment_reference": str(payment.id),
                "collection_status": "awaiting_delivery_collection",
                "shipping_method_id": (
                    str(order.shipping_method_id)
                    if order.shipping_method_id
                    else None
                ),
                "logistics_company_id": (
                    str(order.logistics_company_id)
                    if order.logistics_company_id
                    else None
                ),
            },
        )
        db.add(
            OrderStatusHistory(
                order_id=order.id,
                status=OrderStatus.processing.value,
                notes="Cash on Delivery order accepted; payment will be collected on delivery",
            )
        )
        _commit(db)
        db.refresh(payment)
        return payment

    if payment.provider != "azampay":
        payment.status = PaymentStatus.processing
        _record_transaction(db, payment, "provider_request", PaymentStatus.processing.value, order.total, {
            "integration_status": "pending_real_provider_integration",
        })
        _commit(db)
        db.refresh(payment)
        return payment

    client = AzamPayClient()
    try:
        if method == PaymentMethod.mobile_money:
            result = client.mobile_checkout(
                amount=Decimal(order.total),
                currency=order.currency,
                phone_number=data.phone_number or "",
                provider=data.provider or "",
                external_id=str(payment.id),
                additional_properties={"order_id": str(order.id), "payment_id": str(payment.id)},
            )
        elif method == PaymentMethod.card:
            success_url = data.success_url or settings.AZAMPAY_CARD_SUCCESS_URL
            failure_url = data.failure_url or settings.AZAMPAY_CARD_FAILURE_URL
            if not success_url or not failure_url:
                raise AzamPayConfigurationError("Card checkout requires success_url and failure_url, or configured defaults")
            cart_items = [
                {
                    "name": getattr(item, "product_name", None) or f"Order item {item.id}",
                    "quantity": item.quantity,
                    "price": format(Decimal(item.unit_price), "f"),
                }
                for item in order.items
            ]
            result = client.card_checkout(
                amount=Decimal(order.total),
                currency=order.currency,
                external_id=payment.id.hex[:30],
                success_url=success_url,
                failure_url=failure_url,
                cart={"items": cart_items},
            )
        else:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="AzamPay supports mobile_money and card methods")
    except ValueError as exc:
        payment.status = PaymentStatus.failed
        payment.failure_reason = str(exc)
        _record_transaction(
            db,
            payment,
            "provider_rejected",
            PaymentStatus.failed.value,
            order.total,
            {
                "provider": "azampay",
                "code": "invalid_payment_request",
                "message": str(exc),
                "retryable": False,
            },
        )
        _commit(db)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "INVALID_PAYMENT_REQUEST",
                "message": str(exc),
                "provider": "azampay",
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "retryable": False,
            },
        ) from exc
    except AzamPayConfigurationError as exc:
        payment.status = PaymentStatus.failed
        payment.failure_reason = str(exc)
        _record_transaction(
            db,
            payment,
            "provider_configuration_error",
            PaymentStatus.failed.value,
            order.total,
            {
                "provider": "azampay",
                "code": "provider_configuration_error",
                "message": str(exc),
                "retryable": False,
            },
        )
        _commit(db)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "PAYMENT_PROVIDER_CONFIGURATION_ERROR",
                "message": str(exc),
                "provider": "azampay",
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "retryable": False,
            },
        ) from exc
    except AzamPayAPIError as exc:
        payment.status = PaymentStatus.failed
        payment.failure_reason = str(exc)
        provider_code = str(
            exc.payload.get("code")
            or exc.payload.get("error")
            or "provider_error"
        )
        _record_transaction(
            db,
            payment,
            "provider_error",
            PaymentStatus.failed.value,
            order.total,
            {
                "provider": "azampay",
                "provider_status": exc.status_code,
                "code": provider_code,
                "message": str(exc),
                "retryable": exc.retryable,
            },
        )
        _commit(db)

        http_status = (
            exc.status_code
            if exc.status_code in {502, 503, 504}
            else status.HTTP_502_BAD_GATEWAY
        )
        raise HTTPException(
            status_code=http_status,
            detail={
                "code": "PAYMENT_PROVIDER_UNAVAILABLE"
                if exc.retryable
                else "PAYMENT_PROVIDER_ERROR",
                "message": str(exc),
                "provider": "azampay",
                "provider_status": exc.status_code,
                "order_id": str(order.id),
                "payment_id": str(payment.id),
                "retryable": exc.retryable,
            },
        ) from exc

    payment.status = PaymentStatus.processing
    payment.provider_transaction_id = result.transaction_id
    payment.provider_response = {
        **result.raw,
        "checkout_url": result.checkout_url,
        "message": result.message,
        "mno": data.provider if method == PaymentMethod.mobile_money else None,
    }
    _record_transaction(db, payment, "provider_request", PaymentStatus.processing.value, order.total, payment.provider_response)
    _commit(db, conflict_detail="AzamPay transaction conflict")
    db.refresh(payment)
    return payment


@router.post("/{payment_id}/retry", response_model=PaymentResponse)
def retry_payment(
    payment_id: UUID,
    data: PaymentRetryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to retry this payment")

    order = (
        db.query(Order)
        .filter(Order.id == payment.order_id)
        .with_for_update()
        .first()
    )
    if not order:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment order no longer exists")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to pay for this order")
    if order.status != OrderStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending orders can retry payment",
        )
    if payment.status == PaymentStatus.completed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed payment cannot be retried")
    if payment.status in {PaymentStatus.pending, PaymentStatus.processing}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This payment is still active; wait for its result before retrying",
        )
    if payment.status not in {PaymentStatus.failed, PaymentStatus.cancelled}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Payment in {payment.status.value} status cannot be retried",
        )
    if payment.method not in {PaymentMethod.mobile_money, PaymentMethod.card} or (payment.provider or "").lower() != "azampay":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Only failed or cancelled AzamPay online payments can be retried",
        )

    # A failed provider attempt must not have consumed the order's stock hold.
    ensure_order_reservations_active(db, order)

    active_other = (
        db.query(Payment)
        .filter(
            Payment.order_id == order.id,
            Payment.id != payment.id,
            Payment.status.in_(
                [PaymentStatus.pending, PaymentStatus.processing, PaymentStatus.completed]
            ),
        )
        .with_for_update()
        .first()
    )
    if active_other:
        detail = (
            "Order is already paid"
            if active_other.status == PaymentStatus.completed
            else "Another payment is already active for this order"
        )
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    # Each retry is a NEW Payment row and therefore a NEW AzamPay externalId.
    # The order itself is reused, preventing duplicate orders.
    attempt = Payment(
        order_id=order.id,
        user_id=current_user.id,
        amount=order.total,
        currency=order.currency,
        method=payment.method,
        provider="azampay",
        status=PaymentStatus.pending,
    )
    db.add(attempt)
    db.flush()

    mno_provider = data.provider
    phone_number = data.phone_number
    if attempt.method == PaymentMethod.mobile_money:
        if not mno_provider:
            previous = payment.provider_response or {}
            mno_provider = previous.get("mno")
        if not mno_provider or not phone_number:
            attempt.status = PaymentStatus.failed
            attempt.failure_reason = "provider and phone_number are required to retry mobile money"
            _record_transaction(
                db, attempt, "retry_rejected", PaymentStatus.failed.value, order.total,
                {
                    "previous_payment_id": str(payment.id),
                    "retryable": False,
                    "message": attempt.failure_reason,
                },
            )
            _commit(db)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=_payment_error_detail(
                    code="INVALID_PAYMENT_RETRY",
                    message=attempt.failure_reason,
                    payment=attempt,
                    order=order,
                    retryable=False,
                ),
            )

    _record_transaction(
        db,
        attempt,
        "retry_initiate",
        PaymentStatus.pending.value,
        order.total,
        {
            "previous_payment_id": str(payment.id),
            "payment_reference": str(attempt.id),
            "method": attempt.method.value,
            "provider": "azampay",
            "mno": mno_provider if attempt.method == PaymentMethod.mobile_money else None,
        },
    )

    client = AzamPayClient()
    try:
        result = _execute_azampay_payment(
            client=client,
            payment=attempt,
            order=order,
            method=attempt.method,
            mno_provider=mno_provider,
            phone_number=phone_number,
            success_url=data.success_url,
            failure_url=data.failure_url,
        )
    except ValueError as exc:
        attempt.status = PaymentStatus.failed
        attempt.failure_reason = str(exc)
        _record_transaction(
            db, attempt, "provider_rejected", PaymentStatus.failed.value, order.total,
            {
                "previous_payment_id": str(payment.id),
                "code": "invalid_payment_request",
                "message": str(exc),
                "retryable": False,
            },
        )
        _commit(db)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=_payment_error_detail(
                code="INVALID_PAYMENT_REQUEST",
                message=str(exc),
                payment=attempt,
                order=order,
                retryable=False,
            ),
        ) from exc
    except AzamPayConfigurationError as exc:
        attempt.status = PaymentStatus.failed
        attempt.failure_reason = str(exc)
        _record_transaction(
            db, attempt, "provider_configuration_error", PaymentStatus.failed.value, order.total,
            {
                "previous_payment_id": str(payment.id),
                "message": str(exc),
                "retryable": False,
            },
        )
        _commit(db)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_payment_error_detail(
                code="PAYMENT_PROVIDER_CONFIGURATION_ERROR",
                message=str(exc),
                payment=attempt,
                order=order,
                retryable=False,
            ),
        ) from exc
    except AzamPayAPIError as exc:
        attempt.status = PaymentStatus.failed
        attempt.failure_reason = str(exc)
        _record_transaction(
            db, attempt, "provider_error", PaymentStatus.failed.value, order.total,
            {
                "previous_payment_id": str(payment.id),
                "provider_status": exc.status_code,
                "code": str(exc.payload.get("code") or exc.payload.get("error") or "provider_error"),
                "message": str(exc),
                "retryable": exc.retryable,
            },
        )
        _commit(db)
        raise HTTPException(
            status_code=(
                exc.status_code
                if exc.status_code in {502, 503, 504}
                else status.HTTP_502_BAD_GATEWAY
            ),
            detail=_payment_error_detail(
                code="PAYMENT_PROVIDER_UNAVAILABLE" if exc.retryable else "PAYMENT_PROVIDER_ERROR",
                message=str(exc),
                payment=attempt,
                order=order,
                retryable=exc.retryable,
                provider_status=exc.status_code,
            ),
        ) from exc

    attempt.status = PaymentStatus.processing
    attempt.provider_transaction_id = result.transaction_id
    attempt.provider_response = {
        **result.raw,
        "checkout_url": result.checkout_url,
        "message": result.message,
        "mno": mno_provider if attempt.method == PaymentMethod.mobile_money else None,
        "previous_payment_id": str(payment.id),
    }
    _record_transaction(
        db,
        attempt,
        "provider_request",
        PaymentStatus.processing.value,
        order.total,
        attempt.provider_response,
    )
    _commit(db, conflict_detail="AzamPay retry transaction conflict")
    db.refresh(attempt)
    return attempt


@router.post("/callback/{provider}", response_model=PaymentResponse)
def payment_callback(
    provider: str,
    data: PaymentCallbackRequest,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    _verify_webhook_secret(x_webhook_secret)
    return _apply_payment_callback(provider, data, db)


def _apply_payment_callback(provider: str, data: PaymentCallbackRequest, db: Session) -> Payment:
    normalized_provider = provider.lower().strip()
    if data.provider.lower().strip() != normalized_provider:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Provider path and payload do not match")

    payment = db.query(Payment).filter(Payment.id == data.payment_id).with_for_update().first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if (payment.provider or "").lower() != normalized_provider:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment provider does not match callback provider")

    conflicting = db.query(Payment).filter(
        Payment.provider_transaction_id == data.transaction_id,
        Payment.id != payment.id,
    ).first()
    if conflicting:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Provider transaction ID is already linked to another payment")

    incoming_status = (
        data.status.value
        if isinstance(data.status, PaymentStatus)
        else str(data.status).lower()
    )
    callback_key = _callback_idempotency_key(
        normalized_provider,
        payment.id,
        data.transaction_id,
        incoming_status,
    )

    if _callback_already_processed(db, callback_key):
        return payment

    if payment.status == PaymentStatus.completed:
        if (
            payment.provider_transaction_id == data.transaction_id
            and incoming_status
            in SUCCESS_STATUSES | {PaymentStatus.completed.value}
        ):
            return payment
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Completed payment cannot be changed by another callback",
        )

    callback_payload = dict(data.payload or {})
    callback_payload.update(
        {
            "payment_id": str(payment.id),
            "provider_transaction_id": data.transaction_id,
            "idempotency_key": callback_key,
        }
    )
    _record_transaction(
        db,
        payment,
        "callback",
        incoming_status,
        payment.amount,
        callback_payload,
        idempotency_key=callback_key,
    )

    if incoming_status in SUCCESS_STATUSES or incoming_status == PaymentStatus.completed.value:
        if payment.status not in {PaymentStatus.pending, PaymentStatus.processing}:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Cannot complete a payment in {payment.status.value} status")
        order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
        if not order:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Payment order no longer exists")
        if order.status == OrderStatus.paid:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Order is already marked as paid")
        if order.status != OrderStatus.pending:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Order cannot be paid from {order.status.value} status")

        payment.status = PaymentStatus.completed
        payment.paid_at = datetime.now(timezone.utc)
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload

        _finalise_online_payment(
            db,
            order=order,
            payment=payment,
            provider_name=normalized_provider,
        )
    elif incoming_status in FAILED_STATUSES or incoming_status == PaymentStatus.failed.value:
        payment.status = PaymentStatus.failed
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
        payment.failure_reason = callback_payload.get("reason")
        order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
        if order and order.status == OrderStatus.pending:
            # Keep the order and its inventory reservation alive so the customer
            # can retry payment without rebuilding the cart or creating a new order.
            db.add(OrderStatusHistory(
                order_id=order.id,
                status=OrderStatus.pending.value,
                notes="Payment attempt failed; order preserved for payment retry",
            ))
    elif incoming_status in CANCELLED_STATUSES or incoming_status == PaymentStatus.cancelled.value:
        payment.status = PaymentStatus.cancelled
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
        order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
        if order and order.status == OrderStatus.pending:
            db.add(OrderStatusHistory(
                order_id=order.id,
                status=OrderStatus.pending.value,
                notes="Payment attempt cancelled by provider; order preserved for payment retry",
            ))
    else:
        payment.status = PaymentStatus.processing
        payment.provider_response = callback_payload

    _commit(db, conflict_detail="Duplicate or conflicting payment callback")
    db.refresh(payment)
    return payment


@router.post("/azampay/callback", status_code=status.HTTP_200_OK)
def azampay_callback(
    payload: AzamPayCheckoutCallbackRequest,
    db: Session = Depends(get_db),
):
    """Receive AzamPay Tanzania Checkout completion callbacks.

    This route intentionally has no end-user authentication because AzamPay
    calls it server-to-server. Task 6 adds RSA signature verification using the
    signed-data contract published by AzamPay.
    """

    utility_ref = payload.utilityref.strip()
    external_reference = payload.externalreference.strip()
    incoming_status = payload.transactionstatus.strip().lower()
    operator = payload.operator.strip()

    if not payload.signature:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="AzamPay callback signature is required",
        )

    client = AzamPayClient()
    try:
        signature_valid = client.verify_callback_signature(
            utility_ref=utility_ref,
            external_reference=external_reference,
            transaction_status=payload.transactionstatus,
            operator_name=payload.operator,
            signature_b64=payload.signature,
        )
    except AzamPayConfigurationError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AzamPay callback verification is not configured",
        ) from exc
    except AzamPayAPIError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "AZAMPAY_PUBLIC_KEY_UNAVAILABLE",
                "message": str(exc),
                "provider_status": exc.status_code,
            },
        ) from exc

    if not signature_valid:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid AzamPay callback signature",
        )

    # Xerin sends payment.id as the MNO checkout externalId. AzamPay returns
    # the partner/calling-application reference as utilityref in the callback.
    try:
        payment_id = UUID(utility_ref)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid AzamPay utilityref payment reference",
        ) from exc

    payment = (
        db.query(Payment)
        .filter(Payment.id == payment_id)
        .with_for_update()
        .first()
    )
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Payment referenced by AzamPay callback was not found",
        )

    if (payment.provider or "").lower() != "azampay":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AzamPay callback references a non-AzamPay payment",
        )

    # Prefer AzamPay's transaction ID; use reference only as a fallback.
    provider_transaction_id = (
        payload.transid.strip()
        or payload.reference.strip()
        or external_reference
    )

    # Validate callback amount against our immutable order/payment snapshot.
    try:
        callback_amount = Decimal(payload.amount)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="AzamPay callback contains an invalid amount",
        ) from exc

    if callback_amount != Decimal(payment.amount):
        rejection_key = _callback_idempotency_key(
            "azampay",
            payment.id,
            provider_transaction_id,
            "amount_mismatch",
        )
        if not _callback_already_processed(db, rejection_key):
            _record_transaction(
                db,
                payment,
                "callback_rejected",
                "amount_mismatch",
                payment.amount,
                {
                    "provider": "azampay",
                    "utilityref": utility_ref,
                    "externalreference": external_reference,
                    "transactionstatus": incoming_status,
                    "operator": operator,
                    "callback_amount": str(callback_amount),
                    "expected_amount": str(payment.amount),
                    "idempotency_key": rejection_key,
                },
                idempotency_key=rejection_key,
            )
            _commit(db)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="AzamPay callback amount does not match the payment amount",
        )

    mapped_status = PaymentStatus.processing
    if incoming_status in SUCCESS_STATUSES:
        mapped_status = PaymentStatus.completed
    elif incoming_status in FAILED_STATUSES:
        mapped_status = PaymentStatus.failed
    elif incoming_status in CANCELLED_STATUSES:
        mapped_status = PaymentStatus.cancelled

    # Never persist callback.password. Keep only operational fields needed for
    # reconciliation, audit and later RSA signature-verification diagnostics.
    safe_payload = {
        "message": payload.message,
        "clientId": payload.clientId,
        "transactionstatus": incoming_status,
        "operator": operator,
        "reference": payload.reference,
        "externalreference": external_reference,
        "utilityref": utility_ref,
        "amount": payload.amount,
        "transid": payload.transid,
        "msisdn": payload.msisdn,
        "mnoreference": payload.mnoreference,
        "submerchantAcc": payload.submerchantAcc,
        "additionalProperties": payload.additionalProperties,
        "signature_present": True,
        "signature_verified": True,
    }

    callback_data = PaymentCallbackRequest(
        payment_id=payment.id,
        provider="azampay",
        transaction_id=provider_transaction_id,
        status=mapped_status,
        payload=safe_payload,
    )

    _apply_payment_callback("azampay", callback_data, db)

    # AzamPay documents an empty 200 response for a successful callback.
    return Response(status_code=status.HTTP_200_OK)


@router.get("/my-payments", response_model=PaginatedPaymentResponse)
def my_payments(
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    payment_status: PaymentStatus | None = None,
    method: PaymentMethod | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    page = max(page, 1)
    page_size = min(max(page_size, 1), 100)

    query = (
        db.query(Payment)
        .options(selectinload(Payment.transactions))
        .filter(Payment.user_id == current_user.id)
    )

    if payment_status is not None:
        query = query.filter(Payment.status == payment_status)

    if method is not None:
        query = query.filter(Payment.method == method)

    if search and search.strip():
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                cast(Payment.id, String).ilike(term),
                cast(Payment.order_id, String).ilike(term),
                Payment.provider_transaction_id.ilike(term),
                Payment.provider.ilike(term),
            )
        )

    total = query.count()
    total_pages = (total + page_size - 1) // page_size if total else 0
    rows = (
        query.order_by(Payment.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
        "results": rows,
    }


@router.get("/admin/all", response_model=list[PaymentResponse])
def list_payments(
    order_id: UUID | None = None,
    payment_status: PaymentStatus | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("payments:read")),
):
    del current_user
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    if payment_status:
        query = query.filter(Payment.status == payment_status)
    return query.order_by(Payment.created_at.desc()).all()


@router.get(
    "/orders/{order_id}/state",
    response_model=OrderPaymentStateResponse,
)
def order_payment_state(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Small polling endpoint used by customer payment UX.

    The payment provider callback remains the source of truth. The browser only
    reads this state; it never marks a payment successful itself.
    """
    order = (
        db.query(Order)
        .filter(Order.id == order_id, Order.user_id == current_user.id)
        .first()
    )
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        )

    latest = (
        db.query(Payment)
        .options(selectinload(Payment.transactions))
        .filter(
            Payment.order_id == order.id,
            Payment.user_id == current_user.id,
        )
        .order_by(Payment.created_at.desc())
        .first()
    )

    if latest is None:
        return {
            "order_id": order.id,
            "order_status": order.status.value,
            "payment_status": "not_started",
            "latest_payment": None,
            "retryable": order.status == OrderStatus.pending,
            "terminal": False,
            "poll_after_seconds": None,
            "message": "Payment has not been started for this order.",
        }

    payment_status = latest.status.value
    active = latest.status in {PaymentStatus.pending, PaymentStatus.processing}
    completed = latest.status == PaymentStatus.completed
    failed = latest.status in {PaymentStatus.failed, PaymentStatus.cancelled}
    refunded = latest.status == PaymentStatus.refunded

    if completed:
        message = "Payment confirmed. Your order is moving through fulfilment."
    elif latest.status == PaymentStatus.processing:
        message = (
            "Payment request sent. Complete the authorization with your payment "
            "provider while Xerin waits for confirmation."
        )
    elif latest.status == PaymentStatus.pending:
        if latest.method == PaymentMethod.cash_on_delivery:
            message = "Cash on Delivery selected. Payment will be collected at delivery."
        else:
            message = "Payment is pending confirmation."
    elif failed:
        message = latest.failure_reason or (
            "Payment was not completed. You can retry against the same order."
        )
    elif refunded:
        message = "This payment has been refunded."
    else:
        message = f"Payment status is {payment_status}."

    return {
        "order_id": order.id,
        "order_status": order.status.value,
        "payment_status": payment_status,
        "latest_payment": latest,
        "retryable": bool(
            failed
            and order.status == OrderStatus.pending
            and latest.method in {PaymentMethod.mobile_money, PaymentMethod.card}
            and (latest.provider or "").lower() == "azampay"
        ),
        "terminal": bool(completed or refunded),
        "poll_after_seconds": 4 if active else None,
        "message": message,
    }


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this payment")
    return payment
