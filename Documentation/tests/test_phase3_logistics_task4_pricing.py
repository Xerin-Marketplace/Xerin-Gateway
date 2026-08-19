from decimal import Decimal
from pathlib import Path

from api.enums import MultiSellerPricingStrategy, ShippingRateType
from api.models import ShippingRate
from api.services.multi_seller_pricing import _calculate_amount, _strategy_distance


def test_farthest_seller_strategy():
    distance, seller_id = _strategy_distance(
        MultiSellerPricingStrategy.farthest_seller,
        [
            {"seller_id": "seller-1", "distance_km": Decimal("7")},
            {"seller_id": "seller-2", "distance_km": Decimal("12.5")},
        ],
    )
    assert distance == Decimal("12.500")
    assert seller_id == "seller-2"


def test_sum_individual_strategy():
    distance, seller_id = _strategy_distance(
        MultiSellerPricingStrategy.sum_individual,
        [
            {"seller_id": "seller-1", "distance_km": Decimal("7")},
            {"seller_id": "seller-2", "distance_km": Decimal("5")},
        ],
    )
    assert distance == Decimal("12.000")
    assert seller_id is None


def test_base_plus_distance_pricing_and_minimum_fee():
    rate = ShippingRate(
        rate_type=ShippingRateType.base_plus_per_km,
        base_amount=Decimal("1000"),
        amount_per_km=Decimal("500"),
        minimum_fee=Decimal("5000"),
        maximum_fee=None,
        max_distance_km=Decimal("100"),
    )
    amount, breakdown = _calculate_amount(
        rate, billable_distance_km=Decimal("5")
    )
    assert amount == Decimal("5000.00")
    assert breakdown["minimum_fee_applied"] is True


def test_company_pricing_routes_registered(client):
    paths = client.get("/openapi.json").json()["paths"]
    assert "get" in paths["/api/v1/logistics/me/pricing"]
    assert "patch" in paths["/api/v1/logistics/me/pricing"]
    assert "get" in paths["/api/v1/logistics/me/services"]
    assert "post" in paths["/api/v1/logistics/me/services"]
    assert "patch" in paths["/api/v1/logistics/me/services/{service_id}"]
    assert "delete" in paths["/api/v1/logistics/me/services/{service_id}"]
    assert "get" in paths["/api/v1/logistics/me/rates"]
    assert "post" in paths["/api/v1/logistics/me/rates"]
    assert "patch" in paths["/api/v1/logistics/me/rates/{rate_id}"]
    assert "delete" in paths["/api/v1/logistics/me/rates/{rate_id}"]


def test_task4_migration_extends_task3():
    migration = Path("alembic/versions/p27_logistics_pricing.py").read_text()
    assert 'revision = "p27_logistics_pricing"' in migration
    assert 'down_revision = "p26_logistics_delivery_zones"' in migration
