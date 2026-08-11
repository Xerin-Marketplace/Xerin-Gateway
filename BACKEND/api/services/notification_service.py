from __future__ import annotations

import logging
from datetime import datetime, timezone
from string import Template
from typing import Any, Iterable
from uuid import UUID

from sqlalchemy.orm import Session

from api.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEvent
from api.models import Notification, NotificationDelivery, NotificationPreference, NotificationTemplate, User

logger = logging.getLogger(__name__)


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

    def _get_template(self, db: Session, event: NotificationEvent, channel: NotificationChannel) -> NotificationTemplate | None:
        return db.query(NotificationTemplate).filter(
            NotificationTemplate.event == event,
            NotificationTemplate.channel == channel,
            NotificationTemplate.is_active.is_(True),
        ).first()

    def _render(self, template_str: str, context: dict[str, Any]) -> str:
        try:
            return Template(template_str).safe_substitute(context)
        except Exception:
            return template_str

    def _get_user_contact(self, user: User) -> tuple[str | None, str | None]:
        phone = user.phone
        email = user.email
        return phone, email

    def _send_sms(self, to: str, message: str) -> dict[str, Any]:
        try:
            from api.routers.sms import send_sms
            response = send_sms(to, message)
            return {"accepted": True, "provider": "africastalking", "reference": str(response) if response else None}
        except Exception as exc:
            logger.error("SMS send failed to %s: %s", to, exc)
            return {"accepted": False, "provider": "africastalking", "error": str(exc)}

    def _send_email(self, to: str, subject: str, body: str, html: str | None = None) -> dict[str, Any]:
        try:
            from api.routers.email import send_email
            send_email(to, subject, body, html)
            return {"accepted": True, "provider": "smtp"}
        except Exception as exc:
            logger.error("Email send failed to %s: %s", to, exc)
            return {"accepted": False, "provider": "smtp", "error": str(exc)}

    def dispatch_deliveries(self, db: Session, notification: Notification, user: User) -> None:
        """Attempt to send all pending deliveries for a notification using templates."""
        pending = db.query(NotificationDelivery).filter(
            NotificationDelivery.notification_id == notification.id,
            NotificationDelivery.status.in_([NotificationDeliveryStatus.pending, NotificationDeliveryStatus.failed]),
        ).all()
        phone, email = self._get_user_contact(user)
        context = notification.data or {}
        context.setdefault("user_name", f"{user.first_name} {user.last_name}")
        context.setdefault("title", notification.title)

        for delivery in pending:
            template = self._get_template(db, notification.event, delivery.channel)
            if not template:
                continue
            body = self._render(template.body_template, context)
            subject = self._render(template.subject_template, context) if template.subject_template else notification.title

            delivery.status = NotificationDeliveryStatus.processing
            delivery.attempts += 1
            db.flush()

            if delivery.channel == NotificationChannel.sms and phone:
                result = self._send_sms(phone, body)
            elif delivery.channel == NotificationChannel.email and email:
                result = self._send_email(email, subject, body)
            elif delivery.channel == NotificationChannel.push:
                result = {"accepted": True, "provider": "deferred_push"}
            else:
                result = {"accepted": False, "provider": "none", "error": "No contact info"}

            now = datetime.now(timezone.utc)
            if result.get("accepted"):
                delivery.status = NotificationDeliveryStatus.sent
                delivery.sent_at = now
                delivery.provider = result.get("provider")
                delivery.provider_reference = result.get("reference")
            else:
                delivery.status = NotificationDeliveryStatus.failed
                delivery.failed_at = now
                delivery.failure_reason = result.get("error", "Unknown error")
                delivery.provider = result.get("provider")
            db.flush()

    def notify(self, *, db: Session, user_id: UUID, event: NotificationEvent | str, title: str, message: str, data: dict[str, Any] | None = None, action_url: str | None = None, channels: Iterable[NotificationChannel] | None = None, commit: bool = True, dispatch: bool = True) -> Notification:
        event_value = event if isinstance(event, NotificationEvent) else NotificationEvent(event)
        preference = self.get_or_create_preferences(db, user_id)
        selected = list(channels) if channels is not None else self.enabled_channels(preference, event_value)
        notification = Notification(user_id=user_id, event=event_value, title=title, message=message, data=data or {}, action_url=action_url)
        db.add(notification); db.flush()
        for channel in selected:
            status = NotificationDeliveryStatus.delivered if channel == NotificationChannel.in_app else NotificationDeliveryStatus.pending
            now = datetime.now(timezone.utc) if channel == NotificationChannel.in_app else None
            db.add(NotificationDelivery(notification_id=notification.id, channel=channel, status=status, delivered_at=now))
        db.flush()

        if dispatch:
            user = db.query(User).filter(User.id == user_id).first()
            if user:
                try:
                    self.dispatch_deliveries(db, notification, user)
                except Exception as exc:
                    logger.error("Dispatch failed for notification %s: %s", notification.id, exc)

        if commit:
            db.commit(); db.refresh(notification)
        return notification

    def notify_admins(self, *, db: Session, event: NotificationEvent, title: str, message: str, data: dict[str, Any] | None = None, channels: Iterable[NotificationChannel] | None = None) -> list[Notification]:
        """Send notification to all admin/super_admin users."""
        admins = db.query(User).filter(User.account_type.in_(["admin", "super_admin"])).all()
        results = []
        for admin in admins:
            n = self.notify(
                db=db, user_id=admin.id, event=event, title=title, message=message,
                data=data or {}, channels=channels or [NotificationChannel.in_app, NotificationChannel.email],
                commit=False, dispatch=True,
            )
            results.append(n)
        db.commit()
        return results

    def unread_count(self, db: Session, user_id: UUID) -> int:
        return db.query(Notification).filter(Notification.user_id == user_id, Notification.is_read.is_(False)).count()


notification_service = NotificationService()
