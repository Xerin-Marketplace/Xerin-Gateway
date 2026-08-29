"""Phase 2 Task 7: pickup proof and customer verification.

Revision ID: p23_pickup_proof_verification
Revises: p22_checkout_delivery_quote
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p23_pickup_proof_verification"
down_revision = "p22_checkout_delivery_quote"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "shipment_pickup_proofs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("handover_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("order_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("customer_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("seller_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("photo_url", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("pickup_latitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("pickup_longitude", sa.Numeric(10, 7), nullable=False),
        sa.Column("courier_reference", sa.String(length=180), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=32),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("review_deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("customer_reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customer_reviewed_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("problem_reason", sa.String(length=80), nullable=True),
        sa.Column("problem_notes", sa.Text(), nullable=True),
        sa.Column("uploaded_by_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending','approved','disputed','auto_approved')",
            name="ck_shipment_pickup_proof_status",
        ),
        sa.CheckConstraint(
            "pickup_latitude BETWEEN -90 AND 90",
            name="ck_shipment_pickup_proof_latitude",
        ),
        sa.CheckConstraint(
            "pickup_longitude BETWEEN -180 AND 180",
            name="ck_shipment_pickup_proof_longitude",
        ),
        sa.CheckConstraint(
            "file_size > 0",
            name="ck_shipment_pickup_proof_file_size_positive",
        ),
        sa.ForeignKeyConstraint(
            ["shipment_id"], ["shipments.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["handover_id"], ["shipment_handovers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["order_id"], ["orders.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["customer_id"], ["users.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["seller_id"], ["sellers.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["logistics_company_id"], ["logistics_companies.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["customer_reviewed_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["uploaded_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("shipment_id"),
        sa.UniqueConstraint("handover_id"),
    )

    for column in (
        "shipment_id",
        "handover_id",
        "order_id",
        "customer_id",
        "seller_id",
        "logistics_company_id",
        "status",
        "review_deadline",
        "uploaded_by_id",
    ):
        op.create_index(
            f"ix_shipment_pickup_proofs_{column}",
            "shipment_pickup_proofs",
            [column],
            unique=False,
        )

    op.create_index(
        "ix_shipment_pickup_proofs_customer_status_created",
        "shipment_pickup_proofs",
        ["customer_id", "status", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_shipment_pickup_proofs_customer_status_created",
        table_name="shipment_pickup_proofs",
    )
    for column in reversed(
        (
            "shipment_id",
            "handover_id",
            "order_id",
            "customer_id",
            "seller_id",
            "logistics_company_id",
            "status",
            "review_deadline",
            "uploaded_by_id",
        )
    ):
        op.drop_index(
            f"ix_shipment_pickup_proofs_{column}",
            table_name="shipment_pickup_proofs",
        )
    op.drop_table("shipment_pickup_proofs")
