"""Phase 12 Task 7: advertisement engagement events.

Revision ID: p15_advertisement_engagement
Revises: p14_advertising_foundation
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p15_advertisement_engagement"
down_revision = "p14_advertising_foundation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "advertisement_engagement_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "advertisement_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("advertisements.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("event_type", sa.String(length=20), nullable=False),
        sa.Column(
            "placement",
            postgresql.ENUM(
                "hero_side_top",
                "hero_side_bottom",
                "homepage_banner",
                "category_banner",
                "search_banner",
                name="advertisementplacement",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("session_hash", sa.String(length=64), nullable=False),
        sa.Column("event_key", sa.String(length=160), nullable=False),
        sa.Column("page_path", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.CheckConstraint(
            "event_type IN ('impression', 'click')",
            name="ck_ad_engagement_event_type",
        ),
    )

    op.create_index(
        "ix_advertisement_engagement_events_advertisement_id",
        "advertisement_engagement_events",
        ["advertisement_id"],
    )
    op.create_index(
        "ix_advertisement_engagement_events_event_type",
        "advertisement_engagement_events",
        ["event_type"],
    )
    op.create_index(
        "ix_advertisement_engagement_events_placement",
        "advertisement_engagement_events",
        ["placement"],
    )
    op.create_index(
        "ix_advertisement_engagement_events_session_hash",
        "advertisement_engagement_events",
        ["session_hash"],
    )
    op.create_index(
        "ix_advertisement_engagement_events_event_key",
        "advertisement_engagement_events",
        ["event_key"],
        unique=True,
    )
    op.create_index(
        "ix_advertisement_engagement_events_created_at",
        "advertisement_engagement_events",
        ["created_at"],
    )
    op.create_index(
        "ix_ad_engagement_ad_type_created",
        "advertisement_engagement_events",
        ["advertisement_id", "event_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_ad_engagement_ad_type_created",
        table_name="advertisement_engagement_events",
    )
    op.drop_index(
        "ix_advertisement_engagement_events_created_at",
        table_name="advertisement_engagement_events",
    )
    op.drop_index(
        "ix_advertisement_engagement_events_event_key",
        table_name="advertisement_engagement_events",
    )
    op.drop_index(
        "ix_advertisement_engagement_events_session_hash",
        table_name="advertisement_engagement_events",
    )
    op.drop_index(
        "ix_advertisement_engagement_events_placement",
        table_name="advertisement_engagement_events",
    )
    op.drop_index(
        "ix_advertisement_engagement_events_event_type",
        table_name="advertisement_engagement_events",
    )
    op.drop_index(
        "ix_advertisement_engagement_events_advertisement_id",
        table_name="advertisement_engagement_events",
    )
    op.drop_table("advertisement_engagement_events")
