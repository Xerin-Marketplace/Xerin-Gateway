"""Add optional images to product categories.

Revision ID: p3_category_images
Revises: p3_admin_dashboard
"""
from alembic import op
import sqlalchemy as sa

revision = "p3_category_images"
down_revision = "p3_admin_dashboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("image_url", sa.String(length=500), nullable=True))
    op.add_column("categories", sa.Column("thumbnail_url", sa.String(length=500), nullable=True))
    op.add_column("categories", sa.Column("image_storage_key", sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column("categories", "image_storage_key")
    op.drop_column("categories", "thumbnail_url")
    op.drop_column("categories", "image_url")
