"""Phase 2 Task 5: multi-seller delivery pricing.

Revision ID: p21_multi_seller_pricing
Revises: p20_customer_map_pin_confirmation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p21_multi_seller_pricing"
down_revision = "p20_customer_map_pin_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Existing PostgreSQL enum used by shipping_rates.rate_type.
    op.execute("ALTER TYPE shippingratetype ADD VALUE IF NOT EXISTS 'per_km'")
    op.execute(
        "ALTER TYPE shippingratetype ADD VALUE IF NOT EXISTS 'base_plus_per_km'"
    )
    op.execute(
        "ALTER TYPE shippingratetype ADD VALUE IF NOT EXISTS 'provider_quote'"
    )

    strategy_enum = postgresql.ENUM(
        "farthest_seller",
        "sum_individual",
        "optimized_multi_pickup",
        "logistics_provider_quote",
        name="multisellerpricingstrategy",
    )
    strategy_enum.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "logistics_companies",
        sa.Column(
            "multi_seller_pricing_strategy",
            strategy_enum,
            nullable=False,
            server_default="farthest_seller",
        ),
    )
    op.create_index(
        "ix_logistics_companies_multi_seller_pricing_strategy",
        "logistics_companies",
        ["multi_seller_pricing_strategy"],
        unique=False,
    )

    op.add_column(
        "shipping_rates",
        sa.Column(
            "amount_per_km",
            sa.Numeric(18, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "shipping_rates",
        sa.Column("minimum_fee", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "shipping_rates",
        sa.Column("maximum_fee", sa.Numeric(18, 2), nullable=True),
    )
    op.add_column(
        "shipping_rates",
        sa.Column("max_distance_km", sa.Numeric(10, 3), nullable=True),
    )

    op.create_check_constraint(
        "ck_shipping_rate_perkm_nonnegative",
        "shipping_rates",
        "amount_per_km >= 0",
    )
    op.create_check_constraint(
        "ck_shipping_rate_minimum_fee_nonnegative",
        "shipping_rates",
        "minimum_fee IS NULL OR minimum_fee >= 0",
    )
    op.create_check_constraint(
        "ck_shipping_rate_maximum_fee_valid",
        "shipping_rates",
        "maximum_fee IS NULL OR maximum_fee >= minimum_fee",
    )
    op.create_check_constraint(
        "ck_shipping_rate_max_distance_positive",
        "shipping_rates",
        "max_distance_km IS NULL OR max_distance_km > 0",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_shipping_rate_max_distance_positive",
        "shipping_rates",
        type_="check",
    )
    op.drop_constraint(
        "ck_shipping_rate_maximum_fee_valid",
        "shipping_rates",
        type_="check",
    )
    op.drop_constraint(
        "ck_shipping_rate_minimum_fee_nonnegative",
        "shipping_rates",
        type_="check",
    )
    op.drop_constraint(
        "ck_shipping_rate_perkm_nonnegative",
        "shipping_rates",
        type_="check",
    )

    op.drop_column("shipping_rates", "max_distance_km")
    op.drop_column("shipping_rates", "maximum_fee")
    op.drop_column("shipping_rates", "minimum_fee")
    op.drop_column("shipping_rates", "amount_per_km")

    op.drop_index(
        "ix_logistics_companies_multi_seller_pricing_strategy",
        table_name="logistics_companies",
    )
    op.drop_column(
        "logistics_companies",
        "multi_seller_pricing_strategy",
    )

    postgresql.ENUM(
        "farthest_seller",
        "sum_individual",
        "optimized_multi_pickup",
        "logistics_provider_quote",
        name="multisellerpricingstrategy",
    ).drop(op.get_bind(), checkfirst=True)

    # PostgreSQL enum values added to shippingratetype are intentionally not
    # removed in downgrade because removing enum values is destructive and can
    # invalidate existing data.
