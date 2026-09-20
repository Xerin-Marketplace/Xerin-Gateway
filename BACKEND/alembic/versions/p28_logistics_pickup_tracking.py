"""Phase 3 combined Task 5: pickup jobs and shipment tracking.

Revision ID: p28_logistics_pickup_tracking
Revises: p27_logistics_pricing
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p28_logistics_pickup_tracking"
down_revision = "p27_logistics_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pickup_status = postgresql.ENUM(
        "scheduled", "assigned", "en_route", "arrived", "completed",
        "failed", "cancelled", name="pickupjobstatus", create_type=False,
    )
    pickup_status.create(op.get_bind(), checkfirst=True)
    op.create_table(
        "logistics_pickup_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("assigned_membership_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("logistics_company_users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", pickup_status, nullable=False, server_default="scheduled"),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pickup_reference", sa.String(120), nullable=False, unique=True),
        sa.Column("dispatcher_notes", sa.Text(), nullable=True),
        sa.Column("courier_notes", sa.Text(), nullable=True),
        sa.Column("failure_reason", sa.String(255), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arrived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status != 'failed' OR failure_reason IS NOT NULL", name="ck_logistics_pickup_job_failed_reason"),
    )
    for column in ("logistics_company_id", "shipment_id", "assigned_membership_id", "status", "scheduled_for", "pickup_reference"):
        op.create_index(f"ix_logistics_pickup_jobs_{column}", "logistics_pickup_jobs", [column])


def downgrade() -> None:
    op.drop_table("logistics_pickup_jobs")
    postgresql.ENUM(name="pickupjobstatus").drop(op.get_bind(), checkfirst=True)
