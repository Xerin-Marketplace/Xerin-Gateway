"""Logistics company verification documents and audit versions.

Revision ID: p50_logistics_company_documents
Revises: p49_product_approval_audit
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p50_logistics_company_documents"
down_revision = "p49_product_approval_audit"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "logistics_company_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_type", sa.String(length=80), nullable=False),
        sa.Column("document_name", sa.String(length=180), nullable=False),
        sa.Column("document_url", sa.Text(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("mime_type", sa.String(length=120), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.String(length=40), server_default="pending_review", nullable=False),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("uploaded_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("version >= 1", name="ck_logistics_company_document_version_positive"),
        sa.ForeignKeyConstraint(["logistics_company_id"], ["logistics_companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("logistics_company_id", "document_type", "version", name="uq_logistics_company_document_version"),
    )
    op.create_index("ix_logistics_company_documents_company", "logistics_company_documents", ["logistics_company_id"], unique=False)
    op.create_index("ix_logistics_company_documents_type", "logistics_company_documents", ["document_type"], unique=False)
    op.create_index("ix_logistics_company_documents_status", "logistics_company_documents", ["status"], unique=False)
    op.create_index("ix_logistics_company_documents_current", "logistics_company_documents", ["is_current"], unique=False)
    op.create_index("ix_logistics_company_documents_deleted_at", "logistics_company_documents", ["deleted_at"], unique=False)
    op.create_index(
        "uq_logistics_company_document_current_type",
        "logistics_company_documents",
        ["logistics_company_id", "document_type"],
        unique=True,
        postgresql_where=sa.text("is_current = true AND deleted_at IS NULL"),
    )


def downgrade():
    op.drop_index("uq_logistics_company_document_current_type", table_name="logistics_company_documents")
    op.drop_index("ix_logistics_company_documents_deleted_at", table_name="logistics_company_documents")
    op.drop_index("ix_logistics_company_documents_current", table_name="logistics_company_documents")
    op.drop_index("ix_logistics_company_documents_status", table_name="logistics_company_documents")
    op.drop_index("ix_logistics_company_documents_type", table_name="logistics_company_documents")
    op.drop_index("ix_logistics_company_documents_company", table_name="logistics_company_documents")
    op.drop_table("logistics_company_documents")
