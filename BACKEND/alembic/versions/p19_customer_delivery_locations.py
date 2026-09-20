"""Phase 2 Task 1: customer delivery location enhancement.

Revision ID: p19_customer_delivery_locations
Revises: p18_seller_handover_confirmation
"""

from alembic import op
import sqlalchemy as sa


revision = "p19_customer_delivery_locations"
down_revision = "p18_seller_handover_confirmation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "addresses",
        sa.Column("formatted_address", sa.Text(), nullable=True),
    )
    op.add_column(
        "addresses",
        sa.Column("place_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "addresses",
        sa.Column("delivery_instructions", sa.Text(), nullable=True),
    )
    op.add_column(
        "addresses",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    op.add_column(
        "addresses",
        sa.Column(
            "is_verified",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_index(
        "ix_addresses_place_id",
        "addresses",
        ["place_id"],
        unique=False,
    )
    op.create_index(
        "ix_addresses_is_default",
        "addresses",
        ["is_default"],
        unique=False,
    )
    op.create_index(
        "ix_addresses_is_active",
        "addresses",
        ["is_active"],
        unique=False,
    )
    op.create_index(
        "ix_addresses_is_verified",
        "addresses",
        ["is_verified"],
        unique=False,
    )

    # Helpful composite index for the customer address list/default lookup.
    op.create_index(
        "ix_addresses_user_active_default",
        "addresses",
        ["user_id", "is_active", "is_default"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_addresses_user_active_default", table_name="addresses")
    op.drop_index("ix_addresses_is_verified", table_name="addresses")
    op.drop_index("ix_addresses_is_active", table_name="addresses")
    op.drop_index("ix_addresses_is_default", table_name="addresses")
    op.drop_index("ix_addresses_place_id", table_name="addresses")

    op.drop_column("addresses", "is_verified")
    op.drop_column("addresses", "is_active")
    op.drop_column("addresses", "delivery_instructions")
    op.drop_column("addresses", "place_id")
    op.drop_column("addresses", "formatted_address")
