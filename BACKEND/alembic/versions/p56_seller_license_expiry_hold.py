"""Seller licence expiry hold metadata.

Revision ID: p56_seller_license_expiry_hold
Revises: p55_seller_license_compliance
"""
from alembic import op
import sqlalchemy as sa

revision = "p56_seller_license_expiry_hold"
down_revision = "p55_seller_license_compliance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sellers", sa.Column("suspended_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("sellers", sa.Column("suspension_reason", sa.String(length=120), nullable=True))
    op.create_index("ix_sellers_suspension_reason", "sellers", ["suspension_reason"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_sellers_suspension_reason", table_name="sellers")
    op.drop_column("sellers", "suspension_reason")
    op.drop_column("sellers", "suspended_at")
