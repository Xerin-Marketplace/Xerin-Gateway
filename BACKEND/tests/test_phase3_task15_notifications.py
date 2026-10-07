from pathlib import Path

import pytest
from pydantic import ValidationError

from api.enums import NotificationChannel, NotificationDeliveryStatus, PermissionCode
from api.main import api
from api.models import DeviceToken, Notification, NotificationDelivery, NotificationPreference, NotificationTemplate
from api.schemas import NotificationPreferenceUpdate


def test_notification_models_exist():
    assert Notification.__tablename__ == "notifications"
    assert NotificationPreference.__tablename__ == "notification_preferences"
    assert NotificationTemplate.__tablename__ == "notification_templates"
    assert NotificationDelivery.__tablename__ == "notification_deliveries"
    assert DeviceToken.__tablename__ == "device_tokens"

def test_notification_enums():
    assert {x.value for x in NotificationChannel} == {"in_app","email","sms","push"}
    assert {"pending","sent","delivered","failed"}.issubset({x.value for x in NotificationDeliveryStatus})

def test_notification_permissions_exist():
    expected={"notifications:read","notifications:manage","admin_notifications:read","admin_notifications:manage","admin_notification_templates:manage"}
    assert expected.issubset({x.value for x in PermissionCode})

def test_routes_registered():
    paths=api.openapi()["paths"]
    expected={"/api/v1/notifications","/api/v1/notifications/summary","/api/v1/notifications/read-all","/api/v1/notifications/{notification_id}/read","/api/v1/notifications/preferences","/api/v1/admin/notification-templates","/api/v1/admin/notification-templates/{template_id}"}
    assert expected.issubset(paths)

def test_preference_validation_rejects_unknown_event():
    with pytest.raises(ValidationError):
        NotificationPreferenceUpdate(event_preferences={"not_real":{"email":True}})

def test_migration_chain():
    text=Path("alembic/versions/p3_notifications.py").read_text()
    assert 'revision = "p3_notifications"' in text
    assert 'down_revision = "p3_promotions"' in text
