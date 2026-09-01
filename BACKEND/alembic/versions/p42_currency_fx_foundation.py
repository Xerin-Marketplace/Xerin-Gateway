"""Harden marketplace currency and FX administration around TZS settlement.

Revision ID: p42_currency_fx_foundation
Revises: p41_store_multistore_index_fix
"""

import uuid

from alembic import op
import sqlalchemy as sa

revision = "p42_currency_fx_foundation"
down_revision = "p41_store_multistore_index_fix"
branch_labels = None
depends_on = None


CURRENCIES = (
    ("TZS", "Tanzanian Shilling", "TSh", True, 0),
    ("USD", "US Dollar", "$", False, 2),
    ("AED", "UAE Dirham", "AED", False, 2),
    ("CNY", "Chinese Yuan", "¥", False, 2),
    ("TRY", "Turkish Lira", "₺", False, 2),
    ("GBP", "British Pound", "£", False, 2),
)


def upgrade() -> None:
    # The marketplace settles through local gateways in TZS. Keep exactly one
    # base currency and make that invariant explicit in the database.
    op.execute("UPDATE payment_currencies SET is_base = false WHERE code <> 'TZS'")

    for code, name, symbol, is_base, decimal_places in CURRENCIES:
        op.execute(
            sa.text(
                """
                INSERT INTO payment_currencies
                    (id, code, name, symbol, is_base, is_active, decimal_places)
                VALUES
                    (:id, :code, :name, :symbol, :is_base, true, :decimal_places)
                ON CONFLICT (code) DO UPDATE SET
                    name = EXCLUDED.name,
                    symbol = EXCLUDED.symbol,
                    is_base = EXCLUDED.is_base,
                    is_active = CASE WHEN EXCLUDED.code = 'TZS' THEN true ELSE payment_currencies.is_active END,
                    decimal_places = EXCLUDED.decimal_places
                """
            ).bindparams(
                id=str(uuid.uuid4()),
                code=code,
                name=name,
                symbol=symbol,
                is_base=is_base,
                decimal_places=decimal_places,
            )
        )

    op.execute("UPDATE payment_currencies SET is_base = (code = 'TZS')")
    op.execute("UPDATE payment_currencies SET is_active = true WHERE code = 'TZS'")
    op.execute("UPDATE finance_settings SET settlement_currency = 'TZS'")

    # Prevent a second base currency and prevent a non-TZS row from becoming base.
    op.create_check_constraint(
        "ck_payment_currency_base_is_tzs",
        "payment_currencies",
        "(NOT is_base) OR code = 'TZS'",
    )
    op.execute(
        """
        CREATE UNIQUE INDEX uq_payment_currencies_single_base
        ON payment_currencies ((is_base))
        WHERE is_base = true
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_payment_currencies_single_base")
    op.drop_constraint("ck_payment_currency_base_is_tzs", "payment_currencies", type_="check")
