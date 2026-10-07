import hmac
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.config import settings
from api.deps import get_current_user, get_db
from api.models import (
    InventoryReservation,
    Order,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentTransaction,
    Shipment,
    ShipmentItem,
    ShipmentStatus,
    ShipmentTrackingEvent,
    SellerOrder,
    User,
)
from api.permissions import require_permission
from api.schemas import (
    OrderPaymentStateResponse,
    PaginatedPaymentResponse,
    PaymentCallbackRequest,
    PaymentInitiateRequest,
    PaymentResponse,
    PaymentRetryRequest,
    NameLookupRequest,
    NameLookupResponse,
)
from api.enums import InventoryReservationStatus, SellerOrderStatus
from api.services.azampay_service import AzamPayAPIError, AzamPayClient, AzamPayConfigurationError
from api.services.selcom_service import SelcomAPIError, SelcomClient, SelcomConfigurationError
from api.services.inventory_reservations import commit_order_reservations, ensure_order_reservations_active
from api.services.commission_engine import calculate_order_commissions

router = APIRouter(prefix="/payments", tags=["Payments"])

logger = logging.getLogger(__name__)

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
) -> PaymentTransaction:
    tx = PaymentTransaction(
        payment_id=payment.id,
        transaction_type=transaction_type,
        status=transaction_status,
        amount=amount,
        provider_response=provider_response or {},
    )
    db.add(tx)
    return tx


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
    current_user: User = Depends(get_current_user),
):
    del current_user
    """
    Verify a Mobile Money account before payment/disbursement.
    """

    provider = data.provider.upper()

    allowed = {
        "MPESA",
        "AIRTEL",
        "TIGOPESA",
        "HALOPESA",
    }

    if provider not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported provider. Allowed: {', '.join(allowed)}"
        )

    client = AzamPayClient()

    try:
        result = client.name_lookup(
            phone_number=data.phone_number,
            provider=provider,
        )

        return {
            "success": True,
            "account_name": result.get("accountName"),
            "provider": provider,
            "phone_number": data.phone_number,
            "message": result.get("message"),
        }

    except AzamPayAPIError as exc:
        raise HTTPException(
            status_code=502,
            detail={
                "provider": "azampay",
                "message": str(exc),
            },
        )

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
    mno = data.provider  # mobile-money label chosen by the customer (M-Pesa, Tigo, ...)
    gateway = (
        settings.payment_provider if method in {PaymentMethod.mobile_money, PaymentMethod.card}
        else (data.provider or "")
    ).lower().strip() or None
    if method == PaymentMethod.mobile_money and (not data.provider or not data.phone_number):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="provider and phone_number are required for mobile money")

    existing = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.status.in_([PaymentStatus.pending, PaymentStatus.processing, PaymentStatus.completed]),
    ).with_for_update().first()
    if existing:
        detail = "Order is already paid" if existing.status == PaymentStatus.completed else "A payment is already in progress for this order"
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)

    payment = Payment(
        order_id=order.id,
        user_id=current_user.id,
        amount=order.total,
        currency=order.currency,
        method=method,
        provider=gateway,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.flush()

    _record_transaction(db, payment, "initiate", PaymentStatus.pending.value, order.total, {
        "payment_reference": str(payment.id),
        "method": method.value,
        "provider": payment.provider,
        "mno": mno if method == PaymentMethod.mobile_money else None,
        "phone": data.phone_number,
    })

    if method == PaymentMethod.cash_on_delivery:
        _commit(db)
        db.refresh(payment)
        return payment

    if payment.provider == "selcom":
        if (
            settings.SELCOM_MAX_AMOUNT_TZS
            and str(order.currency).upper() == "TZS"
            and Decimal(order.total) > Decimal(str(settings.SELCOM_MAX_AMOUNT_TZS))
        ):
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Amount exceeds the maximum allowed for mobile payments (TSh {settings.SELCOM_MAX_AMOUNT_TZS:,.0f})",
            )
        selcom = SelcomClient()
        selcom_order_id = str(payment.id)
        buyer_name = f"{current_user.first_name or ''} {current_user.last_name or ''}".strip()
        try:
            created = selcom.create_order_minimal(
                order_id=selcom_order_id,
                amount=order.total,
                currency=order.currency,
                buyer_email=current_user.email or "",
                buyer_name=buyer_name,
                buyer_phone=data.phone_number or current_user.phone or "",
                no_of_items=len(order.items),
                merchant_remarks=f"Xerin Mart order {order.order_number or order.id}",
            )
            provider_payload = {
                "create_order": created.raw,
                "checkout_url": created.payment_gateway_url,
                "selcom_order_id": selcom_order_id,
                "reference": created.reference,
                "mno": mno if method == PaymentMethod.mobile_money else None,
            }
            if method == PaymentMethod.mobile_money:
                push = selcom.wallet_pull(
                    transid=selcom_order_id,
                    order_id=selcom_order_id,
                    msisdn=data.phone_number or current_user.phone or "",
                )
                provider_payload["wallet_push"] = push.raw
                provider_payload["message"] = push.message or "USSD push sent to your phone"
        except ValueError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
        except SelcomConfigurationError as exc:
            db.rollback()
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
        except SelcomAPIError as exc:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={"message": str(exc), "provider": "selcom", "provider_status": exc.status_code},
            ) from exc

        payment.status = PaymentStatus.processing
        payment.provider_transaction_id = selcom_order_id
        payment.provider_response = provider_payload
        _record_transaction(db, payment, "provider_request", PaymentStatus.processing.value, order.total, provider_payload)
        _commit(db, conflict_detail="Selcom transaction conflict")
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
        db.rollback()
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except AzamPayConfigurationError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except AzamPayAPIError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"message": str(exc), "provider": "azampay", "provider_status": exc.status_code},
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


