"""Task 7: payment callback idempotency

Revision ID: p13_payment_callback_idempotency
Revises: p12_customer_checkout_snapshot
"""

from alembic import op
import sqlalchemy as sa

revision = "p13_payment_callback_idempotency"
down_revision = "p12_customer_checkout_snapshot"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "payment_transactions",
        sa.Column("idempotency_key", sa.String(length=255), nullable=True),
    )
    op.create_index(
        "ux_payment_transactions_idempotency_key",
        "payment_transactions",
        ["idempotency_key"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index(
        "ux_payment_transactions_idempotency_key",
        table_name="payment_transactions",
    )
    op.drop_column("payment_transactions", "idempotency_key")
