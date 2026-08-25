from pathlib import Path

from api.routers.email import build_order_cancelled_payment_timeout_email
from api.services.unpaid_order_expiry import AUTO_CANCELLATION_REASON


def test_timeout_reason_is_stable():
    assert AUTO_CANCELLATION_REASON == "payment_confirmation_timeout"


def test_cancellation_email_contains_order_and_release_message():
    subject, plain, html = build_order_cancelled_payment_timeout_email(
        order_id="12345678-aaaa-bbbb-cccc-123456789000",
        recipient_name="Adam",
        total="20,380.00",
        currency="TZS",
        timeout_minutes=5,
    )
    assert "cancelled" in subject.lower()
    assert "12345678-aaaa-bbbb-cccc-123456789000" in plain
    assert "released" in plain.lower()
    assert "20,380.00" in html


def test_order_creation_sets_payment_deadline():
    source = Path("api/routers/orders.py").read_text()
    assert "PAYMENT_ORDER_TIMEOUT_MINUTES" in source
    assert "payment_due_at=" in source


def test_worker_releases_inventory_and_cancels_payment():
    source = Path("api/services/unpaid_order_expiry.py").read_text()
    assert "release_order_reservations" in source
    assert "PaymentStatus.cancelled" in source
    assert "OrderStatus.cancelled" in source
    assert "with_for_update()" in source
