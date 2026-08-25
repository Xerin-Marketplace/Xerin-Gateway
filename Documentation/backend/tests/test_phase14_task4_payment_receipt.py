from io import BytesIO
from types import SimpleNamespace
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from pypdf import PdfReader

from api.services.payment_receipt import build_payment_receipt_pdf


def _order():
    return SimpleNamespace(
        id="11111111-2222-3333-4444-555555555555",
        total=Decimal("20380.00"),
        currency="TZS",
        user=SimpleNamespace(first_name="Adam", last_name="Customer"),
        shipping_address=SimpleNamespace(recipient_name="Adam Customer"),
    )


def _payment(status="completed"):
    now = datetime(2026, 8, 25, 15, 30, tzinfo=timezone.utc)
    return SimpleNamespace(
        id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        amount=Decimal("20380.00"),
        currency="TZS",
        method=SimpleNamespace(value="mobile_money"),
        provider="zenopay",
        status=SimpleNamespace(value=status),
        provider_transaction_id="PROVIDER-REF-123",
        paid_at=now,
        created_at=now,
        updated_at=now,
    )


def test_receipt_requires_completed_payment():
    with pytest.raises(ValueError):
        build_payment_receipt_pdf(_order(), _payment("pending"))


def test_receipt_pdf_contains_verified_payment_details():
    pdf = build_payment_receipt_pdf(_order(), _payment())
    assert pdf.startswith(b"%PDF")
    text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(pdf)).pages)
    assert "PAYMENT RECEIPT" in text
    assert "PAYMENT SUCCESSFUL" in text
    assert "PROVIDER-REF-123" in text
    assert "20,380.00" in text
