"""Phase 2 Task 6: immutable checkout delivery quote.

Revision ID: p22_checkout_delivery_quote
Revises: p21_multi_seller_pricing
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p22_checkout_delivery_quote"
down_revision = "p21_multi_seller_pricing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "checkout_delivery_quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipping_address_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipping_method_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipping_rate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("delivery_mode", sa.String(length=20), nullable=False),
        sa.Column("pricing_strategy", sa.String(length=50), nullable=False),
        sa.Column("rate_type", sa.String(length=50), nullable=False),
        sa.Column("currency", sa.String(length=10), nullable=False),
        sa.Column("seller_count", sa.Integer(), nullable=False),
        sa.Column("billable_distance_km", sa.Numeric(10, 3), nullable=False),
        sa.Column("billable_seller_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("product_subtotal", sa.Numeric(18, 2), nullable=False),
        sa.Column("delivery_amount", sa.Numeric(18, 2), nullable=False),
        sa.Column(
            "checkout_total_before_discounts",
            sa.Numeric(18, 2),
            nullable=False,
        ),
        sa.Column("cart_fingerprint", sa.String(length=64), nullable=False),
        sa.Column(
            "pricing_breakdown",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "seller_routes_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "address_snapshot",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "seller_count > 0",
            name="ck_checkout_delivery_quote_seller_count",
        ),
        sa.CheckConstraint(
            "billable_distance_km >= 0",
            name="ck_checkout_delivery_quote_distance_nonnegative",
        ),
        sa.CheckConstraint(
            "product_subtotal >= 0",
            name="ck_checkout_delivery_quote_subtotal_nonnegative",
        ),
        sa.CheckConstraint(
            "delivery_amount >= 0",
            name="ck_checkout_delivery_quote_delivery_nonnegative",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["shipping_address_id"], ["addresses.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["logistics_company_id"],
            ["logistics_companies.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["shipping_method_id"], ["shipping_methods.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["shipping_rate_id"], ["shipping_rates.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["billable_seller_id"], ["sellers.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    for column in (
        "user_id",
        "shipping_address_id",
        "logistics_company_id",
        "shipping_method_id",
        "shipping_rate_id",
        "delivery_mode",
        "billable_seller_id",
        "cart_fingerprint",
        "expires_at",
        "used_at",
    ):
        op.create_index(
            f"ix_checkout_delivery_quotes_{column}",
            "checkout_delivery_quotes",
            [column],
            unique=False,
        )

    op.create_index(
        "ix_checkout_delivery_quotes_user_expiry",
        "checkout_delivery_quotes",
        ["user_id", "expires_at"],
        unique=False,
    )

    op.add_column(
        "orders",
        sa.Column(
            "delivery_quote_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_orders_delivery_quote_id_checkout_delivery_quotes",
        "orders",
        "checkout_delivery_quotes",
        ["delivery_quote_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_orders_delivery_quote_id",
        "orders",
        ["delivery_quote_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_orders_delivery_quote_id", table_name="orders")
    op.drop_constraint(
        "fk_orders_delivery_quote_id_checkout_delivery_quotes",
        "orders",
        type_="foreignkey",
    )
    op.drop_column("orders", "delivery_quote_id")

    op.drop_index(
        "ix_checkout_delivery_quotes_user_expiry",
        table_name="checkout_delivery_quotes",
    )
    for column in reversed(
        (
            "user_id",
            "shipping_address_id",
            "logistics_company_id",
            "shipping_method_id",
            "shipping_rate_id",
            "delivery_mode",
            "billable_seller_id",
            "cart_fingerprint",
            "expires_at",
            "used_at",
        )
    ):
        op.drop_index(
            f"ix_checkout_delivery_quotes_{column}",
            table_name="checkout_delivery_quotes",
        )

    op.drop_table("checkout_delivery_quotes")
