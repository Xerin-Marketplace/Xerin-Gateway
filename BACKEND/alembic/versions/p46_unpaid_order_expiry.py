"""Unpaid order expiry lifecycle.

Revision ID: p46_unpaid_order_expiry
Revises: p45_logistics_country_normalization
"""
from alembic import op
import sqlalchemy as sa

revision = "p46_unpaid_order_expiry"
down_revision = "p45_logistics_country_normalization"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("orders", sa.Column("payment_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("cancellation_reason", sa.String(length=120), nullable=True))
    op.add_column("orders", sa.Column("cancellation_email_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_payment_due_at", "orders", ["payment_due_at"], unique=False)
    op.create_index("ix_orders_cancelled_at", "orders", ["cancelled_at"], unique=False)
    op.create_index("ix_orders_cancellation_reason", "orders", ["cancellation_reason"], unique=False)


def downgrade():
    op.drop_index("ix_orders_cancellation_reason", table_name="orders")
    op.drop_index("ix_orders_cancelled_at", table_name="orders")
    op.drop_index("ix_orders_payment_due_at", table_name="orders")
    op.drop_column("orders", "cancellation_email_sent_at")
    op.drop_column("orders", "cancellation_reason")
    op.drop_column("orders", "cancelled_at")
    op.drop_column("orders", "payment_due_at")
