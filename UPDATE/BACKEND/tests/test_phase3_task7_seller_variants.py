from api.enums import PermissionCode
from api.main import api
from api.models import ProductOption, ProductOptionValue, ProductVariant, ProductVariantValue
from api.schemas import ProductVariantCreate, ProductVariantGenerateRequest

def test_variant_models_and_permission_exist():
    assert ProductOption.__tablename__ == "product_options"
    assert ProductOptionValue.__tablename__ == "product_option_values"
    assert ProductVariantValue.__tablename__ == "product_variant_values"
    assert PermissionCode.seller_product_variants_manage.value == "seller_product_variants:manage"
    for field in ("sale_price","barcode","weight","image_id","is_active"):
        assert hasattr(ProductVariant, field)

def test_variant_routes_registered():
    paths=api.openapi()["paths"]
    expected=["/api/v1/products/{product_id}/options","/api/v1/products/{product_id}/options/{option_id}","/api/v1/products/{product_id}/variants/generate","/api/v1/products/my-products/{product_id}/variants","/api/v1/products/{product_id}/variants/{variant_id}"]
    for path in expected: assert path in paths

def test_variant_schema_validation():
    item=ProductVariantCreate(variant_name="Black / M",sku="TS-BLK-M",price=100,sale_price=90,stock_quantity=5)
    assert item.stock_quantity == 5
    req=ProductVariantGenerateRequest(sku_prefix="TS",default_price=100,default_sale_price=80)
    assert req.sku_prefix == "TS"

def test_migration_revision_is_safe_length():
    from pathlib import Path
    text=Path("alembic/versions/p3_seller_variants.py").read_text()
    assert 'revision = "p3_seller_variants"' in text
    assert 'down_revision = "p4_seller_products"' in text
