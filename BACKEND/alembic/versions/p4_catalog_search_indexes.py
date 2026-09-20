"""Add trigram indexes for catalog search performance."""
from alembic import op
revision="p4_catalog_search_indexes"
down_revision="p3_category_images"
branch_labels=None
depends_on=None

def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    for s in [
        "CREATE INDEX IF NOT EXISTS ix_products_name_trgm ON products USING gin (name gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_products_sku_trgm ON products USING gin (sku gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_products_slug_trgm ON products USING gin (slug gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_products_description_trgm ON products USING gin (description gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_categories_name_trgm ON categories USING gin (name gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_categories_slug_trgm ON categories USING gin (slug gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_business_categories_name_trgm ON business_categories USING gin (name gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_business_categories_slug_trgm ON business_categories USING gin (slug gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_business_categories_description_trgm ON business_categories USING gin (description gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_brands_name_trgm ON brands USING gin (name gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_brands_slug_trgm ON brands USING gin (slug gin_trgm_ops)",
        "CREATE INDEX IF NOT EXISTS ix_sellers_business_name_trgm ON sellers USING gin (business_name gin_trgm_ops)",
    ]: op.execute(s)

def downgrade():
    for i in ["ix_sellers_business_name_trgm","ix_brands_slug_trgm","ix_brands_name_trgm","ix_business_categories_description_trgm","ix_business_categories_slug_trgm","ix_business_categories_name_trgm","ix_categories_slug_trgm","ix_categories_name_trgm","ix_products_description_trgm","ix_products_slug_trgm","ix_products_sku_trgm","ix_products_name_trgm"]: op.execute(f"DROP INDEX IF EXISTS {i}")
