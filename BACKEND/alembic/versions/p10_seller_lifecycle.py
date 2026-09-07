"""Seller phases 1-10 lifecycle foundation.

Revision ID: p10_seller_lifecycle
Revises: p9_finance_configuration
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p10_seller_lifecycle"
down_revision = "p9_finance_configuration"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Phase 1: seller base price vs marketplace/customer price.
    op.add_column("products", sa.Column("seller_base_price", sa.Numeric(18,2), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("seller_sale_price", sa.Numeric(18,2), nullable=True))
    op.add_column("products", sa.Column("commission_rate_snapshot", sa.Numeric(10,4), nullable=False, server_default="0"))
    op.add_column("products", sa.Column("commission_amount_snapshot", sa.Numeric(18,2), nullable=False, server_default="0"))
    op.execute("UPDATE products SET seller_base_price = price WHERE seller_base_price = 0")

    op.add_column("product_variants", sa.Column("seller_base_price", sa.Numeric(18,2), nullable=True))
    op.add_column("product_variants", sa.Column("seller_sale_price", sa.Numeric(18,2), nullable=True))
    op.add_column("product_variants", sa.Column("commission_rate_snapshot", sa.Numeric(10,4), nullable=True))
    op.add_column("product_variants", sa.Column("commission_amount_snapshot", sa.Numeric(18,2), nullable=True))
    op.execute("UPDATE product_variants SET seller_base_price = price, seller_sale_price = sale_price WHERE price IS NOT NULL")

    # Phase 2: payout account verification.
    op.add_column("seller_payout_accounts", sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("seller_payout_accounts", sa.Column("verification_status", sa.String(30), nullable=False, server_default="pending"))
    op.add_column("seller_payout_accounts", sa.Column("provider_reference", sa.String(180), nullable=True))
    op.add_column("seller_payout_accounts", sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("seller_payout_accounts", sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_seller_payout_accounts_verification_status", "seller_payout_accounts", ["verification_status"])

    # Phase 3: seller-funded promotions.
    op.add_column("promotions", sa.Column("funding_source", sa.String(30), nullable=False, server_default="seller"))

    # Phases 5-6: seller order chat and packaging.
    op.create_table(
        "seller_order_packages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seller_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weight_kg", sa.Numeric(10,3), nullable=True),
        sa.Column("length_cm", sa.Numeric(10,2), nullable=True),
        sa.Column("width_cm", sa.Numeric(10,2), nullable=True),
        sa.Column("height_cm", sa.Numeric(10,2), nullable=True),
        sa.Column("package_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_ready", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("prepared_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("package_count > 0", name="ck_seller_order_package_count_positive"),
        sa.CheckConstraint("weight_kg IS NULL OR weight_kg >= 0", name="ck_seller_order_package_weight_nonnegative"),
    )
    op.create_index("ix_seller_order_packages_seller_order", "seller_order_packages", ["seller_order_id"], unique=True)

    op.create_table(
        "seller_order_package_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("package_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seller_order_packages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_seller_order_package_attachments_package", "seller_order_package_attachments", ["package_id"])

    op.create_table(
        "seller_order_messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("seller_order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seller_orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("sender_role_label", sa.String(60), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_internal", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_seller_order_messages_order", "seller_order_messages", ["seller_order_id"])
    op.create_index("ix_seller_order_messages_sender", "seller_order_messages", ["sender_user_id"])
    op.create_index("ix_seller_order_messages_created", "seller_order_messages", ["created_at"])

    op.create_table(
        "seller_order_message_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("message_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("seller_order_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_url", sa.Text(), nullable=False),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_seller_order_message_attachments_message", "seller_order_message_attachments", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_seller_order_message_attachments_message", table_name="seller_order_message_attachments")
    op.drop_table("seller_order_message_attachments")
    op.drop_index("ix_seller_order_messages_created", table_name="seller_order_messages")
    op.drop_index("ix_seller_order_messages_sender", table_name="seller_order_messages")
    op.drop_index("ix_seller_order_messages_order", table_name="seller_order_messages")
    op.drop_table("seller_order_messages")
    op.drop_index("ix_seller_order_package_attachments_package", table_name="seller_order_package_attachments")
    op.drop_table("seller_order_package_attachments")
    op.drop_index("ix_seller_order_packages_seller_order", table_name="seller_order_packages")
    op.drop_table("seller_order_packages")

    op.drop_column("promotions", "funding_source")

    op.drop_index("ix_seller_payout_accounts_verification_status", table_name="seller_payout_accounts")
    op.drop_column("seller_payout_accounts", "updated_at")
    op.drop_column("seller_payout_accounts", "verified_at")
    op.drop_column("seller_payout_accounts", "provider_reference")
    op.drop_column("seller_payout_accounts", "verification_status")
    op.drop_column("seller_payout_accounts", "is_active")

    op.drop_column("product_variants", "commission_amount_snapshot")
    op.drop_column("product_variants", "commission_rate_snapshot")
    op.drop_column("product_variants", "seller_sale_price")
    op.drop_column("product_variants", "seller_base_price")

    op.drop_column("products", "commission_amount_snapshot")
    op.drop_column("products", "commission_rate_snapshot")
    op.drop_column("products", "seller_sale_price")
    op.drop_column("products", "seller_base_price")
