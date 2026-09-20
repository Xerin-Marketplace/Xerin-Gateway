"""Phase 3 Task 2: logistics company users and tenant permissions.

Revision ID: p25_logistics_company_users
Revises: p24_logistics_company_profile
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p25_logistics_company_users"
down_revision = "p24_logistics_company_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    member_role = postgresql.ENUM(
        "company_admin",
        "operations_manager",
        "dispatcher",
        "driver",
        "viewer",
        name="logisticsmemberrole",
        create_type=False,
    )
    member_role.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "logistics_company_users",
        sa.Column(
            "member_role",
            member_role,
            nullable=False,
            server_default="viewer",
        ),
    )
    op.add_column(
        "logistics_company_users",
        sa.Column(
            "permissions_json",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
    )
    op.create_index(
        "ix_logistics_company_users_member_role",
        "logistics_company_users",
        ["member_role"],
    )
    op.create_unique_constraint(
        "uq_logistics_company_user_single_company",
        "logistics_company_users",
        ["user_id"],
    )

    # Existing primary contacts become company administrators. Other existing
    # memberships remain read-only viewers until explicitly assigned a role.
    op.execute(
        """
        UPDATE logistics_company_users
        SET member_role = 'company_admin'
        WHERE is_primary_contact = TRUE
        """
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_logistics_company_user_single_company",
        "logistics_company_users",
        type_="unique",
    )
    op.drop_index(
        "ix_logistics_company_users_member_role",
        table_name="logistics_company_users",
    )
    op.drop_column("logistics_company_users", "permissions_json")
    op.drop_column("logistics_company_users", "member_role")
    postgresql.ENUM(name="logisticsmemberrole").drop(
        op.get_bind(), checkfirst=True
    )
