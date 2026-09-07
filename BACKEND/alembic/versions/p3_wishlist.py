"""Phase 3 Task 13: wishlist and favorite stores.

Revision ID: p3_wishlist
Revises: p3_reviews
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_wishlist"
down_revision = "p3_reviews"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "wishlist_products",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "product_id", name="uq_wishlist_product_user_product"),
    )
    op.create_index("ix_wishlist_products_product_id", "wishlist_products", ["product_id"])
    op.create_index("ix_wishlist_products_user_id", "wishlist_products", ["user_id"])
    op.create_index("ix_wishlist_products_created_at", "wishlist_products", ["created_at"])
    op.create_index("ix_wishlist_products_user_created", "wishlist_products", ["user_id", "created_at"])

    op.create_table(
        "favorite_stores",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "store_id", name="uq_favorite_store_user_store"),
    )
    op.create_index("ix_favorite_stores_store_id", "favorite_stores", ["store_id"])
    op.create_index("ix_favorite_stores_user_id", "favorite_stores", ["user_id"])
    op.create_index("ix_favorite_stores_created_at", "favorite_stores", ["created_at"])
    op.create_index("ix_favorite_stores_user_created", "favorite_stores", ["user_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_favorite_stores_user_created", table_name="favorite_stores")
    op.drop_index("ix_favorite_stores_created_at", table_name="favorite_stores")
    op.drop_index("ix_favorite_stores_user_id", table_name="favorite_stores")
    op.drop_index("ix_favorite_stores_store_id", table_name="favorite_stores")
    op.drop_table("favorite_stores")
    op.drop_index("ix_wishlist_products_user_created", table_name="wishlist_products")
    op.drop_index("ix_wishlist_products_created_at", table_name="wishlist_products")
    op.drop_index("ix_wishlist_products_user_id", table_name="wishlist_products")
    op.drop_index("ix_wishlist_products_product_id", table_name="wishlist_products")
    op.drop_table("wishlist_products")
