"""Scope seller product SKUs per seller instead of marketplace-wide.

Revision ID: p53_seller_scoped_product_sku
Revises: p52_merge_delivery_specs
"""
from alembic import op

revision = "p53_seller_scoped_product_sku"
down_revision = "p52_merge_delivery_specs"
branch_labels = None
depends_on = None


def upgrade():
    # Product SKU used to be globally unique. In a marketplace, different sellers
    # may legitimately use the same manufacturer/internal SKU.
    op.execute("""
        DO $$
        DECLARE
            constraint_name text;
        BEGIN
            SELECT con.conname
              INTO constraint_name
              FROM pg_constraint con
              JOIN pg_class rel ON rel.oid = con.conrelid
              JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
             WHERE nsp.nspname = current_schema()
               AND rel.relname = 'products'
               AND con.contype = 'u'
               AND (
                    SELECT array_agg(att.attname ORDER BY cols.ordinality)
                      FROM unnest(con.conkey) WITH ORDINALITY AS cols(attnum, ordinality)
                      JOIN pg_attribute att
                        ON att.attrelid = rel.oid
                       AND att.attnum = cols.attnum
               ) = ARRAY['sku']::name[]
             LIMIT 1;

            IF constraint_name IS NOT NULL THEN
                EXECUTE format('ALTER TABLE products DROP CONSTRAINT %I', constraint_name);
            END IF;
        END $$;
    """)

    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_products_seller_sku
        ON products (seller_id, sku)
        WHERE seller_id IS NOT NULL
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_products_seller_sku")

    # Downgrade is only possible when no duplicate SKU exists across sellers.
    op.execute("""
        ALTER TABLE products
        ADD CONSTRAINT products_sku_key UNIQUE (sku)
    """)
