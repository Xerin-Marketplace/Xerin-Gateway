"""Phase 1 task 3: hash sessions/OTPs and add core integrity constraints.

Revision ID: phase1_task3
Revises: add_otp_purpose
Create Date: 2026-07-30

IMPORTANT: This migration intentionally invalidates all existing login sessions and
unverified OTPs. Users must log in again and request a new OTP after deployment.
"""

from alembic import op
import sqlalchemy as sa


revision = "phase1_task3"
down_revision = "add_otp_purpose"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # Security transition: raw secrets must never be copied into the new columns.
    bind.execute(sa.text("DELETE FROM sessions"))
    bind.execute(sa.text("UPDATE otp_requests SET verified = TRUE WHERE verified = FALSE"))

    op.add_column("sessions", sa.Column("token_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_sessions_user_id", "sessions", ["user_id"], unique=False)
    op.create_index("ix_sessions_expires_at", "sessions", ["expires_at"], unique=False)
    op.create_index("ix_sessions_token_hash", "sessions", ["token_hash"], unique=True)
    op.drop_column("sessions", "refresh_token")
    op.alter_column("sessions", "token_hash", nullable=False)
    op.alter_column("sessions", "user_id", nullable=False)
    op.alter_column("sessions", "expires_at", nullable=False)

    op.add_column("otp_requests", sa.Column("otp_hash", sa.String(length=64), nullable=True))
    op.create_index("ix_otp_requests_user_id", "otp_requests", ["user_id"], unique=False)
    op.create_index("ix_otp_requests_phone", "otp_requests", ["phone"], unique=False)
    op.create_index("ix_otp_requests_expires_at", "otp_requests", ["expires_at"], unique=False)
    op.drop_column("otp_requests", "otp_code")
    # Historical rows are already invalidated. Give them a non-secret sentinel hash.
    bind.execute(sa.text("UPDATE otp_requests SET otp_hash = repeat('0', 64) WHERE otp_hash IS NULL"))
    op.alter_column("otp_requests", "otp_hash", nullable=False)
    op.alter_column("otp_requests", "phone", nullable=False)
    op.alter_column("otp_requests", "expires_at", nullable=False)

    # Remove exact duplicate seller/category assignments before enforcing uniqueness.
    bind.execute(sa.text("""
        DELETE FROM seller_business_categories a
        USING seller_business_categories b
        WHERE a.id > b.id
          AND a.seller_id = b.seller_id
          AND a.category_id = b.category_id
    """))
    op.create_unique_constraint(
        "uq_seller_business_category",
        "seller_business_categories",
        ["seller_id", "category_id"],
    )

    # Normalize calculated stock before enforcing consistency.
    bind.execute(sa.text("""
        UPDATE inventory
        SET reserved_quantity = GREATEST(0, LEAST(reserved_quantity, quantity)),
            quantity = GREATEST(0, quantity)
    """))
    bind.execute(sa.text("UPDATE inventory SET available_quantity = quantity - reserved_quantity"))

    # The old single-column unique constraint prevents more than one NULL poorly and
    # does not express the intended product + variant key.
    op.drop_constraint("inventory_variant_id_key", "inventory", type_="unique")
    op.create_index("ix_inventory_product_id", "inventory", ["product_id"], unique=False)
    op.create_index(
        "ix_inventory_product_variant",
        "inventory",
        ["product_id", "variant_id"],
        unique=True,
    )
    op.create_index(
        "uq_inventory_product_without_variant",
        "inventory",
        ["product_id"],
        unique=True,
        postgresql_where=sa.text("variant_id IS NULL"),
    )
    op.create_check_constraint("ck_inventory_quantity_nonnegative", "inventory", "quantity >= 0")
    op.create_check_constraint("ck_inventory_reserved_nonnegative", "inventory", "reserved_quantity >= 0")
    op.create_check_constraint("ck_inventory_reserved_lte_quantity", "inventory", "reserved_quantity <= quantity")
    op.create_check_constraint(
        "ck_inventory_available_consistent",
        "inventory",
        "available_quantity = quantity - reserved_quantity",
    )

    op.create_index("ix_order_items_order_id", "order_items", ["order_id"], unique=False)
    op.create_index("ix_order_status_history_order_id", "order_status_history", ["order_id"], unique=False)
    op.create_index("ix_payment_transactions_payment_id", "payment_transactions", ["payment_id"], unique=False)
    op.create_index("ix_payments_provider_transaction_id", "payments", ["provider_transaction_id"], unique=True)

    op.create_check_constraint("ck_product_price_nonnegative", "products", "price >= 0")
    op.create_check_constraint(
        "ck_product_sale_price_nonnegative", "products", "sale_price IS NULL OR sale_price >= 0"
    )
    op.create_check_constraint(
        "ck_product_sale_price_lte_price", "products", "sale_price IS NULL OR sale_price <= price"
    )
    op.create_check_constraint("ck_payment_amount_nonnegative", "payments", "amount >= 0")


def downgrade() -> None:
    op.drop_constraint("ck_payment_amount_nonnegative", "payments", type_="check")
    op.drop_constraint("ck_product_sale_price_lte_price", "products", type_="check")
    op.drop_constraint("ck_product_sale_price_nonnegative", "products", type_="check")
    op.drop_constraint("ck_product_price_nonnegative", "products", type_="check")

    op.drop_index("ix_payments_provider_transaction_id", table_name="payments")
    op.drop_index("ix_payment_transactions_payment_id", table_name="payment_transactions")
    op.drop_index("ix_order_status_history_order_id", table_name="order_status_history")
    op.drop_index("ix_order_items_order_id", table_name="order_items")

    op.drop_constraint("ck_inventory_available_consistent", "inventory", type_="check")
    op.drop_constraint("ck_inventory_reserved_lte_quantity", "inventory", type_="check")
    op.drop_constraint("ck_inventory_reserved_nonnegative", "inventory", type_="check")
    op.drop_constraint("ck_inventory_quantity_nonnegative", "inventory", type_="check")
    op.drop_index("uq_inventory_product_without_variant", table_name="inventory")
    op.drop_index("ix_inventory_product_variant", table_name="inventory")
    op.drop_index("ix_inventory_product_id", table_name="inventory")
    op.create_unique_constraint("inventory_variant_id_key", "inventory", ["variant_id"])

    op.drop_constraint(
        "uq_seller_business_category", "seller_business_categories", type_="unique"
    )

    op.add_column("otp_requests", sa.Column("otp_code", sa.String(length=10), nullable=True))
    op.drop_index("ix_otp_requests_expires_at", table_name="otp_requests")
    op.drop_index("ix_otp_requests_phone", table_name="otp_requests")
    op.drop_index("ix_otp_requests_user_id", table_name="otp_requests")
    op.drop_column("otp_requests", "otp_hash")

    op.add_column("sessions", sa.Column("refresh_token", sa.Text(), nullable=True))
    op.drop_index("ix_sessions_token_hash", table_name="sessions")
    op.drop_index("ix_sessions_expires_at", table_name="sessions")
    op.drop_index("ix_sessions_user_id", table_name="sessions")
    op.drop_column("sessions", "token_hash")
