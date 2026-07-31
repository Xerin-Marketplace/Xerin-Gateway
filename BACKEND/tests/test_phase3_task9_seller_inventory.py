from pathlib import Path


def test_seller_inventory_router_exists():
    text = Path("api/routers/seller_inventory.py").read_text(
        encoding="utf-8"
    )

    routes = (
        '@router.get(""',
        '@router.get("/summary"',
        '@router.get("/low-stock"',
        '@router.get("/history"',
        '@router.post("/{inventory_id}/adjust"',
        '@router.post("/{inventory_id}/restock"',
    )

    for route in routes:
        assert route in text


def test_seller_inventory_permissions_exist():
    text = Path("api/enums.py").read_text()
    assert 'seller_inventory_read = "seller_inventory:read"' in text
    assert 'seller_inventory_manage = "seller_inventory:manage"' in text


def test_inventory_movement_reasons_exist():
    text = Path("api/enums.py").read_text()
    for value in ("restock", "manual_correction", "damaged", "lost", "returned", "order_cancelled", "warehouse_transfer"):
        assert f'{value} = "{value}"' in text


def test_migration_chain():
    text = Path("alembic/versions/p3_seller_inventory.py").read_text()
    assert 'revision = "p3_seller_inventory"' in text
    assert 'down_revision = "p3_seller_orders"' in text
