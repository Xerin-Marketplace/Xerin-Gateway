from decimal import Decimal
from types import SimpleNamespace

from api.services.seller_fulfillment_readiness import _positive


def test_positive_package_measurement():
    assert _positive(Decimal("1.250")) is True
    assert _positive(Decimal("0")) is False
    assert _positive(None) is False


def test_readiness_route_exists(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    path = "/api/v1/seller/orders/{seller_order_id}/fulfillment-readiness"
    assert path in response.json()["paths"]
    assert "get" in response.json()["paths"][path]


def test_ready_to_ship_route_still_exists(client):
    response = client.get("/openapi.json")
    path = "/api/v1/seller/orders/{seller_order_id}/ready-to-ship"
    assert path in response.json()["paths"]
    assert "post" in response.json()["paths"][path]
