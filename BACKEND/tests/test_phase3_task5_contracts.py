from api.enums import PermissionCode
from api.main import api
from api.schemas import AnalyticsOverviewResponse, ReconciliationResponse
from api.services.analytics_service import resolve_range


def test_analytics_permissions_exist():
    assert PermissionCode.analytics_admin_read.value == "analytics:admin_read"
    assert PermissionCode.analytics_seller_read.value == "analytics:seller_read"


def test_analytics_routes_registered():
    paths = set(api.openapi()["paths"])
    assert "/api/v1/analytics/admin/overview" in paths
    assert "/api/v1/analytics/admin/reconciliation" in paths
    assert "/api/v1/analytics/seller/me/overview" in paths
    assert "/api/v1/analytics/seller/me/products" in paths


def test_analytics_response_contracts():
    assert "money" in AnalyticsOverviewResponse.model_fields
    assert "is_balanced" in ReconciliationResponse.model_fields


def test_default_analytics_range_is_valid():
    start, end = resolve_range(None, None)
    assert start < end
