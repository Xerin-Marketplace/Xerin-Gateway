"""Completion Phase 2 Task 1: recipient OTP proof of delivery.

Revision ID: p36_delivery_verification
Revises: p35_financial_reconciliation
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p36_delivery_verification"
down_revision = "p35_financial_reconciliation"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)


def upgrade():
    op.create_table(
        "shipment_delivery_proofs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("shipment_id", UUID, sa.ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("order_id", UUID, sa.ForeignKey("orders.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logistics_company_id", UUID, sa.ForeignKey("logistics_companies.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending_otp"),
        sa.Column("recipient_name", sa.String(150), nullable=False),
        sa.Column("recipient_phone_last4", sa.String(4)),
        sa.Column("photo_url", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(255)),
        sa.Column("mime_type", sa.String(120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("delivery_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("delivery_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("destination_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("destination_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("distance_from_destination_meters", sa.Numeric(12, 2), nullable=False),
        sa.Column("otp_hash", sa.String(64), nullable=False),
        sa.Column("otp_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("otp_attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("notes", sa.Text()),
        sa.Column("initiated_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("verified_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("verified_at", sa.DateTime(timezone=True)),
        sa.Column("disputed_at", sa.DateTime(timezone=True)),
        sa.Column("dispute_reason", sa.String(100)),
        sa.Column("dispute_notes", sa.Text()),
        sa.Column("logistics_release_transaction_id", UUID, sa.ForeignKey("logistics_wallet_transactions.id", ondelete="SET NULL")),
        sa.Column("settlement_status", sa.String(40), nullable=False, server_default="held"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('pending_otp','verified','disputed','expired')", name="ck_shipment_delivery_proof_status"),
        sa.CheckConstraint("settlement_status IN ('held','released','awaiting_cod_remittance','blocked')", name="ck_shipment_delivery_proof_settlement"),
        sa.CheckConstraint("delivery_latitude BETWEEN -90 AND 90 AND destination_latitude BETWEEN -90 AND 90", name="ck_shipment_delivery_proof_latitudes"),
        sa.CheckConstraint("delivery_longitude BETWEEN -180 AND 180 AND destination_longitude BETWEEN -180 AND 180", name="ck_shipment_delivery_proof_longitudes"),
        sa.CheckConstraint("distance_from_destination_meters >= 0 AND file_size > 0 AND otp_attempts >= 0", name="ck_shipment_delivery_proof_values"),
    )
    for name, cols, unique in (
        ("ix_delivery_proof_shipment", ["shipment_id"], True),
        ("ix_delivery_proof_order", ["order_id"], False),
        ("ix_delivery_proof_customer", ["customer_id"], False),
        ("ix_delivery_proof_company", ["logistics_company_id"], False),
        ("ix_delivery_proof_status", ["status"], False),
        ("ix_delivery_proof_otp_expires", ["otp_expires_at"], False),
        ("ix_delivery_proof_release_tx", ["logistics_release_transaction_id"], False),
    ):
        op.create_index(name, "shipment_delivery_proofs", cols, unique=unique)
    op.create_table(
        "shipment_delivery_proof_events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("proof_id", UUID, sa.ForeignKey("shipment_delivery_proofs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(40), nullable=False),
        sa.Column("note", sa.Text()),
        sa.Column("created_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_delivery_proof_events_proof", "shipment_delivery_proof_events", ["proof_id"])


def downgrade():
    op.drop_table("shipment_delivery_proof_events")
    op.drop_table("shipment_delivery_proofs")
