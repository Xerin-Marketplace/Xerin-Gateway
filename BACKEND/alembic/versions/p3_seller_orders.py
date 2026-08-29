"""Seller order management and fulfilment aggregate.

Revision ID: p3_seller_orders
Revises: p3_seller_variants
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# Alembic revision identifiers
revision = "p3_seller_orders"
down_revision = "p3_seller_variants"
branch_labels = None
depends_on = None


# Reuse the PostgreSQL enum when creating the table.
# create_type=False prevents SQLAlchemy from attempting to create
# sellerorderstatus automatically during op.create_table().
STATUS = postgresql.ENUM(
    "new",
    "accepted",
    "processing",
    "ready_to_ship",
    "shipped",
    "delivered",
    "cancellation_requested",
    "cancelled",
    name="sellerorderstatus",
    create_type=False,
)


def upgrade() -> None:
    """Create seller order management structures."""

    # Create the enum only when it does not already exist.
    # This solves:
    # psycopg2.errors.DuplicateObject:
    # type "sellerorderstatus" already exists
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'sellerorderstatus'
            ) THEN
                CREATE TYPE sellerorderstatus AS ENUM (
                    'new',
                    'accepted',
                    'processing',
                    'ready_to_ship',
                    'shipped',
                    'delivered',
                    'cancellation_requested',
                    'cancelled'
                );
            END IF;
        END
        $$;
        """
    )

    op.create_table(
        "seller_orders",

        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            nullable=False,
        ),

        sa.Column(
            "order_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "orders.id",
                ondelete="CASCADE",
            ),
            nullable=False,
        ),

        sa.Column(
            "seller_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(
                "sellers.id",
                ondelete="RESTRICT",
            ),
            nullable=False,
        ),

        sa.Column(
            "status",
            STATUS,
            nullable=False,
            server_default=sa.text("'new'::sellerorderstatus"),
        ),

        sa.Column(
            "seller_subtotal",
            sa.Numeric(18, 2),
            nullable=False,
            server_default=sa.text("0"),
        ),

        sa.Column(
            "item_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),

        sa.Column(
            "accepted_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "processing_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "ready_to_ship_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "shipped_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "delivered_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "cancellation_requested_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.Column(
            "cancellation_reason",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "seller_notes",
            sa.Text(),
            nullable=True,
        ),

        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),

        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),

        sa.UniqueConstraint(
            "order_id",
            "seller_id",
            name="uq_seller_order_order_seller",
        ),

        sa.CheckConstraint(
            "seller_subtotal >= 0",
            name="ck_seller_order_subtotal_nonnegative",
        ),

        sa.CheckConstraint(
            "item_count >= 0",
            name="ck_seller_order_item_count_nonnegative",
        ),
    )

    op.create_index(
        "ix_seller_orders_order_id",
        "seller_orders",
        ["order_id"],
        unique=False,
    )

    op.create_index(
        "ix_seller_orders_seller_id",
        "seller_orders",
        ["seller_id"],
        unique=False,
    )

    op.create_index(
        "ix_seller_orders_status",
        "seller_orders",
        ["status"],
        unique=False,
    )

    # Create seller-order records for eligible existing orders.
    op.execute(
        """
        INSERT INTO seller_orders (
            id,
            order_id,
            seller_id,
            status,
            seller_subtotal,
            item_count,
            created_at
        )
        SELECT
            gen_random_uuid(),
            oi.order_id,
            oi.seller_id,

            CASE
                WHEN o.status::text = 'shipped'
                    THEN 'shipped'::sellerorderstatus

                WHEN o.status::text = 'delivered'
                    THEN 'delivered'::sellerorderstatus

                WHEN o.status::text = 'processing'
                    THEN 'processing'::sellerorderstatus

                ELSE 'new'::sellerorderstatus
            END,

            COALESCE(SUM(oi.total_price), 0),
            COALESCE(SUM(oi.quantity), 0),
            COALESCE(o.created_at, now())

        FROM order_items AS oi

        INNER JOIN orders AS o
            ON o.id = oi.order_id

        WHERE
            oi.seller_id IS NOT NULL
            AND o.status::text IN (
                'paid',
                'processing',
                'shipped',
                'delivered'
            )

        GROUP BY
            oi.order_id,
            oi.seller_id,
            o.status,
            o.created_at

        ON CONFLICT (order_id, seller_id)
        DO NOTHING;
        """
    )


def downgrade() -> None:
    """Remove seller order management structures."""

    op.drop_index(
        "ix_seller_orders_status",
        table_name="seller_orders",
    )

    op.drop_index(
        "ix_seller_orders_seller_id",
        table_name="seller_orders",
    )

    op.drop_index(
        "ix_seller_orders_order_id",
        table_name="seller_orders",
    )

    op.drop_table("seller_orders")

    # Remove the enum after removing the table that depends on it.
    # The dependency check prevents the downgrade from breaking another
    # table if the enum is being reused elsewhere.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM pg_type
                WHERE typname = 'sellerorderstatus'
            )
            AND NOT EXISTS (
                SELECT 1
                FROM pg_depend AS dependency
                INNER JOIN pg_type AS enum_type
                    ON enum_type.oid = dependency.refobjid
                WHERE
                    enum_type.typname = 'sellerorderstatus'
                    AND dependency.deptype = 'n'
            )
            THEN
                DROP TYPE sellerorderstatus;
            END IF;
        END
        $$;
        """
    )