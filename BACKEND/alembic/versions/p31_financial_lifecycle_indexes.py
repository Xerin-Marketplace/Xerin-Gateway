"""Phase 4 Task 2: financial lifecycle reconciliation indexes.

Revision ID: p31_financial_lifecycle_indexes
Revises: p30_order_workflow_indexes
"""
from alembic import op

revision = "p31_financial_lifecycle_indexes"
down_revision = "p30_order_workflow_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_escrow_holds_order_status", "escrow_holds", ["order_id", "status"])
    op.create_index("ix_refunds_order_status", "refunds", ["order_id", "status"])
    op.create_index("ix_wallet_transactions_order_type", "wallet_transactions", ["order_id", "transaction_type"])
    op.create_index("ix_payout_requests_seller_status", "payout_requests", ["seller_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_payout_requests_seller_status", table_name="payout_requests")
    op.drop_index("ix_wallet_transactions_order_type", table_name="wallet_transactions")
    op.drop_index("ix_refunds_order_status", table_name="refunds")
    op.drop_index("ix_escrow_holds_order_status", table_name="escrow_holds")
