from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from api.deps import get_db
from api.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEvent, PermissionCode
from api.models import DeviceToken, Notification, NotificationDelivery, NotificationPreference, NotificationTemplate, User
from api.permissions import require_permission
from api.schemas import (
    DeviceTokenCreate, DeviceTokenResponse, NotificationPreferenceResponse, NotificationPreferenceUpdate,
    NotificationResponse, NotificationSummary, NotificationTemplateCreate, NotificationTemplateResponse,
    NotificationTemplateUpdate,
)
from api.services.notification_service import notification_service

router = APIRouter(tags=["Notifications"])


def _notification_or_404(db: Session, user_id: UUID, notification_id: UUID) -> Notification:
    item = db.query(Notification).filter(Notification.id == notification_id, Notification.user_id == user_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Notification not found")
    return item


@router.get("/notifications", response_model=list[NotificationResponse])
def list_notifications(unread_only: bool = False, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0), db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_read.value))):
    query = db.query(Notification).filter(Notification.user_id == current_user.id)
    if unread_only: query = query.filter(Notification.is_read.is_(False))
    return query.order_by(Notification.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/notifications/summary", response_model=NotificationSummary)
def notification_summary(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_read.value))):
    total = db.query(Notification).filter(Notification.user_id == current_user.id).count()
    unread = notification_service.unread_count(db, current_user.id)
    return NotificationSummary(total=total, unread=unread, read=total-unread)


