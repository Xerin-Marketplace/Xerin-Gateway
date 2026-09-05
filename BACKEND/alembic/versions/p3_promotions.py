
"""Phase 3 Task 14: promotions and campaign engine.

Revision ID: p3_promotions
Revises: p3_wishlist
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_promotions"
down_revision = "p3_wishlist"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "promotions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("promotion_type", sa.String(40), nullable=False),
        sa.Column("discount_value", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("minimum_order_amount", sa.Numeric(18,2), nullable=True),
        sa.Column("maximum_discount_amount", sa.Numeric(18,2), nullable=True),
        sa.Column("usage_limit", sa.Integer(), nullable=True),
        sa.Column("usage_per_customer", sa.Integer(), nullable=True),
        sa.Column("usage_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("stackable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("automatic", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("discount_value >= 0", name="ck_promotion_discount_nonnegative"),
        sa.CheckConstraint("ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at", name="ck_promotion_valid_range"),
    )
    op.create_index("ix_promotions_seller_id", "promotions", ["seller_id"])
    op.create_index("ix_promotions_code", "promotions", ["code"], unique=True)
    op.create_table(
        "promotion_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("promotion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rule_type", sa.String(40), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=True),
        sa.Column("value", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "promotion_usages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("promotion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("promotions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("discount_amount", sa.Numeric(18,2), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "campaigns",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("slug", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("banner_url", sa.Text(), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at", name="ck_campaign_valid_range"),
    )
    op.create_index("ix_campaigns_slug", "campaigns", ["slug"], unique=True)
    op.create_table(
        "campaign_promotions",
        sa.Column("campaign_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("campaigns.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("promotion_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade():
    op.drop_table("campaign_promotions")
    op.drop_index("ix_campaigns_slug", table_name="campaigns")
    op.drop_table("campaigns")
    op.drop_table("promotion_usages")
    op.drop_table("promotion_rules")
    op.drop_index("ix_promotions_code", table_name="promotions")
    op.drop_index("ix_promotions_seller_id", table_name="promotions")
    op.drop_table("promotions")
