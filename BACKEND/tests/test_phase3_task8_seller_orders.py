from api.enums import PermissionCode, SellerOrderStatus
from api.main import api
from api.models import SellerOrder


def test_seller_order_contract():
    assert SellerOrder.__tablename__ == "seller_orders"
    assert SellerOrderStatus.ready_to_ship.value == "ready_to_ship"
    assert PermissionCode.seller_orders_read.value == "seller_orders:read"
    assert PermissionCode.seller_orders_manage.value == "seller_orders:manage"


def test_seller_order_routes_registered():
    paths = api.openapi()["paths"]
    expected = {
        "/api/v1/seller/orders", "/api/v1/seller/orders/summary",
        "/api/v1/seller/orders/{seller_order_id}",
        "/api/v1/seller/orders/{seller_order_id}/accept",
        "/api/v1/seller/orders/{seller_order_id}/start-processing",
        "/api/v1/seller/orders/{seller_order_id}/ready-to-ship",
        "/api/v1/seller/orders/{seller_order_id}/dispatch",
        "/api/v1/seller/orders/{seller_order_id}/request-cancellation",
    }
    assert expected.issubset(paths)


def test_unique_seller_order_per_order_and_seller():
    assert "uq_seller_order_order_seller" in {c.name for c in SellerOrder.__table__.constraints}
