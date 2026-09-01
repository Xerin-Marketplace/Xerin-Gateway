"""Phase 1 Task 4: seller package preparation enhancements.

Revision ID: p17_seller_package_preparation
Revises: p16_seller_pickup_locations
"""

from alembic import op
import sqlalchemy as sa

revision = "p17_seller_package_preparation"
down_revision = "p16_seller_pickup_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("seller_order_packages", sa.Column("package_label", sa.String(length=120), nullable=True))
    op.add_column("seller_order_packages", sa.Column("package_type", sa.String(length=50), nullable=False, server_default="parcel"))
    op.add_column("seller_order_packages", sa.Column("contents_summary", sa.Text(), nullable=True))
    op.add_column("seller_order_packages", sa.Column("fragile", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("seller_order_packages", sa.Column("keep_upright", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("seller_order_packages", sa.Column("temperature_sensitive", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("seller_order_packages", sa.Column("handling_instructions", sa.Text(), nullable=True))
    op.add_column("seller_order_packages", sa.Column("declared_value", sa.Numeric(14, 2), nullable=True))
    op.add_column("seller_order_packages", sa.Column("declared_currency", sa.String(length=3), nullable=False, server_default="TZS"))
    op.add_column("seller_order_packages", sa.Column("sealed_at", sa.DateTime(timezone=True), nullable=True))

    op.create_check_constraint(
        "ck_seller_order_package_declared_value_nonnegative",
        "seller_order_packages",
        "declared_value IS NULL OR declared_value >= 0",
    )
    op.create_check_constraint(
        "ck_seller_order_package_type",
        "seller_order_packages",
        "package_type IN ('parcel', 'box', 'envelope', 'crate', 'pallet', 'other')",
    )
    op.create_index("ix_seller_order_packages_package_type", "seller_order_packages", ["package_type"])
    op.create_index("ix_seller_order_packages_is_ready", "seller_order_packages", ["is_ready"])
    op.create_index(
        "ix_seller_order_packages_order_ready",
        "seller_order_packages",
        ["seller_order_id", "is_ready"],
    )


def downgrade() -> None:
    op.drop_index("ix_seller_order_packages_order_ready", table_name="seller_order_packages")
    op.drop_index("ix_seller_order_packages_is_ready", table_name="seller_order_packages")
    op.drop_index("ix_seller_order_packages_package_type", table_name="seller_order_packages")
    op.drop_constraint("ck_seller_order_package_type", "seller_order_packages", type_="check")
    op.drop_constraint("ck_seller_order_package_declared_value_nonnegative", "seller_order_packages", type_="check")
    op.drop_column("seller_order_packages", "sealed_at")
    op.drop_column("seller_order_packages", "declared_currency")
    op.drop_column("seller_order_packages", "declared_value")
    op.drop_column("seller_order_packages", "handling_instructions")
    op.drop_column("seller_order_packages", "temperature_sensitive")
    op.drop_column("seller_order_packages", "keep_upright")
    op.drop_column("seller_order_packages", "fragile")
    op.drop_column("seller_order_packages", "contents_summary")
    op.drop_column("seller_order_packages", "package_type")
    op.drop_column("seller_order_packages", "package_label")