@router.patch("/notifications/read-all", response_model=NotificationSummary)
def read_all(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    now = datetime.now(timezone.utc)
    db.query(Notification).filter(Notification.user_id == current_user.id, Notification.is_read.is_(False)).update({Notification.is_read: True, Notification.read_at: now}, synchronize_session=False)
    db.commit()
    total = db.query(Notification).filter(Notification.user_id == current_user.id).count()
    return NotificationSummary(total=total, unread=0, read=total)


@router.patch("/notifications/{notification_id}/read", response_model=NotificationResponse)
def read_notification(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    item = _notification_or_404(db, current_user.id, notification_id)
    if not item.is_read: item.is_read=True; item.read_at=datetime.now(timezone.utc); db.commit(); db.refresh(item)
    return item


@router.delete("/notifications/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(notification_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    item = _notification_or_404(db, current_user.id, notification_id); db.delete(item); db.commit()


@router.get("/notifications/preferences", response_model=NotificationPreferenceResponse)
def get_preferences(db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_read.value))):
    preference = notification_service.get_or_create_preferences(db, current_user.id); db.commit(); db.refresh(preference); return preference


@router.patch("/notifications/preferences", response_model=NotificationPreferenceResponse)
def update_preferences(data: NotificationPreferenceUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    preference = notification_service.get_or_create_preferences(db, current_user.id)
    for key, value in data.model_dump(exclude_unset=True).items(): setattr(preference, key, value)
    db.commit(); db.refresh(preference); return preference


@router.post("/notifications/device-tokens", response_model=DeviceTokenResponse, status_code=status.HTTP_201_CREATED)
def register_device(data: DeviceTokenCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    token = db.query(DeviceToken).filter(DeviceToken.token == data.token).first()
    if token:
        token.user_id=current_user.id; token.platform=data.platform; token.device_name=data.device_name; token.is_active=True
    else: token=DeviceToken(user_id=current_user.id, **data.model_dump()); db.add(token)
    db.commit(); db.refresh(token); return token


@router.delete("/notifications/device-tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def unregister_device(token_id: UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.notifications_manage.value))):
    token=db.query(DeviceToken).filter(DeviceToken.id==token_id, DeviceToken.user_id==current_user.id).first()
    if not token: raise HTTPException(status_code=404, detail="Device token not found")
    db.delete(token); db.commit()


@router.get("/admin/notification-templates", response_model=list[NotificationTemplateResponse])
def list_templates(db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.admin_notifications_read.value))):
    return db.query(NotificationTemplate).order_by(NotificationTemplate.event, NotificationTemplate.channel).all()


@router.post("/admin/notification-templates", response_model=NotificationTemplateResponse, status_code=status.HTTP_201_CREATED)
def create_template(data: NotificationTemplateCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission(PermissionCode.admin_notification_templates_manage.value))):
    item=NotificationTemplate(**data.model_dump(), created_by_id=current_user.id); db.add(item)
    try: db.commit(); db.refresh(item); return item
    except IntegrityError as exc: db.rollback(); raise HTTPException(status_code=409, detail="Template already exists for this event and channel") from exc


@router.patch("/admin/notification-templates/{template_id}", response_model=NotificationTemplateResponse)
def update_template(template_id: UUID, data: NotificationTemplateUpdate, db: Session = Depends(get_db), _: User = Depends(require_permission(PermissionCode.admin_notification_templates_manage.value))):
    item=db.query(NotificationTemplate).filter(NotificationTemplate.id==template_id).first()
    if not item: raise HTTPException(status_code=404, detail="Notification template not found")
    for key,value in data.model_dump(exclude_unset=True).items(): setattr(item,key,value)
    db.commit(); db.refresh(item); return item


# =========================================================
# ADMIN NOTIFICATION MANAGEMENT
# =========================================================

class TestSendRequest(BaseModel):
    channel: NotificationChannel
    recipient: str = Field(min_length=3)
    subject: str | None = None
    message: str = Field(min_length=1)


class BulkSMSRequest(BaseModel):
    recipients: list[str] = Field(min_length=1, max_length=500)
    message: str = Field(min_length=1)
    sender_id: str | None = None


class NotificationDeliveryLogResponse(BaseModel):
    id: UUID
    notification_id: UUID
    channel: NotificationChannel
    status: NotificationDeliveryStatus
    provider: str | None
    provider_reference: str | None
    attempts: int
    sent_at: datetime | None
    delivered_at: datetime | None
    failed_at: datetime | None
    failure_reason: str | None
    notification_title: str | None = None
    notification_event: str | None = None
    user_name: str | None = None
    user_phone: str | None = None
    user_email: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True


class NotificationLogListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[NotificationDeliveryLogResponse]


class NotificationStatsResponse(BaseModel):
    total_notifications: int
    total_deliveries: int
    by_channel: dict[str, int]
    by_status: dict[str, int]
    by_event: dict[str, int]


@router.get("/admin/notification-stats", response_model=NotificationStatsResponse)
def notification_stats(
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.notification_logs_read.value)),
):
    total_notifications = db.query(Notification).count()
    total_deliveries = db.query(NotificationDelivery).count()

    channel_counts = {}
    for ch in NotificationChannel:
        channel_counts[ch.value] = db.query(NotificationDelivery).filter(NotificationDelivery.channel == ch).count()

    status_counts = {}
    for st in NotificationDeliveryStatus:
        status_counts[st.value] = db.query(NotificationDelivery).filter(NotificationDelivery.status == st).count()

    event_counts = {}
    for ev in NotificationEvent:
        event_counts[ev.value] = db.query(Notification).filter(Notification.event == ev).count()

    return NotificationStatsResponse(
        total_notifications=total_notifications,
        total_deliveries=total_deliveries,
        by_channel=channel_counts,
        by_status=status_counts,
        by_event=event_counts,
    )


