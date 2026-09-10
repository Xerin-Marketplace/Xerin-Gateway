"""Admin Phase 2 logistics management.

Revision ID: p8_logistics_management
Revises: p7_marketplace_settings
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "p8_logistics_management"
down_revision = "p7_marketplace_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    logistics_status = postgresql.ENUM(
        "pending", "active", "suspended", "inactive",
        name="logisticscompanystatus",
        create_type=False,
    )
    logistics_scope = postgresql.ENUM(
        "local", "international", "both",
        name="logisticsscope",
        create_type=False,
    )
    auth_type = postgresql.ENUM(
        "none", "api_key", "bearer", "basic", "oauth2", "custom",
        name="logisticsintegrationauthtype",
        create_type=False,
    )

    logistics_status.create(op.get_bind(), checkfirst=True)
    logistics_scope.create(op.get_bind(), checkfirst=True)
    auth_type.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "logistics_companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("code", sa.String(80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("contact_name", sa.String(150), nullable=True),
        sa.Column("contact_email", sa.String(255), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("website_url", sa.Text(), nullable=True),
        sa.Column("scope", logistics_scope, nullable=False, server_default="local"),
        sa.Column("status", logistics_status, nullable=False, server_default="pending"),
        sa.Column("supports_cod", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("supports_tracking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("supports_webhooks", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("metadata_json", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("name", name="uq_logistics_company_name"),
        sa.UniqueConstraint("code", name="uq_logistics_company_code"),
    )
    op.create_index("ix_logistics_companies_code", "logistics_companies", ["code"])
    op.create_index("ix_logistics_companies_scope", "logistics_companies", ["scope"])
    op.create_index("ix_logistics_companies_status", "logistics_companies", ["status"])

    op.create_table(
        "logistics_company_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(120), nullable=True),
        sa.Column("is_primary_contact", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("logistics_company_id", "user_id", name="uq_logistics_company_user"),
    )
    op.create_index("ix_logistics_company_users_company", "logistics_company_users", ["logistics_company_id"])
    op.create_index("ix_logistics_company_users_user", "logistics_company_users", ["user_id"])

    op.create_table(
        "logistics_integration_configs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("api_base_url", sa.Text(), nullable=True),
        sa.Column("outbound_webhook_url", sa.Text(), nullable=True),
        sa.Column("auth_type", auth_type, nullable=False, server_default="none"),
        sa.Column("credential_reference", sa.String(255), nullable=True),
        sa.Column("webhook_secret_reference", sa.String(255), nullable=True),
        sa.Column("api_key_header", sa.String(120), nullable=True),
        sa.Column("extra_config", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("last_tested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_test_success", sa.Boolean(), nullable=True),
        sa.Column("last_test_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("logistics_company_id", name="uq_logistics_integration_company"),
    )
    op.create_index("ix_logistics_integration_company", "logistics_integration_configs", ["logistics_company_id"])

    op.add_column(
        "shipping_zones",
        sa.Column("scope", logistics_scope, nullable=False, server_default="local"),
    )
    op.create_index("ix_shipping_zones_scope", "shipping_zones", ["scope"])

    op.add_column(
        "shipping_methods",
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.add_column("shipping_methods", sa.Column("service_code", sa.String(100), nullable=True))
    op.add_column(
        "shipping_methods",
        sa.Column("scope", logistics_scope, nullable=False, server_default="local"),
    )
    op.add_column(
        "shipping_methods",
        sa.Column("supports_cod", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "shipping_methods",
        sa.Column("supports_tracking", sa.Boolean(), nullable=False, server_default=sa.text("true")),
    )
    op.create_foreign_key(
        "fk_shipping_methods_logistics_company",
        "shipping_methods",
        "logistics_companies",
        ["logistics_company_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index("ix_shipping_methods_logistics_company", "shipping_methods", ["logistics_company_id"])
    op.create_index("ix_shipping_methods_service_code", "shipping_methods", ["service_code"])
    op.create_index("ix_shipping_methods_scope", "shipping_methods", ["scope"])

    op.add_column(
        "shipping_rates",
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
    )

    op.add_column(
        "shipments",
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_shipments_logistics_company",
        "shipments",
        "logistics_companies",
        ["logistics_company_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_shipments_logistics_company", "shipments", ["logistics_company_id"])

    op.create_table(
        "logistics_webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("logistics_company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        sa.Column("event_type", sa.String(120), nullable=False),
        sa.Column("external_event_id", sa.String(255), nullable=True),
        sa.Column("shipment_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("shipments.id", ondelete="SET NULL"), nullable=True),
        sa.Column("request_payload", postgresql.JSONB(), nullable=True),
        sa.Column("response_payload", postgresql.JSONB(), nullable=True),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("processed", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("logistics_company_id", "external_event_id", name="uq_logistics_webhook_external_event"),
    )
    op.create_index("ix_logistics_webhook_company", "logistics_webhook_events", ["logistics_company_id"])
    op.create_index("ix_logistics_webhook_event_type", "logistics_webhook_events", ["event_type"])
    op.create_index("ix_logistics_webhook_shipment", "logistics_webhook_events", ["shipment_id"])


def downgrade() -> None:
    op.drop_index("ix_logistics_webhook_shipment", table_name="logistics_webhook_events")
    op.drop_index("ix_logistics_webhook_event_type", table_name="logistics_webhook_events")
    op.drop_index("ix_logistics_webhook_company", table_name="logistics_webhook_events")
    op.drop_table("logistics_webhook_events")

    op.drop_index("ix_shipments_logistics_company", table_name="shipments")
    op.drop_constraint("fk_shipments_logistics_company", "shipments", type_="foreignkey")
    op.drop_column("shipments", "logistics_company_id")

    op.drop_column("shipping_rates", "currency")

    op.drop_index("ix_shipping_methods_scope", table_name="shipping_methods")
    op.drop_index("ix_shipping_methods_service_code", table_name="shipping_methods")
    op.drop_index("ix_shipping_methods_logistics_company", table_name="shipping_methods")
    op.drop_constraint("fk_shipping_methods_logistics_company", "shipping_methods", type_="foreignkey")
    op.drop_column("shipping_methods", "supports_tracking")
    op.drop_column("shipping_methods", "supports_cod")
    op.drop_column("shipping_methods", "scope")
    op.drop_column("shipping_methods", "service_code")
    op.drop_column("shipping_methods", "logistics_company_id")

    op.drop_index("ix_shipping_zones_scope", table_name="shipping_zones")
    op.drop_column("shipping_zones", "scope")

    op.drop_index("ix_logistics_integration_company", table_name="logistics_integration_configs")
    op.drop_table("logistics_integration_configs")

    op.drop_index("ix_logistics_company_users_user", table_name="logistics_company_users")
    op.drop_index("ix_logistics_company_users_company", table_name="logistics_company_users")
    op.drop_table("logistics_company_users")

    op.drop_index("ix_logistics_companies_status", table_name="logistics_companies")
    op.drop_index("ix_logistics_companies_scope", table_name="logistics_companies")
    op.drop_index("ix_logistics_companies_code", table_name="logistics_companies")
    op.drop_table("logistics_companies")

    bind = op.get_bind()
    postgresql.ENUM(name="logisticsintegrationauthtype").drop(bind, checkfirst=True)
    postgresql.ENUM(name="logisticsscope").drop(bind, checkfirst=True)
    postgresql.ENUM(name="logisticscompanystatus").drop(bind, checkfirst=True)
