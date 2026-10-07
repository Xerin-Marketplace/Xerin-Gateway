from api.models import Inventory, Product, Session


def test_refresh_sessions_store_hash_not_raw_token():
    columns = {column.name for column in Session.__table__.columns}
    assert "token_hash" in columns
    assert "refresh_token" not in columns


def test_product_has_money_check_constraints():
    names = {constraint.name for constraint in Product.__table__.constraints}
    assert "ck_product_price_nonnegative" in names
    assert "ck_product_sale_price_lte_price" in names


def test_inventory_has_nonnegative_constraints():
    names = {constraint.name for constraint in Inventory.__table__.constraints}
    assert "ck_inventory_quantity_nonnegative" in names
    assert "ck_inventory_reserved_nonnegative" in names
    assert "ck_inventory_reserved_lte_quantity" in names
