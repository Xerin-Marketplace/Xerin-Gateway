"""Phase 3 Task 1: logistics company profile and account.

Revision ID: p24_logistics_company_profile
Revises: p23_pickup_proof_verification
"""

from alembic import op
import sqlalchemy as sa


revision = "p24_logistics_company_profile"
down_revision = "p23_pickup_proof_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("logistics_companies", sa.Column("legal_name", sa.String(180), nullable=True))
    op.add_column("logistics_companies", sa.Column("registration_number", sa.String(100), nullable=True))
    op.add_column("logistics_companies", sa.Column("tax_identification_number", sa.String(100), nullable=True))
    op.add_column("logistics_companies", sa.Column("license_number", sa.String(100), nullable=True))
    op.add_column("logistics_companies", sa.Column("logo_url", sa.Text(), nullable=True))
    op.add_column("logistics_companies", sa.Column("address_line1", sa.String(255), nullable=True))
    op.add_column("logistics_companies", sa.Column("address_line2", sa.String(255), nullable=True))
    op.add_column("logistics_companies", sa.Column("city", sa.String(120), nullable=True))
    op.add_column("logistics_companies", sa.Column("region", sa.String(120), nullable=True))
    op.add_column(
        "logistics_companies",
        sa.Column("country", sa.String(100), nullable=False, server_default="Tanzania"),
    )
    op.add_column("logistics_companies", sa.Column("postal_code", sa.String(30), nullable=True))
    op.create_unique_constraint(
        "uq_logistics_company_registration_number",
        "logistics_companies",
        ["registration_number"],
    )
    op.create_unique_constraint(
        "uq_logistics_company_tax_identification_number",
        "logistics_companies",
        ["tax_identification_number"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_logistics_company_tax_identification_number",
        "logistics_companies",
        type_="unique",
    )
    op.drop_constraint(
        "uq_logistics_company_registration_number",
        "logistics_companies",
        type_="unique",
    )
    for column_name in (
        "postal_code",
        "country",
        "region",
        "city",
        "address_line2",
        "address_line1",
        "logo_url",
        "license_number",
        "tax_identification_number",
        "registration_number",
        "legal_name",
    ):
        op.drop_column("logistics_companies", column_name)
