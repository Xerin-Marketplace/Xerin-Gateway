"""Admin Phase 3 finance configuration and escrow foundation.

Revision ID: p9_finance_configuration
Revises: p8_logistics_management
"""

import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p9_finance_configuration"
down_revision = "p8_logistics_management"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "finance_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("singleton_key", sa.String(30), nullable=False, server_default="default"),
        sa.Column("default_payment_provider_code", sa.String(80), nullable=True),
        sa.Column("settlement_currency", sa.String(10), nullable=False, server_default="TZS"),
        sa.Column("minimum_payout_amount", sa.Numeric(18, 2), nullable=False, server_default="1000"),
        sa.Column("payout_fee_type", sa.String(30), nullable=False, server_default="fixed"),
        sa.Column("payout_fee_value", sa.Numeric(18, 4), nullable=False, server_default="0"),
        sa.Column("payout_processing_days", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("auto_payout_enabled", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("escrow_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("auto_release_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("allow_partial_release", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("hold_commission_until_release", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("singleton_key", name="uq_finance_settings_singleton"),
        sa.CheckConstraint("minimum_payout_amount >= 0", name="ck_finance_minimum_payout_nonnegative"),
        sa.CheckConstraint("payout_fee_value >= 0", name="ck_finance_payout_fee_nonnegative"),
        sa.CheckConstraint("payout_processing_days >= 0", name="ck_finance_payout_processing_days_nonnegative"),
        sa.CheckConstraint("payout_fee_type IN ('fixed','percentage')", name="ck_finance_payout_fee_type"),
    )

    op.create_table(
        "escrow_holds",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("sellers.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("gross_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("seller_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("commission_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("refunded_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("released_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="held"),
        sa.Column("release_after", sa.DateTime(timezone=True), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("disputed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(180), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("reference", name="uq_escrow_hold_reference"),
        sa.CheckConstraint("gross_amount >= 0", name="ck_escrow_gross_nonnegative"),
        sa.CheckConstraint("seller_amount >= 0", name="ck_escrow_seller_nonnegative"),
        sa.CheckConstraint("commission_amount >= 0", name="ck_escrow_commission_nonnegative"),
        sa.CheckConstraint("refunded_amount >= 0", name="ck_escrow_refunded_nonnegative"),
        sa.CheckConstraint("released_amount >= 0", name="ck_escrow_released_nonnegative"),
        sa.CheckConstraint("seller_amount + commission_amount <= gross_amount", name="ck_escrow_allocations_within_gross"),
        sa.CheckConstraint("refunded_amount + released_amount <= gross_amount", name="ck_escrow_settled_within_gross"),
    )
    op.create_index("ix_escrow_holds_payment", "escrow_holds", ["payment_id"])
    op.create_index("ix_escrow_holds_order", "escrow_holds", ["order_id"])
    op.create_index("ix_escrow_holds_order_item", "escrow_holds", ["order_item_id"])
    op.create_index("ix_escrow_holds_seller", "escrow_holds", ["seller_id"])
    op.create_index("ix_escrow_holds_status", "escrow_holds", ["status"])
    op.create_index("ix_escrow_holds_release_after", "escrow_holds", ["release_after"])
    op.create_index("ix_escrow_holds_reference", "escrow_holds", ["reference"])

    op.create_table(
        "escrow_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("escrow_hold_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("escrow_holds.id", ondelete="CASCADE"), nullable=False),
        sa.Column("event_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount IS NULL OR amount >= 0", name="ck_escrow_event_amount_nonnegative"),
    )
    op.create_index("ix_escrow_events_hold", "escrow_events", ["escrow_hold_id"])
    op.create_index("ix_escrow_events_type", "escrow_events", ["event_type"])

    # Create the singleton finance configuration using existing Phase 3 foundations.
    op.execute(
        sa.text(
            """
            INSERT INTO finance_settings
                (id, singleton_key, default_payment_provider_code, settlement_currency)
            VALUES
                (:id, 'default', 'azampay', 'TZS')
            ON CONFLICT (singleton_key) DO NOTHING
            """
        ).bindparams(id=str(uuid.uuid4()))
    )


def downgrade() -> None:
    op.drop_index("ix_escrow_events_type", table_name="escrow_events")
    op.drop_index("ix_escrow_events_hold", table_name="escrow_events")
    op.drop_table("escrow_events")

    op.drop_index("ix_escrow_holds_reference", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_release_after", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_status", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_seller", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_order_item", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_order", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_payment", table_name="escrow_holds")
    op.drop_table("escrow_holds")

    op.drop_table("finance_settings")
