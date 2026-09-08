"""Phase 3 product-to-store assignment.

Revision ID: p40_product_store_assignment
Revises: p39_multi_store_foundation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p40_product_store_assignment"
down_revision = "p39_multi_store_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("store_id", postgresql.UUID(as_uuid=True), nullable=True))

    # Legacy products pre-date multi-store support. Assign each one to the seller's
    # earliest store, which represents the old one-store-per-seller relationship.
    op.execute(
        """
        UPDATE products AS p
        SET store_id = (
            SELECT st.id
            FROM stores AS st
            WHERE st.seller_id = p.seller_id
            ORDER BY st.created_at ASC, st.id ASC
            LIMIT 1
        )
        WHERE p.store_id IS NULL
        """
    )

    bind = op.get_bind()
    orphan_count = bind.execute(sa.text("SELECT count(*) FROM products WHERE store_id IS NULL")).scalar_one()
    if orphan_count:
        raise RuntimeError(
            f"Cannot make products.store_id mandatory: {orphan_count} existing product(s) belong to sellers with no store. "
            "Create a store for those sellers and rerun the migration."
        )

    op.create_foreign_key(
        "fk_products_store_id_stores", "products", "stores", ["store_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_index("ix_products_store_id", "products", ["store_id"], unique=False)
    op.alter_column("products", "store_id", nullable=False)


def downgrade() -> None:
    op.drop_index("ix_products_store_id", table_name="products")
    op.drop_constraint("fk_products_store_id_stores", "products", type_="foreignkey")
    op.drop_column("products", "store_id")
