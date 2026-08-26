"""Phase 3 combined Task 6: integrations, webhooks and dashboard.

Revision ID: p29_logistics_integration_dashboard
Revises: p28_logistics_pickup_tracking
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p29_logistics_integration_dashboard"
down_revision = "p28_logistics_pickup_tracking"
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column("logistics_integration_configs", sa.Column("webhook_enabled_events", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")))
    op.add_column("logistics_integration_configs", sa.Column("last_webhook_sent_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("logistics_integration_configs", sa.Column("last_webhook_received_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_logistics_webhook_company_created", "logistics_webhook_events", ["logistics_company_id", "created_at"])
    op.create_index("ix_logistics_webhook_company_processed", "logistics_webhook_events", ["logistics_company_id", "processed"])

def downgrade() -> None:
    op.drop_index("ix_logistics_webhook_company_processed", table_name="logistics_webhook_events")
    op.drop_index("ix_logistics_webhook_company_created", table_name="logistics_webhook_events")
    op.drop_column("logistics_integration_configs", "last_webhook_received_at")
    op.drop_column("logistics_integration_configs", "last_webhook_sent_at")
    op.drop_column("logistics_integration_configs", "webhook_enabled_events")
