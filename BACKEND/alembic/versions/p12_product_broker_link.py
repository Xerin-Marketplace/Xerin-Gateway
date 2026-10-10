"""Link products to their broker_products source (catalog mirror for broker listings).

Revision ID: p12_product_broker_link
Revises: p11_broker_earning_engine
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p12_product_broker_link"
down_revision = "p11_broker_earning_engine"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "products",
        sa.Column(
            "broker_product_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("broker_products.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_products_broker_product_id",
        "products",
        ["broker_product_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_products_broker_product_id", table_name="products")
    op.drop_column("products", "broker_product_id")
