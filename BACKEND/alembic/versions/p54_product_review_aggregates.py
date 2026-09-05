"""Add synchronized public product review aggregates.

Revision ID: p54_product_review_aggregates
Revises: p53_seller_scoped_product_sku
"""
from alembic import op
import sqlalchemy as sa


revision = "p54_product_review_aggregates"
down_revision = "p53_seller_scoped_product_sku"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("rating", sa.Numeric(3, 2), nullable=False, server_default="0"),
    )
    op.add_column(
        "products",
        sa.Column("review_count", sa.Integer(), nullable=False, server_default="0"),
    )

    # Backfill from reviews already approved before this migration.
    op.execute("""
        UPDATE products AS p
           SET rating = COALESCE(stats.avg_rating, 0),
               review_count = COALESCE(stats.review_count, 0)
          FROM (
                SELECT
                    product_id,
                    ROUND(AVG(rating)::numeric, 2) AS avg_rating,
                    COUNT(*)::integer AS review_count
                  FROM product_reviews
                 WHERE status = 'approved'
                 GROUP BY product_id
               ) AS stats
         WHERE p.id = stats.product_id
    """)


def downgrade():
    op.drop_column("products", "review_count")
    op.drop_column("products", "rating")
