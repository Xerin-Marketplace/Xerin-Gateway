from pathlib import Path

from api.enums import PermissionCode
from api.main import api
from api.models import ProductRecommendation, ProductView, RecommendationEvent, SearchHistory, SearchTerm
from api.schemas import ProductViewCreate, SearchSuggestionResponse


def test_task17_models_exist():
    assert SearchHistory.__tablename__ == "search_history"
    assert SearchTerm.__tablename__ == "search_terms"
    assert ProductView.__tablename__ == "product_views"
    assert ProductRecommendation.__tablename__ == "product_recommendations"
    assert RecommendationEvent.__tablename__ == "recommendation_events"


def test_task17_permissions_exist():
    assert PermissionCode.search_read.value == "search:read"
    assert PermissionCode.recommendations_read.value == "recommendations:read"
    assert PermissionCode.search_history_manage.value == "search_history:manage"
    assert PermissionCode.seller_search_analytics_read.value == "seller_search_analytics:read"


def test_task17_schemas_validate():
    assert ProductViewCreate(source="search").source == "search"
    assert SearchSuggestionResponse(suggestions=["phone"]).suggestions == ["phone"]


def test_task17_routes_registered():
    paths = api.openapi()["paths"]
    expected = {
        "/api/v1/search/products", "/api/v1/search/suggestions", "/api/v1/search/trending",
        "/api/v1/products/{product_id}/view", "/api/v1/products/{product_id}/related",
        "/api/v1/recommendations", "/api/v1/recommendations/recently-viewed",
        "/api/v1/seller/search-analytics", "/api/v1/seller/product-performance",
    }
    assert expected.issubset(paths)


def test_task17_migration_chain():
    text = Path("alembic/versions/p3_search_recommendations.py").read_text()
    assert 'revision = "p3_search_recommendations"' in text
    assert 'down_revision = "p3_product_qa"' in text
    for table in ("search_history", "search_terms", "product_views", "product_recommendations", "recommendation_events"):
        assert table in text
