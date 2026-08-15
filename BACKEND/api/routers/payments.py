import hmac
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.config import settings
from api.deps import get_current_user, get_db
from api.models import (
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
    PaymentCallbackRequest,
    PaymentInitiateRequest,
    PaymentResponse,
    NameLookupRequest,
    NameLookupResponse,
)
from api.enums import InventoryReservationStatus, SellerOrderStatus
from api.services.azampay_service import AzamPayAPIError, AzamPayClient, AzamPayConfigurationError
from api.services.inventory_reservations import commit_order_reservations, ensure_order_reservations_active, release_order_reservations
from api.services.commission_engine import calculate_order_commissions

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
    elif incoming_status in FAILED_STATUSES or incoming_status == PaymentStatus.failed.value:
        payment.status = PaymentStatus.failed
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
        payment.failure_reason = callback_payload.get("reason")
        order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
        if order and order.status == OrderStatus.pending:
            release_order_reservations(db, order, target_status=InventoryReservationStatus.released)
            order.status = OrderStatus.cancelled
            db.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.cancelled.value, notes="Order cancelled after failed payment"))
    elif incoming_status in CANCELLED_STATUSES or incoming_status == PaymentStatus.cancelled.value:
        payment.status = PaymentStatus.cancelled
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
        order = db.query(Order).filter(Order.id == payment.order_id).with_for_update().first()
        if order and order.status == OrderStatus.pending:
            release_order_reservations(db, order, target_status=InventoryReservationStatus.cancelled)
            order.status = OrderStatus.cancelled
            db.add(OrderStatusHistory(order_id=order.id, status=OrderStatus.cancelled.value, notes="Order cancelled by payment provider"))
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
    if configured_secret and (not x_azampay_secret or not hmac.compare_digest(x_azampay_secret, configured_secret)):
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
    return payment
