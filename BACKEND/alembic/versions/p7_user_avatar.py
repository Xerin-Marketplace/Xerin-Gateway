"""Add avatar_url to users for profile photos.

Revision ID: p7_user_avatar
Revises: p6_logistics_kyc_fare
"""
from alembic import op
import sqlalchemy as sa


revision = "p7_user_avatar"
down_revision = "p6_logistics_kyc_fare"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "avatar_url")
