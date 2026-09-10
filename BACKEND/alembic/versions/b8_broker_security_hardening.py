"""B8 broker security and production hardening

Revision ID: b8_broker_security_hardening
Revises: b7_broker_dashboard_analytics
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b8_broker_security_hardening"
down_revision = "b7_broker_dashboard_analytics"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("broker_referral_clicks", sa.Column("ip_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_broker_referral_clicks_ip_hash", "broker_referral_clicks", ["ip_hash"])
    op.add_column("broker_payout_requests", sa.Column("idempotency_key", sa.String(length=120), nullable=True))
    op.create_index("ix_broker_payout_requests_idempotency_key", "broker_payout_requests", ["idempotency_key"], unique=True)
    op.create_table(
        "broker_risk_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", sa.String(length=60), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False, server_default="warning"),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="open"),
        sa.Column("ip_hash", sa.String(length=64), nullable=True),
        sa.Column("resource_type", sa.String(length=60), nullable=True),
        sa.Column("resource_id", sa.String(length=120), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("severity IN ('info','warning','high','critical')", name="ck_broker_risk_severity"),
        sa.CheckConstraint("status IN ('open','resolved')", name="ck_broker_risk_status"),
    )
    for col in ("broker_id","user_id","event_type","severity","status","ip_hash","resource_type","resource_id","created_at"):
        op.create_index(f"ix_broker_risk_events_{col}", "broker_risk_events", [col])


def downgrade():
    op.drop_table("broker_risk_events")
    op.drop_index("ix_broker_payout_requests_idempotency_key", table_name="broker_payout_requests")
    op.drop_column("broker_payout_requests", "idempotency_key")
    op.drop_index("ix_broker_referral_clicks_ip_hash", table_name="broker_referral_clicks")
    op.drop_column("broker_referral_clicks", "ip_hash")
