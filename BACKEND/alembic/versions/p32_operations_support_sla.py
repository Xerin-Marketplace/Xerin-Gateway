"""Phase 4 Task 3: operations overview and support SLA tracking.

Revision ID: p32_operations_support_sla
Revises: p31_financial_lifecycle_indexes
"""
from alembic import op
import sqlalchemy as sa

revision = "p32_operations_support_sla"
down_revision = "p31_financial_lifecycle_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("support_tickets", sa.Column("first_response_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("support_tickets", sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("support_tickets", sa.Column("first_responded_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("support_tickets", sa.Column("sla_breached_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("""
        UPDATE support_tickets
        SET first_response_due_at = created_at + CASE priority
            WHEN 'urgent' THEN interval '1 hour' WHEN 'high' THEN interval '4 hours'
            WHEN 'medium' THEN interval '8 hours' ELSE interval '24 hours' END,
            resolution_due_at = created_at + CASE priority
            WHEN 'urgent' THEN interval '4 hours' WHEN 'high' THEN interval '24 hours'
            WHEN 'medium' THEN interval '48 hours' ELSE interval '72 hours' END
    """)
    op.alter_column("support_tickets", "first_response_due_at", nullable=False)
    op.alter_column("support_tickets", "resolution_due_at", nullable=False)
    op.create_index("ix_support_tickets_first_response_due_at", "support_tickets", ["first_response_due_at"])
    op.create_index("ix_support_tickets_resolution_due_at", "support_tickets", ["resolution_due_at"])
    op.create_index("ix_support_tickets_sla_breached_at", "support_tickets", ["sla_breached_at"])
    op.create_index("ix_notification_deliveries_status_created", "notification_deliveries", ["status", "created_at"])
    op.create_index("ix_security_events_resolved_created", "security_events", ["resolved", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_security_events_resolved_created", table_name="security_events")
    op.drop_index("ix_notification_deliveries_status_created", table_name="notification_deliveries")
    op.drop_index("ix_support_tickets_sla_breached_at", table_name="support_tickets")
    op.drop_index("ix_support_tickets_resolution_due_at", table_name="support_tickets")
    op.drop_index("ix_support_tickets_first_response_due_at", table_name="support_tickets")
    op.drop_column("support_tickets", "sla_breached_at")
    op.drop_column("support_tickets", "first_responded_at")
    op.drop_column("support_tickets", "resolution_due_at")
    op.drop_column("support_tickets", "first_response_due_at")
