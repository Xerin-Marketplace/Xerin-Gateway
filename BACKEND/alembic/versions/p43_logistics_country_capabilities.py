"""Logistics country route capabilities."""
from alembic import op
import sqlalchemy as sa
revision = "p43_logistics_country_capabilities"
down_revision = "p42_currency_fx_foundation"
branch_labels = None
depends_on = None

def upgrade():
    op.add_column("shipping_zones", sa.Column("supports_domestic_delivery", sa.Boolean(), nullable=False, server_default=sa.text("true")))
    op.add_column("shipping_zones", sa.Column("supports_cross_border_inbound", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.add_column("shipping_zones", sa.Column("supports_cross_border_outbound", sa.Boolean(), nullable=False, server_default=sa.text("false")))
    op.execute("""
      UPDATE shipping_zones SET
        supports_domestic_delivery = CASE WHEN scope::text IN ('local','both') THEN true ELSE false END,
        supports_cross_border_inbound = CASE WHEN scope::text IN ('international','both') THEN true ELSE false END,
        supports_cross_border_outbound = CASE WHEN scope::text IN ('international','both') THEN true ELSE false END
    """)
    op.create_index("ix_shipping_zones_domestic_delivery","shipping_zones",["supports_domestic_delivery"])
    op.create_index("ix_shipping_zones_cross_border_inbound","shipping_zones",["supports_cross_border_inbound"])
    op.create_index("ix_shipping_zones_cross_border_outbound","shipping_zones",["supports_cross_border_outbound"])

def downgrade():
    op.drop_index("ix_shipping_zones_cross_border_outbound", table_name="shipping_zones")
    op.drop_index("ix_shipping_zones_cross_border_inbound", table_name="shipping_zones")
    op.drop_index("ix_shipping_zones_domestic_delivery", table_name="shipping_zones")
    op.drop_column("shipping_zones","supports_cross_border_outbound")
    op.drop_column("shipping_zones","supports_cross_border_inbound")
    op.drop_column("shipping_zones","supports_domestic_delivery")
