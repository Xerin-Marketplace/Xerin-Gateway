"""add purpose column to otp_requests

Revision ID: add_otp_purpose
Revises:   # <-- fill in with your current head revision id before running
Create Date: 2026-07-03
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "add_otp_purpose"
down_revision = None  # <-- set this to your current head revision id
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "otp_requests",
        sa.Column(
            "purpose",
            sa.String(length=50),
            nullable=False,
            server_default="generic",
        ),
    )


def downgrade():
    op.drop_column("otp_requests", "purpose")