from pathlib import Path

from api.main import api
from api.models import Seller, User, UserRole
from api.schemas import SellerApplicationRequest, SellerApplicationStatusResponse


def test_become_seller_routes_registered():
    paths = set(api.openapi()["paths"])
    assert "/api/v1/sellers/apply" in paths
    assert "/api/v1/sellers/application-status" in paths


def test_application_schema_uses_existing_account_identity():
    fields = SellerApplicationRequest.model_fields
    assert "business_name" in fields
    assert "business_category_ids" in fields
    assert "agreement_accepted" in fields
    assert "email" not in fields
    assert "phone" not in fields
    assert "password" not in fields


def test_application_status_contract():
    fields = SellerApplicationStatusResponse.model_fields
    assert {"has_application", "status", "can_access_seller_dashboard"} <= set(fields)


def test_database_supports_one_user_with_customer_and_seller_roles():
    assert Seller.__table__.c.user_id.unique is True
    assert UserRole.__table__.c.user_id.primary_key is True
    assert User.__table__.c.email.unique is True
    assert User.__table__.c.phone.unique is True


def test_admin_approval_assigns_seller_role():
    text = Path("api/routers/sellers.py").read_text(encoding="utf-8")
    assert '_assign_role(db, seller.user_id, "seller")' in text
    assert "seller.approved_at" in text
