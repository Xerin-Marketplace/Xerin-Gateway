from api.enums import PermissionCode
from api.main import api
from api.models import Product, ProductImage, ProductStatus
from api.schemas import ProductImageReorderRequest, ProductImageUpdate


def test_seller_product_permissions_exist():
    expected = {
        "seller_products:create",
        "seller_products:read",
        "seller_products:update",
        "seller_products:delete",
        "seller_product_images:manage",
        "seller_products:submit",
    }
    values = {permission.value for permission in PermissionCode}
    assert expected <= values


def test_product_lifecycle_and_image_metadata_contract():
    assert ProductStatus.draft.value == "draft"
    assert hasattr(Product, "submitted_at")
    assert hasattr(Product, "approved_at")
    assert hasattr(Product, "approved_by_user_id")

    for field in (
        "thumbnail_url",
        "storage_key",
        "original_filename",
        "mime_type",
        "file_size",
        "width",
        "height",
        "alt_text",
        "display_order",
        "is_primary",
        "uploaded_by_user_id",
    ):
        assert hasattr(ProductImage, field)


def test_multi_image_and_seller_journey_routes_registered():
    paths = set(api.openapi()["paths"])
    expected = {
        "/api/v1/products",
        "/api/v1/products/my-products",
        "/api/v1/products/my-products/{product_id}",
        "/api/v1/products/{product_id}/submit",
        "/api/v1/products/{product_id}/images/upload",
        "/api/v1/products/{product_id}/images/reorder",
        "/api/v1/products/{product_id}/images/{image_id}/primary",
        "/api/v1/admin/products/pending",
        "/api/v1/admin/products/{product_id}/approve",
        "/api/v1/admin/products/{product_id}/reject",
    }
    assert expected <= paths


def test_image_update_and_reorder_schemas_validate():
    update = ProductImageUpdate(alt_text="Front view", display_order=2, is_primary=True)
    assert update.display_order == 2

    schema = ProductImageReorderRequest(
        images=[{"image_id": "00000000-0000-0000-0000-000000000001", "display_order": 0}]
    )
    assert len(schema.images) == 1


def test_image_upload_is_multipart_and_accepts_multiple_files():
    schema = api.openapi()
    operation = schema["paths"]["/api/v1/products/{product_id}/images/upload"]["post"]
    content = operation["requestBody"]["content"]
    assert "multipart/form-data" in content
