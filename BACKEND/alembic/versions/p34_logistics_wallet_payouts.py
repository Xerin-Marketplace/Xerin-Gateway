"""Completion Phase 1 Task 2: logistics wallet and payout lifecycle.

Revision ID: p34_logistics_wallet_payouts
Revises: p33_trusted_seller_settlement
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p34_logistics_wallet_payouts"
down_revision = "p33_trusted_seller_settlement"
branch_labels = None
depends_on = None

UUID = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table("logistics_wallets",
        sa.Column("id", UUID, primary_key=True), sa.Column("logistics_company_id", UUID, sa.ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"), sa.Column("pending_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("available_balance", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("reserved_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("paid_out_balance", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("refunded_balance", sa.Numeric(18,2), nullable=False, server_default="0"),
        sa.Column("debt_balance", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("is_frozen", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("logistics_company_id"), sa.CheckConstraint("pending_balance >= 0 AND available_balance >= 0 AND reserved_balance >= 0 AND paid_out_balance >= 0 AND refunded_balance >= 0 AND debt_balance >= 0", name="ck_logistics_wallet_balances_nonnegative"))
    op.create_index("ix_logistics_wallets_company", "logistics_wallets", ["logistics_company_id"], unique=True)
    op.create_index("ix_logistics_wallets_frozen", "logistics_wallets", ["is_frozen"])
    op.create_table("logistics_payout_accounts",
        sa.Column("id", UUID, primary_key=True), sa.Column("logistics_company_id", UUID, sa.ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("account_type", sa.String(50), nullable=False), sa.Column("provider", sa.String(100), nullable=False), sa.Column("account_name", sa.String(255), nullable=False), sa.Column("account_number", sa.String(255), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"), sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("verification_status", sa.String(30), nullable=False, server_default="pending"), sa.Column("verification_note", sa.Text()), sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("logistics_company_id", "provider", "account_number", name="uq_logistics_payout_account"), sa.CheckConstraint("verification_status IN ('pending','verified','rejected')", name="ck_logistics_payout_account_verification"))
    op.create_index("ix_logistics_payout_accounts_company", "logistics_payout_accounts", ["logistics_company_id"])
    op.create_index("ix_logistics_payout_accounts_verification", "logistics_payout_accounts", ["verification_status"])
    op.create_table("logistics_payout_requests",
        sa.Column("id", UUID, primary_key=True), sa.Column("wallet_id", UUID, sa.ForeignKey("logistics_wallets.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("logistics_company_id", UUID, sa.ForeignKey("logistics_companies.id", ondelete="RESTRICT"), nullable=False), sa.Column("payout_account_id", UUID, sa.ForeignKey("logistics_payout_accounts.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False), sa.Column("currency", sa.String(10), nullable=False), sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("provider_reference", sa.String(180), unique=True), sa.Column("company_note", sa.Text()), sa.Column("admin_note", sa.Text()),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("processed_at", sa.DateTime(timezone=True)), sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("amount > 0", name="ck_logistics_payout_amount_positive"), sa.CheckConstraint("status IN ('pending','approved','processing','completed','rejected','failed','cancelled')", name="ck_logistics_payout_status"))
    for name, cols in (("ix_logistics_payout_requests_wallet",["wallet_id"]),("ix_logistics_payout_requests_company",["logistics_company_id"]),("ix_logistics_payout_requests_status",["status"])): op.create_index(name,"logistics_payout_requests",cols)
    op.create_table("logistics_payout_events", sa.Column("id", UUID, primary_key=True), sa.Column("payout_request_id", UUID, sa.ForeignKey("logistics_payout_requests.id", ondelete="CASCADE"), nullable=False), sa.Column("status", sa.String(30), nullable=False), sa.Column("note", sa.Text()), sa.Column("created_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_logistics_payout_events_request", "logistics_payout_events", ["payout_request_id"])
    op.create_table("logistics_wallet_transactions",
        sa.Column("id", UUID, primary_key=True), sa.Column("wallet_id", UUID, sa.ForeignKey("logistics_wallets.id", ondelete="CASCADE"), nullable=False), sa.Column("transaction_type", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(18,2), nullable=False), sa.Column("currency", sa.String(10), nullable=False), sa.Column("reference", sa.String(180), nullable=False, unique=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id", ondelete="SET NULL")), sa.Column("payout_request_id", UUID, sa.ForeignKey("logistics_payout_requests.id", ondelete="SET NULL")),
        sa.Column("eligible_at", sa.DateTime(timezone=True)), sa.Column("released_at", sa.DateTime(timezone=True)), sa.Column("description", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("amount >= 0", name="ck_logistics_wallet_transaction_amount_nonnegative"))
    for name, cols, unique in (("ix_logistics_wallet_tx_wallet",["wallet_id"],False),("ix_logistics_wallet_tx_type",["transaction_type"],False),("ix_logistics_wallet_tx_reference",["reference"],True),("ix_logistics_wallet_tx_order",["order_id"],False),("ix_logistics_wallet_tx_payout",["payout_request_id"],False),("ix_logistics_wallet_tx_eligible",["eligible_at"],False)): op.create_index(name,"logistics_wallet_transactions",cols,unique=unique)


def downgrade() -> None:
    op.drop_table("logistics_wallet_transactions")
    op.drop_table("logistics_payout_events")
    op.drop_table("logistics_payout_requests")
    op.drop_table("logistics_payout_accounts")
    op.drop_table("logistics_wallets")
