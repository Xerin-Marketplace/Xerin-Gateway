"""Add broker earning engine tables: offers, acceptances, referral clicks, commissions.

Revision ID: p11_broker_earning_engine
Revises: p10_broker_risk_events
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p11_broker_earning_engine"
down_revision = "p10_broker_risk_events"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "broker_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("commission_type", sa.String(16), nullable=False),
        sa.Column("commission_value", sa.Numeric(10, 2), nullable=False),
        sa.Column("max_attributed_sales", sa.Integer(), nullable=True),
        sa.Column("attributed_sales_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_broker_offers_product_id", "broker_offers", ["product_id"])
    op.create_index("ix_broker_offers_seller_id", "broker_offers", ["seller_id"])

    op.create_table(
        "broker_offer_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referral_code", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("accepted_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("offer_id", "broker_id", name="uq_broker_offer_acceptance"),
    )
    op.create_index("ix_broker_offer_acceptances_offer_id", "broker_offer_acceptances", ["offer_id"])
    op.create_index("ix_broker_offer_acceptances_broker_id", "broker_offer_acceptances", ["broker_id"])
    op.create_index("ix_broker_offer_acceptances_referral_code", "broker_offer_acceptances", ["referral_code"], unique=True)

    op.create_table(
        "broker_referral_clicks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("acceptance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_offer_acceptances.id", ondelete="CASCADE"), nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_offers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("referral_code", sa.String(20), nullable=False),
        sa.Column("visitor_key", sa.String(80), nullable=False),
        sa.Column("source", sa.String(60), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_broker_referral_clicks_acceptance_id", "broker_referral_clicks", ["acceptance_id"])
    op.create_index("ix_broker_referral_clicks_broker_id", "broker_referral_clicks", ["broker_id"])
    op.create_index("ix_broker_referral_clicks_referral_code", "broker_referral_clicks", ["referral_code"])
    op.create_index("ix_broker_referral_clicks_visitor_key", "broker_referral_clicks", ["visitor_key"])

    op.create_table(
        "broker_commissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("broker_offer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_offers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("broker_attribution_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("broker_offer_acceptances.id", ondelete="SET NULL"), nullable=True),
        sa.Column("escrow_hold_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reversed_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("net_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(60), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_broker_commissions_broker_id", "broker_commissions", ["broker_id"])
    op.create_index("ix_broker_commissions_order_id", "broker_commissions", ["order_id"])
    op.create_index("ix_broker_commissions_order_item_id", "broker_commissions", ["order_item_id"])
    op.create_index("ix_broker_commissions_status", "broker_commissions", ["status"])
    op.create_unique_constraint("uq_broker_commissions_reference", "broker_commissions", ["reference"])


def downgrade() -> None:
    op.drop_table("broker_commissions")
    op.drop_table("broker_referral_clicks")
    op.drop_table("broker_offer_acceptances")
    op.drop_table("broker_offers")
