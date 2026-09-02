"""Broker B3 seller offers and broker opportunity acceptance.

Revision ID: b3_seller_broker_offers
Revises: b2_broker_own_products
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b3_seller_broker_offers"
down_revision = "b2_broker_own_products"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_offers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commission_type", sa.String(20), nullable=False, server_default="fixed"),
        sa.Column("commission_value", sa.Numeric(18,2), nullable=False),
        sa.Column("max_attributed_sales", sa.Integer(), nullable=True),
        sa.Column("attributed_sales_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["seller_id"], ["sellers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("product_id", name="uq_broker_offer_product"),
        sa.CheckConstraint("commission_type IN ('fixed','percentage')", name="ck_broker_offer_commission_type"),
        sa.CheckConstraint("commission_value > 0", name="ck_broker_offer_commission_positive"),
        sa.CheckConstraint("max_attributed_sales IS NULL OR max_attributed_sales > 0", name="ck_broker_offer_max_sales_positive"),
        sa.CheckConstraint("attributed_sales_count >= 0", name="ck_broker_offer_attributed_nonnegative"),
    )
    op.create_index("ix_broker_offers_product_id", "broker_offers", ["product_id"])
    op.create_index("ix_broker_offers_seller_id", "broker_offers", ["seller_id"])
    op.create_index("ix_broker_offers_starts_at", "broker_offers", ["starts_at"])
    op.create_index("ix_broker_offers_ends_at", "broker_offers", ["ends_at"])
    op.create_index("ix_broker_offers_is_active", "broker_offers", ["is_active"])

    op.create_table(
        "broker_offer_acceptances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("stopped_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["offer_id"], ["broker_offers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["broker_id"], ["brokers.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("offer_id", "broker_id", name="uq_broker_offer_acceptance"),
    )
    op.create_index("ix_broker_offer_acceptances_offer_id", "broker_offer_acceptances", ["offer_id"])
    op.create_index("ix_broker_offer_acceptances_broker_id", "broker_offer_acceptances", ["broker_id"])
    op.create_index("ix_broker_offer_acceptances_is_active", "broker_offer_acceptances", ["is_active"])


def downgrade():
    op.drop_table("broker_offer_acceptances")
    op.drop_table("broker_offers")
