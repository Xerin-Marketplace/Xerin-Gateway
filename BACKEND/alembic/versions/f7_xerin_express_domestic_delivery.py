"""F7 Xerin Express domestic delivery orchestration

Revision ID: f7_xerin_express
Revises: f6_delivery_based_escrow
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
revision = "f7_xerin_express"
down_revision = "f6_delivery_based_escrow"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("shipping_methods", sa.Column("xerin_delivery_tier", sa.String(length=20), nullable=True))
    op.add_column("shipping_methods", sa.Column("promised_delivery_minutes", sa.Integer(), nullable=True))
    op.create_index("ix_shipping_methods_xerin_delivery_tier", "shipping_methods", ["xerin_delivery_tier"])
    op.create_check_constraint("ck_shipping_method_xerin_delivery_tier", "shipping_methods", "xerin_delivery_tier IS NULL OR xerin_delivery_tier IN ('standard','express')")
    op.create_check_constraint("ck_shipping_method_promised_minutes_positive", "shipping_methods", "promised_delivery_minutes IS NULL OR promised_delivery_minutes > 0")
    op.create_table("xerin_domestic_service_standards",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("origin_region", sa.String(length=100), nullable=False),
        sa.Column("destination_region", sa.String(length=100), nullable=False),
        sa.Column("tier", sa.String(length=20), nullable=False),
        sa.Column("max_delivery_minutes", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("origin_region", "destination_region", "tier", name="uq_xerin_domestic_standard_route_tier"),
        sa.CheckConstraint("tier IN ('standard','express')", name="ck_xerin_domestic_standard_tier"),
        sa.CheckConstraint("max_delivery_minutes > 0", name="ck_xerin_domestic_standard_minutes_positive"),
    )
    op.create_index("ix_xerin_domestic_service_standards_origin_region", "xerin_domestic_service_standards", ["origin_region"])
    op.create_index("ix_xerin_domestic_service_standards_destination_region", "xerin_domestic_service_standards", ["destination_region"])
    op.create_index("ix_xerin_domestic_service_standards_tier", "xerin_domestic_service_standards", ["tier"])

def downgrade():
    op.drop_table("xerin_domestic_service_standards")
    op.drop_constraint("ck_shipping_method_promised_minutes_positive", "shipping_methods", type_="check")
    op.drop_constraint("ck_shipping_method_xerin_delivery_tier", "shipping_methods", type_="check")
    op.drop_index("ix_shipping_methods_xerin_delivery_tier", table_name="shipping_methods")
    op.drop_column("shipping_methods", "promised_delivery_minutes")
    op.drop_column("shipping_methods", "xerin_delivery_tier")
