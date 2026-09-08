"""Customer Phase 5: immutable checkout/order pricing snapshots.

Revision ID: p12_customer_checkout_snapshot
Revises: p11_customer_cart_promotions
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p12_customer_checkout_snapshot"
down_revision = "p11_customer_cart_promotions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "orders",
        sa.Column(
            "coupon_discount_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "promotion_discount_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "original_shipping_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "orders",
        sa.Column(
            "shipping_discount_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "orders",
        sa.Column("promotion_code", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "promotion_seller_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.add_column(
        "orders",
        sa.Column("delivery_mode", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "orders",
        sa.Column(
            "logistics_company_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )

    op.create_foreign_key(
        "fk_orders_promotion_seller_id_sellers",
        "orders",
        "sellers",
        ["promotion_seller_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_orders_logistics_company_id_logistics_companies",
        "orders",
        "logistics_companies",
        ["logistics_company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_orders_promotion_seller_id",
        "orders",
        ["promotion_seller_id"],
        unique=False,
    )
    op.create_index(
        "ix_orders_logistics_company_id",
        "orders",
        ["logistics_company_id"],
        unique=False,
    )

    op.add_column(
        "order_items",
        sa.Column(
            "promotion_discount_amount",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "customer_total",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )

    # Existing rows predate seller promotions, so their customer line amount
    # equals the gross line amount.
    op.execute(
        """
        UPDATE order_items
        SET customer_total = total_price
        WHERE customer_total = 0
        """
    )


def downgrade():
    op.drop_column("order_items", "customer_total")
    op.drop_column("order_items", "promotion_discount_amount")

    op.drop_index(
        "ix_orders_logistics_company_id",
        table_name="orders",
    )
    op.drop_index(
        "ix_orders_promotion_seller_id",
        table_name="orders",
    )
    op.drop_constraint(
        "fk_orders_logistics_company_id_logistics_companies",
        "orders",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_orders_promotion_seller_id_sellers",
        "orders",
        type_="foreignkey",
    )

    op.drop_column("orders", "logistics_company_id")
    op.drop_column("orders", "delivery_mode")
    op.drop_column("orders", "promotion_seller_id")
    op.drop_column("orders", "promotion_code")
    op.drop_column("orders", "shipping_discount_amount")
    op.drop_column("orders", "original_shipping_amount")
    op.drop_column("orders", "promotion_discount_amount")
    op.drop_column("orders", "coupon_discount_amount")
