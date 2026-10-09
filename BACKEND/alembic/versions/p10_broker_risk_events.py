"""Add broker_risk_events table.

Revision ID: p10_broker_risk_events
Revises: p9_broker_products
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p10_broker_risk_events"
down_revision = "p9_broker_products"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_risk_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("severity", sa.String(16), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("resource_type", sa.String(60), nullable=True),
        sa.Column("resource_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("details", postgresql.JSONB(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_broker_risk_events_broker_id", "broker_risk_events", ["broker_id"])
    op.create_index("ix_broker_risk_events_user_id", "broker_risk_events", ["user_id"])
    op.create_index("ix_broker_risk_events_event_type", "broker_risk_events", ["event_type"])
    op.create_index("ix_broker_risk_events_status", "broker_risk_events", ["status"])


def downgrade() -> None:
    op.drop_table("broker_risk_events")
