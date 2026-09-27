"""Monitoring layer unit tests — redaction, dedup, severity rules.

These run without a live database: everything uses mock/in-memory
sessions or pure functions.
"""
from __future__ import annotations

import os

os.environ.setdefault("MONITORING_ENABLED", "true")
os.environ.setdefault("MONITORING_ALERT_EMAIL", "ops@example.com")

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from api.enums import AuditSeverity, SecurityEventType
from api.services.audit_service import redact_sensitive
from api.services.monitoring import should_email, _alert_body


class TestRedaction:
    def test_redacts_passwords_and_tokens(self):
        payload = {
            "password": "secret123",
            "access_token": "jwt.abc",
            "nested": {"otp": "123456", "note": "ok"},
            "items": [{"api_key": "k1"}, {"safe": True}],
        }
        out = redact_sensitive(payload)
        assert out["password"] == "[REDACTED]"
        assert out["access_token"] == "[REDACTED]"
        assert out["nested"]["otp"] == "[REDACTED]"
        assert out["nested"]["note"] == "ok"
        assert out["items"][0]["api_key"] == "[REDACTED]"
        assert out["items"][1]["safe"] is True


class TestSeverityRules:
    def test_critical_always_emails(self):
        assert should_email(AuditSeverity.critical, "order.created")

    def test_warning_emails(self):
        assert should_email(AuditSeverity.warning, "auth.failed_login")

    def test_notice_alertable_prefix(self):
        assert should_email(AuditSeverity.notice, "payment.completed")
        assert not should_email(AuditSeverity.notice, "product.viewed")

    def test_info_never_emails(self):
        assert not should_email(AuditSeverity.info, "order.created")


class TestAlertBody:
    def test_no_secrets_in_body(self):
        body = _alert_body(
            severity=AuditSeverity.critical,
            title="SECURITY ALERT",
            details={"Endpoint": "/api/x", "IP": "1.2.3.4"},
        )
        assert "CRITICAL" in body
        assert "SECURITY ALERT" in body
        assert "1.2.3.4" in body

    def test_intrusion_blocks_sqli(self):
        from api.middleware.intrusion import _classify
        verdict = _classify("/api/products?id=' OR '1'='1")
        assert verdict is not None
        assert verdict[0] == SecurityEventType.sql_injection_attempt

    def test_intrusion_blocks_traversal(self):
        from api.middleware.intrusion import _classify
        verdict = _classify("/files/../../etc/passwd")
        assert verdict is not None
        assert verdict[0] == SecurityEventType.path_traversal_attempt

    def test_intrusion_allows_normal(self):
        from api.middleware.intrusion import _classify
        assert _classify("/products?q=jacket&page=2") is None
        assert _classify("/search?q=men's shoes") is None


class TestEmailDeliveryTracking:
    def test_failed_email_keeps_notification_pending(self):
        from api.services.email_alerts import deliver_alert
        from api.models import AlertNotification

        n = AlertNotification(
            dedup_key="k", recipient="ops@example.com",
            subject="s", body_text="b", severity="critical",
            status="pending", attempts=0,
        )
        db = MagicMock()
        with patch("api.services.email_alerts.send_email", side_effect=OSError("smtp down")):
            deliver_alert(db, n)
        assert n.status == "pending"
        assert n.attempts == 1
        assert n.next_retry_at is not None
        assert "OSError" in (n.last_error or "")

    def test_successful_email_marks_sent(self):
        from api.services.email_alerts import deliver_alert
        from api.models import AlertNotification

        n = AlertNotification(
            dedup_key="k", recipient="ops@example.com",
            subject="s", body_text="b", severity="critical",
            status="pending", attempts=0,
        )
        db = MagicMock()
        with patch("api.services.email_alerts.send_email", return_value=None):
            deliver_alert(db, n)
        assert n.status == "sent"
        assert n.sent_at is not None
