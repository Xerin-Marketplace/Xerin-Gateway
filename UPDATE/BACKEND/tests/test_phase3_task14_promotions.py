
from decimal import Decimal
from pathlib import Path

from api.enums import PermissionCode
from api.main import api
from api.models import Campaign, CampaignPromotion, Promotion, PromotionRule, PromotionUsage
from api.schemas import PromotionCreate


def test_promotion_models_exist():
    assert Promotion.__tablename__ == "promotions"
    assert PromotionRule.__tablename__ == "promotion_rules"
    assert PromotionUsage.__tablename__ == "promotion_usages"
    assert Campaign.__tablename__ == "campaigns"
    assert CampaignPromotion.__tablename__ == "campaign_promotions"


def test_promotion_permissions_exist():
    expected = {"promotions:read", "promotions:create", "promotions:update", "promotions:delete", "campaigns:manage"}
    assert expected.issubset({item.value for item in PermissionCode})


def test_promotion_routes_registered():
    paths = api.openapi()["paths"]
    expected = {
        "/api/v1/promotions/available", "/api/v1/promotions/apply",
        "/api/v1/seller/promotions", "/api/v1/seller/promotions/{promotion_id}",
        "/api/v1/campaigns", "/api/v1/admin/campaigns",
    }
    assert expected.issubset(paths)


def test_percentage_validation():
    try:
        PromotionCreate(name="Bad", promotion_type="percentage", discount_value=Decimal("101"))
    except ValueError:
        pass
    else:
        raise AssertionError("Percentage values above 100 must be rejected")


def test_migration_chain():
    text = Path("alembic/versions/p3_promotions.py").read_text()
    assert 'revision = "p3_promotions"' in text
    assert 'down_revision = "p3_wishlist"' in text
