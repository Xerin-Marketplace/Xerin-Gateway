"""Persist district and ward selected during Seller/Winga onboarding.

Revision ID: f9_onboarding_locations
Revises: f7_xerin_express
"""
from alembic import op
import sqlalchemy as sa

revision = "f9_onboarding_locations"
down_revision = "f7_xerin_express"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("seller_profiles", sa.Column("business_district", sa.String(length=100), nullable=True))
    op.add_column("seller_profiles", sa.Column("business_ward", sa.String(length=100), nullable=True))
    op.add_column("brokers", sa.Column("district", sa.String(length=100), nullable=True))
    op.add_column("brokers", sa.Column("ward", sa.String(length=100), nullable=True))


def downgrade():
    op.drop_column("brokers", "ward")
    op.drop_column("brokers", "district")
    op.drop_column("seller_profiles", "business_ward")
    op.drop_column("seller_profiles", "business_district")
