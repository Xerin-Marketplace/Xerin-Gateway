"""Add marketplace automatic product approval setting.

Revision ID: p48_auto_product_approval
Revises: p47_payment_finalization_marker
"""
from alembic import op
import sqlalchemy as sa

revision = "p48_auto_product_approval"
down_revision = "p47_payment_finalization_marker"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "marketplace_settings",
        sa.Column(
            "auto_approve_products",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade():
    op.drop_column("marketplace_settings", "auto_approve_products")
