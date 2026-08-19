from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from api.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEvent
from api.models import DeviceToken, Notification, NotificationDelivery, NotificationPreference, User
from api.services.notification_providers import default_providers


class NotificationService:
    def get_or_create_preferences(self, db: Session, user_id: UUID) -> NotificationPreference:
        preference = db.query(NotificationPreference).filter(NotificationPreference.user_id == user_id).first()
        if preference is None:
            preference = NotificationPreference(user_id=user_id)
            db.add(preference)
            db.flush()
        return preference

    def enabled_channels(self, preference: NotificationPreference, event: NotificationEvent) -> list[NotificationChannel]:
        defaults = {
            NotificationChannel.in_app: preference.in_app_enabled,
            NotificationChannel.email: preference.email_enabled,
            NotificationChannel.sms: preference.sms_enabled,
            NotificationChannel.push: preference.push_enabled,
        }
        overrides = (preference.event_preferences or {}).get(event.value, {})
        return [channel for channel, enabled in defaults.items() if bool(overrides.get(channel.value, enabled))]

    def notify(self, *, db: Session, user_id: UUID, event: NotificationEvent | str, title: str, message: str, data: dict[str, Any] | None = None, action_url: str | None = None, channels: Iterable[NotificationChannel] | None = None, commit: bool = True) -> Notification:
        event_value = event if isinstance(event, NotificationEvent) else NotificationEvent(event)
        preference = self.get_or_create_preferences(db, user_id)
        selected = list(channels) if channels is not None else self.enabled_channels(preference, event_value)
        notification = Notification(user_id=user_id, event=event_value, title=title, message=message, data=data or {}, action_url=action_url)
        db.add(notification); db.flush()
        for channel in selected:
            status = NotificationDeliveryStatus.delivered if channel == NotificationChannel.in_app else NotificationDeliveryStatus.pending
            now = datetime.now(timezone.utc) if channel == NotificationChannel.in_app else None
            db.add(NotificationDelivery(notification_id=notification.id, channel=channel, status=status, delivered_at=now))
        if commit:
            db.commit(); db.refresh(notification)
        return notification

    def unread_count(self, db: Session, user_id: UUID) -> int:
        return db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read.is_(False)).count()

    def process_deliveries(
        self,
        db: Session,
        *,
        limit: int = 100,
        delivery_id: UUID | None = None,
        include_failed: bool = False,
        max_attempts: int = 3,
    ) -> dict[str, int]:
        """Send queued external deliveries using configured provider adapters."""
        statuses = [NotificationDeliveryStatus.pending]
        if include_failed:
            statuses.append(NotificationDeliveryStatus.failed)
        query = db.query(NotificationDelivery).filter(
            NotificationDelivery.status.in_(statuses),
            NotificationDelivery.attempts < max_attempts,
        )
        if delivery_id is not None:
            query = query.filter(NotificationDelivery.id == delivery_id)
        rows = query.order_by(NotificationDelivery.created_at).with_for_update(skip_locked=True).limit(limit).all()
        providers = default_providers()
        result = {"processed": 0, "sent": 0, "failed": 0}
        for delivery in rows:
            notification = db.query(Notification).filter(Notification.id == delivery.notification_id).first()
            user = db.query(User).filter(User.id == notification.user_id).first() if notification else None
            delivery.attempts += 1
            delivery.status = NotificationDeliveryStatus.processing
            result["processed"] += 1
            try:
                if not notification or not user:
                    raise ValueError("Notification recipient no longer exists")
                if delivery.channel == NotificationChannel.email:
                    recipient = user.email
                elif delivery.channel == NotificationChannel.sms:
                    recipient = user.phone
                elif delivery.channel == NotificationChannel.push:
                    token = db.query(DeviceToken).filter(DeviceToken.user_id == user.id, DeviceToken.is_active.is_(True)).order_by(DeviceToken.created_at.desc()).first()
                    recipient = token.token if token else None
                else:
                    raise ValueError("In-app delivery does not require provider dispatch")
                if not recipient:
                    raise ValueError(f"No active {delivery.channel.value} recipient is configured")
                provider_result = providers[delivery.channel].send(
                    recipient=recipient,
                    subject=notification.title,
                    message=notification.message,
                    data=notification.data or {},
                )
                delivery.provider = provider_result.provider
                delivery.provider_reference = provider_result.reference
                if not provider_result.accepted:
                    raise ValueError(provider_result.error or "Notification provider rejected delivery")
                delivery.status = NotificationDeliveryStatus.sent
                delivery.sent_at = datetime.now(timezone.utc)
                delivery.failure_reason = None
                result["sent"] += 1
            except Exception as exc:
                delivery.status = NotificationDeliveryStatus.failed
                delivery.failed_at = datetime.now(timezone.utc)
                delivery.failure_reason = str(exc)[:2000]
                result["failed"] += 1
        db.commit()
        return result


notification_service = NotificationService()
