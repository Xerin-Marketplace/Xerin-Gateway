"""Phase 3 Task 12: customer reviews and seller ratings.

Revision ID: p3_reviews
Revises: p3_storefront
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_reviews"
down_revision = "p3_storefront"
branch_labels = None
depends_on = None

review_status = postgresql.ENUM("pending", "approved", "rejected", "hidden", "reported", name="reviewstatus", create_type=False)
report_reason = postgresql.ENUM("spam", "abusive", "misleading", "inappropriate", "conflict_of_interest", "other", name="reviewreportreason", create_type=False)


def upgrade():
    bind = op.get_bind()
    review_status.create(bind, checkfirst=True)
    report_reason.create(bind, checkfirst=True)

    op.create_table(
        "product_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_items.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(150)), sa.Column("comment", sa.Text()),
        sa.Column("verified_purchase", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", review_status, nullable=False, server_default="pending"),
        sa.Column("seller_reply", sa.Text()), sa.Column("seller_replied_at", sa.DateTime(timezone=True)),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_product_review_rating"),
        sa.CheckConstraint("helpful_count >= 0", name="ck_product_review_helpful_count"),
        sa.UniqueConstraint("order_item_id"), sa.UniqueConstraint("customer_id", "order_item_id", name="uq_product_review_customer_order_item"),
    )
    for col in ("product_id", "order_item_id", "customer_id", "seller_id", "status"):
        op.create_index(f"ix_product_reviews_{col}", "product_reviews", [col])

    op.create_table(
        "store_reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("stores.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seller_orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False), sa.Column("title", sa.String(150)), sa.Column("comment", sa.Text()),
        sa.Column("verified_purchase", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("status", review_status, nullable=False, server_default="pending"),
        sa.Column("seller_reply", sa.Text()), sa.Column("seller_replied_at", sa.DateTime(timezone=True)),
        sa.Column("helpful_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_store_review_rating"),
        sa.CheckConstraint("helpful_count >= 0", name="ck_store_review_helpful_count"),
        sa.UniqueConstraint("seller_order_id"), sa.UniqueConstraint("customer_id", "seller_order_id", name="uq_store_review_customer_seller_order"),
    )
    for col in ("store_id", "seller_order_id", "customer_id", "status"):
        op.create_index(f"ix_store_reviews_{col}", "store_reviews", [col])

    op.create_table("review_images", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("product_review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_reviews.id", ondelete="CASCADE"), nullable=False), sa.Column("image_url", sa.Text(), nullable=False), sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_review_images_product_review_id", "review_images", ["product_review_id"])
    op.create_table("review_votes", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("product_review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_reviews.id", ondelete="CASCADE"), nullable=False), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("is_helpful", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("product_review_id", "user_id", name="uq_review_vote_review_user"))
    op.create_index("ix_review_votes_product_review_id", "review_votes", ["product_review_id"]); op.create_index("ix_review_votes_user_id", "review_votes", ["user_id"])
    op.create_table("review_reports", sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("product_review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_reviews.id", ondelete="CASCADE")), sa.Column("store_review_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("store_reviews.id", ondelete="CASCADE")), sa.Column("reported_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("reason", report_reason, nullable=False), sa.Column("details", sa.Text()), sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.CheckConstraint("(product_review_id IS NOT NULL) <> (store_review_id IS NOT NULL)", name="ck_review_report_single_target"))
    for col in ("product_review_id", "store_review_id", "reported_by_id"):
        op.create_index(f"ix_review_reports_{col}", "review_reports", [col])


def downgrade():
    for table in ("review_reports", "review_votes", "review_images", "store_reviews", "product_reviews"):
        op.drop_table(table)
    bind = op.get_bind(); report_reason.drop(bind, checkfirst=True); review_status.drop(bind, checkfirst=True)
