"""Completion Phase 2 Task 3: signed outbound partner webhooks.

Revision ID: p38_partner_webhooks
Revises: p37_partner_api_security
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p38_partner_webhooks"
down_revision = "p37_partner_api_security"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.add_column("logistics_webhook_events", sa.Column("delivery_status", sa.String(20), nullable=False, server_default="queued"))
    op.add_column("logistics_webhook_events", sa.Column("attempt_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("logistics_webhook_events", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="6"))
    op.add_column("logistics_webhook_events", sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True, server_default=sa.func.now()))
    op.add_column("logistics_webhook_events", sa.Column("last_attempt_at", sa.DateTime(timezone=True)))
    op.add_column("logistics_webhook_events", sa.Column("delivered_at", sa.DateTime(timezone=True)))
    op.add_column("logistics_webhook_events", sa.Column("dead_lettered_at", sa.DateTime(timezone=True)))
    op.add_column("logistics_webhook_events", sa.Column("locked_at", sa.DateTime(timezone=True)))
    op.add_column("logistics_webhook_events", sa.Column("lock_token", UUID))
    op.create_check_constraint(
        "ck_logistics_webhook_delivery_status",
        "logistics_webhook_events",
        "delivery_status IN ('queued','delivering','retrying','delivered','dead_letter')",
    )
    op.create_check_constraint(
        "ck_logistics_webhook_attempt_counts",
        "logistics_webhook_events",
        "attempt_count >= 0 AND max_attempts > 0",
    )
    op.create_index("ix_logistics_webhook_delivery_status", "logistics_webhook_events", ["delivery_status"])
    op.create_index("ix_logistics_webhook_next_attempt", "logistics_webhook_events", ["next_attempt_at"])
    op.create_index("ix_logistics_webhook_lock_token", "logistics_webhook_events", ["lock_token"])
    op.execute(
        "UPDATE logistics_webhook_events SET delivery_status='delivered', "
        "delivered_at=created_at, next_attempt_at=NULL "
        "WHERE direction='outbound' AND processed=true"
    )

    op.create_table(
        "partner_webhook_attempts",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("event_id", UUID, sa.ForeignKey("logistics_webhook_events.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("request_url", sa.Text(), nullable=False),
        sa.Column("credential_key_id", sa.String(80)),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer()),
        sa.Column("http_status", sa.Integer()),
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("response_excerpt", sa.Text()),
        sa.Column("error_message", sa.Text()),
        sa.UniqueConstraint("event_id", "attempt_number", name="uq_partner_webhook_attempt_number"),
        sa.CheckConstraint("attempt_number > 0", name="ck_partner_webhook_attempt_number"),
    )
    op.create_index("ix_partner_webhook_attempt_event", "partner_webhook_attempts", ["event_id"])


def downgrade():
    op.drop_table("partner_webhook_attempts")
    op.drop_index("ix_logistics_webhook_lock_token", table_name="logistics_webhook_events")
    op.drop_index("ix_logistics_webhook_next_attempt", table_name="logistics_webhook_events")
    op.drop_index("ix_logistics_webhook_delivery_status", table_name="logistics_webhook_events")
    op.drop_constraint("ck_logistics_webhook_attempt_counts", "logistics_webhook_events", type_="check")
    op.drop_constraint("ck_logistics_webhook_delivery_status", "logistics_webhook_events", type_="check")
    for column in (
        "lock_token", "locked_at", "dead_lettered_at", "delivered_at", "last_attempt_at",
        "next_attempt_at", "max_attempts", "attempt_count", "delivery_status",
    ):
        op.drop_column("logistics_webhook_events", column)
