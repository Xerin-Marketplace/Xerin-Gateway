from pathlib import Path

from api.enums import PermissionCode, ReviewStatus
from api.main import api
from api.models import ProductReview, ReviewImage, ReviewReport, ReviewVote, StoreReview
from api.schemas import ReviewCreate


def test_review_models_exist():
    assert ProductReview.__tablename__ == "product_reviews"
    assert StoreReview.__tablename__ == "store_reviews"
    assert ReviewImage.__tablename__ == "review_images"
    assert ReviewVote.__tablename__ == "review_votes"
    assert ReviewReport.__tablename__ == "review_reports"


def test_review_permissions_and_statuses():
    assert PermissionCode.reviews_create.value == "reviews:create"
    assert PermissionCode.seller_reviews_reply.value == "seller_reviews:reply"
    assert PermissionCode.admin_reviews_moderate.value == "admin_reviews:moderate"
    assert ReviewStatus.approved.value == "approved"


def test_review_schema_rating_validation():
    assert ReviewCreate(order_item_id="11111111-1111-1111-1111-111111111111", rating=5).rating == 5


def test_review_routes_registered():
    paths = api.openapi()["paths"]
    expected = {
        "/api/v1/products/{product_id}/reviews",
        "/api/v1/reviews/{review_id}",
        "/api/v1/stores/{slug}/reviews",
        "/api/v1/seller/reviews",
        "/api/v1/seller/reviews/{review_id}/reply",
        "/api/v1/seller/reviews/{review_id}/report",
        "/api/v1/admin/reviews",
        "/api/v1/admin/reviews/{review_id}/moderate",
    }
    assert expected.issubset(paths)


def test_review_migration_chain():
    text = Path("alembic/versions/p3_reviews.py").read_text()
    assert 'revision = "p3_reviews"' in text
    assert 'down_revision = "p3_storefront"' in text
