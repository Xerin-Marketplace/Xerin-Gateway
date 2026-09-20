"""Store-origin seller orders and shipments.

Revision ID: p44_store_origin_fulfillment
Revises: p43_logistics_country_capabilities
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p44_store_origin_fulfillment"
down_revision = "p43_logistics_country_capabilities"
branch_labels = None
depends_on = None


def upgrade():
    uuid = postgresql.UUID(as_uuid=True)
    for table in ("order_items", "seller_orders", "shipments"):
        op.add_column(table, sa.Column("store_id", uuid, nullable=True))

    # Products already have a required store_id. Snapshot it into historical
    # order items first, then derive each old seller-order/shipment origin.
    op.execute("""
        UPDATE order_items oi
        SET store_id = p.store_id
        FROM products p
        WHERE p.id = oi.product_id AND oi.store_id IS NULL
    """)
    op.execute("""
        UPDATE seller_orders so
        SET store_id = src.store_id
        FROM (
          SELECT order_id, seller_id, MIN(store_id::text)::uuid AS store_id
          FROM order_items
          WHERE store_id IS NOT NULL
          GROUP BY order_id, seller_id
        ) src
        WHERE src.order_id = so.order_id AND src.seller_id = so.seller_id
          AND so.store_id IS NULL
    """)
    op.execute("""
        UPDATE shipments sh
        SET store_id = src.store_id
        FROM (
          SELECT order_id, seller_id, MIN(store_id::text)::uuid AS store_id
          FROM order_items
          WHERE store_id IS NOT NULL
          GROUP BY order_id, seller_id
        ) src
        WHERE src.order_id = sh.order_id AND src.seller_id = sh.seller_id
          AND sh.store_id IS NULL
    """)

    for table in ("order_items", "seller_orders", "shipments"):
        op.alter_column(table, "store_id", nullable=False)
        op.create_foreign_key(f"fk_{table}_store_id", table, "stores", ["store_id"], ["id"], ondelete="RESTRICT")
        op.create_index(f"ix_{table}_store_id", table, ["store_id"])

    op.drop_constraint("uq_seller_order_order_seller", "seller_orders", type_="unique")
    op.create_unique_constraint("uq_seller_order_order_seller_store", "seller_orders", ["order_id", "seller_id", "store_id"])
    op.drop_constraint("uq_shipment_order_seller", "shipments", type_="unique")
    op.create_unique_constraint("uq_shipment_order_seller_store", "shipments", ["order_id", "seller_id", "store_id"])


def downgrade():
    op.drop_constraint("uq_shipment_order_seller_store", "shipments", type_="unique")
    op.create_unique_constraint("uq_shipment_order_seller", "shipments", ["order_id", "seller_id"])
    op.drop_constraint("uq_seller_order_order_seller_store", "seller_orders", type_="unique")
    op.create_unique_constraint("uq_seller_order_order_seller", "seller_orders", ["order_id", "seller_id"])
    for table in ("shipments", "seller_orders", "order_items"):
        op.drop_index(f"ix_{table}_store_id", table_name=table)
        op.drop_constraint(f"fk_{table}_store_id", table, type_="foreignkey")
        op.drop_column(table, "store_id")
