"""Phase 3 combined Task 4: logistics pricing and multi-seller rates.

Revision ID: p27_logistics_pricing
Revises: p26_logistics_delivery_zones
"""

from alembic import op
import sqlalchemy as sa


revision = "p27_logistics_pricing"
down_revision = "p26_logistics_delivery_zones"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    for constraint in inspector.get_unique_constraints("shipping_methods"):
        if constraint.get("column_names") == ["name"]:
            op.drop_constraint(
                constraint["name"], "shipping_methods", type_="unique"
            )

    op.create_unique_constraint(
        "uq_shipping_method_company_name",
        "shipping_methods",
        ["logistics_company_id", "name"],
    )
    op.create_unique_constraint(
        "uq_shipping_method_company_service_code",
        "shipping_methods",
        ["logistics_company_id", "service_code"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_shipping_method_company_service_code",
        "shipping_methods",
        type_="unique",
    )
    op.drop_constraint(
        "uq_shipping_method_company_name",
        "shipping_methods",
        type_="unique",
    )
    op.create_unique_constraint(
        "shipping_methods_name_key", "shipping_methods", ["name"]
    )
