from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from api.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEvent
from api.models import Notification, NotificationDelivery, NotificationPreference, User


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


notification_service = NotificationService()
