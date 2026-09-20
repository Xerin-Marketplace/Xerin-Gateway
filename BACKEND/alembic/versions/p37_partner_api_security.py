"""Completion Phase 2 Task 2: partner API authentication and request security.

Revision ID: p37_partner_api_security
Revises: p36_delivery_verification
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p37_partner_api_security"
down_revision = "p36_delivery_verification"
branch_labels = None
depends_on = None
UUID = postgresql.UUID(as_uuid=True)
JSONB = postgresql.JSONB(astext_type=sa.Text())


def upgrade():
    op.create_table(
        "partner_credentials",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("logistics_company_id", UUID, sa.ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("key_id", sa.String(80), nullable=False, unique=True),
        sa.Column("signing_key_ciphertext", sa.Text(), nullable=False),
        sa.Column("secret_fingerprint", sa.String(16), nullable=False),
        sa.Column("scopes", JSONB, nullable=False, server_default="[]"),
        sa.Column("allowed_cidrs", JSONB, nullable=False, server_default="[]"),
        sa.Column("rate_limit_per_minute", sa.Integer(), nullable=False, server_default="120"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_at", sa.DateTime(timezone=True)),
        sa.Column("last_used_ip", sa.String(64)),
        sa.Column("rotated_from_id", UUID, sa.ForeignKey("partner_credentials.id", ondelete="SET NULL")),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_by_id", UUID, sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("status IN ('active','rotated','revoked','expired')", name="ck_partner_credential_status"),
        sa.CheckConstraint("rate_limit_per_minute > 0", name="ck_partner_credential_rate_limit"),
    )
    op.create_index("ix_partner_credentials_company", "partner_credentials", ["logistics_company_id"])
    op.create_index("ix_partner_credentials_key", "partner_credentials", ["key_id"], unique=True)
    op.create_index("ix_partner_credentials_status", "partner_credentials", ["status"])
    op.create_index("ix_partner_credentials_expires", "partner_credentials", ["expires_at"])

    op.create_table(
        "partner_request_nonces",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("credential_id", UUID, sa.ForeignKey("partner_credentials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("nonce", sa.String(128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("credential_id", "nonce", name="uq_partner_credential_nonce"),
    )
    op.create_index("ix_partner_nonces_credential", "partner_request_nonces", ["credential_id"])
    op.create_index("ix_partner_nonces_expires", "partner_request_nonces", ["expires_at"])

    op.create_table(
        "partner_request_logs",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("credential_id", UUID, sa.ForeignKey("partner_credentials.id", ondelete="SET NULL")),
        sa.Column("logistics_company_id", UUID, sa.ForeignKey("logistics_companies.id", ondelete="SET NULL")),
        sa.Column("request_id", sa.String(80), nullable=False, unique=True),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("source_ip", sa.String(64)),
        sa.Column("nonce", sa.String(128)),
        sa.Column("idempotency_key", sa.String(180)),
        sa.Column("body_sha256", sa.String(64)),
        sa.Column("auth_result", sa.String(40), nullable=False),
        sa.Column("response_status", sa.Integer()),
        sa.Column("error_code", sa.String(80)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_partner_logs_credential", "partner_request_logs", ["credential_id"])
    op.create_index("ix_partner_logs_company", "partner_request_logs", ["logistics_company_id"])
    op.create_index("ix_partner_logs_request", "partner_request_logs", ["request_id"], unique=True)
    op.create_index("ix_partner_logs_result", "partner_request_logs", ["auth_result"])
    op.create_index("ix_partner_logs_created", "partner_request_logs", ["created_at"])

    op.create_table(
        "partner_idempotency_records",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("credential_id", UUID, sa.ForeignKey("partner_credentials.id", ondelete="CASCADE"), nullable=False),
        sa.Column("idempotency_key", sa.String(180), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("request_hash", sa.String(64), nullable=False),
        sa.Column("state", sa.String(20), nullable=False, server_default="processing"),
        sa.Column("response_status", sa.Integer()),
        sa.Column("response_body", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("credential_id", "idempotency_key", name="uq_partner_credential_idempotency"),
        sa.CheckConstraint("state IN ('processing','completed','failed')", name="ck_partner_idempotency_state"),
    )
    op.create_index("ix_partner_idempotency_credential", "partner_idempotency_records", ["credential_id"])


def downgrade():
    op.drop_table("partner_idempotency_records")
    op.drop_table("partner_request_logs")
    op.drop_table("partner_request_nonces")
    op.drop_table("partner_credentials")
