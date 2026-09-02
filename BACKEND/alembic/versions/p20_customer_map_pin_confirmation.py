"""Phase 2 Task 2: exact customer map pin confirmation.

Revision ID: p20_customer_map_pin_confirmation
Revises: p19_customer_delivery_locations
"""

from alembic import op
import sqlalchemy as sa


revision = "p20_customer_map_pin_confirmation"
down_revision = "p19_customer_delivery_locations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "addresses",
        sa.Column("location_provider", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "addresses",
        sa.Column(
            "location_confirmed_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_addresses_location_confirmed_at",
        "addresses",
        ["location_confirmed_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_addresses_location_confirmed_at",
        table_name="addresses",
    )
    op.drop_column("addresses", "location_confirmed_at")
    op.drop_column("addresses", "location_provider")
