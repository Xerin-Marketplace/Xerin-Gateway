"""Broker B2 own products and 24-hour listing lifecycle.

Revision ID: b2_broker_own_products
Revises: b1_broker_identity_access
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2_broker_own_products"
down_revision = "b1_broker_identity_access"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("products", "seller_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.alter_column("products", "store_id", existing_type=postgresql.UUID(as_uuid=True), nullable=True)
    op.add_column("products", sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("products", sa.Column("listing_owner_type", sa.String(20), nullable=False, server_default="seller"))
    op.add_column("products", sa.Column("listing_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("listing_expired_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("fulfillment_location", sa.Text(), nullable=True))
    op.create_foreign_key("fk_products_broker_id", "products", "brokers", ["broker_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_products_broker_id", "products", ["broker_id"])
    op.create_index("ix_products_listing_owner_type", "products", ["listing_owner_type"])
    op.create_index("ix_products_listing_expires_at", "products", ["listing_expires_at"])
    op.create_index("ix_products_listing_expired_at", "products", ["listing_expired_at"])
    op.create_check_constraint("ck_product_listing_owner_type", "products", "listing_owner_type IN ('seller','broker')")
    op.create_check_constraint("ck_product_listing_owner_consistency", "products", "(listing_owner_type = 'seller' AND seller_id IS NOT NULL AND store_id IS NOT NULL AND broker_id IS NULL) OR (listing_owner_type = 'broker' AND broker_id IS NOT NULL AND seller_id IS NULL AND store_id IS NULL)")


def downgrade():
    op.drop_constraint("ck_product_listing_owner_consistency", "products", type_="check")
    op.drop_constraint("ck_product_listing_owner_type", "products", type_="check")
    op.drop_index("ix_products_listing_expired_at", table_name="products")
    op.drop_index("ix_products_listing_expires_at", table_name="products")
    op.drop_index("ix_products_listing_owner_type", table_name="products")
    op.drop_index("ix_products_broker_id", table_name="products")
    op.drop_constraint("fk_products_broker_id", "products", type_="foreignkey")
    op.drop_column("products", "fulfillment_location")
    op.drop_column("products", "listing_expired_at")
    op.drop_column("products", "listing_expires_at")
    op.drop_column("products", "listing_owner_type")
    op.drop_column("products", "broker_id")
    op.alter_column("products", "store_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
    op.alter_column("products", "seller_id", existing_type=postgresql.UUID(as_uuid=True), nullable=False)
