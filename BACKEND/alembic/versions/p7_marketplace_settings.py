"""Admin phase 1 marketplace settings.

Revision ID: p7_marketplace_settings
Revises: p6_payment_admin

Adds global operational settings while reusing the existing commission_rules
table for global/category/seller/product commission configuration.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p7_marketplace_settings"
down_revision = "p6_payment_admin"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "marketplace_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton_key", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("escrow_release_hours", sa.Integer(), nullable=True),
        sa.Column("dispute_period_hours", sa.Integer(), nullable=True),
        sa.Column("cod_allowed", sa.Boolean(), nullable=True),
        sa.Column("international_delivery_allowed", sa.Boolean(), nullable=True),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("singleton_key = 1", name="ck_marketplace_settings_singleton_key"),
        sa.UniqueConstraint("singleton_key", name="uq_marketplace_settings_singleton_key"),
        sa.CheckConstraint(
            "escrow_release_hours IS NULL OR escrow_release_hours BETWEEN 1 AND 720",
            name="ck_marketplace_settings_escrow_release_hours",
        ),
        sa.CheckConstraint(
            "dispute_period_hours IS NULL OR dispute_period_hours BETWEEN 1 AND 720",
            name="ck_marketplace_settings_dispute_period_hours",
        ),
    )


def downgrade() -> None:
    op.drop_table("marketplace_settings")
