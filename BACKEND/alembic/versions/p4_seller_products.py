"""Seller product ownership and multi-image gallery.

Revision ID: p4_seller_products
Revises: p4_audit_security
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p4_seller_products"
down_revision = "p4_audit_security"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("products", sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_products_approved_by_user_id_users",
        "products",
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.add_column("product_images", sa.Column("thumbnail_url", sa.Text(), nullable=True))
    op.add_column("product_images", sa.Column("storage_key", sa.Text(), nullable=True))
    op.add_column("product_images", sa.Column("original_filename", sa.String(length=255), nullable=True))
    op.add_column("product_images", sa.Column("mime_type", sa.String(length=100), nullable=True))
    op.add_column("product_images", sa.Column("file_size", sa.Integer(), nullable=True))
    op.add_column("product_images", sa.Column("width", sa.Integer(), nullable=True))
    op.add_column("product_images", sa.Column("height", sa.Integer(), nullable=True))
    op.add_column("product_images", sa.Column("alt_text", sa.String(length=255), nullable=True))
    op.add_column("product_images", sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("product_images", sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("product_images", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))

    op.create_index("ix_product_images_product_id", "product_images", ["product_id"], unique=False)
    op.create_unique_constraint("uq_product_images_storage_key", "product_images", ["storage_key"])
    op.create_foreign_key(
        "fk_product_images_uploaded_by_user_id_users",
        "product_images",
        "users",
        ["uploaded_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_check_constraint(
        "ck_product_image_display_order_nonnegative",
        "product_images",
        "display_order >= 0",
    )
    op.create_check_constraint(
        "ck_product_image_file_size_nonnegative",
        "product_images",
        "file_size IS NULL OR file_size >= 0",
    )
    op.alter_column("product_images", "display_order", server_default=None)


def downgrade() -> None:
    op.drop_constraint("ck_product_image_file_size_nonnegative", "product_images", type_="check")
    op.drop_constraint("ck_product_image_display_order_nonnegative", "product_images", type_="check")
    op.drop_constraint("fk_product_images_uploaded_by_user_id_users", "product_images", type_="foreignkey")
    op.drop_constraint("uq_product_images_storage_key", "product_images", type_="unique")
    op.drop_index("ix_product_images_product_id", table_name="product_images")

    for column in (
        "updated_at",
        "uploaded_by_user_id",
        "display_order",
        "alt_text",
        "height",
        "width",
        "file_size",
        "mime_type",
        "original_filename",
        "storage_key",
        "thumbnail_url",
    ):
        op.drop_column("product_images", column)

    op.drop_constraint("fk_products_approved_by_user_id_users", "products", type_="foreignkey")
    op.drop_column("products", "approved_by_user_id")
    op.drop_column("products", "approved_at")
    op.drop_column("products", "submitted_at")
