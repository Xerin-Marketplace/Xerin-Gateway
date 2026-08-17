from decimal import Decimal
from unittest.mock import Mock, patch

import pytest

from api.services.azampay_service import AzamPayClient


def test_mno_provider_normalization():
    assert AzamPayClient.normalize_mno("Airtel Money") == "Airtel"
    assert AzamPayClient.normalize_mno("Mixx") == "Tigo"
    assert AzamPayClient.normalize_mno("Vodacom") == "Mpesa"
    with pytest.raises(ValueError):
        AzamPayClient.normalize_mno("Unknown")


@patch("api.services.azampay_service.settings")
def test_mobile_checkout_payload(mock_settings):
    mock_settings.AZAMPAY_TIMEOUT_SECONDS = 30
    mock_settings.AZAMPAY_MNO_CHECKOUT_PATH = "/azampay/mno/checkout"
    client = AzamPayClient()
    client._post = Mock(return_value={"success": True, "transactionId": "TX1", "message": "received"})

    result = client.mobile_checkout(
        amount=Decimal("1000.00"),
        currency="TZS",
        phone_number="255700000000",
        provider="Airtel Money",
        external_id="payment-id",
    )

    assert result.transaction_id == "TX1"
    payload = client._post.call_args.args[1]
    assert payload["provider"] == "Airtel"
    assert payload["accountNumber"] == "255700000000"
    assert payload["amount"] == 1000
    assert isinstance(payload["amount"], int)


def test_openapi_contains_azampay_callback(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/payments/azampay/callback" in response.json()["paths"]


def test_mno_checkout_normalizes_msisdn_and_decimal_amount():
    client = AzamPayClient()
    client._post = Mock(return_value={"success": True, "transactionId": "TX2", "message": "received"})
    client.mobile_checkout(amount=Decimal("1000.50"), currency="tzs", phone_number="+255 700-000-000", provider="Vodacom", external_id="payment-123", additional_properties={"order_id": "order-123"})
    payload = client._post.call_args.args[1]
    assert payload["accountNumber"] == "255700000000"
    assert payload["amount"] == 1000.5
    assert payload["currency"] == "TZS"
    assert payload["externalId"] == "payment-123"
    assert payload["provider"] == "Mpesa"

@pytest.mark.parametrize("amount", [Decimal("-1"), Decimal("5000000.01")])
def test_mno_checkout_rejects_amount_outside_azampay_range(amount):
    client = AzamPayClient(); client._post = Mock()
    with pytest.raises(ValueError, match="between 0 and 5,000,000"):
        client.mobile_checkout(amount=amount, currency="TZS", phone_number="255700000000", provider="Airtel", external_id="payment-id")
    client._post.assert_not_called()

def test_mno_checkout_rejects_oversized_additional_properties():
    client = AzamPayClient(); client._post = Mock()
    with pytest.raises(ValueError, match="4096 bytes"):
        client.mobile_checkout(amount=Decimal("1000"), currency="TZS", phone_number="255700000000", provider="Airtel", external_id="payment-id", additional_properties={"data": "x" * 5000})
    client._post.assert_not_called()


@patch("api.services.azampay_service.settings")
def test_payment_partners_parses_registered_merchant_partners(mock_settings):
    mock_settings.AZAMPAY_TIMEOUT_SECONDS = 30
    mock_settings.AZAMPAY_PAYMENT_PARTNERS_PATH = "/api/v1/Partner/GetPaymentPartners"
    client = AzamPayClient()

    response = Mock()
    response.ok = True
    response.status_code = 200
    response.json.return_value = [
        {
            "logoUrl": "https://example.test/airtel.png",
            "partnerName": "Airtel",
            "provider": 2,
            "vendorName": "Xerin",
            "paymentVendorId": "11111111-1111-1111-1111-111111111111",
            "paymentPartnerId": "22222222-2222-2222-2222-222222222222",
            "currency": "TZS",
            "unexpectedSecret": "must-not-leak",
        }
    ]
    client._get = Mock(return_value=response)

    result = client.payment_partners()

    assert result[0]["partnerName"] == "Airtel"
    assert result[0]["provider"] == 2
    assert result[0]["currency"] == "TZS"
    assert "unexpectedSecret" not in result[0]


def test_openapi_contains_azampay_diagnostics(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/payments/azampay/diagnostics" in response.json()["paths"]
