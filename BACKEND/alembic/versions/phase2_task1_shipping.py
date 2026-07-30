"""Phase 2 Task 1: addresses and shipping configuration.

IMPORTANT: replace DOWN_REVISION with the output of `python -m alembic heads`.
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "phase2_task1_shipping"
down_revision = "phase1_task3"
branch_labels = None
depends_on = None

def upgrade():
    shipping_rate_type = postgresql.ENUM("flat", "weight_based", "free", name="shippingratetype")
    shipping_rate_type.create(op.get_bind(), checkfirst=True)
    for name, typ in [
        ("label", sa.String(50)), ("recipient_name", sa.String(150)), ("recipient_phone", sa.String(30)),
        ("district", sa.String(100)), ("ward", sa.String(100)), ("landmark", sa.String(255)),
        ("latitude", sa.Numeric(10,7)), ("longitude", sa.Numeric(10,7)), ("updated_at", sa.DateTime(timezone=True)),
    ]:
        op.add_column("addresses", sa.Column(name, typ, nullable=True))
    op.alter_column("addresses", "country", existing_type=sa.String(100), nullable=False, server_default="Tanzania")
    op.alter_column("addresses", "region", existing_type=sa.String(100), nullable=False)
    op.alter_column("addresses", "city", existing_type=sa.String(100), nullable=False)
    op.alter_column("addresses", "street", existing_type=sa.Text(), nullable=False)

    op.create_table("shipping_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True),
        sa.Column("country", sa.String(100), nullable=False, server_default="Tanzania"),
        sa.Column("regions", postgresql.JSONB(), nullable=False, server_default="[]"), sa.Column("cities", postgresql.JSONB(), nullable=False, server_default="[]"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True)))
    op.create_table("shipping_methods",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("name", sa.String(120), nullable=False, unique=True), sa.Column("description", sa.Text()), sa.Column("carrier_name", sa.String(120)),
        sa.Column("min_delivery_days", sa.Integer(), nullable=False, server_default="1"), sa.Column("max_delivery_days", sa.Integer(), nullable=False, server_default="7"), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("min_delivery_days >= 0", name="ck_shipping_method_min_days_nonnegative"), sa.CheckConstraint("max_delivery_days >= min_delivery_days", name="ck_shipping_method_days_valid"))
    op.create_table("shipping_rates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True), sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipping_zones.id", ondelete="CASCADE"), nullable=False), sa.Column("method_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipping_methods.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rate_type", shipping_rate_type, nullable=False, server_default="flat"), sa.Column("base_amount", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("amount_per_kg", sa.Numeric(18,2), nullable=False, server_default="0"), sa.Column("free_shipping_threshold", sa.Numeric(18,2)), sa.Column("min_weight_kg", sa.Numeric(10,3)), sa.Column("max_weight_kg", sa.Numeric(10,3)), sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("zone_id", "method_id", name="uq_shipping_rate_zone_method"), sa.CheckConstraint("base_amount >= 0", name="ck_shipping_rate_base_nonnegative"), sa.CheckConstraint("amount_per_kg >= 0", name="ck_shipping_rate_perkg_nonnegative"))
    op.create_index("ix_shipping_rates_zone_id", "shipping_rates", ["zone_id"]); op.create_index("ix_shipping_rates_method_id", "shipping_rates", ["method_id"])

def downgrade():
    op.drop_table("shipping_rates"); op.drop_table("shipping_methods"); op.drop_table("shipping_zones")
    for name in ["updated_at","longitude","latitude","landmark","ward","district","recipient_phone","recipient_name","label"]: op.drop_column("addresses", name)
    postgresql.ENUM(name="shippingratetype").drop(op.get_bind(), checkfirst=True)