@router.post("/callback/{provider}", response_model=PaymentResponse)
def payment_callback(
    provider: str,
    data: PaymentCallbackRequest,
    x_webhook_secret: str | None = Header(default=None, alias="X-Webhook-Secret"),
    db: Session = Depends(get_db),
):
    _verify_webhook_secret(x_webhook_secret)
    return _apply_payment_callback(provider, data, db)


def _payment_event(db: Session, action: str, description: str, *, severity: str,
                   payment: Payment | None = None, order: Order | None = None,
                   metadata: dict | None = None) -> None:
    """Audit a payment lifecycle event; alerting follows severity rules."""
    if not settings.MONITORING_ENABLED:
        return
    try:
        from api.services.monitoring import record_business_event
        record_business_event(
            db,
            action=action,
            description=description,
            severity=severity,
            resource_type="payment",
            resource_id=str(payment.id) if payment else None,
            event_metadata={
                "provider": payment.provider if payment else None,
                "order_id": str(order.id) if order else (str(payment.order_id) if payment else None),
                "amount": str(payment.amount) if payment else None,
                **(metadata or {}),
            },
            dedup_key=f"{action}:{payment.id if payment else 'unknown'}",
        )
    except Exception:
        logger.exception("payment monitoring event failed for %s", action)


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

    incoming_status = data.status.value if isinstance(data.status, PaymentStatus) else str(data.status).lower()
    if payment.status == PaymentStatus.completed:
        if payment.provider_transaction_id == data.transaction_id and incoming_status in SUCCESS_STATUSES | {PaymentStatus.completed.value}:
            return payment
        _payment_event(db, "payment.callback_conflict",
                       "Callback attempted to mutate a completed payment",
                       severity="critical", payment=payment,
                       metadata={"incoming_status": incoming_status,
                                 "incoming_txn": str(data.transaction_id)[:80]})
        db.commit()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Completed payment cannot be changed by another callback")

    callback_payload = dict(data.payload or {})
    callback_payload.update({"payment_id": str(payment.id), "provider_transaction_id": data.transaction_id})
    _record_transaction(db, payment, "callback", incoming_status, payment.amount, callback_payload)

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

        _deduct_reserved_inventory(db, order)
        _create_shipments_for_order(db, order)
        calculate_order_commissions(db, order)
        payment.status = PaymentStatus.completed
        payment.paid_at = datetime.now(timezone.utc)
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
        order.status = OrderStatus.paid
        db.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.paid.value, notes=f"Payment confirmed via {normalized_provider}"))
        _payment_event(db, "payment.completed", "Payment completed",
                       severity="notice", payment=payment, order=order)
    elif incoming_status in FAILED_STATUSES or incoming_status == PaymentStatus.failed.value:
        payment.status = PaymentStatus.failed
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
        payment.failure_reason = callback_payload.get("reason")
        _payment_event(db, "payment.failed", "Payment failed",
                       severity="warning", payment=payment,
                       metadata={"reason": str(payment.failure_reason or "")[:200]})
        # Keep the order pending so the buyer can retry payment against the
        # same order. Reserved stock is released by the reservation-expiry /
        # unpaid-order timeout jobs if the buyer abandons checkout.
    elif incoming_status in CANCELLED_STATUSES or incoming_status == PaymentStatus.cancelled.value:
        payment.status = PaymentStatus.cancelled
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
        # Same as failure: the order stays pending and retryable.
    else:
        payment.status = PaymentStatus.processing
        payment.provider_response = callback_payload

    _commit(db, conflict_detail="Duplicate or conflicting payment callback")
    db.refresh(payment)
    return payment


