"""F6 delivery-based escrow settlement and customer protection claims.

Revision ID: f6_delivery_based_escrow
Revises: b8_broker_security_hardening
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6_delivery_based_escrow"
down_revision = "b8_broker_security_hardening"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "marketplace_settings",
        sa.Column("seller_release_grace_hours", sa.Integer(), nullable=True, server_default="144"),
    )
    op.add_column(
        "marketplace_settings",
        sa.Column("allow_customer_early_acceptance", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_check_constraint(
        "ck_marketplace_settings_seller_release_grace_hours",
        "marketplace_settings",
        "seller_release_grace_hours IS NULL OR seller_release_grace_hours BETWEEN 1 AND 720",
    )
    op.execute("UPDATE marketplace_settings SET seller_release_grace_hours = COALESCE(seller_release_grace_hours, 144)")

    op.create_table(
        "settlement_protection_claims",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("order_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("order_items.id", ondelete="SET NULL"), nullable=True),
        sa.Column("scope", sa.String(20), nullable=False, server_default="item"),
        sa.Column("reason", sa.String(60), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("when_noticed", sa.String(40), nullable=True),
        sa.Column("package_damaged", sa.Boolean(), nullable=True),
        sa.Column("product_used", sa.Boolean(), nullable=True),
        sa.Column("evidence_urls", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("likely_responsibility", sa.String(30), nullable=False, server_default="undetermined"),
        sa.Column("status", sa.String(40), nullable=False, server_default="submitted"),
        sa.Column("hold_applied", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("admin_resolution_note", sa.Text(), nullable=True),
        sa.Column("resolved_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("scope IN ('item','order')", name="ck_settlement_claim_scope"),
        sa.CheckConstraint("likely_responsibility IN ('undetermined','seller','logistics','customer','platform','shared')", name="ck_settlement_claim_responsibility"),
        sa.CheckConstraint("status IN ('submitted','under_review','evidence_required','recorded_no_hold','post_settlement','seller_liable','logistics_liable','customer_liable','rejected','resolved')", name="ck_settlement_claim_status"),
    )
    op.create_index("ix_settlement_protection_claims_order_id", "settlement_protection_claims", ["order_id"])
    op.create_index("ix_settlement_protection_claims_customer_id", "settlement_protection_claims", ["customer_id"])
    op.create_index("ix_settlement_protection_claims_order_item_id", "settlement_protection_claims", ["order_item_id"])
    op.create_index("ix_settlement_protection_claims_scope", "settlement_protection_claims", ["scope"])
    op.create_index("ix_settlement_protection_claims_reason", "settlement_protection_claims", ["reason"])
    op.create_index("ix_settlement_protection_claims_likely_responsibility", "settlement_protection_claims", ["likely_responsibility"])
    op.create_index("ix_settlement_protection_claims_status", "settlement_protection_claims", ["status"])
    op.create_index("ix_settlement_protection_claims_created_at", "settlement_protection_claims", ["created_at"])
    op.create_index("ix_settlement_claim_order_status", "settlement_protection_claims", ["order_id", "status"])

    # Existing unpaid/held rows must no longer auto-release from a payment-time deadline.
    # Verified delivery will arm a fresh post-delivery deadline under the new rule.
    op.execute("""
        UPDATE escrow_holds
           SET release_after = NULL
         WHERE status IN ('held','release_pending','partially_refunded')
           AND seller_release_verified_at IS NULL
    """)


def downgrade():
    op.drop_table("settlement_protection_claims")
    op.drop_constraint("ck_marketplace_settings_seller_release_grace_hours", "marketplace_settings", type_="check")
    op.drop_column("marketplace_settings", "allow_customer_early_acceptance")
    op.drop_column("marketplace_settings", "seller_release_grace_hours")
