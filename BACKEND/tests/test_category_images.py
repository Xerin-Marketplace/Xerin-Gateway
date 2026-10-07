from pathlib import Path


def test_category_image_contracts():
    models = Path("api/models.py").read_text()
    schemas = Path("api/schemas.py").read_text()
    products = Path("api/routers/products.py").read_text()
    admin = Path("api/routers/admin.py").read_text()
    migration = Path("alembic/versions/p3_category_images.py").read_text()

    assert "image_url = Column(String(500), nullable=True)" in models
    assert "thumbnail_url = Column(String(500), nullable=True)" in models
    assert "image_url: Optional[str] = None" in schemas
    assert '@router.post("/categories/with-image"' in products
    assert '@router.post("/categories/{category_id}/image"' in products
    assert '@router.delete("/categories/{category_id}/image"' in products
    assert '@router.post("/product-categories/with-image"' in admin
    assert 'down_revision = "p3_admin_dashboard"' in migration
