"""F6 delivery-based seller escrow settlement

Revision ID: f6_delivery_based_escrow
Revises: b8_broker_security_hardening
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision="f6_delivery_based_escrow"
down_revision="b8_broker_security_hardening"
branch_labels=None
depends_on=None

def upgrade():
    op.add_column("marketplace_settings",sa.Column("seller_release_grace_hours",sa.Integer(),nullable=False,server_default="144"))
    op.create_check_constraint("ck_marketplace_settings_seller_release_grace_hours","marketplace_settings","seller_release_grace_hours BETWEEN 1 AND 720")
    op.add_column("escrow_holds",sa.Column("seller_release_delivery_proof_id",postgresql.UUID(as_uuid=True),nullable=True))
    op.add_column("escrow_holds",sa.Column("delivery_verified_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("escrow_holds",sa.Column("customer_accepted_at",sa.DateTime(timezone=True),nullable=True))
    op.add_column("escrow_holds",sa.Column("customer_accepted_by_id",postgresql.UUID(as_uuid=True),nullable=True))
    op.create_foreign_key("fk_escrow_holds_delivery_proof","escrow_holds","shipment_delivery_proofs",["seller_release_delivery_proof_id"],["id"],ondelete="SET NULL")
    op.create_foreign_key("fk_escrow_holds_customer_accepted_by","escrow_holds","users",["customer_accepted_by_id"],["id"],ondelete="SET NULL")
    op.create_index("ix_escrow_holds_seller_release_delivery_proof_id","escrow_holds",["seller_release_delivery_proof_id"]); op.create_index("ix_escrow_holds_delivery_verified_at","escrow_holds",["delivery_verified_at"])
    op.drop_constraint("ck_escrow_seller_release_evidence_complete","escrow_holds",type_="check")
    op.create_check_constraint("ck_escrow_seller_release_evidence_complete","escrow_holds","(seller_release_shipment_id IS NULL AND seller_release_handover_id IS NULL AND seller_release_proof_id IS NULL AND seller_release_delivery_proof_id IS NULL) OR (seller_release_shipment_id IS NOT NULL AND seller_release_handover_id IS NOT NULL AND seller_release_proof_id IS NOT NULL AND seller_release_delivery_proof_id IS NOT NULL)")
    op.create_table("order_item_disputes",sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),sa.Column("case_reference",sa.String(40),nullable=False),sa.Column("order_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("orders.id",ondelete="CASCADE"),nullable=False),sa.Column("order_item_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("order_items.id",ondelete="CASCADE"),nullable=False),sa.Column("customer_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="RESTRICT"),nullable=False),sa.Column("seller_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("sellers.id",ondelete="RESTRICT"),nullable=False),sa.Column("shipment_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("shipments.id",ondelete="SET NULL"),nullable=True),sa.Column("escrow_hold_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("escrow_holds.id",ondelete="SET NULL"),nullable=True),sa.Column("scope",sa.String(20),nullable=False,server_default="item"),sa.Column("reason",sa.String(60),nullable=False),sa.Column("notes",sa.Text(),nullable=True),sa.Column("evidence_urls",postgresql.JSONB(),nullable=False,server_default=sa.text("'[]'::jsonb")),sa.Column("quantity",sa.Integer(),nullable=False,server_default="1"),sa.Column("amount_held",sa.Numeric(18,2),nullable=False,server_default="0"),sa.Column("escrow_impact",sa.Boolean(),nullable=False,server_default=sa.text("false")),sa.Column("responsibility_status",sa.String(30),nullable=False,server_default="undetermined"),sa.Column("resolution_status",sa.String(40),nullable=False,server_default="submitted"),sa.Column("resolution_note",sa.Text(),nullable=True),sa.Column("resolved_by_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("users.id",ondelete="SET NULL"),nullable=True),sa.Column("resolved_at",sa.DateTime(timezone=True),nullable=True),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False,server_default=sa.func.now()),sa.Column("updated_at",sa.DateTime(timezone=True),nullable=True),sa.CheckConstraint("scope IN ('item','order')",name="ck_order_item_disputes_scope"),sa.CheckConstraint("quantity > 0 AND amount_held >= 0",name="ck_order_item_disputes_values"),sa.CheckConstraint("responsibility_status IN ('undetermined','seller','logistics','customer','platform','shared')",name="ck_order_item_disputes_responsibility"),sa.CheckConstraint("resolution_status IN ('submitted','under_review','evidence_required','resolved','rejected','recorded_no_escrow_hold')",name="ck_order_item_disputes_resolution"))
    for col in ["case_reference","order_id","order_item_id","customer_id","seller_id","shipment_id","escrow_hold_id","reason","escrow_impact","responsibility_status","resolution_status","created_at"]: op.create_index(f"ix_order_item_disputes_{col}","order_item_disputes",[col])

def downgrade():
    op.drop_table("order_item_disputes")
    op.drop_constraint("ck_escrow_seller_release_evidence_complete","escrow_holds",type_="check")
    op.create_check_constraint("ck_escrow_seller_release_evidence_complete","escrow_holds","(seller_release_shipment_id IS NULL AND seller_release_handover_id IS NULL AND seller_release_proof_id IS NULL) OR (seller_release_shipment_id IS NOT NULL AND seller_release_handover_id IS NOT NULL AND seller_release_proof_id IS NOT NULL)")
    for name in ["ix_escrow_holds_delivery_verified_at","ix_escrow_holds_seller_release_delivery_proof_id"]: op.drop_index(name,table_name="escrow_holds")
    op.drop_constraint("fk_escrow_holds_customer_accepted_by","escrow_holds",type_="foreignkey"); op.drop_constraint("fk_escrow_holds_delivery_proof","escrow_holds",type_="foreignkey")
    for col in ["customer_accepted_by_id","customer_accepted_at","delivery_verified_at","seller_release_delivery_proof_id"]: op.drop_column("escrow_holds",col)
    op.drop_constraint("ck_marketplace_settings_seller_release_grace_hours","marketplace_settings",type_="check"); op.drop_column("marketplace_settings","seller_release_grace_hours")
