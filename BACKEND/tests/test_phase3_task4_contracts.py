from api.main import api
from api.enums import RefundStatus, PermissionCode
from api.models import Refund, RefundItem, RefundEvent, InventoryMovement, SellerWallet

def test_refund_models_exist():
    assert Refund.__tablename__=="refunds" and RefundItem.__tablename__=="refund_items" and RefundEvent.__tablename__=="refund_events"

def test_inventory_movement_and_wallet_debt_contract():
    assert InventoryMovement.__tablename__=="inventory_movements"
    assert hasattr(SellerWallet,"debt_balance")

def test_refund_permissions_and_statuses():
    assert PermissionCode.refunds_create.value=="refunds:create"
    assert RefundStatus.completed.value=="completed" and RefundStatus.processing.value=="processing"

def test_refund_routes_registered():
    paths=set(api.openapi()["paths"]); assert "/api/v1/refunds" in paths and "/api/v1/refunds/{refund_id}/process" in paths and "/api/v1/refunds/admin" in paths

def test_refund_migration_short_revision():
    from pathlib import Path
    text=Path("alembic/versions/p3_refund_engine.py").read_text(); assert 'revision="p3_refund_engine"' in text and 'down_revision="p3_seller_wallets"' in text
