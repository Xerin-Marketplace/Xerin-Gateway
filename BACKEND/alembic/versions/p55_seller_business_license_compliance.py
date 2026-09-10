"""Seller business licence compliance metadata and document versioning.

Revision ID: p55_seller_license_compliance
Revises: p54_product_review_aggregates
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p55_seller_license_compliance"
down_revision = "p54_product_review_aggregates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("seller_kyc_documents", sa.Column("document_number", sa.String(length=180), nullable=True))
    op.add_column("seller_kyc_documents", sa.Column("issued_date", sa.Date(), nullable=True))
    op.add_column("seller_kyc_documents", sa.Column("expiry_date", sa.Date(), nullable=True))
    op.add_column("seller_kyc_documents", sa.Column("version", sa.Integer(), server_default="1", nullable=False))
    op.add_column("seller_kyc_documents", sa.Column("is_current", sa.Boolean(), server_default=sa.true(), nullable=False))
    op.add_column("seller_kyc_documents", sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("seller_kyc_documents", sa.Column("approved_by_user_id", postgresql.UUID(as_uuid=True), nullable=True))
    op.create_foreign_key(
        "fk_seller_kyc_approved_by_user",
        "seller_kyc_documents",
        "users",
        ["approved_by_user_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_seller_kyc_documents_expiry_date", "seller_kyc_documents", ["expiry_date"], unique=False)
    op.create_index("ix_seller_kyc_documents_is_current", "seller_kyc_documents", ["is_current"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_seller_kyc_documents_is_current", table_name="seller_kyc_documents")
    op.drop_index("ix_seller_kyc_documents_expiry_date", table_name="seller_kyc_documents")
    op.drop_constraint("fk_seller_kyc_approved_by_user", "seller_kyc_documents", type_="foreignkey")
    op.drop_column("seller_kyc_documents", "approved_by_user_id")
    op.drop_column("seller_kyc_documents", "approved_at")
    op.drop_column("seller_kyc_documents", "is_current")
    op.drop_column("seller_kyc_documents", "version")
    op.drop_column("seller_kyc_documents", "expiry_date")
    op.drop_column("seller_kyc_documents", "issued_date")
    op.drop_column("seller_kyc_documents", "document_number")
