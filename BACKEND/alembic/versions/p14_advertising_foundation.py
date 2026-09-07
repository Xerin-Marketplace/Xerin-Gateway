"""Phase 12 Task 1: advertisement foundation.

Revision ID: p14_advertising_foundation
Revises: p13_payment_callback_idempotency, p3_search_recommendations

This revision intentionally merges the two existing Alembic heads while adding
the advertisement foundation.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p14_advertising_foundation"
down_revision = ("p13_payment_callback_idempotency", "p3_search_recommendations")
branch_labels = None
depends_on = None


def upgrade() -> None:
    advertisement_status = postgresql.ENUM(
        "draft",
        "active",
        "paused",
        name="advertisementstatus",
        create_type=False,
    )
    advertisement_placement = postgresql.ENUM(
        "hero_side_top",
        "hero_side_bottom",
        "homepage_banner",
        "category_banner",
        "search_banner",
        name="advertisementplacement",
        create_type=False,
    )
    advertisement_billing_type = postgresql.ENUM(
        "fixed",
        "cpc",
        "cpm",
        name="advertisementbillingtype",
        create_type=False,
    )

    bind = op.get_bind()
    advertisement_status.create(bind, checkfirst=True)
    advertisement_placement.create(bind, checkfirst=True)
    advertisement_billing_type.create(bind, checkfirst=True)

    op.create_table(
        "advertisements",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("advertiser_name", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(length=1000), nullable=False),
        sa.Column("mobile_image_url", sa.String(length=1000), nullable=True),
        sa.Column("alt_text", sa.String(length=255), nullable=True),
        sa.Column("target_url", sa.String(length=1500), nullable=True),
        sa.Column(
            "cta_label",
            sa.String(length=80),
            nullable=True,
            server_default="Shop Now",
        ),
        sa.Column(
            "placement",
            advertisement_placement,
            nullable=False,
        ),
        sa.Column(
            "status",
            advertisement_status,
            nullable=False,
            server_default="draft",
        ),
        sa.Column(
            "starts_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "ends_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "billing_type",
            advertisement_billing_type,
            nullable=False,
            server_default="fixed",
        ),
        sa.Column("price", sa.Numeric(18, 2), nullable=True),
        sa.Column(
            "currency",
            sa.String(length=3),
            nullable=False,
            server_default="TZS",
        ),
        sa.Column(
            "impression_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "click_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "metadata_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_by_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.CheckConstraint(
            "ends_at > starts_at",
            name="ck_advertisement_valid_schedule",
        ),
        sa.CheckConstraint(
            "priority >= 0",
            name="ck_advertisement_priority_nonnegative",
        ),
        sa.CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_advertisement_price_nonnegative",
        ),
        sa.CheckConstraint(
            "impression_count >= 0 AND click_count >= 0",
            name="ck_advertisement_counters_nonnegative",
        ),
    )

    op.create_index(
        "ix_advertisements_advertiser_name",
        "advertisements",
        ["advertiser_name"],
    )
    op.create_index(
        "ix_advertisements_placement",
        "advertisements",
        ["placement"],
    )
    op.create_index(
        "ix_advertisements_status",
        "advertisements",
        ["status"],
    )
    op.create_index(
        "ix_advertisements_starts_at",
        "advertisements",
        ["starts_at"],
    )
    op.create_index(
        "ix_advertisements_ends_at",
        "advertisements",
        ["ends_at"],
    )
    op.create_index(
        "ix_advertisements_created_by_id",
        "advertisements",
        ["created_by_id"],
    )
    op.create_index(
        "ix_advertisements_live_slot",
        "advertisements",
        ["placement", "status", "starts_at", "ends_at", "priority"],
    )


def downgrade() -> None:
    op.drop_index("ix_advertisements_live_slot", table_name="advertisements")
    op.drop_index("ix_advertisements_created_by_id", table_name="advertisements")
    op.drop_index("ix_advertisements_ends_at", table_name="advertisements")
    op.drop_index("ix_advertisements_starts_at", table_name="advertisements")
    op.drop_index("ix_advertisements_status", table_name="advertisements")
    op.drop_index("ix_advertisements_placement", table_name="advertisements")
    op.drop_index("ix_advertisements_advertiser_name", table_name="advertisements")
    op.drop_table("advertisements")

    bind = op.get_bind()
    postgresql.ENUM(name="advertisementbillingtype").drop(bind, checkfirst=True)
    postgresql.ENUM(name="advertisementplacement").drop(bind, checkfirst=True)
    postgresql.ENUM(name="advertisementstatus").drop(bind, checkfirst=True)
