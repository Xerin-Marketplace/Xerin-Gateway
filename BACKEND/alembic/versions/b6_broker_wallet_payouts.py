"""Broker B6 wallet ledger and payouts.

Revision ID: b6_broker_wallet_payouts
Revises: b5_broker_commission_escrow
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b6_broker_wallet_payouts"
down_revision = "b5_broker_commission_escrow"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
        sa.Column("pending_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("available_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("reserved_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("paid_out_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("reversed_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("debt_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("broker_id", name="uq_broker_wallet_broker"),
        sa.CheckConstraint("pending_balance >= 0 AND available_balance >= 0 AND reserved_balance >= 0 AND paid_out_balance >= 0 AND reversed_balance >= 0 AND debt_balance >= 0", name="ck_broker_wallet_balances_nonnegative"),
    )
    op.create_index("ix_broker_wallets_broker_id", "broker_wallets", ["broker_id"])
    op.create_index("ix_broker_wallets_is_frozen", "broker_wallets", ["is_frozen"])

    op.create_table(
        "broker_payout_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("account_type", sa.String(30), nullable=False),
        sa.Column("provider", sa.String(100), nullable=False),
        sa.Column("account_name", sa.String(150), nullable=False),
        sa.Column("account_number", sa.String(120), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verification_status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("verification_note", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.CheckConstraint("account_type IN ('mobile_money','bank')", name="ck_broker_payout_account_type"),
        sa.CheckConstraint("verification_status IN ('pending','verified','rejected')", name="ck_broker_payout_account_verification"),
    )
    op.create_index("ix_broker_payout_accounts_broker_id", "broker_payout_accounts", ["broker_id"])
    op.create_index("ix_broker_payout_accounts_is_active", "broker_payout_accounts", ["is_active"])
    op.create_index("ix_broker_payout_accounts_verification_status", "broker_payout_accounts", ["verification_status"])

    op.create_table(
        "broker_payout_requests",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("payout_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("provider_reference", sa.String(180), nullable=True),
        sa.Column("broker_note", sa.Text(), nullable=True),
        sa.Column("admin_note", sa.Text(), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["wallet_id"], ["broker_wallets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["payout_account_id"], ["broker_payout_accounts.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("provider_reference", name="uq_broker_payout_provider_reference"),
        sa.CheckConstraint("amount > 0", name="ck_broker_payout_amount_positive"),
        sa.CheckConstraint("status IN ('pending','approved','processing','completed','failed','rejected','cancelled')", name="ck_broker_payout_status"),
    )
    for col in ("wallet_id","broker_id","payout_account_id","status"):
        op.create_index(f"ix_broker_payout_requests_{col}", "broker_payout_requests", [col])

    op.create_table(
        "broker_payout_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payout_request_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["payout_request_id"], ["broker_payout_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_broker_payout_events_payout_request_id", "broker_payout_events", ["payout_request_id"])

    op.create_table(
        "broker_wallet_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commission_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("payout_request_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("transaction_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("reference", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["wallet_id"], ["broker_wallets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["commission_id"], ["broker_commissions.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("reference", name="uq_broker_wallet_transaction_reference"),
        sa.CheckConstraint("amount >= 0", name="ck_broker_wallet_transaction_amount_nonnegative"),
    )
    for col in ("wallet_id","broker_id","commission_id","payout_request_id","transaction_type","reference"):
        op.create_index(f"ix_broker_wallet_transactions_{col}", "broker_wallet_transactions", [col])


def downgrade():
    op.drop_table("broker_wallet_transactions")
    op.drop_table("broker_payout_events")
    op.drop_table("broker_payout_requests")
    op.drop_table("broker_payout_accounts")
    op.drop_table("broker_wallets")