@router.post("/azampay/callback", response_model=PaymentResponse)
def azampay_callback(
    payload: dict,
    x_azampay_secret: str | None = Header(default=None, alias="X-AzamPay-Secret"),
    db: Session = Depends(get_db),
):
    configured_secret = settings.AZAMPAY_CALLBACK_SECRET
    if not configured_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AzamPay callback secret is not configured",
        )
    if not x_azampay_secret or not hmac.compare_digest(x_azampay_secret, configured_secret):
        if settings.MONITORING_ENABLED:
            try:
                from api.services.monitoring import record_security_alert
                from api.enums import SecurityEventType, AuditSeverity
                record_security_alert(
                    db,
                    event_type=SecurityEventType.invalid_webhook,
                    description="AzamPay callback with an invalid or missing secret",
                    severity=AuditSeverity.critical,
                    request_path="/payments/azampay/callback",
                    http_method="POST",
                    dedup_key="security.invalid_webhook:azampay",
                )
                db.commit()
            except Exception:
                db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid AzamPay callback secret")

    reference = str(payload.get("utilityref") or payload.get("externalId") or payload.get("external_id") or "").strip()
    transaction_id = str(payload.get("reference") or payload.get("transactionId") or payload.get("transaction_id") or "").strip()
    incoming_status = str(payload.get("transactionstatus") or payload.get("status") or "processing").lower().strip()
    if not reference:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="AzamPay callback is missing payment reference")
    try:
        payment_id = UUID(reference)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid AzamPay payment reference") from exc

    mapped = PaymentStatus.processing
    if incoming_status in SUCCESS_STATUSES:
        mapped = PaymentStatus.completed
    elif incoming_status in FAILED_STATUSES:
        mapped = PaymentStatus.failed
    elif incoming_status in CANCELLED_STATUSES:
        mapped = PaymentStatus.cancelled

    callback_data = PaymentCallbackRequest(
        payment_id=payment_id,
        provider="azampay",
        transaction_id=transaction_id or f"azampay-{reference}",
        status=mapped,
        payload=payload,
    )
    return _apply_payment_callback("azampay", callback_data, db)


SELCOM_SUCCESS_STATUSES = {"COMPLETED"}
SELCOM_FAILED_STATUSES = {"FAIL", "FAILED", "REJECTED"}
SELCOM_CANCELLED_STATUSES = {"CANCELLED", "USERCANCELED", "USERCANCELLED"}


def _map_selcom_status(payment_status: str, result: str) -> PaymentStatus:
    status_value = (payment_status or "").upper()
    result_value = (result or "").upper()
    if status_value in SELCOM_SUCCESS_STATUSES or result_value == "SUCCESS":
        return PaymentStatus.completed
    if status_value in SELCOM_FAILED_STATUSES or result_value == "FAIL":
        return PaymentStatus.failed
    if status_value in SELCOM_CANCELLED_STATUSES:
        return PaymentStatus.cancelled
    return PaymentStatus.processing


