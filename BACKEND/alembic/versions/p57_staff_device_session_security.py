"""staff device session security

Revision ID: p57_staff_device_session_security
Revises: p56_seller_license_expiry_hold
"""

from alembic import op
import sqlalchemy as sa

revision = "p57_staff_device_session_security"
down_revision = "p56_seller_license_expiry_hold"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("sessions", sa.Column("device_id", sa.String(length=128), nullable=True))
    op.add_column("sessions", sa.Column("device_name", sa.String(length=255), nullable=True))
    op.add_column("sessions", sa.Column("user_agent", sa.Text(), nullable=True))
    op.add_column("sessions", sa.Column("ip_address", sa.String(length=64), nullable=True))
    op.add_column("sessions", sa.Column("approximate_location", sa.String(length=255), nullable=True))
    op.add_column(
        "sessions",
        sa.Column("is_recognized", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.add_column("sessions", sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_sessions_device_id", "sessions", ["device_id"], unique=False)


def downgrade():
    op.drop_index("ix_sessions_device_id", table_name="sessions")
    op.drop_column("sessions", "last_seen_at")
    op.drop_column("sessions", "is_recognized")
    op.drop_column("sessions", "approximate_location")
    op.drop_column("sessions", "ip_address")
    op.drop_column("sessions", "user_agent")
    op.drop_column("sessions", "device_name")
    op.drop_column("sessions", "device_id")
