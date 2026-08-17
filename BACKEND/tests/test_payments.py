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


def test_openapi_contains_payment_retry_endpoint(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    path = "/api/v1/payments/{payment_id}/retry"
    assert path in response.json()["paths"]
    assert "post" in response.json()["paths"][path]


def test_payment_retry_requires_authentication(client):
    response = client.post(
        f"/api/v1/payments/{uuid4()}/retry",
        json={"provider": "Airtel", "phone_number": "255700000000"},
    )
    assert response.status_code in {401, 403}
