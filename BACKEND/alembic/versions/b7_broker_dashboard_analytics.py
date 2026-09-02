"""Broker B7 dashboard analytics and referral click tracking.

Revision ID: b7_broker_dashboard_analytics
Revises: b6_broker_wallet_payouts
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b7_broker_dashboard_analytics"
down_revision = "b6_broker_wallet_payouts"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "broker_referral_clicks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("referral_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("visitor_key", sa.String(96), nullable=False),
        sa.Column("source", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["referral_link_id"], ["broker_referral_links.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["offer_id"], ["broker_offers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
    )
    for col in ("referral_link_id", "offer_id", "broker_id", "product_id", "visitor_key", "created_at"):
        op.create_index(f"ix_broker_referral_clicks_{col}", "broker_referral_clicks", [col])
    op.create_index("ix_broker_referral_clicks_broker_created", "broker_referral_clicks", ["broker_id", "created_at"])
    op.create_index("ix_broker_referral_clicks_link_visitor_created", "broker_referral_clicks", ["referral_link_id", "visitor_key", "created_at"])

def downgrade():
    op.drop_table("broker_referral_clicks")
