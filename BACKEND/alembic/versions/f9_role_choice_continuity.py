"""F9 persist initial role choice and onboarding continuity.

Revision ID: f9_role_continuity
Revises: f9_onboarding_locations
"""
from alembic import op
import sqlalchemy as sa

revision = "f9_role_continuity"
down_revision = "f9_onboarding_locations"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("users", sa.Column("initial_role_choice", sa.String(length=20), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "initial_role_choice_completed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )
    # Every account that existed before this deployment keeps its current login behavior.
    op.execute("UPDATE users SET initial_role_choice_completed = true")

def downgrade():
    op.drop_column("users", "initial_role_choice_completed")
    op.drop_column("users", "initial_role_choice")
