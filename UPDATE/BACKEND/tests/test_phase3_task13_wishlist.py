from pathlib import Path

from api.enums import PermissionCode
from api.main import api
from api.models import FavoriteStore, WishlistProduct


def test_wishlist_models_and_constraints_exist():
    assert WishlistProduct.__tablename__ == "wishlist_products"
    assert FavoriteStore.__tablename__ == "favorite_stores"
    wishlist_constraints = {constraint.name for constraint in WishlistProduct.__table__.constraints}
    favorite_constraints = {constraint.name for constraint in FavoriteStore.__table__.constraints}
    assert "uq_wishlist_product_user_product" in wishlist_constraints
    assert "uq_favorite_store_user_store" in favorite_constraints


def test_wishlist_permissions_exist():
    assert PermissionCode.wishlist_read.value == "wishlist:read"
    assert PermissionCode.wishlist_manage.value == "wishlist:manage"


def test_wishlist_routes_registered():
    paths = api.openapi()["paths"]
    expected = {
        "/api/v1/wishlist/products",
        "/api/v1/wishlist/products/{product_id}",
        "/api/v1/wishlist/stores",
        "/api/v1/wishlist/stores/{store_slug}",
        "/api/v1/wishlist/summary",
        "/api/v1/wishlist/clear",
    }
    assert expected.issubset(paths)


def test_wishlist_migration_chain():
    text = Path("alembic/versions/p3_wishlist.py").read_text()
    assert 'revision = "p3_wishlist"' in text
    assert 'down_revision = "p3_reviews"' in text


def test_wishlist_router_enforces_visibility_and_ownership():
    text = Path("api/routers/wishlist.py").read_text()
    assert "ProductStatus.approved" in text
    assert "WishlistProduct.user_id == current_user.id" in text
    assert "FavoriteStore.user_id == current_user.id" in text
