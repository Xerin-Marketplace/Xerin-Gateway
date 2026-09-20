"""Phase 3 Task 1: inventory reservation engine.

Revision ID: p3_inventory_reservations
Revises: phase2_task2_shipments
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_inventory_reservations"
down_revision = "phase2_task2_shipments"
branch_labels = None
depends_on = None


def upgrade():
    reservation_status = postgresql.ENUM("active", "committed", "released", "expired", "cancelled", name="inventoryreservationstatus", create_type=False)
    reservation_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "inventory_reservations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("inventory_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("status", reservation_status, nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("quantity > 0", name="ck_inventory_reservation_quantity_positive"),
        sa.ForeignKeyConstraint(["inventory_id"], ["inventory.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("order_item_id", name="uq_inventory_reservations_order_item_id"),
    )
    op.create_index("ix_inventory_reservations_inventory_id", "inventory_reservations", ["inventory_id"])
    op.create_index("ix_inventory_reservations_order_id", "inventory_reservations", ["order_id"])
    op.create_index("ix_inventory_reservations_order_item_id", "inventory_reservations", ["order_item_id"])
    op.create_index("ix_inventory_reservations_user_id", "inventory_reservations", ["user_id"])
    op.create_index("ix_inventory_reservations_status", "inventory_reservations", ["status"])
    op.create_index("ix_inventory_reservations_expires_at", "inventory_reservations", ["expires_at"])
    op.create_index("ix_inventory_reservation_active_expiry", "inventory_reservations", ["status", "expires_at"])


def downgrade():
    op.drop_table("inventory_reservations")
    postgresql.ENUM(name="inventoryreservationstatus").drop(op.get_bind(), checkfirst=True)
