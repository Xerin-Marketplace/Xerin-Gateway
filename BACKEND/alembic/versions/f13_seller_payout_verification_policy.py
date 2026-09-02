"""F13 configurable seller payout account verification.

Revision ID: f13_payout_verification
Revises: f9_role_continuity
"""
from alembic import op
import sqlalchemy as sa

revision = "f13_payout_verification"
down_revision = "f9_role_continuity"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column(
        "marketplace_settings",
        sa.Column(
            "auto_verify_seller_payout_accounts",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

def downgrade():
    op.drop_column("marketplace_settings", "auto_verify_seller_payout_accounts")
