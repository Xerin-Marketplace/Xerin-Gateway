"""Add payment administration, providers, currency/FX, disputes and reconciliation.

Revision ID: p6_payment_admin
Revises: p5_support_tickets
"""

import uuid
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p6_payment_admin"
down_revision = "p5_support_tickets"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_provider_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("provider_type", sa.String(50), nullable=False, server_default="gateway"),
        sa.Column("status", sa.String(30), nullable=False, server_default="active"),
        sa.Column("supported_currencies", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("supported_methods", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("environment", sa.String(30), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code", name="uq_payment_provider_configs_code"),
    )
    op.create_index("ix_payment_provider_configs_code", "payment_provider_configs", ["code"])
    op.create_index("ix_payment_provider_configs_status", "payment_provider_configs", ["status"])

    op.create_table(
        "payment_currencies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(10), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("symbol", sa.String(12), nullable=False),
        sa.Column("is_base", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("decimal_places", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code", name="uq_payment_currencies_code"),
    )
    op.create_index("ix_payment_currencies_code", "payment_currencies", ["code"])

    op.create_table(
        "payment_fx_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("base_currency", sa.String(10), nullable=False),
        sa.Column("quote_currency", sa.String(10), nullable=False),
        sa.Column("rate", sa.Numeric(20, 8), nullable=False),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("effective_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("rate > 0", name="ck_payment_fx_rate_positive"),
        sa.CheckConstraint("base_currency <> quote_currency", name="ck_payment_fx_distinct_currency"),
        sa.UniqueConstraint("base_currency", "quote_currency", "effective_at", name="uq_payment_fx_pair_effective"),
    )
    op.create_index("ix_payment_fx_pair", "payment_fx_rates", ["base_currency", "quote_currency", "effective_at"])

    op.create_table(
        "payment_countries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("code", sa.String(3), nullable=False),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("currency_code", sa.String(10), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("payments_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("payouts_enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("code", name="uq_payment_countries_code"),
    )

    op.create_table(
        "payment_disputes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("amount >= 0", name="ck_payment_dispute_amount_nonnegative"),
    )
    op.create_index("ix_payment_disputes_status", "payment_disputes", ["status"])
    op.create_index("ix_payment_disputes_provider_reference", "payment_disputes", ["provider_reference"])

    op.create_table(
        "payment_risk_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("event_type", sa.String(80), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False, server_default="medium"),
        sa.Column("status", sa.String(30), nullable=False, server_default="open"),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("score", sa.Numeric(8, 2), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("resolution_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_payment_risk_events_status_severity", "payment_risk_events", ["status", "severity"])

    op.create_table(
        "payment_reconciliation_records",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("payment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("provider", sa.String(100), nullable=True),
        sa.Column("provider_reference", sa.String(255), nullable=True),
        sa.Column("expected_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("provider_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("currency", sa.String(10), nullable=False),
        sa.Column("difference", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"),
        sa.Column("reconciliation_note", sa.Text(), nullable=True),
        sa.Column("reconciled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_payment_reconciliation_status", "payment_reconciliation_records", ["status"])
    op.create_index("ix_payment_reconciliation_provider_reference", "payment_reconciliation_records", ["provider_reference"])

    # Current integration discovered in the backend: AzamPay for MNO and hosted-card checkout.
    provider_id = str(uuid.uuid4())
    op.execute(sa.text("""
        INSERT INTO payment_provider_configs
            (id, name, code, provider_type, status, supported_currencies, supported_methods, environment, is_default)
        VALUES
            (:id, 'AzamPay', 'azampay', 'gateway', 'active', '[\"TZS\"]'::jsonb,
             '[\"mobile_money\", \"card\"]'::jsonb, 'configured', true)
        ON CONFLICT (code) DO NOTHING
    """).bindparams(id=provider_id))

    # TZS and USD are configuration records. No FX rate is inserted because rates must come from an approved source.
    op.execute(sa.text("""
        INSERT INTO payment_currencies (id, code, name, symbol, is_base, is_active, decimal_places)
        VALUES
          (:tzs_id, 'TZS', 'Tanzanian Shilling', 'TSh', true, true, 0),
          (:usd_id, 'USD', 'US Dollar', '$', false, true, 2)
        ON CONFLICT (code) DO NOTHING
    """).bindparams(tzs_id=str(uuid.uuid4()), usd_id=str(uuid.uuid4())))

    op.execute(sa.text("""
        INSERT INTO payment_countries (id, code, name, currency_code, is_active, payments_enabled, payouts_enabled)
        VALUES (:id, 'TZA', 'Tanzania', 'TZS', true, true, true)
        ON CONFLICT (code) DO NOTHING
    """).bindparams(id=str(uuid.uuid4())))


def downgrade() -> None:
    for table in [
        "payment_reconciliation_records",
        "payment_risk_events",
        "payment_disputes",
        "payment_countries",
        "payment_fx_rates",
        "payment_currencies",
        "payment_provider_configs",
    ]:
        op.drop_table(table)
