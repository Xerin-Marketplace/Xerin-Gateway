from datetime import datetime, timezone
from decimal import Decimal

from api.enums import SellerOrderStatus
from api.models import SellerOrderPackage
from api.schemas import SellerOrderPackageCreate, SellerOrderPackageUpdate


def test_package_create_contract_supports_logistics_handling():
    data = SellerOrderPackageCreate(
        package_label="Box 1",
        package_type="box",
        contents_summary="Electronics",
        weight_kg=Decimal("2.5"),
        length_cm=Decimal("30"),
        width_cm=Decimal("20"),
        height_cm=Decimal("15"),
        fragile=True,
        keep_upright=True,
        declared_value=Decimal("350000"),
        declared_currency="tzs",
        is_ready=True,
    )
    assert data.package_type == "box"
    assert data.fragile is True
    assert data.declared_currency == "TZS"


def test_ready_package_requires_weight():
    try:
        SellerOrderPackageCreate(package_type="parcel", is_ready=True)
    except Exception:
        return
    raise AssertionError("Ready package without weight should fail")


def test_package_update_is_partial():
    data = SellerOrderPackageUpdate(fragile=True)
    assert data.model_dump(exclude_unset=True) == {"fragile": True}


def test_package_indexes_exist():
    names = {index.name for index in SellerOrderPackage.__table__.indexes}
    assert "ix_seller_order_packages_order_ready" in names
    assert "ix_seller_order_packages_package_type" in names


def test_package_crud_paths_exist(client):
    paths = client.get("/openapi.json").json()["paths"]
    root = "/api/v1/seller/orders/{seller_order_id}/packages"
    detail = "/api/v1/seller/orders/{seller_order_id}/packages/{package_id}"
    assert "get" in paths[root]
    assert "post" in paths[root]
    assert "get" in paths[detail]
    assert "patch" in paths[detail]
    assert "delete" in paths[detail]
