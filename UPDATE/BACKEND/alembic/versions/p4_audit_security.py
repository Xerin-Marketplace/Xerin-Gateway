"""Phase 4 Task 1 audit logs and security events.

Revision ID: p4_audit_security
Revises: p3_refund_engine
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p4_audit_security"
down_revision = "p3_refund_engine"
branch_labels = None
depends_on = None


def upgrade():
    audit_severity = postgresql.ENUM("info", "warning", "critical", name="auditseverity", create_type=False)
    security_type = postgresql.ENUM(
        "authentication_failed",
        "authorization_denied",
        "suspicious_request",
        "sensitive_action",
        name="securityeventtype",
        create_type=False,
    )
    audit_severity.create(op.get_bind(), checkfirst=True)
    security_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(120), nullable=False),
        sa.Column("resource_type", sa.String(120), nullable=True),
        sa.Column("resource_id", sa.String(180), nullable=True),
        sa.Column("http_method", sa.String(10), nullable=True),
        sa.Column("request_path", sa.String(500), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("old_values", postgresql.JSONB(), nullable=True),
        sa.Column("new_values", postgresql.JSONB(), nullable=True),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=False, unique=True),
        sa.Column("severity", audit_severity, nullable=False, server_default="info"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("actor_user_id", "action", "resource_type", "resource_id", "request_path", "response_status", "ip_address", "request_id", "severity", "created_at"):
        op.create_index(f"ix_audit_logs_{column}", "audit_logs", [column], unique=column == "request_id")

    op.create_table(
        "security_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("actor_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("event_type", security_type, nullable=False),
        sa.Column("severity", audit_severity, nullable=False, server_default="warning"),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("request_path", sa.String(500), nullable=True),
        sa.Column("http_method", sa.String(10), nullable=True),
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("request_id", sa.String(100), nullable=False, unique=True),
        sa.Column("event_metadata", postgresql.JSONB(), nullable=True),
        sa.Column("resolved", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    for column in ("actor_user_id", "event_type", "severity", "request_path", "response_status", "ip_address", "request_id", "resolved", "created_at"):
        op.create_index(f"ix_security_events_{column}", "security_events", [column], unique=column == "request_id")


def downgrade():
    op.drop_table("security_events")
    op.drop_table("audit_logs")
    postgresql.ENUM(name="securityeventtype").drop(op.get_bind(), checkfirst=True)
    postgresql.ENUM(name="auditseverity").drop(op.get_bind(), checkfirst=True)
