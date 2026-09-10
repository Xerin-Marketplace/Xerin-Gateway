"""Broker B1 identity, KYC and approval.

Revision ID: b1_broker_identity_access
Revises: p50_logistics_company_documents
"""
from alembic import op
import sqlalchemy as sa
import uuid
from sqlalchemy.dialects import postgresql

revision = "b1_broker_identity_access"
down_revision = "p50_logistics_company_documents"
branch_labels = None
depends_on = None


def upgrade():
    status_enum = postgresql.ENUM("pending_kyc", "kyc_submitted", "under_review", "approved", "rejected", "suspended", name="brokerstatus", create_type=False)
    status_enum.create(op.get_bind(), checkfirst=True)
    op.create_table("brokers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("broker_code", sa.String(32), nullable=False, unique=True),
        sa.Column("country", sa.String(100), nullable=False), sa.Column("region", sa.String(100), nullable=False), sa.Column("city", sa.String(100), nullable=False),
        sa.Column("nida_number", sa.String(100), nullable=True), sa.Column("status", status_enum, nullable=False, server_default="pending_kyc"),
        sa.Column("approved_at", sa.DateTime(timezone=True)), sa.Column("rejected_at", sa.DateTime(timezone=True)), sa.Column("suspended_at", sa.DateTime(timezone=True)), sa.Column("status_reason", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_brokers_user_id", "brokers", ["user_id"]); op.create_index("ix_brokers_broker_code", "brokers", ["broker_code"]); op.create_index("ix_brokers_nida_number", "brokers", ["nida_number"]); op.create_index("ix_brokers_status", "brokers", ["status"])
    op.create_table("broker_kyc_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_type", sa.String(50), nullable=False), sa.Column("file_path", sa.Text(), nullable=False), sa.Column("original_filename", sa.String(255)), sa.Column("mime_type", sa.String(100)),
        sa.Column("status", sa.String(30), nullable=False, server_default="pending"), sa.Column("rejection_reason", sa.Text()), sa.Column("reviewed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("broker_id", "document_type", name="uq_broker_kyc_document_type"),
    )
    op.create_index("ix_broker_kyc_documents_broker_id", "broker_kyc_documents", ["broker_id"]); op.create_index("ix_broker_kyc_documents_document_type", "broker_kyc_documents", ["document_type"]); op.create_index("ix_broker_kyc_documents_status", "broker_kyc_documents", ["status"])
    op.create_table("broker_status_history",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("broker_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("brokers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_status", sa.String(30)), sa.Column("to_status", sa.String(30), nullable=False), sa.Column("reason", sa.Text()), sa.Column("changed_by_user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_broker_status_history_broker_id", "broker_status_history", ["broker_id"]); op.create_index("ix_broker_status_history_to_status", "broker_status_history", ["to_status"])

    bind=op.get_bind()
    role_id=bind.execute(sa.text("SELECT id FROM roles WHERE name='broker'")).scalar()
    if role_id is None:
        new_role_id=str(uuid.uuid4()); bind.execute(sa.text("INSERT INTO roles (id,name,description) VALUES (:id,'broker','Xerin marketplace broker')"),{'id':new_role_id}); role_id=new_role_id
    codes={
        'broker_profile:read':'View own broker profile','broker_profile:update':'Update own broker profile','broker_kyc:upload':'Upload broker KYC','broker_kyc:submit':'Submit broker KYC',
        'admin_brokers:read':'View brokers','admin_brokers:review':'Review broker KYC','admin_brokers:suspend':'Suspend brokers'
    }
    for code,name in codes.items():
        pid=bind.execute(sa.text("SELECT id FROM permissions WHERE code=:c"),{'c':code}).scalar()
        if pid is None:
            new_permission_id=str(uuid.uuid4()); bind.execute(sa.text("INSERT INTO permissions (id,code,name) VALUES (:id,:c,:n)"),{'id':new_permission_id,'c':code,'n':name}); pid=new_permission_id
        if code.startswith('broker_'):
            bind.execute(sa.text("INSERT INTO role_permissions (role_id,permission_id) VALUES (:r,:p) ON CONFLICT DO NOTHING"),{'r':role_id,'p':pid})
        if code.startswith('admin_'):
            bind.execute(sa.text("INSERT INTO role_permissions (role_id,permission_id) SELECT r.id,:p FROM roles r WHERE r.name IN ('admin','super_admin') ON CONFLICT DO NOTHING"),{'p':pid})


def downgrade():
    op.drop_table("broker_status_history"); op.drop_table("broker_kyc_documents"); op.drop_table("brokers")
    postgresql.ENUM(name="brokerstatus").drop(op.get_bind(), checkfirst=True)
