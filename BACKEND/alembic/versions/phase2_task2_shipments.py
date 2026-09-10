"""Phase 2 Task 2: checkout shipping and multi-seller shipments.

Revision ID: phase2_task2_shipments
Revises: phase2_task1_shipping
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "phase2_task2_shipments"
down_revision = "phase2_task1_shipping"
branch_labels = None
depends_on = None


def upgrade():
    shipment_status = postgresql.ENUM(
        "pending", "ready_for_dispatch", "dispatched", "in_transit",
        "out_for_delivery", "delivered", "delivery_failed",
        "returned_to_sender", "cancelled", name="shipmentstatus", create_type=False,
    )
    shipment_status.create(op.get_bind(), checkfirst=True)

    op.add_column("orders", sa.Column("shipping_rate_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("orders", sa.Column("shipping_method_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("orders", sa.Column("shipping_method_name", sa.String(120), nullable=True))
    op.add_column("orders", sa.Column("shipping_carrier", sa.String(120), nullable=True))
    op.add_column("orders", sa.Column("estimated_delivery_from", sa.DateTime(timezone=True), nullable=True))
    op.add_column("orders", sa.Column("estimated_delivery_to", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_orders_shipping_rate_id", "orders", ["shipping_rate_id"])
    op.create_index("ix_orders_shipping_method_id", "orders", ["shipping_method_id"])
    op.create_foreign_key("fk_orders_shipping_rate", "orders", "shipping_rates", ["shipping_rate_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_orders_shipping_method", "orders", "shipping_methods", ["shipping_method_id"], ["id"], ondelete="RESTRICT")

    op.create_table("shipments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipping_method_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("status", shipment_status, nullable=False, server_default="pending"),
        sa.Column("carrier_name", sa.String(120), nullable=True),
        sa.Column("tracking_number", sa.String(150), nullable=True),
        sa.Column("estimated_delivery_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("estimated_delivery_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dispatched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["shipping_method_id"], ["shipping_methods.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("order_id", "seller_id", name="uq_shipment_order_seller"),
        sa.UniqueConstraint("tracking_number", name="uq_shipments_tracking_number"),
    )
    op.create_index("ix_shipments_order_id", "shipments", ["order_id"])
    op.create_index("ix_shipments_seller_id", "shipments", ["seller_id"])
    op.create_index("ix_shipments_status", "shipments", ["status"])
    op.create_index("ix_shipments_tracking_number", "shipments", ["tracking_number"])

    op.create_table("shipment_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_shipment_item_quantity_positive"),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("order_item_id", name="uq_shipment_items_order_item_id"),
    )
    op.create_index("ix_shipment_items_shipment_id", "shipment_items", ["shipment_id"])
    op.create_index("ix_shipment_items_order_item_id", "shipment_items", ["order_item_id"])

    op.create_table("shipment_tracking_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", shipment_status, nullable=False),
        sa.Column("location", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["shipment_id"], ["shipments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_shipment_tracking_events_shipment_id", "shipment_tracking_events", ["shipment_id"])


def downgrade():
    op.drop_table("shipment_tracking_events")
    op.drop_table("shipment_items")
    op.drop_table("shipments")
    op.drop_constraint("fk_orders_shipping_method", "orders", type_="foreignkey")
    op.drop_constraint("fk_orders_shipping_rate", "orders", type_="foreignkey")
    op.drop_index("ix_orders_shipping_method_id", table_name="orders")
    op.drop_index("ix_orders_shipping_rate_id", table_name="orders")
    for column in ["estimated_delivery_to", "estimated_delivery_from", "shipping_carrier", "shipping_method_name", "shipping_method_id", "shipping_rate_id"]:
        op.drop_column("orders", column)
    postgresql.ENUM(name="shipmentstatus").drop(op.get_bind(), checkfirst=True)
