"""Seller product options and production-ready variants.

Revision ID: p3_seller_variants
Revises: p4_seller_products
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p3_seller_variants"
down_revision = "p4_seller_products"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("product_options",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(100), nullable=False), sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("product_id","name",name="uq_product_option_name"), sa.CheckConstraint("display_order >= 0",name="ck_product_option_display_order_nonnegative"))
    op.create_index("ix_product_options_product_id","product_options",["product_id"])
    op.create_table("product_option_values",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("option_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("product_options.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", sa.String(100), nullable=False), sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("option_id","value",name="uq_product_option_value"), sa.CheckConstraint("display_order >= 0",name="ck_product_option_value_display_order_nonnegative"))
    op.create_index("ix_product_option_values_option_id","product_option_values",["option_id"])
    op.add_column("product_variants",sa.Column("barcode",sa.String(100),nullable=True))
    op.add_column("product_variants",sa.Column("sale_price",sa.Numeric(18,2),nullable=True))
    op.add_column("product_variants",sa.Column("weight",sa.Numeric(10,3),nullable=True))
    op.add_column("product_variants",sa.Column("image_id",postgresql.UUID(as_uuid=True),nullable=True))
    op.add_column("product_variants",sa.Column("is_active",sa.Boolean(),nullable=False,server_default=sa.true()))
    op.add_column("product_variants",sa.Column("updated_at",sa.DateTime(timezone=True),nullable=True))
    op.create_unique_constraint("uq_product_variants_barcode","product_variants",["barcode"])
    op.create_foreign_key("fk_product_variants_image_id","product_variants","product_images",["image_id"],["id"],ondelete="SET NULL")
    op.create_check_constraint("ck_variant_price_nonnegative","product_variants","price IS NULL OR price >= 0")
    op.create_check_constraint("ck_variant_sale_price_nonnegative","product_variants","sale_price IS NULL OR sale_price >= 0")
    op.create_check_constraint("ck_variant_sale_price_lte_price","product_variants","sale_price IS NULL OR price IS NULL OR sale_price <= price")
    op.create_check_constraint("ck_variant_weight_nonnegative","product_variants","weight IS NULL OR weight >= 0")
    op.create_table("product_variant_values",
        sa.Column("id",postgresql.UUID(as_uuid=True),primary_key=True),
        sa.Column("variant_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("product_variants.id",ondelete="CASCADE"),nullable=False),
        sa.Column("option_value_id",postgresql.UUID(as_uuid=True),sa.ForeignKey("product_option_values.id",ondelete="RESTRICT"),nullable=False),
        sa.UniqueConstraint("variant_id","option_value_id",name="uq_variant_option_value"))
    op.create_index("ix_product_variant_values_variant_id","product_variant_values",["variant_id"])
    op.create_index("ix_product_variant_values_option_value_id","product_variant_values",["option_value_id"])

def downgrade():
    op.drop_table("product_variant_values")
    for name in ["ck_variant_weight_nonnegative","ck_variant_sale_price_lte_price","ck_variant_sale_price_nonnegative","ck_variant_price_nonnegative"]: op.drop_constraint(name,"product_variants",type_="check")
    op.drop_constraint("fk_product_variants_image_id","product_variants",type_="foreignkey")
    op.drop_constraint("uq_product_variants_barcode","product_variants",type_="unique")
    for col in ["updated_at","is_active","image_id","weight","sale_price","barcode"]: op.drop_column("product_variants",col)
    op.drop_table("product_option_values")
    op.drop_table("product_options")
