"""Add explicit payment finalization marker.

Revision ID: p47_payment_finalization_marker
Revises: p46_unpaid_order_expiry
"""
from alembic import op
import sqlalchemy as sa

revision = "p47_payment_finalization_marker"
down_revision = "p46_unpaid_order_expiry"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "payments",
        sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_payments_finalized_at",
        "payments",
        ["finalized_at"],
        unique=False,
    )

    # Existing completed payments predate this marker. They have already gone
    # through the old finalization path, so mark them finalized using paid_at
    # (or their creation timestamp as a conservative fallback).
    op.execute("""
        UPDATE payments
        SET finalized_at = COALESCE(paid_at, updated_at, created_at, now())
        WHERE status = 'completed' AND finalized_at IS NULL
    """)


def downgrade():
    op.drop_index("ix_payments_finalized_at", table_name="payments")
    op.drop_column("payments", "finalized_at")
