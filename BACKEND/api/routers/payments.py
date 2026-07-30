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
    Inventory,
    Order,
    OrderStatus,
    OrderStatusHistory,
    Payment,
    PaymentMethod,
    PaymentStatus,
    PaymentTransaction,
    User,
)
from api.permissions import require_permission
from api.schemas import PaymentCallbackRequest, PaymentInitiateRequest, PaymentResponse

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
    for item in order.items:
        query = db.query(Inventory).filter(Inventory.product_id == item.product_id)
        query = query.filter(Inventory.variant_id == item.variant_id) if item.variant_id else query.filter(Inventory.variant_id.is_(None))
        inventory = query.with_for_update().first()
        if not inventory:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Inventory missing for product {item.product_id}")
        if inventory.reserved_quantity < item.quantity or inventory.quantity < item.quantity:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Reserved stock is inconsistent for product {item.product_id}")
        inventory.quantity -= item.quantity
        inventory.reserved_quantity -= item.quantity
        inventory.available_quantity = inventory.quantity - inventory.reserved_quantity


def _commit(db: Session, *, conflict_detail: str = "Payment conflict") -> None:
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=conflict_detail) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/initiate", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def initiate_payment(data: PaymentInitiateRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    order = db.query(Order).filter(Order.id == data.order_id).with_for_update().first()
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to pay for this order")
    if order.status != OrderStatus.pending:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Only pending orders can be paid")

    method = data.method if isinstance(data.method, PaymentMethod) else PaymentMethod(data.method)
    if method == PaymentMethod.mobile_money and (not data.provider or not data.phone_number):
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="provider and phone_number are required for mobile money")

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
        provider=data.provider.lower().strip() if data.provider else None,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.flush()

    _record_transaction(db, payment, "initiate", PaymentStatus.pending.value, order.total, {
        "payment_reference": str(payment.id),
        "method": method.value,
        "provider": payment.provider,
        "phone": data.phone_number,
    })

    payment.status = PaymentStatus.pending if method == PaymentMethod.cash_on_delivery else PaymentStatus.processing
    if payment.status == PaymentStatus.processing:
        _record_transaction(db, payment, "provider_request", PaymentStatus.processing.value, order.total, {
            "payment_reference": str(payment.id),
            "provider": payment.provider,
            "phone": data.phone_number,
            "integration_status": "pending_real_provider_integration",
        })

    _commit(db)
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
    elif incoming_status in CANCELLED_STATUSES or incoming_status == PaymentStatus.cancelled.value:
        payment.status = PaymentStatus.cancelled
        payment.provider_transaction_id = data.transaction_id
        payment.provider_response = callback_payload
    else:
        payment.status = PaymentStatus.processing
        payment.provider_response = callback_payload

    _commit(db, conflict_detail="Duplicate or conflicting payment callback")
    db.refresh(payment)
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
    return payment
