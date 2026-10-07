from pathlib import Path
from api.enums import CommissionScope, CommissionRuleType, MarketplaceTransactionType, PermissionCode
from api.models import CommissionRule, OrderItemCommission, MarketplaceTransaction

def test_commission_enums_and_permissions():
    assert CommissionScope.product.value == "product"
    assert CommissionRuleType.percentage.value == "percentage"
    assert MarketplaceTransactionType.seller_earning.value == "seller_earning"
    assert PermissionCode.commissions_write.value == "commissions:write"

def test_commission_model_tables():
    assert CommissionRule.__tablename__ == "commission_rules"
    assert OrderItemCommission.__tablename__ == "order_item_commissions"
    assert MarketplaceTransaction.__tablename__ == "marketplace_transactions"

def test_payment_callback_calculates_commission():
    text=Path("api/routers/payments.py").read_text()
    assert "calculate_order_commissions(db, order)" in text

def test_migration_has_short_revision_id():
    text=Path("alembic/versions/p3_commission_engine.py").read_text()
    assert 'revision="p3_commission_engine"' in text
    assert 'down_revision="p3_inventory_reservations"' in text
