"""Broker B4 referral links and attribution snapshots.

Revision ID: b4_broker_referral_attribution
Revises: b3_seller_broker_offers
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b4_broker_referral_attribution"
down_revision = "b3_seller_broker_offers"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "broker_referral_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("acceptance_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("referral_code", sa.String(length=40), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["acceptance_id"],["broker_offer_acceptances.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["offer_id"],["broker_offers.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["broker_id"],["brokers.id"],ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["product_id"],["products.id"],ondelete="CASCADE"),
        sa.UniqueConstraint("acceptance_id", name="uq_broker_referral_link_acceptance"),
        sa.UniqueConstraint("referral_code", name="uq_broker_referral_code"),
    )
    for c in ("acceptance_id","offer_id","broker_id","product_id","referral_code","is_active"):
        op.create_index(f"ix_broker_referral_links_{c}","broker_referral_links",[c])

    op.create_table(
        "broker_attributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("referral_link_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("offer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("broker_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("commission_type", sa.String(length=20), nullable=False),
        sa.Column("commission_value", sa.Numeric(18,2), nullable=False),
        sa.Column("commission_amount_per_unit", sa.Numeric(18,2), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="locked"),
        sa.Column("locked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("ordered_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referral_link_id"],["broker_referral_links.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["offer_id"],["broker_offers.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["broker_id"],["brokers.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["product_id"],["products.id"],ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"],["users.id"],ondelete="CASCADE"),
        sa.CheckConstraint("commission_type IN ('fixed','percentage')", name="ck_broker_attribution_commission_type"),
        sa.CheckConstraint("commission_amount_per_unit >= 0", name="ck_broker_attribution_commission_nonnegative"),
    )
    for c in ("referral_link_id","offer_id","broker_id","product_id","user_id","status"):
        op.create_index(f"ix_broker_attributions_{c}","broker_attributions",[c])

    op.add_column("cart_items", sa.Column("broker_attribution_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key("fk_cart_items_broker_attribution","cart_items","broker_attributions",["broker_attribution_id"],["id"],ondelete="SET NULL")
    op.create_index("ix_cart_items_broker_attribution_id","cart_items",["broker_attribution_id"])

    for name, typ in [
        ("broker_attribution_id", postgresql.UUID(as_uuid=True)),
        ("broker_id", postgresql.UUID(as_uuid=True)),
        ("broker_referral_link_id", postgresql.UUID(as_uuid=True)),
        ("broker_offer_id", postgresql.UUID(as_uuid=True)),
        ("broker_commission_type", sa.String(length=20)),
        ("broker_commission_value", sa.Numeric(18,2)),
        ("broker_commission_amount", sa.Numeric(18,2)),
    ]:
        op.add_column("order_items", sa.Column(name, typ, nullable=True))
    op.create_foreign_key("fk_order_items_broker_attribution","order_items","broker_attributions",["broker_attribution_id"],["id"],ondelete="SET NULL")
    op.create_foreign_key("fk_order_items_broker","order_items","brokers",["broker_id"],["id"],ondelete="SET NULL")
    op.create_foreign_key("fk_order_items_broker_referral_link","order_items","broker_referral_links",["broker_referral_link_id"],["id"],ondelete="SET NULL")
    op.create_foreign_key("fk_order_items_broker_offer","order_items","broker_offers",["broker_offer_id"],["id"],ondelete="SET NULL")
    for c in ("broker_attribution_id","broker_id","broker_referral_link_id","broker_offer_id"):
        op.create_index(f"ix_order_items_{c}","order_items",[c])


def downgrade():
    for c in ("broker_offer_id","broker_referral_link_id","broker_id","broker_attribution_id"):
        op.drop_index(f"ix_order_items_{c}", table_name="order_items")
    for fk in ("fk_order_items_broker_offer","fk_order_items_broker_referral_link","fk_order_items_broker","fk_order_items_broker_attribution"):
        op.drop_constraint(fk,"order_items",type_="foreignkey")
    for c in ("broker_commission_amount","broker_commission_value","broker_commission_type","broker_offer_id","broker_referral_link_id","broker_id","broker_attribution_id"):
        op.drop_column("order_items",c)
    op.drop_index("ix_cart_items_broker_attribution_id", table_name="cart_items")
    op.drop_constraint("fk_cart_items_broker_attribution","cart_items",type_="foreignkey")
    op.drop_column("cart_items","broker_attribution_id")
    op.drop_table("broker_attributions")
    op.drop_table("broker_referral_links")
