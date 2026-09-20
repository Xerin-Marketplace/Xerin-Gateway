"""Completion Phase 1 Task 1: trusted pickup seller settlement.

Revision ID: p33_trusted_seller_settlement
Revises: p32_operations_support_sla
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p33_trusted_seller_settlement"
down_revision = "p32_operations_support_sla"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("escrow_holds", sa.Column("seller_release_shipment_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("escrow_holds", sa.Column("seller_release_handover_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("escrow_holds", sa.Column("seller_release_proof_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column("escrow_holds", sa.Column("seller_release_trigger", sa.String(length=40), nullable=True))
    op.add_column("escrow_holds", sa.Column("seller_release_verified_at", sa.DateTime(timezone=True), nullable=True))
    op.create_foreign_key("fk_escrow_seller_release_shipment", "escrow_holds", "shipments", ["seller_release_shipment_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_escrow_seller_release_handover", "escrow_holds", "shipment_handovers", ["seller_release_handover_id"], ["id"], ondelete="SET NULL")
    op.create_foreign_key("fk_escrow_seller_release_proof", "escrow_holds", "shipment_pickup_proofs", ["seller_release_proof_id"], ["id"], ondelete="SET NULL")
    op.create_check_constraint(
        "ck_escrow_seller_release_evidence_complete",
        "escrow_holds",
        "(seller_release_shipment_id IS NULL AND seller_release_handover_id IS NULL AND seller_release_proof_id IS NULL) OR (seller_release_shipment_id IS NOT NULL AND seller_release_handover_id IS NOT NULL AND seller_release_proof_id IS NOT NULL)",
    )
    op.create_index("ix_escrow_holds_seller_release_shipment_id", "escrow_holds", ["seller_release_shipment_id"])
    op.create_index("ix_escrow_holds_seller_release_handover_id", "escrow_holds", ["seller_release_handover_id"])
    op.create_index("ix_escrow_holds_seller_release_proof_id", "escrow_holds", ["seller_release_proof_id"])
    op.create_index("ix_escrow_holds_seller_release_verified", "escrow_holds", ["seller_release_verified_at"])


def downgrade() -> None:
    op.drop_index("ix_escrow_holds_seller_release_verified", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_seller_release_proof_id", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_seller_release_handover_id", table_name="escrow_holds")
    op.drop_index("ix_escrow_holds_seller_release_shipment_id", table_name="escrow_holds")
    op.drop_constraint("fk_escrow_seller_release_proof", "escrow_holds", type_="foreignkey")
    op.drop_constraint("fk_escrow_seller_release_handover", "escrow_holds", type_="foreignkey")
    op.drop_constraint("fk_escrow_seller_release_shipment", "escrow_holds", type_="foreignkey")
    op.drop_constraint("ck_escrow_seller_release_evidence_complete", "escrow_holds", type_="check")
    op.drop_column("escrow_holds", "seller_release_verified_at")
    op.drop_column("escrow_holds", "seller_release_trigger")
    op.drop_column("escrow_holds", "seller_release_proof_id")
    op.drop_column("escrow_holds", "seller_release_handover_id")
    op.drop_column("escrow_holds", "seller_release_shipment_id")
