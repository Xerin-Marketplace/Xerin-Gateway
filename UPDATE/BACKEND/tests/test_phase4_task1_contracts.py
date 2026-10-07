from api.enums import AuditSeverity, PermissionCode, SecurityEventType
from api.main import api
from api.models import AuditLog, SecurityEvent
from api.schemas import AuditLogResponse, SecurityEventResponse
from api.services.audit_service import redact_sensitive


def test_audit_models_exist():
    assert AuditLog.__tablename__ == "audit_logs"
    assert SecurityEvent.__tablename__ == "security_events"
    assert "request_id" in AuditLog.__table__.columns
    assert "resolved" in SecurityEvent.__table__.columns


def test_audit_permissions_exist():
    assert PermissionCode.audit_logs_read.value == "audit_logs:read"
    assert PermissionCode.security_events_read.value == "security_events:read"


def test_audit_routes_registered():
    paths = set(api.openapi()["paths"])
    assert "/api/v1/audit-logs" in paths
    assert "/api/v1/audit-logs/{audit_id}" in paths
    assert "/api/v1/audit-logs/security/events" in paths
    assert "/api/v1/audit-logs/security/events/{event_id}/resolve" in paths


def test_sensitive_values_are_redacted():
    result = redact_sensitive({"email": "a@example.com", "password": "secret", "nested": {"otp": "123456"}})
    assert result["email"] == "a@example.com"
    assert result["password"] == "[REDACTED]"
    assert result["nested"]["otp"] == "[REDACTED]"


def test_audit_response_contracts():
    assert "severity" in AuditLogResponse.model_fields
    assert "event_type" in SecurityEventResponse.model_fields
    assert AuditSeverity.critical.value == "critical"
    assert SecurityEventType.authorization_denied.value == "authorization_denied"