@router.post("/selcom/callback", response_model=PaymentResponse)
@router.post("/selcom/webhook", response_model=PaymentResponse, include_in_schema=False)
def selcom_callback(
    payload: dict,
    timestamp: str | None = Header(default=None),
    digest: str | None = Header(default=None),
    signed_fields: str | None = Header(default=None, alias="Signed-Fields"),
    db: Session = Depends(get_db),
):
    """Selcom payment webhook — fires on successful transactions.

    Authenticated with the same SELCOM signature headers as the API
    (Digest = HMAC-SHA256 over timestamp + signed payload fields).
    """
    client = SelcomClient()
    if not client.verify_webhook(
        timestamp=timestamp,
        digest=digest,
        signed_fields=signed_fields,
        payload=payload,
    ):
        if settings.MONITORING_ENABLED:
            try:
                from api.services.monitoring import record_security_alert
                from api.enums import SecurityEventType, AuditSeverity
                record_security_alert(
                    db,
                    event_type=SecurityEventType.invalid_webhook,
                    description="Selcom callback with an invalid or missing signature",
                    severity=AuditSeverity.critical,
                    request_path="/payments/selcom/callback",
                    http_method="POST",
                    dedup_key="security.invalid_webhook:selcom",
                )
                db.commit()
            except Exception:
                db.rollback()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid Selcom callback signature")

    order_ref = str(payload.get("order_id") or "").strip()
    if not order_ref:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Selcom callback is missing order_id")
    try:
        payment_id = UUID(order_ref)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Invalid Selcom order_id") from exc

    mapped = _map_selcom_status(
        str(payload.get("payment_status") or ""),
        str(payload.get("result") or ""),
    )
    transaction_id = str(payload.get("reference") or payload.get("transid") or order_ref)

    callback_data = PaymentCallbackRequest(
        payment_id=payment_id,
        provider="selcom",
        transaction_id=transaction_id,
        status=mapped,
        payload=payload,
    )
    return _apply_payment_callback("selcom", callback_data, db)


TERMINAL_PAYMENT_STATUSES = {
    PaymentStatus.completed,
    PaymentStatus.failed,
    PaymentStatus.cancelled,
    PaymentStatus.refunded,
}

PAYMENT_STATE_MESSAGES = {
    "not_started": "Payment has not been started for this order.",
    "pending": "Payment request created. Waiting for confirmation.",
    "processing": "Waiting for the payment provider to confirm the payment.",
    "completed": "Payment confirmed.",
    "failed": "The payment attempt failed. You can retry the payment.",
    "cancelled": "The payment attempt was cancelled.",
    "refunded": "This payment was refunded.",
}


def _order_reservations_active(db: Session, order: Order) -> bool:
    now = datetime.now(timezone.utc)
    rows = db.query(InventoryReservation).filter(
        InventoryReservation.order_id == order.id,
    ).all()
    return bool(rows) and all(
        row.status == InventoryReservationStatus.active
        and (row.expires_at is None or row.expires_at > now)
        for row in rows
    )


