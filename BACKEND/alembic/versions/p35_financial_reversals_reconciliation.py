"""Completion Phase 1 Task 3: reversals, debt recovery and reconciliation.

Revision ID: p35_financial_reconciliation
Revises: p34_logistics_wallet_payouts
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p35_financial_reconciliation"
down_revision = "p34_logistics_wallet_payouts"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.add_column("refunds", sa.Column("reverse_logistics_entitlement", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("refunds", sa.Column("logistics_reversal", sa.Numeric(18,2), nullable=False, server_default="0"))
    op.add_column("refunds", sa.Column("logistics_debt_amount", sa.Numeric(18,2), nullable=False, server_default="0"))
    op.drop_constraint("ck_refund_amounts_valid", "refunds", type_="check")
    op.create_check_constraint("ck_refund_amounts_valid", "refunds", "items_amount >= 0 AND shipping_amount >= 0 AND tax_amount >= 0 AND logistics_reversal >= 0 AND logistics_debt_amount >= 0 AND total_amount > 0")
    op.create_table("financial_reconciliation_records",
        sa.Column("id", UUID, primary_key=True), sa.Column("order_id", UUID, sa.ForeignKey("orders.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False, unique=True), sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False), sa.Column("snapshot", postgresql.JSONB(), nullable=False), sa.Column("findings", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("snapshot_hash", sa.String(64), nullable=False), sa.Column("created_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("status IN ('balanced','exception')", name="ck_financial_reconciliation_status"))
    for name, cols, unique in (("ix_financial_reconciliation_order",["order_id"],False),("ix_financial_reconciliation_key",["idempotency_key"],True),("ix_financial_reconciliation_status",["status"],False),("ix_financial_reconciliation_hash",["snapshot_hash"],False),("ix_financial_reconciliation_created",["created_at"],False)):
        op.create_index(name,"financial_reconciliation_records",cols,unique=unique)
    op.create_table("financial_reconciliation_events",
        sa.Column("id", UUID, primary_key=True), sa.Column("reconciliation_id", UUID, sa.ForeignKey("financial_reconciliation_records.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(30), nullable=False), sa.Column("note", sa.Text()), sa.Column("created_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("action IN ('created','acknowledged','resolved','reopened')", name="ck_financial_reconciliation_event_action"))
    op.create_index("ix_financial_reconciliation_events_record", "financial_reconciliation_events", ["reconciliation_id"])


def downgrade() -> None:
    op.drop_table("financial_reconciliation_events")
    op.drop_table("financial_reconciliation_records")
    op.drop_constraint("ck_refund_amounts_valid", "refunds", type_="check")
    op.create_check_constraint("ck_refund_amounts_valid", "refunds", "items_amount >= 0 AND shipping_amount >= 0 AND tax_amount >= 0 AND total_amount > 0")
    op.drop_column("refunds", "logistics_debt_amount")
    op.drop_column("refunds", "logistics_reversal")
    op.drop_column("refunds", "reverse_logistics_entitlement")
