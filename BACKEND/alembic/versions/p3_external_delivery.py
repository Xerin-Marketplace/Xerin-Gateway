"""External delivery provider integration.

Revision ID: p3_external_delivery
Revises: p3_seller_inventory
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_external_delivery"
down_revision = "p3_seller_inventory"
branch_labels = None
depends_on = None

DELIVERY_STATUS = postgresql.ENUM(
    "created", "awaiting_pickup", "courier_assigned", "picked_up",
    "in_transit", "out_for_delivery", "delivered", "delivery_failed",
    "cancelled", "returned", name="deliverystatus", create_type=False,
)


def upgrade() -> None:
    op.execute("""
    DO $$ BEGIN
        IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'deliverystatus') THEN
            CREATE TYPE deliverystatus AS ENUM (
                'created','awaiting_pickup','courier_assigned','picked_up',
                'in_transit','out_for_delivery','delivered','delivery_failed',
                'cancelled','returned'
            );
        END IF;
    END $$;
    """)
    op.create_table(
        "delivery_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seller_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("external_delivery_id", sa.String(255), nullable=False),
        sa.Column("status", DELIVERY_STATUS, nullable=False, server_default=sa.text("'created'::deliverystatus")),
        sa.Column("tracking_number", sa.String(150)),
        sa.Column("tracking_url", sa.Text()),
        sa.Column("delivery_fee", sa.Numeric(18, 2)),
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
        sa.Column("courier_name", sa.String(150)),
        sa.Column("courier_phone", sa.String(50)),
        sa.Column("estimated_pickup_at", sa.DateTime(timezone=True)),
        sa.Column("estimated_delivery_at", sa.DateTime(timezone=True)),
        sa.Column("failure_reason", sa.Text()),
        sa.Column("request_payload", postgresql.JSONB()),
        sa.Column("provider_response", postgresql.JSONB()),
        sa.Column("last_synced_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("shipment_id", name="uq_delivery_jobs_shipment_id"),
        sa.UniqueConstraint("provider", "external_delivery_id", name="uq_delivery_job_provider_external_id"),
        sa.CheckConstraint("delivery_fee IS NULL OR delivery_fee >= 0", name="ck_delivery_job_fee_nonnegative"),
    )
    for name, cols in (
        ("ix_delivery_jobs_shipment_id", ["shipment_id"]),
        ("ix_delivery_jobs_seller_order_id", ["seller_order_id"]),
        ("ix_delivery_jobs_provider", ["provider"]),
        ("ix_delivery_jobs_external_delivery_id", ["external_delivery_id"]),
        ("ix_delivery_jobs_status", ["status"]),
        ("ix_delivery_jobs_tracking_number", ["tracking_number"]),
    ):
        op.create_index(name, "delivery_jobs", cols)


def downgrade() -> None:
    op.drop_table("delivery_jobs")
    op.execute("DROP TYPE IF EXISTS deliverystatus")
