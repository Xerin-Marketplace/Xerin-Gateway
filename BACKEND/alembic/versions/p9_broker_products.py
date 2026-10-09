"""Add broker_products + broker_product_images tables.

Revision ID: p9_broker_products
Revises: p8_support_tickets
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p9_broker_products"
down_revision = "p8_support_tickets"
branch_labels = None
depends_on = None

product_status = postgresql.ENUM(
    "draft", "pending_review", "approved", "rejected", "inactive",
    name="productstatus",
    create_type=False,
)


def upgrade() -> None:
    op.create_table(
        "broker_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="SET NULL"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column("brand_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("sku", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("price", sa.Numeric(18, 2), nullable=False),
        sa.Column("sale_price", sa.Numeric(18, 2), nullable=True),
        sa.Column("currency", sa.String(10), nullable=True),
        sa.Column("weight", sa.Numeric(10, 2), nullable=True),
        sa.Column("status", product_status, nullable=False, server_default="draft"),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("listing_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("listing_expired_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fulfillment_location", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("reserved_quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broker_products_broker_id", "broker_products", ["broker_id"])
    op.create_index("ix_broker_products_status", "broker_products", ["status"])
    op.create_index("ix_broker_products_sku", "broker_products", ["sku"], unique=True)
    op.create_index("ix_broker_products_slug", "broker_products", ["slug"], unique=True)

    op.create_table(
        "broker_product_images",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.Text(), nullable=False),
        sa.Column("thumbnail_url", sa.Text(), nullable=True),
        sa.Column("storage_key", sa.Text(), nullable=True),
        sa.Column("original_filename", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("file_size", sa.Integer(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("alt_text", sa.String(255), nullable=True),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_primary", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broker_product_images_product_id", "broker_product_images", ["product_id"])
    op.create_unique_constraint("uq_broker_product_images_storage_key", "broker_product_images", ["storage_key"])


def downgrade() -> None:
    op.drop_table("broker_product_images")
    op.drop_table("broker_products")
