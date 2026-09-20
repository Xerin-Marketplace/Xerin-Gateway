"""Seller inventory dashboard, adjustments and stock history.

Revision ID: p3_seller_inventory
Revises: p3_seller_orders
"""
from alembic import op
import sqlalchemy as sa

revision = "p3_seller_inventory"
down_revision = "p3_seller_orders"
branch_labels = None
depends_on = None

NEW_MOVEMENT_VALUES = (
    "restock",
    "manual_correction",
    "damaged",
    "lost",
    "returned",
    "order_cancelled",
    "warehouse_transfer",
)


def upgrade() -> None:
    for value in NEW_MOVEMENT_VALUES:
        op.execute(f"ALTER TYPE inventorymovementtype ADD VALUE IF NOT EXISTS '{value}'")
    op.add_column("inventory_movements", sa.Column("reference", sa.String(length=255), nullable=True))
    op.create_index("ix_inventory_movements_reference", "inventory_movements", ["reference"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_inventory_movements_reference", table_name="inventory_movements")
    op.drop_column("inventory_movements", "reference")
    # PostgreSQL enum values are intentionally retained because removing enum
    # labels safely requires rebuilding the type and all dependent columns.