@router.get("/orders/{order_id}/state", response_model=OrderPaymentStateResponse)
def order_payment_state(
    order_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this order")

    latest = (
        db.query(Payment)
        .filter(Payment.order_id == order.id)
        .order_by(Payment.created_at.desc())
        .first()
    )

    if latest is not None:
        payment_status = latest.status.value
    elif order.status == OrderStatus.paid:
        payment_status = "completed"
    elif order.status == OrderStatus.cancelled:
        payment_status = "cancelled"
    else:
        payment_status = "not_started"

    is_cod = bool(latest and latest.method == PaymentMethod.cash_on_delivery)
    order_terminal = order.status in {
        OrderStatus.cancelled,
        OrderStatus.refunded,
    }
    terminal = (
        payment_status in {s.value for s in TERMINAL_PAYMENT_STATUSES}
        or order_terminal
        or is_cod
    )
    retryable = bool(
        latest
        and latest.status in {PaymentStatus.failed, PaymentStatus.cancelled}
        and latest.method != PaymentMethod.cash_on_delivery
        and order.status == OrderStatus.pending
        and _order_reservations_active(db, order)
    )
    poll_after = (
        30 if is_cod else 5
    ) if payment_status in {"pending", "processing"} else None

    message = PAYMENT_STATE_MESSAGES.get(payment_status, "Payment state unavailable.")
    if latest is not None:
        provider_message = (latest.provider_response or {}).get("message")
        if payment_status in {"pending", "processing"} and provider_message:
            message = str(provider_message)
        elif payment_status == "failed" and latest.failure_reason:
            message = str(latest.failure_reason)
    if order_terminal and payment_status == "cancelled":
        message = "The payment window expired and this order was cancelled."

    return {
        "order_id": order.id,
        "order_status": order.status.value,
        "payment_status": payment_status,
        "latest_payment": latest,
        "retryable": retryable,
        "terminal": terminal,
        "poll_after_seconds": poll_after,
        "message": message,
    }


@router.get("/my-payments", response_model=PaginatedPaymentResponse)
def my_payments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    payment_status: PaymentStatus | None = Query(None),
    method: PaymentMethod | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Payment).filter(Payment.user_id == current_user.id)
    if payment_status is not None:
        query = query.filter(Payment.status == payment_status)
    if method is not None:
        query = query.filter(Payment.method == method)
    query = query.order_by(Payment.created_at.desc())
    return {
        "total": query.count(),
        "page": page,
        "page_size": page_size,
        "results": query.offset((page - 1) * page_size).limit(page_size).all(),
    }


@router.post("/{payment_id}/retry", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def retry_payment(
    payment_id: UUID,
    data: PaymentRetryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Start a new payment attempt against the same pending order."""
    payment = db.query(Payment).filter(Payment.id == payment_id).with_for_update().first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to retry this payment")
    if payment.method == PaymentMethod.cash_on_delivery:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cash on delivery payments cannot be retried")
    if payment.status not in {PaymentStatus.failed, PaymentStatus.cancelled}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only failed or cancelled payments can be retried")

    order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.status != OrderStatus.pending:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This order can no longer be paid. Please place a new order.",
        )

    previous_mno = (payment.provider_response or {}).get("mno")
    return initiate_payment(
        PaymentInitiateRequest(
            order_id=order.id,
            method=payment.method,
            provider=data.provider or previous_mno,
            phone_number=data.phone_number,
            success_url=data.success_url,
            failure_url=data.failure_url,
        ),
        db=db,
        current_user=current_user,
    )


def _refresh_selcom_status(db: Session, payment: Payment) -> Payment:
    try:
        status_data = SelcomClient().order_status(str(payment.id))
        entry = (status_data.get("data") or [{}])[0]
        mapped = _map_selcom_status(str(entry.get("payment_status") or ""), "")
        if mapped != PaymentStatus.processing:
            payment = _apply_payment_callback(
                "selcom",
                PaymentCallbackRequest(
                    payment_id=payment.id,
                    provider="selcom",
                    transaction_id=str(entry.get("reference") or entry.get("transid") or payment.id),
                    status=mapped,
                    payload=entry,
                ),
                db,
            )
    except Exception:
        logger.exception("selcom order-status refresh failed for payment %s", payment.id)
    return payment


@router.post("/{payment_id}/verify-status", response_model=PaymentResponse)
def verify_payment_status(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this payment")

    if payment.provider == "selcom" and payment.status in {PaymentStatus.pending, PaymentStatus.processing}:
        payment = _refresh_selcom_status(db, payment)

    return payment


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


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payment not found")
    if payment.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this payment")

    # Selcom webhook only fires on success — poll order status so a
    # cancelled/failed USSD push doesn't leave the payment processing forever.
    if payment.provider == "selcom" and payment.status in {PaymentStatus.pending, PaymentStatus.processing}:
        payment = _refresh_selcom_status(db, payment)

    return payment
