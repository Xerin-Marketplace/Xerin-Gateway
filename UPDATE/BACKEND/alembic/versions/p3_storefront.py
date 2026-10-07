"""Phase 3 Task 11: seller storefront enhancements.

Revision ID: p3_storefront
Revises: p3_external_delivery
"""
from alembic import op
import sqlalchemy as sa

revision = "p3_storefront"
down_revision = "p3_external_delivery"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stores", sa.Column("about", sa.Text(), nullable=True))
    op.add_column("stores", sa.Column("theme_color", sa.String(7), nullable=False, server_default="#111827"))
    op.add_column("stores", sa.Column("secondary_color", sa.String(7), nullable=False, server_default="#ffffff"))
    op.add_column("stores", sa.Column("whatsapp_phone", sa.String(30), nullable=True))
    op.add_column("stores", sa.Column("vacation_mode", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("stores", sa.Column("accept_orders", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("stores", sa.Column("processing_days", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("stores", sa.Column("seo_title", sa.String(255), nullable=True))
    op.add_column("stores", sa.Column("seo_description", sa.String(500), nullable=True))
    op.create_check_constraint("ck_store_processing_days", "stores", "processing_days >= 0 AND processing_days <= 60")


def downgrade():
    op.drop_constraint("ck_store_processing_days", "stores", type_="check")
    for name in ("seo_description", "seo_title", "processing_days", "accept_orders", "vacation_mode", "whatsapp_phone", "secondary_color", "theme_color", "about"):
        op.drop_column("stores", name)
