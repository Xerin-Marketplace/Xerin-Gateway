from pathlib import Path


def test_order_items_snapshot_store_origin():
    source = Path("api/routers/orders.py").read_text()
    assert "store_id=cart_item.product.store_id" in source


def test_payment_fulfillment_groups_by_seller_and_store():
    source = Path("api/routers/payments.py").read_text()
    assert "grouped: dict[tuple[UUID, UUID], list]" in source
    assert "SellerOrder.store_id == store_id" in source
    assert "store_id=store_id" in source


def test_workflow_matches_store_origin():
    source = Path("api/services/order_workflow.py").read_text()
    assert "(row.seller_id, row.store_id)" in source
    assert "(shipment.seller_id, shipment.store_id)" in source


def test_migration_replaces_seller_only_uniqueness():
    source = Path("alembic/versions/p44_store_origin_fulfillment.py").read_text()
    assert "uq_seller_order_order_seller_store" in source
    assert "uq_shipment_order_seller_store" in source
