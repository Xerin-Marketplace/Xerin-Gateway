from uuid import uuid4

from api.config import settings


def _payload():
    return {
        "payment_id": str(uuid4()),
        "provider": "mpesa",
        "transaction_id": "TX-123",
        "status": "completed",
        "payload": {"receipt": "TX-123"},
    }


def test_callback_rejects_missing_webhook_secret(client):
    response = client.post("/api/v1/payments/callback/mpesa", json=_payload())
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid payment webhook signature"


def test_callback_rejects_wrong_webhook_secret(client):
    response = client.post(
        "/api/v1/payments/callback/mpesa",
        headers={"X-Webhook-Secret": "wrong"},
        json=_payload(),
    )
    assert response.status_code == 401


def test_callback_rejects_provider_mismatch_before_database_access(client):
    payload = _payload()
    payload["provider"] = "airtel"
    response = client.post(
        "/api/v1/payments/callback/mpesa",
        headers={"X-Webhook-Secret": settings.PAYMENT_WEBHOOK_SECRET},
        json=payload,
    )
    assert response.status_code == 422
