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
    assert payload["amount"] == "1000.00"


def test_openapi_contains_azampay_callback(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/payments/azampay/callback" in response.json()["paths"]
