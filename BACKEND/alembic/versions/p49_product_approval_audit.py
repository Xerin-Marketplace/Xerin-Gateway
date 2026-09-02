"""Add product approval audit method.

Revision ID: p49_product_approval_audit
Revises: p48_auto_product_approval
"""
from alembic import op
import sqlalchemy as sa

revision = "p49_product_approval_audit"
down_revision = "p48_auto_product_approval"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "products",
        sa.Column("approval_method", sa.String(length=20), nullable=True),
    )
    op.create_index(
        "ix_products_approval_method",
        "products",
        ["approval_method"],
        unique=False,
    )

    # Existing approved products predate automatic approval, so they are
    # treated as manual approvals for audit continuity.
    op.execute("""
        UPDATE products
        SET approval_method = 'manual'
        WHERE status = 'approved'
          AND approval_method IS NULL
    """)


def downgrade():
    op.drop_index("ix_products_approval_method", table_name="products")
    op.drop_column("products", "approval_method")
