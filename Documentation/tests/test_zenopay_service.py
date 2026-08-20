from decimal import Decimal
from unittest.mock import Mock, patch

import pytest
import requests

from api.services.payment_gateway import GatewayPaymentStatus, PaymentProvider
from api.services.zenopay_service import ZenoPayAPIError, ZenoPayClient


def test_normalizes_tanzanian_phone_numbers():
    assert ZenoPayClient.normalize_phone("+255 712 345 678") == "0712345678"
    assert ZenoPayClient.normalize_phone("0652-449-389") == "0652449389"
    with pytest.raises(ValueError):
        ZenoPayClient.normalize_phone("123")


@patch("api.services.zenopay_service.settings")
def test_initiates_mobile_money_with_current_api_contract(mock_settings):
    mock_settings.ZENOPAY_TIMEOUT_SECONDS = 30
    mock_settings.ZENOPAY_API_KEY = "secret"
    mock_settings.ZENOPAY_BASE_URL = "https://zenoapi.com"
    mock_settings.ZENOPAY_MNO_PAYMENT_PATH = "/api/payments/mobile_money_tanzania"
    mock_settings.ZENOPAY_WEBHOOK_URL = "https://api.xerin.test/api/v1/payments/zenopay/webhook"
    mock_settings.ZENOPAY_MAX_AMOUNT_TZS = 5_000_000
    client = ZenoPayClient()
    client._request = Mock(return_value={"resultcode": "000", "message": "Order submitted"})

    result = client.initiate_mobile_money(
        external_order_id="payment-uuid", buyer_email="buyer@example.com",
        buyer_name="Xerin Buyer", buyer_phone="+255712345678",
        amount=Decimal("1000"), metadata={"payment_id": "payment-uuid"},
    )

    assert result.provider is PaymentProvider.ZENOPAY
    assert result.accepted is True
    assert result.status is GatewayPaymentStatus.PENDING
    payload = client._request.call_args.kwargs["json"]
    assert payload["order_id"] == "payment-uuid"
    assert payload["buyer_phone"] == "0712345678"
    assert payload["amount"] == 1000
    assert "x-api-key" not in payload


@patch("api.services.zenopay_service.settings")
def test_status_check_normalizes_completed_response(mock_settings):
    mock_settings.ZENOPAY_TIMEOUT_SECONDS = 30
    mock_settings.ZENOPAY_API_KEY = "secret"
    mock_settings.ZENOPAY_BASE_URL = "https://zenoapi.com"
    mock_settings.ZENOPAY_ORDER_STATUS_PATH = "/api/payments/order-status"
    client = ZenoPayClient()
    client._request = Mock(return_value={"resultcode": "000", "data": [{
        "order_id": "payment-uuid", "payment_status": "COMPLETED", "amount": "1000",
        "channel": "MPESA", "msisdn": "0712345678", "reference": "ZENO-1",
    }]})

    result = client.check_status("payment-uuid")

    assert result.status is GatewayPaymentStatus.COMPLETED
    assert result.amount == Decimal("1000")
    assert result.provider_reference == "ZENO-1"
    assert client._request.call_args.kwargs["params"] == {"order_id": "payment-uuid"}


@patch("api.services.zenopay_service.settings")
@patch("api.services.zenopay_service.requests.request")
def test_timeout_is_safe_and_retryable(request_mock, mock_settings):
    mock_settings.ZENOPAY_TIMEOUT_SECONDS = 5
    mock_settings.ZENOPAY_API_KEY = "secret"
    mock_settings.ZENOPAY_BASE_URL = "https://zenoapi.com"
    request_mock.side_effect = requests.exceptions.Timeout()
    client = ZenoPayClient()

    with pytest.raises(ZenoPayAPIError) as exc_info:
        client._request("GET", "/api/payments/order-status", params={"order_id": "one"})

    assert exc_info.value.retryable is True
    assert exc_info.value.payload == {"code": "provider_timeout"}
    assert "secret" not in str(exc_info.value)


def test_rejects_fractional_tzs_amount():
    with pytest.raises(ValueError, match="whole number"):
        ZenoPayClient._amount_tzs(Decimal("1000.50"))


def test_openapi_contains_zenopay_routes(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/api/v1/payments/zenopay/webhook" in paths
    assert "/api/v1/payments/{payment_id}/verify-status" in paths


def test_zenopay_webhook_rejects_invalid_order_id_before_database_access(client):
    response = client.post(
        "/api/v1/payments/zenopay/webhook",
        json={"order_id": "not-a-uuid", "payment_status": "COMPLETED"},
    )
    assert response.status_code == 422


def test_zenopay_status_verification_requires_authentication(client):
    from uuid import uuid4

    response = client.post(f"/api/v1/payments/{uuid4()}/verify-status")
    assert response.status_code in {401, 403}
