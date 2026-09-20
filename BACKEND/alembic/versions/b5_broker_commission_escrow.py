"""Broker B5 commission and escrow lifecycle.

Revision ID: b5_broker_commission_escrow
Revises: b4_broker_referral_attribution
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b5_broker_commission_escrow"
down_revision = "b4_broker_referral_attribution"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "escrow_holds",
        sa.Column("broker_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
    )
    op.create_check_constraint(
        "ck_escrow_broker_nonnegative",
        "escrow_holds",
        "broker_amount >= 0",
    )
    # Replace the allocation rule so Broker funds are explicitly accounted for.
    op.drop_constraint("ck_escrow_allocations_within_gross", "escrow_holds", type_="check")
    op.create_check_constraint(
        "ck_escrow_allocations_within_gross",
        "escrow_holds",
        "seller_amount + commission_amount + broker_amount <= gross_amount",
    )

    op.create_table(
        "broker_commissions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_offer_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("broker_attribution_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("escrow_hold_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("reversed_amount", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("available_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reversed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reference", sa.String(length=180), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_id"], ["orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["order_item_id"], ["order_items.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["broker_offer_id"], ["broker_offers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["broker_attribution_id"], ["broker_attributions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["escrow_hold_id"], ["escrow_holds.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("order_item_id", name="uq_broker_commission_order_item"),
        sa.UniqueConstraint("escrow_hold_id", name="uq_broker_commission_escrow_hold"),
        sa.UniqueConstraint("reference", name="uq_broker_commission_reference"),
        sa.CheckConstraint("amount >= 0", name="ck_broker_commission_amount_nonnegative"),
        sa.CheckConstraint(
            "reversed_amount >= 0 AND reversed_amount <= amount",
            name="ck_broker_commission_reversed_within_amount",
        ),
        sa.CheckConstraint(
            "status IN ('pending','available','partially_reversed','reversed','cancelled')",
            name="ck_broker_commission_status",
        ),
    )
    for col in (
        "broker_id",
        "order_id",
        "order_item_id",
        "broker_offer_id",
        "broker_attribution_id",
        "escrow_hold_id",
        "status",
        "available_at",
        "reference",
    ):
        op.create_index(f"ix_broker_commissions_{col}", "broker_commissions", [col])


def downgrade():
    for col in (
        "reference",
        "available_at",
        "status",
        "escrow_hold_id",
        "broker_attribution_id",
        "broker_offer_id",
        "order_item_id",
        "order_id",
        "broker_id",
    ):
        op.drop_index(f"ix_broker_commissions_{col}", table_name="broker_commissions")
    op.drop_table("broker_commissions")

    op.drop_constraint("ck_escrow_allocations_within_gross", "escrow_holds", type_="check")
    op.create_check_constraint(
        "ck_escrow_allocations_within_gross",
        "escrow_holds",
        "seller_amount + commission_amount <= gross_amount",
    )
    op.drop_constraint("ck_escrow_broker_nonnegative", "escrow_holds", type_="check")
    op.drop_column("escrow_holds", "broker_amount")
