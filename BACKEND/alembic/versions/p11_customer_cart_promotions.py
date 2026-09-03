"""Customer Phase 3: seller promotion state on carts.

Revision ID: p11_customer_cart_promotions
Revises: p10_seller_lifecycle
"""

from alembic import op
import sqlalchemy as sa

revision = "p11_customer_cart_promotions"
down_revision = "p10_seller_lifecycle"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "carts",
        sa.Column("promotion_code", sa.String(length=50), nullable=True),
    )
    op.create_index(
        "ix_carts_promotion_code",
        "carts",
        ["promotion_code"],
        unique=False,
    )


def downgrade():
    op.drop_index("ix_carts_promotion_code", table_name="carts")
    op.drop_column("carts", "promotion_code")
