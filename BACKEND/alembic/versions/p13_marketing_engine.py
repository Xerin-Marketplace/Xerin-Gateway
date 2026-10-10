"""Marketing & customer engagement engine — templates, campaigns, messages,
preferences/consent, holiday events, and monthly automation.

Revision ID: p13_marketing_engine
Revises: p12_product_broker_link
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p13_marketing_engine"
down_revision = "p12_product_broker_link"
branch_labels = None
depends_on = None


def upgrade() -> None:
    uuid = postgresql.UUID(as_uuid=True)
    op.create_table(
        "marketing_templates",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("key", sa.String(80), unique=True, nullable=False),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("purpose", sa.String(60)),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("language", sa.String(5), nullable=False, server_default="en"),
        sa.Column("subject", sa.String(255)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("variables", postgresql.JSONB),
        sa.Column("is_approved", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("version", sa.Integer, nullable=False, server_default="1"),
        sa.Column("updated_by_id", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_marketing_templates_key", "marketing_templates", ["key"], unique=True)

    op.create_table(
        "marketing_preferences",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False),
        sa.Column("email_marketing", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("sms_marketing", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("unsubscribe_token", sa.String(80), unique=True, nullable=False),
        sa.Column("source", sa.String(40)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_marketing_preferences_user_id", "marketing_preferences", ["user_id"], unique=True)

    op.create_table(
        "marketing_events",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("rule_type", sa.String(20), nullable=False, server_default="fixed"),
        sa.Column("month", sa.Integer),
        sa.Column("day", sa.Integer),
        sa.Column("easter_offset", sa.Integer),
        sa.Column("jurisdiction", sa.String(30), nullable=False, server_default="tanzania"),
        sa.Column("category", sa.String(40)),
        sa.Column("is_estimated", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("source_url", sa.Text),
        sa.Column("lead_days", sa.Integer, nullable=False, server_default="7"),
        sa.Column("suggested_email", sa.Text),
        sa.Column("suggested_sms", sa.Text),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "marketing_campaigns",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("name", sa.String(180), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("template_id", uuid, sa.ForeignKey("marketing_templates.id", ondelete="SET NULL")),
        sa.Column("segment_key", sa.String(60), nullable=False, server_default="all_customers"),
        sa.Column("subject", sa.String(255)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("promotion_id", uuid, sa.ForeignKey("promotions.id", ondelete="SET NULL")),
        sa.Column("event_id", uuid, sa.ForeignKey("marketing_events.id", ondelete="SET NULL")),
        sa.Column("scheduled_at", sa.DateTime(timezone=True)),
        sa.Column("approved_by_id", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("approved_at", sa.DateTime(timezone=True)),
        sa.Column("created_by_id", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("stats", postgresql.JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )
    op.create_index("ix_marketing_campaigns_status", "marketing_campaigns", ["status"])

    op.create_table(
        "marketing_messages",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("campaign_id", uuid, sa.ForeignKey("marketing_campaigns.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("recipient", sa.String(255), nullable=False),
        sa.Column("subject", sa.String(255)),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("status", sa.String(15), nullable=False, server_default="queued"),
        sa.Column("error", sa.Text),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("sent_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_marketing_messages_campaign_id", "marketing_messages", ["campaign_id"])
    op.create_index("ix_marketing_messages_status", "marketing_messages", ["status"])
    op.create_index("ix_marketing_messages_user_id", "marketing_messages", ["user_id"])

    op.create_table(
        "marketing_automation",
        sa.Column("id", uuid, primary_key=True),
        sa.Column("key", sa.String(40), unique=True, nullable=False, server_default="monthly_engagement"),
        sa.Column("is_enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("auto_send", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("day_of_month", sa.Integer, nullable=False, server_default="5"),
        sa.Column("send_time", sa.String(5), nullable=False, server_default="10:00"),
        sa.Column("channels", postgresql.JSONB, nullable=False, server_default='["sms"]'),
        sa.Column("segment_key", sa.String(60), nullable=False, server_default="all_customers"),
        sa.Column("last_run_at", sa.DateTime(timezone=True)),
        sa.Column("next_run_at", sa.DateTime(timezone=True)),
        sa.Column("last_campaign_id", uuid, sa.ForeignKey("marketing_campaigns.id", ondelete="SET NULL")),
        sa.Column("updated_by_id", uuid, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), onupdate=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("marketing_automation")
    op.drop_table("marketing_messages")
    op.drop_table("marketing_campaigns")
    op.drop_table("marketing_events")
    op.drop_table("marketing_preferences")
    op.drop_table("marketing_templates")
