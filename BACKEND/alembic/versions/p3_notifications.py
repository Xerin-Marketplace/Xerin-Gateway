"""Phase 3 Task 15: notification center

Revision ID: p3_notifications
Revises: p3_promotions
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_notifications"
down_revision = "p3_promotions"
branch_labels = None
depends_on = None

EVENTS = ("order_placed","payment_confirmed","order_accepted","order_dispatched","delivery_updated","order_delivered","refund_updated","promotion_available","review_reply","new_order","low_stock","product_reviewed","cancellation_requested","payout_updated","seller_approval_required","product_approval_required","system_alert")
CHANNELS = ("in_app","email","sms","push")
STATUSES = ("pending","processing","sent","delivered","failed","cancelled")

def _enum(name, values):
    enum = postgresql.ENUM(*values, name=name)
    enum.create(op.get_bind(), checkfirst=True)
    return postgresql.ENUM(*values, name=name, create_type=False)

def upgrade():
    event=_enum("notificationevent", EVENTS); channel=_enum("notificationchannel", CHANNELS); delivery_status=_enum("notificationdeliverystatus", STATUSES)
    op.create_table("notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event", event, nullable=False), sa.Column("title", sa.String(180), nullable=False), sa.Column("message", sa.Text(), nullable=False),
        sa.Column("data", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("action_url", sa.Text()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("read_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"]); op.create_index("ix_notifications_user_read_created", "notifications", ["user_id","is_read","created_at"])
    op.create_table("notification_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("in_app_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")), sa.Column("email_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("sms_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")), sa.Column("push_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("event_preferences", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")), sa.Column("quiet_hours_start", sa.Time()), sa.Column("quiet_hours_end", sa.Time()),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_index("ix_notification_preferences_user_id", "notification_preferences", ["user_id"], unique=True)
    op.create_table("notification_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("event", event, nullable=False), sa.Column("channel", channel, nullable=False),
        sa.Column("subject_template", sa.String(255)), sa.Column("body_template", sa.Text(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event","channel",name="uq_notification_template_event_channel"))
    op.create_table("notification_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("notification_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("notifications.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", channel, nullable=False), sa.Column("status", delivery_status, nullable=False, server_default="pending"), sa.Column("provider", sa.String(100)), sa.Column("provider_reference", sa.String(255)),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"), sa.Column("sent_at", sa.DateTime(timezone=True)), sa.Column("delivered_at", sa.DateTime(timezone=True)), sa.Column("failed_at", sa.DateTime(timezone=True)), sa.Column("failure_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)), sa.UniqueConstraint("notification_id","channel",name="uq_notification_delivery_channel"))
    op.create_index("ix_notification_deliveries_notification_id", "notification_deliveries", ["notification_id"])
    op.create_table("device_tokens",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("token", sa.Text(), nullable=False), sa.Column("platform", sa.String(30), nullable=False), sa.Column("device_name", sa.String(120)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("last_used_at", sa.DateTime(timezone=True)), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.UniqueConstraint("token",name="uq_device_tokens_token"))
    op.create_index("ix_device_tokens_user_id", "device_tokens", ["user_id"])

def downgrade():
    op.drop_index("ix_device_tokens_user_id", table_name="device_tokens"); op.drop_table("device_tokens")
    op.drop_index("ix_notification_deliveries_notification_id", table_name="notification_deliveries"); op.drop_table("notification_deliveries")
    op.drop_table("notification_templates")
    op.drop_index("ix_notification_preferences_user_id", table_name="notification_preferences"); op.drop_table("notification_preferences")
    op.drop_index("ix_notifications_user_read_created", table_name="notifications"); op.drop_index("ix_notifications_user_id", table_name="notifications"); op.drop_table("notifications")
    bind=op.get_bind()
    for name,values in (("notificationdeliverystatus",STATUSES),("notificationchannel",CHANNELS),("notificationevent",EVENTS)):
        postgresql.ENUM(*values,name=name).drop(bind,checkfirst=True)
