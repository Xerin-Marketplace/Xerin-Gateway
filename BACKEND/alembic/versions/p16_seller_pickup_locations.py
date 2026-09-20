"""Phase 1 Task 1: seller pickup locations.

Revision ID: p16_seller_pickup_locations
Revises: p15_advertisement_engagement
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p16_seller_pickup_locations"
down_revision = "p15_advertisement_engagement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "seller_pickup_locations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "seller_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("sellers.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(length=120), nullable=False, server_default="Main pickup"),
        sa.Column("formatted_address", sa.Text(), nullable=False),
        sa.Column("country", sa.String(length=100), nullable=False, server_default="Tanzania"),
        sa.Column("region", sa.String(length=100), nullable=False),
        sa.Column("city", sa.String(length=100), nullable=False),
        sa.Column("district", sa.String(length=100), nullable=True),
        sa.Column("ward", sa.String(length=100), nullable=True),
        sa.Column("street", sa.Text(), nullable=True),
        sa.Column("landmark", sa.String(length=255), nullable=True),
        sa.Column("postal_code", sa.String(length=50), nullable=True),
        sa.Column("place_id", sa.String(length=255), nullable=True),
        sa.Column("latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("pickup_contact_name", sa.String(length=180), nullable=False),
        sa.Column("pickup_phone", sa.String(length=30), nullable=False),
        sa.Column("pickup_instructions", sa.Text(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_seller_pickup_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_seller_pickup_longitude"),
    )
    op.create_index("ix_seller_pickup_locations_seller_id", "seller_pickup_locations", ["seller_id"])
    op.create_index("ix_seller_pickup_locations_place_id", "seller_pickup_locations", ["place_id"])
    op.create_index("ix_seller_pickup_locations_is_default", "seller_pickup_locations", ["is_default"])
    op.create_index("ix_seller_pickup_locations_is_verified", "seller_pickup_locations", ["is_verified"])
    op.create_index("ix_seller_pickup_locations_is_active", "seller_pickup_locations", ["is_active"])
    op.create_index(
        "ix_seller_pickup_locations_seller_active_default",
        "seller_pickup_locations",
        ["seller_id", "is_active", "is_default"],
    )
    op.create_index(
        "uq_seller_pickup_location_default",
        "seller_pickup_locations",
        ["seller_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
    )


def downgrade() -> None:
    op.drop_index("uq_seller_pickup_location_default", table_name="seller_pickup_locations")
    op.drop_index("ix_seller_pickup_locations_seller_active_default", table_name="seller_pickup_locations")
    op.drop_index("ix_seller_pickup_locations_is_active", table_name="seller_pickup_locations")
    op.drop_index("ix_seller_pickup_locations_is_verified", table_name="seller_pickup_locations")
    op.drop_index("ix_seller_pickup_locations_is_default", table_name="seller_pickup_locations")
    op.drop_index("ix_seller_pickup_locations_place_id", table_name="seller_pickup_locations")
    op.drop_index("ix_seller_pickup_locations_seller_id", table_name="seller_pickup_locations")
    op.drop_table("seller_pickup_locations")