@router.get("/admin/notification-logs", response_model=NotificationLogListResponse)
def notification_delivery_logs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: NotificationChannel | None = Query(None),
    delivery_status: NotificationDeliveryStatus | None = Query(None, alias="status"),
    event: NotificationEvent | None = Query(None),
    search: str | None = Query(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_permission(PermissionCode.notification_logs_read.value)),
):
    q = db.query(NotificationDelivery).join(Notification)
    if channel:
        q = q.filter(NotificationDelivery.channel == channel)
    if delivery_status:
        q = q.filter(NotificationDelivery.status == delivery_status)
    if event:
        q = q.filter(Notification.event == event)
    if search:
        q = q.join(User, Notification.user_id == User.id).filter(
            or_(
                User.first_name.ilike(f"%{search}%"),
                User.last_name.ilike(f"%{search}%"),
                User.phone.ilike(f"%{search}%"),
                User.email.ilike(f"%{search}%"),
                Notification.title.ilike(f"%{search}%"),
            )
        )
    total = q.count()
    deliveries = q.order_by(NotificationDelivery.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()

    results = []
    for d in deliveries:
        notif = db.query(Notification).filter(Notification.id == d.notification_id).first()
        user = db.query(User).filter(User.id == notif.user_id).first() if notif else None
        results.append(NotificationDeliveryLogResponse(
            id=d.id, notification_id=d.notification_id, channel=d.channel, status=d.status,
            provider=d.provider, provider_reference=d.provider_reference, attempts=d.attempts,
            sent_at=d.sent_at, delivered_at=d.delivered_at, failed_at=d.failed_at,
            failure_reason=d.failure_reason, created_at=d.created_at,
            notification_title=notif.title if notif else None,
            notification_event=notif.event.value if notif else None,
            user_name=f"{user.first_name} {user.last_name}" if user else None,
            user_phone=user.phone if user else None,
            user_email=user.email if user else None,
        ))

    return NotificationLogListResponse(total=total, page=page, page_size=page_size, results=results)


@router.post("/admin/notification-test-send")
def test_send(
    data: TestSendRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.notification_bulk_send.value)),
):
    """Send a test SMS or email to verify provider configuration."""
    if data.channel == NotificationChannel.sms:
        result = notification_service._send_sms(data.recipient, data.message)
    elif data.channel == NotificationChannel.email:
        result = notification_service._send_email(data.recipient, data.subject or "Test Notification", data.message)
    else:
        raise HTTPException(400, "Only SMS and email channels are supported for test send")
    return result


@router.post("/admin/notification-bulk-sms")
def bulk_sms(
    data: BulkSMSRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.notification_bulk_send.value)),
):
    """Send bulk SMS to multiple recipients."""
    results = []
    for recipient in data.recipients:
        result = notification_service._send_sms(recipient, data.message)
        results.append({"recipient": recipient, **result})
    sent_count = sum(1 for r in results if r.get("accepted"))
    failed_count = len(results) - sent_count
    return {"total": len(results), "sent": sent_count, "failed": failed_count, "results": results}


