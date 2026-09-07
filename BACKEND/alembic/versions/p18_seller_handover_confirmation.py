"""Phase 1 Task 6: seller handover confirmation.

Revision ID: p18_seller_handover_confirmation
Revises: p17_seller_package_preparation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p18_seller_handover_confirmation"
down_revision = "p17_seller_package_preparation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipment_handovers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seller_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("logistics_companies.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="awaiting_courier"),
        sa.Column("courier_arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("courier_arrived_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("courier_arrival_latitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("courier_arrival_longitude", sa.Numeric(10, 7), nullable=True),
        sa.Column("courier_arrival_notes", sa.Text(), nullable=True),
        sa.Column("seller_confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("seller_confirmed_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seller_confirmation_notes", sa.Text(), nullable=True),
        sa.Column("pickup_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("package_snapshot", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('awaiting_courier', 'courier_arrived', 'seller_confirmed')", name="ck_shipment_handover_status"),
        sa.CheckConstraint("courier_arrival_latitude IS NULL OR courier_arrival_latitude BETWEEN -90 AND 90", name="ck_shipment_handover_arrival_latitude"),
        sa.CheckConstraint("courier_arrival_longitude IS NULL OR courier_arrival_longitude BETWEEN -180 AND 180", name="ck_shipment_handover_arrival_longitude"),
        sa.UniqueConstraint("shipment_id", name="uq_shipment_handovers_shipment_id"),
        sa.UniqueConstraint("seller_order_id", name="uq_shipment_handovers_seller_order_id"),
    )
    op.create_index("ix_shipment_handovers_shipment_id", "shipment_handovers", ["shipment_id"], unique=True)
    op.create_index("ix_shipment_handovers_seller_order_id", "shipment_handovers", ["seller_order_id"], unique=True)
    op.create_index("ix_shipment_handovers_seller_id", "shipment_handovers", ["seller_id"])
    op.create_index("ix_shipment_handovers_logistics_company_id", "shipment_handovers", ["logistics_company_id"])
    op.create_index("ix_shipment_handovers_status", "shipment_handovers", ["status"])
    op.create_index("ix_shipment_handovers_company_status", "shipment_handovers", ["logistics_company_id", "status", "created_at"])
    op.create_index("ix_shipment_handovers_seller_status", "shipment_handovers", ["seller_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_shipment_handovers_seller_status", table_name="shipment_handovers")
    op.drop_index("ix_shipment_handovers_company_status", table_name="shipment_handovers")
    op.drop_index("ix_shipment_handovers_status", table_name="shipment_handovers")
    op.drop_index("ix_shipment_handovers_logistics_company_id", table_name="shipment_handovers")
    op.drop_index("ix_shipment_handovers_seller_id", table_name="shipment_handovers")
    op.drop_index("ix_shipment_handovers_seller_order_id", table_name="shipment_handovers")
    op.drop_index("ix_shipment_handovers_shipment_id", table_name="shipment_handovers")
    op.drop_table("shipment_handovers")
