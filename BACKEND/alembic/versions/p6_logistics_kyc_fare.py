"""Add driver KYC, delivery zones, fares, surge pricing, trip coordinates, trip fees, and system settings tables.

Revision ID: p6_logistics_kyc_fare
Revises: p5_order_number
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "p6_logistics_kyc_fare"
down_revision = "p5_order_number"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Driver documents
    op.create_table(
        "driver_documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("document_type", sa.Enum("national_id", "driving_license", "vehicle_registration", "insurance_certificate", "passport_photo", "proof_of_address", "medical_certificate", "police_clearance", "other", name="driverdocumenttype"), nullable=False, index=True),
        sa.Column("document_number", sa.String(100), nullable=True),
        sa.Column("document_image_url", sa.Text(), nullable=True),
        sa.Column("document_image_back_url", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("pending", "approved", "rejected", "expired", name="driverdocumentstatus"), nullable=False, server_default="pending", index=True),
        sa.Column("expiry_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Driver KYC
    op.create_table(
        "driver_kyc",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("driver_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("drivers.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        sa.Column("national_id_number", sa.String(50), nullable=True),
        sa.Column("license_number", sa.String(50), nullable=True),
        sa.Column("license_class", sa.String(20), nullable=True),
        sa.Column("license_expiry", sa.DateTime(timezone=True), nullable=True),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=False, server_default="Tanzania"),
        sa.Column("emergency_contact_name", sa.String(200), nullable=True),
        sa.Column("emergency_contact_phone", sa.String(30), nullable=True),
        sa.Column("next_of_kin", sa.String(200), nullable=True),
        sa.Column("next_of_kin_phone", sa.String(30), nullable=True),
        sa.Column("bank_account_name", sa.String(200), nullable=True),
        sa.Column("bank_account_number", sa.String(50), nullable=True),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("profile_image_url", sa.Text(), nullable=True),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("verified_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Delivery zones
    op.create_table(
        "delivery_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("country", sa.String(100), nullable=False, server_default="Tanzania"),
        sa.Column("boundaries", postgresql.JSONB(), nullable=True),
        sa.Column("center_latitude", sa.Float(), nullable=True),
        sa.Column("center_longitude", sa.Float(), nullable=True),
        sa.Column("radius_km", sa.Numeric(10, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Delivery fares
    op.create_table(
        "delivery_fares",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("fare_type", sa.Enum("delivery", "parcel", "ride", name="faretype"), nullable=False, server_default="delivery", index=True),
        sa.Column("vehicle_type", postgresql.ENUM("motorcycle", "car", "van", "truck", "bicycle", "tuk_tuk", name="vehicletype", create_type=False), nullable=True, index=True),
        sa.Column("base_fare", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("per_km_fare", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("waiting_fee_per_min", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("idle_fee_per_min", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cancellation_fee_percent", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("min_cancellation_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("trip_delay_fee_per_min", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("penalty_fee_for_cancel", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("fee_add_to_next", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("min_fare", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("max_fare", sa.Numeric(18, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Surge pricing
    op.create_table(
        "surge_pricings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("delivery_zones.id", ondelete="CASCADE"), nullable=True, index=True),
        sa.Column("surge_type", sa.Enum("all_vehicles", "specific_category", "all_parcels", name="surgepricingtype"), nullable=False, server_default="all_vehicles"),
        sa.Column("surge_percentage", sa.Numeric(5, 2), nullable=False, server_default="0"),
        sa.Column("vehicle_type", postgresql.ENUM("motorcycle", "car", "van", "truck", "bicycle", "tuk_tuk", name="vehicletype", create_type=False), nullable=True),
        sa.Column("schedule_type", sa.Enum("always", "time_based", name="surgescheduletype"), nullable=False, server_default="always"),
        sa.Column("start_time", sa.Time(), nullable=True),
        sa.Column("end_time", sa.Time(), nullable=True),
        sa.Column("days_of_week", postgresql.JSONB(), nullable=True),
        sa.Column("customer_note", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true", index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Delivery trip coordinates
    op.create_table(
        "delivery_trip_coordinates",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("delivery_trips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("pickup_latitude", sa.Float(), nullable=True),
        sa.Column("pickup_longitude", sa.Float(), nullable=True),
        sa.Column("pickup_address", sa.Text(), nullable=True),
        sa.Column("destination_latitude", sa.Float(), nullable=True),
        sa.Column("destination_longitude", sa.Float(), nullable=True),
        sa.Column("destination_address", sa.Text(), nullable=True),
        sa.Column("intermediate_coordinates", postgresql.JSONB(), nullable=True),
        sa.Column("intermediate_addresses", postgresql.JSONB(), nullable=True),
        sa.Column("driver_accept_latitude", sa.Float(), nullable=True),
        sa.Column("driver_accept_longitude", sa.Float(), nullable=True),
        sa.Column("start_latitude", sa.Float(), nullable=True),
        sa.Column("start_longitude", sa.Float(), nullable=True),
        sa.Column("drop_latitude", sa.Float(), nullable=True),
        sa.Column("drop_longitude", sa.Float(), nullable=True),
        sa.Column("is_reached_destination", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # Delivery trip fees
    op.create_table(
        "delivery_trip_fees",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("trip_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("delivery_trips.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("base_fare", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("distance_fare", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("waiting_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("idle_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("delay_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("cancellation_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("return_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("surge_fee", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("vat_tax", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("admin_commission", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("tips", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("total_fare", sa.Numeric(18, 2), nullable=False, server_default="0"),
        sa.Column("currency", sa.String(10), nullable=False, server_default="TZS"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )

    # System settings
    op.create_table(
        "system_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True, index=True),
        sa.Column("value", sa.Text(), nullable=True),
        sa.Column("data_type", sa.String(20), nullable=False, server_default="string"),
        sa.Column("category", sa.String(50), nullable=False, server_default="general", index=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_encrypted", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("updated_by_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("system_settings")
    op.drop_table("delivery_trip_fees")
    op.drop_table("delivery_trip_coordinates")
    op.drop_table("surge_pricings")
    op.drop_table("delivery_fares")
    op.drop_table("delivery_zones")
    op.drop_table("driver_kyc")
    op.drop_table("driver_documents")
    op.execute("DROP TYPE IF EXISTS driverdocumenttype")
    op.execute("DROP TYPE IF EXISTS driverdocumentstatus")
    op.execute("DROP TYPE IF EXISTS faretype")
    op.execute("DROP TYPE IF EXISTS surgepricingtype")
    op.execute("DROP TYPE IF EXISTS surgescheduletype")
