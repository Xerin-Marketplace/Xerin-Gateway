from api.enums import DeliveryStatus, PermissionCode
from api.models import DeliveryJob
from api.main import api


def test_delivery_contracts_exist():
    assert DeliveryJob.__tablename__ == "delivery_jobs"
    assert PermissionCode.seller_delivery_request.value == "seller_delivery:request"
    assert DeliveryStatus.awaiting_pickup.value == "awaiting_pickup"


def test_delivery_routes_are_registered():
    paths = api.openapi()["paths"]
    assert "/api/v1/delivery/quote" in paths
    assert "/api/v1/delivery/seller-orders/{seller_order_id}" in paths
    assert "/api/v1/delivery/seller-orders/{seller_order_id}/request" in paths
    assert "/api/v1/delivery/webhooks/{provider}" in paths