@router.post("/admin/notification-templates/seed")
def seed_default_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(PermissionCode.notification_templates_manage.value)),
):
    """Seed default notification templates for all events and channels."""
    default_templates = [
        # Order placed
        (NotificationEvent.order_placed, NotificationChannel.sms, None, "Hello ${user_name}, your order ${order_number} has been placed successfully. Total: ${total} ${currency}. Thank you for shopping with Xerin!"),
        (NotificationEvent.order_placed, NotificationChannel.email, "Order Confirmed - ${order_number}", "Dear ${user_name},\n\nYour order ${order_number} has been placed successfully.\nTotal: ${total} ${currency}\n\nWe will notify you as your order progresses.\n\nThank you for shopping with Xerin!"),
        # Payment confirmed
        (NotificationEvent.payment_confirmed, NotificationChannel.sms, None, "Payment confirmed for order ${order_number}. We are now processing your order."),
        (NotificationEvent.payment_confirmed, NotificationChannel.email, "Payment Confirmed - ${order_number}", "Dear ${user_name},\n\nYour payment for order ${order_number} has been confirmed. Your order is now being processed.\n\nXerin Team"),
        # Order accepted
        (NotificationEvent.order_accepted, NotificationChannel.sms, None, "Your order ${order_number} is now being processed by the seller."),
        # Order dispatched
        (NotificationEvent.order_dispatched, NotificationChannel.sms, None, "Your order ${order_number} has been dispatched and is on its way."),
        (NotificationEvent.order_dispatched, NotificationChannel.email, "Order Dispatched - ${order_number}", "Dear ${user_name},\n\nYour order ${order_number} has been dispatched and is on its way to you.\n\nXerin Team"),
        # Order delivered
        (NotificationEvent.order_delivered, NotificationChannel.sms, None, "Your order ${order_number} has been delivered. Thank you for shopping with Xerin!"),
        (NotificationEvent.order_delivered, NotificationChannel.email, "Order Delivered - ${order_number}", "Dear ${user_name},\n\nYour order ${order_number} has been delivered successfully.\n\nThank you for shopping with Xerin!"),
        # Driver assigned
        (NotificationEvent.driver_assigned, NotificationChannel.sms, None, "A driver has been assigned to your order ${order_number}. Your package will be picked up soon."),
        # Out for delivery
        (NotificationEvent.out_for_delivery, NotificationChannel.sms, None, "Your order ${order_number} is out for delivery and will arrive soon. OTP: ${otp}"),
        (NotificationEvent.out_for_delivery, NotificationChannel.email, "Out for Delivery - ${order_number}", "Dear ${user_name},\n\nYour order ${order_number} is out for delivery and will arrive soon.\nDelivery OTP: ${otp}\n\nXerin Team"),
        # Delivery failed
        (NotificationEvent.delivery_failed, NotificationChannel.sms, None, "Delivery for order ${order_number} could not be completed. Our team will contact you shortly."),
        # Warehouse received
        (NotificationEvent.warehouse_received, NotificationChannel.sms, None, "Your stock has been received at Xerin warehouse. Reference: ${reference}"),
        # Ready for delivery
        (NotificationEvent.ready_for_delivery, NotificationChannel.sms, None, "Your order ${order_number} is ready for delivery at Xerin warehouse."),
        # Stock transfer events
        (NotificationEvent.stock_transfer_approved, NotificationChannel.sms, None, "Your stock transfer ${reference} has been approved."),
        (NotificationEvent.stock_transfer_received, NotificationChannel.sms, None, "Your stock transfer ${reference} has been received at the warehouse."),
        (NotificationEvent.stock_transfer_rejected, NotificationChannel.sms, None, "Your stock transfer ${reference} has been rejected. Reason: ${rejection_reason}"),
        # Admin alerts
        (NotificationEvent.admin_order_alert, NotificationChannel.email, "New Order Alert - ${order_number}", "A new order ${order_number} has been placed.\nTotal: ${total} ${currency}\n\nPlease review in the admin dashboard."),
        (NotificationEvent.admin_delivery_alert, NotificationChannel.email, "Delivery Failed Alert", "A delivery has failed.\nOrder: ${order_number}\nTrip: ${trip_ref}\n\nPlease review in the admin dashboard."),
        # Promotion
        (NotificationEvent.promotion_available, NotificationChannel.sms, None, "${title}: ${message}. Shop now on Xerin!"),
        (NotificationEvent.promotion_available, NotificationChannel.email, "${title}", "${message}\n\nShop now on Xerin!"),
        # Cancellation
        (NotificationEvent.cancellation_requested, NotificationChannel.sms, None, "Your order ${order_number} has been cancelled."),
        # OTP
        (NotificationEvent.otp_verification, NotificationChannel.sms, None, "Your Xerin verification code is: ${otp_code}. Valid for 10 minutes."),
    ]

    created = 0
    skipped = 0
    for event_val, channel_val, subject, body in default_templates:
        existing = db.query(NotificationTemplate).filter(
            NotificationTemplate.event == event_val,
            NotificationTemplate.channel == channel_val,
        ).first()
        if existing:
            skipped += 1
            continue
        db.add(NotificationTemplate(
            event=event_val,
            channel=channel_val,
            subject_template=subject,
            body_template=body,
            is_active=True,
            created_by_id=current_user.id,
        ))
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "total": len(default_templates)}
