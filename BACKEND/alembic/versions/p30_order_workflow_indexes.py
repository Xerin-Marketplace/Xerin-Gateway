"""Phase 4 Task 1: end-to-end order workflow query indexes.

Revision ID: p30_order_workflow_indexes
Revises: p29_logistics_integration_dashboard
"""
from alembic import op

revision = "p30_order_workflow_indexes"
down_revision = "p29_logistics_integration_dashboard"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_seller_orders_order_status", "seller_orders", ["order_id", "status"])
    op.create_index("ix_shipments_order_status", "shipments", ["order_id", "status"])
    op.create_index("ix_shipment_tracking_shipment_created", "shipment_tracking_events", ["shipment_id", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_shipment_tracking_shipment_created", table_name="shipment_tracking_events")
    op.drop_index("ix_shipments_order_status", table_name="shipments")
    op.drop_index("ix_seller_orders_order_status", table_name="seller_orders")
