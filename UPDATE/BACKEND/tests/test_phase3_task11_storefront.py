from pathlib import Path
from api.enums import PermissionCode
from api.main import api
from api.models import Store


def test_storefront_model_contract():
    for field in ("about", "theme_color", "secondary_color", "whatsapp_phone", "vacation_mode", "accept_orders", "processing_days", "seo_title", "seo_description"):
        assert hasattr(Store, field)


def test_storefront_permissions_exist():
    assert PermissionCode.seller_store_read.value == "seller_store:read"
    assert PermissionCode.seller_store_update.value == "seller_store:update"
    assert PermissionCode.seller_store_branding.value == "seller_store:branding"


def test_storefront_routes_registered():
    paths = api.openapi()["paths"]
    for route in ("/api/v1/seller/store", "/api/v1/seller/store/logo", "/api/v1/seller/store/banner", "/api/v1/stores/{slug}/products", "/api/v1/stores/{slug}/categories"):
        assert route in paths
    assert "/api/v1/stores" in paths
    assert "/api/v1/stores/{store_slug}" in paths

def test_storefront_migration_chain():
    text = Path("alembic/versions/p3_storefront.py").read_text()
    assert 'revision = "p3_storefront"' in text
    assert 'down_revision = "p3_external_delivery"' in text
