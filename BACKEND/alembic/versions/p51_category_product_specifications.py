"""Category-driven product specifications.

Revision ID: p51_category_product_specs
Revises: f13_payout_verification
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p51_category_product_specs"
down_revision = "f13_payout_verification"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "category_attributes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id", ondelete="CASCADE"), nullable=False),
        sa.Column("key", sa.String(100), nullable=False),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("input_type", sa.String(30), nullable=False, server_default="text"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("allowed_values", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("settings", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_filterable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_comparable", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("use_for_similarity", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("similarity_weight", sa.Numeric(6,2), nullable=False, server_default="1"),
        sa.Column("is_variant_attribute", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("inherit_to_children", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("display_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("category_id", "key", name="uq_category_attribute_key"),
        sa.CheckConstraint("similarity_weight >= 0", name="ck_category_attribute_similarity_weight_nonnegative"),
        sa.CheckConstraint("input_type IN ('text','textarea','number','boolean','select','multiselect','date')", name="ck_category_attribute_input_type"),
    )
    op.create_index("ix_category_attributes_category_id", "category_attributes", ["category_id"])
    op.create_index("ix_category_attributes_category_active_order", "category_attributes", ["category_id", "is_active", "display_order"])

    op.create_table(
        "product_specifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("product_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("attribute_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("category_attributes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("normalized_value", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("product_id", "attribute_id", name="uq_product_specification_attribute"),
    )
    op.create_index("ix_product_specifications_product_id", "product_specifications", ["product_id"])
    op.create_index("ix_product_specifications_attribute_id", "product_specifications", ["attribute_id"])
    op.create_index("ix_product_specifications_normalized_value", "product_specifications", ["normalized_value"])
    op.create_index("ix_product_specifications_attribute_normalized", "product_specifications", ["attribute_id", "normalized_value"])


def downgrade():
    op.drop_table("product_specifications")
    op.drop_table("category_attributes")
