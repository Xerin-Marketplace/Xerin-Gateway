"""Phase 3 Task 3: logistics-company delivery zones.

Revision ID: p26_logistics_delivery_zones
Revises: p25_logistics_company_users
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p26_logistics_delivery_zones"
down_revision = "p25_logistics_company_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for constraint in inspector.get_unique_constraints("shipping_zones"):
        if constraint.get("column_names") == ["name"]:
            op.drop_constraint(
                constraint["name"], "shipping_zones", type_="unique"
            )

    op.add_column(
        "shipping_zones",
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shipping_zones_logistics_company",
        "shipping_zones",
        "logistics_companies",
        ["logistics_company_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_shipping_zones_logistics_company_id",
        "shipping_zones",
        ["logistics_company_id"],
    )
    op.add_column(
        "shipping_zones",
        sa.Column(
            "districts",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "shipping_zones",
        sa.Column(
            "wards",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "shipping_zones",
        sa.Column(
            "postal_codes",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.add_column(
        "shipping_zones",
        sa.Column("coverage_geojson", postgresql.JSONB(), nullable=True),
    )
    op.add_column(
        "shipping_zones",
        sa.Column(
            "covers_entire_country",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.execute(
        """
        UPDATE shipping_zones
        SET covers_entire_country = TRUE
        WHERE regions = '[]'::jsonb AND cities = '[]'::jsonb
        """
    )
    op.create_unique_constraint(
        "uq_shipping_zone_company_name",
        "shipping_zones",
        ["logistics_company_id", "name"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_shipping_zone_company_name", "shipping_zones", type_="unique"
    )
    op.drop_column("shipping_zones", "covers_entire_country")
    op.drop_column("shipping_zones", "coverage_geojson")
    op.drop_column("shipping_zones", "postal_codes")
    op.drop_column("shipping_zones", "wards")
    op.drop_column("shipping_zones", "districts")
    op.drop_index(
        "ix_shipping_zones_logistics_company_id", table_name="shipping_zones"
    )
    op.drop_constraint(
        "fk_shipping_zones_logistics_company",
        "shipping_zones",
        type_="foreignkey",
    )
    op.drop_column("shipping_zones", "logistics_company_id")
    op.create_unique_constraint(
        "shipping_zones_name_key", "shipping_zones", ["name"]
    )
