"""Add order_number column and received_at_hub status to orders.

Revision ID: p5_order_number
Revises: p3_category_images
"""
from alembic import op
import sqlalchemy as sa


revision = "p5_order_number"
down_revision = "p3_category_images"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("order_number", sa.String(length=20), nullable=True))
    op.create_index("ix_orders_order_number", "orders", ["order_number"], unique=True)

    op.execute(
        "ALTER TYPE orderstatus ADD VALUE IF NOT EXISTS 'received_at_hub'"
    )


def downgrade() -> None:
    op.drop_index("ix_orders_order_number", table_name="orders")
    op.drop_column("orders", "order_number")
