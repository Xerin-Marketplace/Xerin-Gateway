from uuid import UUID
from decimal import Decimal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session

from api.deps import get_db, get_current_user
from api.models import (
    User,
    Order,
    OrderStatus,
    Payment,
    PaymentStatus,
    PaymentMethod,
    PaymentTransaction,
    Inventory,
)
from api.schemas import (
    PaymentInitiateRequest,
    PaymentCallbackRequest,
    PaymentResponse,
)
from api.permissions import require_permission

router = APIRouter(prefix="/payments", tags=["Payments"])


def _deduct_inventory_on_payment(db: Session, order: Order) -> None:
    for item in order.items:
        inventory = db.query(Inventory).filter(
            Inventory.product_id == item.product_id,
            Inventory.variant_id == item.variant_id,
        ).with_for_update().first()

        if inventory:
            inventory.quantity = max(0, inventory.quantity - item.quantity)
            inventory.reserved_quantity = max(0, inventory.reserved_quantity - item.quantity)
            inventory.available_quantity = inventory.quantity - inventory.reserved_quantity


def _record_transaction(
    db: Session,
    payment: Payment,
    transaction_type: str,
    status: str,
    amount: Decimal | None = None,
    provider_response: dict | None = None,
) -> PaymentTransaction:
    tx = PaymentTransaction(
        payment_id=payment.id,
        transaction_type=transaction_type,
        status=status,
        amount=amount,
        provider_response=provider_response or {},
    )
    db.add(tx)
    return tx


@router.post("/initiate", response_model=PaymentResponse, status_code=status.HTTP_201_CREATED)
def initiate_payment(
    data: PaymentInitiateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = db.query(Order).filter(Order.id == data.order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    if order.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to pay for this order")

    if order.status != OrderStatus.pending:
        raise HTTPException(status_code=400, detail="Order is not in pending status")

    try:
        method = PaymentMethod(data.method)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid payment method")

    # Prevent duplicate pending payments
    existing = db.query(Payment).filter(
        Payment.order_id == order.id,
        Payment.status.in_([PaymentStatus.pending, PaymentStatus.processing]),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="A payment is already in progress for this order")

    payment = Payment(
        order_id=order.id,
        user_id=current_user.id,
        amount=order.total,
        currency=order.currency,
        method=method,
        provider=data.provider,
        status=PaymentStatus.pending,
    )
    db.add(payment)
    db.flush()

    _record_transaction(
        db,
        payment,
        "initiate",
        PaymentStatus.pending.value,
        amount=order.total,
        provider_response={"method": data.method, "provider": data.provider, "phone": data.phone_number},
    )

    # Simulate mobile-money push: in production this calls the provider API
    if method == PaymentMethod.mobile_money:
        payment.status = PaymentStatus.processing
        _record_transaction(
            db,
            payment,
            "provider_request",
            PaymentStatus.processing.value,
            amount=order.total,
            provider_response={"provider": data.provider, "phone": data.phone_number, "simulated": True},
        )
    elif method == PaymentMethod.cash_on_delivery:
        payment.status = PaymentStatus.pending
    else:
        payment.status = PaymentStatus.processing

    db.commit()
    db.refresh(payment)
    return payment


@router.post("/callback/{provider}", response_model=PaymentResponse)
def payment_callback(
    provider: str,
    data: PaymentCallbackRequest,
    request: Request,
    db: Session = Depends(get_db),
):
    payment = db.query(Payment).filter(
        Payment.provider_transaction_id == data.transaction_id,
    ).first()

    if not payment:
        # Fallback: find by provider + pending transaction
        payment = db.query(Payment).filter(
            Payment.provider == provider,
            Payment.status == PaymentStatus.processing,
        ).order_by(Payment.created_at.desc()).first()

    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    _record_transaction(
        db,
        payment,
        "callback",
        data.status,
        amount=payment.amount,
        provider_response=data.payload or {},
    )

    if data.status.lower() in ("success", "completed", "paid"):
        payment.status = PaymentStatus.completed
        payment.paid_at = datetime.now(timezone.utc)
        payment.provider_transaction_id = data.transaction_id

        order = payment.order
        order.status = OrderStatus.paid

        # Move reserved stock to deducted
        _deduct_inventory_on_payment(db, order)

        # Add order status history
        from api.models import OrderStatusHistory
        history = OrderStatusHistory(
            order_id=order.id,
            status=OrderStatus.paid.value,
            notes=f"Payment confirmed via {provider}",
        )
        db.add(history)

    elif data.status.lower() in ("failed", "failure"):
        payment.status = PaymentStatus.failed
        payment.failure_reason = data.payload.get("reason") if data.payload else None
    elif data.status.lower() in ("cancelled", "canceled"):
        payment.status = PaymentStatus.cancelled
    else:
        payment.status = PaymentStatus.processing

    db.commit()
    db.refresh(payment)
    return payment


@router.get("/{payment_id}", response_model=PaymentResponse)
def get_payment(
    payment_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    if payment.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to view this payment")

    return payment


@router.get("/admin/all", response_model=list[PaymentResponse])
def list_payments(
    order_id: UUID | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("payments:read")),
):
    query = db.query(Payment)
    if order_id:
        query = query.filter(Payment.order_id == order_id)
    if status:
        query = query.filter(Payment.status == status)
    return query.order_by(Payment.created_at.desc()).all()
