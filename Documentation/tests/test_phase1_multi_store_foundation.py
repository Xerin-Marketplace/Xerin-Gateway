from pathlib import Path


def _text(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_seller_store_relationship_is_one_to_many():
    models = _text("api/models.py")
    assert "stores = relationship(" in models
    assert 'back_populates="stores"' in models
    store_block = models.split("class Store(Base):", 1)[1].split("class StoreGalleryImage", 1)[0]
    seller_id_block = store_block.split("seller_id = Column(", 1)[1].split("store_name = Column", 1)[0]
    assert "unique=True" not in seller_id_block


def test_store_scope_enum_and_model_field_exist():
    enums = _text("api/enums.py")
    models = _text("api/models.py")
    assert "class StoreScope" in enums
    assert 'local = "local"' in enums
    assert 'global_ = "global"' in enums
    assert "store_scope = Column(" in models


def test_multi_store_api_contract_exists():
    routes = _text("api/routers/stores.py")
    schemas = _text("api/schemas.py")
    assert '"/mine"' in routes
    assert '"/mine/{store_id}"' in routes
    assert "def create_my_store(" in routes
    assert "def list_my_stores(" in routes
    assert "class StoreCreate" in schemas
    assert "store_scope: StoreScope" in schemas


def test_scope_is_backend_derived_from_country():
    routes = _text("api/routers/stores.py")
    assert "def derive_store_scope" in routes
    assert "TANZANIA_COUNTRY_NAMES" in routes
    assert "StoreScope.local" in routes
    assert "StoreScope.global_" in routes


def test_migration_removes_one_store_unique_rule():
    migration = _text("alembic/versions/p39_multi_store_foundation.py")
    assert 'down_revision = "p38_partner_webhooks"' in migration
    assert "get_unique_constraints" in migration
    assert 'op.add_column(\n        "stores"' in migration
    assert "ix_stores_store_scope" in migration
