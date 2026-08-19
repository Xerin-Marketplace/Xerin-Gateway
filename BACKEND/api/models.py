import uuid
import enum

from sqlalchemy import (
    Column,
    String,
    Boolean,
    DateTime,
    ForeignKey,
    Enum,
    Text,
    UniqueConstraint,
    CheckConstraint,
    Index,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import datetime
from sqlalchemy import Float, Time
from sqlalchemy import Numeric, Integer
from sqlalchemy.dialects.postgresql import JSONB
from api.database import Base
from api.enums import (
    DayOfWeek,
    StoreStatus,
    ShippingRateType,
    ShipmentStatus,
    InventoryReservationStatus,
    CommissionScope,
    CommissionRuleType,
    MarketplaceTransactionType,
    WalletTransactionType,
    PayoutStatus,
    RefundStatus,
    RefundReason,
    InventoryMovementType,
    AuditSeverity,
    SecurityEventType,
    SellerOrderStatus,
    DeliveryStatus,
    ReviewStatus,
    ReviewReportReason,
    NotificationChannel,
    NotificationDeliveryStatus,
    NotificationEvent,
    QuestionStatus,
    QuestionReportReason,
    LogisticsCompanyStatus,
    LogisticsScope,
    LogisticsMemberRole,
    LogisticsIntegrationAuthType,
    MultiSellerPricingStrategy,
    PickupJobStatus,
    AdvertisementStatus,
    AdvertisementPlacement,
    AdvertisementBillingType,
)


class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    suspended = "suspended"
    pending_verification = "pending_verification"


class SellerStatus(str, enum.Enum):
    pending = "pending"
    under_review = "under_review"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    first_name = Column(String(100))
    last_name = Column(String(100))
    email = Column(String(255), unique=True, index=True, nullable=False)
    phone = Column(String(30), unique=True, index=True)
    password_hash = Column(Text, nullable=False)
    status = Column(Enum(UserStatus), default=UserStatus.pending_verification)
    is_verified = Column(Boolean, default=False)
    last_login_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    addresses = relationship("Address", back_populates="user")
    seller_profile = relationship("Seller", back_populates="user", uselist=False)
    roles = relationship("UserRole", back_populates="user")
    wishlist_products = relationship(
        "WishlistProduct", back_populates="user", cascade="all, delete-orphan"
    )
    favorite_stores = relationship(
        "FavoriteStore", back_populates="user", cascade="all, delete-orphan"
    )
    notifications = relationship(
        "Notification", back_populates="user", cascade="all, delete-orphan"
    )
    notification_preference = relationship(
        "NotificationPreference",
        back_populates="user",
        uselist=False,
        cascade="all, delete-orphan",
    )
    device_tokens = relationship(
        "DeviceToken", back_populates="user", cascade="all, delete-orphan"
    )
    logistics_memberships = relationship(
        "LogisticsCompanyUser", back_populates="user", cascade="all, delete-orphan"
    )


class Role(Base):
    __tablename__ = "roles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(50), unique=True, nullable=False)  # admin, customer, seller
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserRole(Base):
    __tablename__ = "user_roles"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True)

    user = relationship("User", back_populates="roles")
    role = relationship("Role")


class Permission(Base):
    __tablename__ = "permissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(100), unique=True, nullable=False)
    name = Column(String(150), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserPermission(Base):
    __tablename__ = "user_permissions"

    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), primary_key=True)
    permission_id = Column(
        UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True
    )

    user = relationship("User")
    permission = relationship("Permission")


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(
        UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True
    )

    role = relationship("Role")
    permission = relationship("Permission")


class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OTPRequest(Base):
    __tablename__ = "otp_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    phone = Column(String(30), nullable=False, index=True)
    otp_hash = Column(String(64), nullable=False)
    # What this OTP is for: "register", "password_reset", "phone_verify", etc.
    # Prevents an OTP issued for one flow (e.g. forgot-password) from being
    # accepted in an unrelated flow (e.g. account verification).
    purpose = Column(String(50), nullable=False, server_default="generic")
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Address(Base):
    __tablename__ = "addresses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label = Column(String(50), nullable=True)
    recipient_name = Column(String(150), nullable=True)
    recipient_phone = Column(String(30), nullable=True)
    country = Column(String(100), nullable=False, server_default="Tanzania")
    region = Column(String(100), nullable=False)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    city = Column(String(100), nullable=False)
    street = Column(Text, nullable=False)
    landmark = Column(String(255), nullable=True)
    postal_code = Column(String(50), nullable=True)

    # Phase 2 Task 1: exact customer delivery destination.
    # Keep the human-readable address and map provider reference together with
    # coordinates so logistics can later calculate road distance reliably.
    formatted_address = Column(Text, nullable=True)
    place_id = Column(String(255), nullable=True, index=True)
    latitude = Column(Numeric(10, 7), nullable=True)
    longitude = Column(Numeric(10, 7), nullable=True)
    delivery_instructions = Column(Text, nullable=True)

    is_default = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)
    is_verified = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    location_provider = Column(String(30), nullable=True)
    location_confirmed_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    @property
    def delivery_ready(self) -> bool:
        """True when the address has everything needed for logistics quoting.

        Phase 2 Task 2 will make map-pin confirmation explicit in the UI. For
        now, readiness is derived from active status + recipient contact + GPS.
        """
        return bool(
            self.is_active
            and self.is_verified
            and self.location_confirmed_at is not None
            and self.recipient_name
            and self.recipient_phone
            and self.latitude is not None
            and self.longitude is not None
        )

    user = relationship("User", back_populates="addresses")


class Seller(Base):
    __tablename__ = "sellers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    business_name = Column(String(255), nullable=False)
    contact_email = Column(String(255))
    contact_phone = Column(String(30))
    status = Column(Enum(SellerStatus), default=SellerStatus.pending)
    agreement_accepted = Column(Boolean, default=False)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    user = relationship("User", back_populates="seller_profile")
    business_categories = relationship(
        "SellerBusinessCategory", back_populates="seller", cascade="all, delete-orphan"
    )
    kyc_documents = relationship(
        "SellerKYCDocument", back_populates="seller", cascade="all, delete-orphan"
    )
    payout_accounts = relationship(
        "SellerPayoutAccount", back_populates="seller", cascade="all, delete-orphan"
    )
    commission_rules = relationship("CommissionRule", back_populates="seller")
    commission_records = relationship("OrderItemCommission", back_populates="seller")
    wallet = relationship(
        "SellerWallet",
        back_populates="seller",
        uselist=False,
        cascade="all, delete-orphan",
    )
    profile = relationship(
        "SellerProfile",
        back_populates="seller",
        uselist=False,
        cascade="all, delete-orphan",
    )

    store = relationship(
        "Store",
        back_populates="seller",
        uselist=False,
        cascade="all, delete-orphan",
    )
    pickup_locations = relationship(
        "SellerPickupLocation",
        back_populates="seller",
        cascade="all, delete-orphan",
        order_by="SellerPickupLocation.created_at",
    )


class SellerPickupLocation(Base):
    """Reusable seller pickup origin for logistics fulfillment.

    Orders/shipments will snapshot the address/coordinates later so historical
    deliveries are not changed when the seller edits a pickup point.
    """

    __tablename__ = "seller_pickup_locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    label = Column(String(120), nullable=False, default="Main pickup", server_default="Main pickup")
    formatted_address = Column(Text, nullable=False)
    country = Column(String(100), nullable=False, default="Tanzania", server_default="Tanzania")
    region = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    street = Column(Text, nullable=True)
    landmark = Column(String(255), nullable=True)
    postal_code = Column(String(50), nullable=True)

    # Google/other map provider reference. Provider-specific metadata stays optional.
    place_id = Column(String(255), nullable=True, index=True)
    latitude = Column(Numeric(10, 7), nullable=False)
    longitude = Column(Numeric(10, 7), nullable=False)

    pickup_contact_name = Column(String(180), nullable=False)
    pickup_phone = Column(String(30), nullable=False)
    pickup_instructions = Column(Text, nullable=True)

    is_default = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    is_verified = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true", index=True)

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    seller = relationship("Seller", back_populates="pickup_locations")

    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_seller_pickup_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_seller_pickup_longitude"),
        Index(
            "ix_seller_pickup_locations_seller_active_default",
            "seller_id",
            "is_active",
            "is_default",
        ),
        Index(
            "uq_seller_pickup_location_default",
            "seller_id",
            unique=True,
            postgresql_where=text("is_default = true"),
        ),
    )


class SellerProfile(Base):
    __tablename__ = "seller_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(
        UUID(as_uuid=True), ForeignKey("sellers.id"), unique=True, nullable=False
    )

    business_description = Column(Text, nullable=True)
    business_country = Column(String(100), nullable=True)
    business_region = Column(String(100), nullable=True)
    business_city = Column(String(100), nullable=True)
    business_address = Column(Text, nullable=True)
    product_description = Column(Text, nullable=True)
    years_in_business = Column(String(50), nullable=True)
    website_url = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    seller = relationship("Seller", back_populates="profile")


class SellerKYCDocument(Base):
    __tablename__ = "seller_kyc_documents"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document_type = Column(String(100), nullable=False)
    document_url = Column(Text, nullable=False)
    status = Column(String(50), default="pending")
    rejection_reason = Column(Text, nullable=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    seller = relationship("Seller", back_populates="kyc_documents")


class SellerPayoutAccount(Base):
    __tablename__ = "seller_payout_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    account_type = Column(String(50), nullable=False)
    provider = Column(String(100), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_number = Column(String(255), nullable=False)
    currency = Column(String(10), default="TZS")
    is_default = Column(Boolean, default=False)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    verification_status = Column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    provider_reference = Column(String(180), nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    seller = relationship("Seller", back_populates="payout_accounts")


class SellerBusinessCategory(Base):
    __tablename__ = "seller_business_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    business_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business_categories.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    seller = relationship("Seller", back_populates="business_categories")
    business_category = relationship("BusinessCategory")

    __table_args__ = (
        UniqueConstraint(
            "seller_id", "business_category_id", name="uq_seller_business_category"
        ),
    )


class ProductStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    inactive = "inactive"


class BusinessCategory(Base):
    __tablename__ = "business_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), unique=True, nullable=False)
    slug = Column(String(150), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Category(Base):
    __tablename__ = "categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True)
    name = Column(String(150), nullable=False)
    slug = Column(String(150), unique=True, index=True, nullable=False)
    image_url = Column(String(500), nullable=True)
    thumbnail_url = Column(String(500), nullable=True)
    image_storage_key = Column(String(500), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Brand(Base):
    __tablename__ = "brands"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    slug = Column(String(150), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=False)
    category_id = Column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)

    sku = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text)

    # Seller enters base prices. `price` / `sale_price` remain marketplace-facing
    # prices for backwards compatibility with storefront/cart code.
    seller_base_price = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    seller_sale_price = Column(Numeric(18, 2), nullable=True)
    commission_rate_snapshot = Column(
        Numeric(10, 4), nullable=False, default=0, server_default="0"
    )
    commission_amount_snapshot = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    price = Column(Numeric(18, 2), nullable=False)
    sale_price = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(10), default="TZS")
    weight = Column(Numeric(10, 2), nullable=True)

    status = Column(Enum(ProductStatus), default=ProductStatus.draft, nullable=False)
    rejection_reason = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    submitted_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    approved_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    seller = relationship("Seller")
    category = relationship("Category")
    brand = relationship("Brand")
    images = relationship(
        "ProductImage", back_populates="product", cascade="all, delete-orphan"
    )
    variants = relationship(
        "ProductVariant", back_populates="product", cascade="all, delete-orphan"
    )
    options = relationship(
        "ProductOption",
        back_populates="product",
        cascade="all, delete-orphan",
        order_by="ProductOption.display_order",
    )
    tags = relationship(
        "ProductTag", back_populates="product", cascade="all, delete-orphan"
    )
    wishlist_entries = relationship(
        "WishlistProduct", back_populates="product", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("price >= 0", name="ck_product_price_nonnegative"),
        CheckConstraint(
            "sale_price IS NULL OR sale_price >= 0",
            name="ck_product_sale_price_nonnegative",
        ),
        CheckConstraint(
            "sale_price IS NULL OR sale_price <= price",
            name="ck_product_sale_price_lte_price",
        ),
    )


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url = Column(Text, nullable=False)
    thumbnail_url = Column(Text, nullable=True)
    storage_key = Column(Text, nullable=True, unique=True)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(100), nullable=True)
    file_size = Column(Integer, nullable=True)
    width = Column(Integer, nullable=True)
    height = Column(Integer, nullable=True)
    alt_text = Column(String(255), nullable=True)
    display_order = Column(Integer, nullable=False, default=0)
    is_primary = Column(Boolean, nullable=False, default=False)
    uploaded_by_user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("Product", back_populates="images")

    __table_args__ = (
        CheckConstraint(
            "display_order >= 0", name="ck_product_image_display_order_nonnegative"
        ),
        CheckConstraint(
            "file_size IS NULL OR file_size >= 0",
            name="ck_product_image_file_size_nonnegative",
        ),
    )


class ProductOption(Base):
    __tablename__ = "product_options"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name = Column(String(100), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("Product", back_populates="options")
    values = relationship(
        "ProductOptionValue",
        back_populates="option",
        cascade="all, delete-orphan",
        order_by="ProductOptionValue.display_order",
    )

    __table_args__ = (
        UniqueConstraint("product_id", "name", name="uq_product_option_name"),
        CheckConstraint(
            "display_order >= 0", name="ck_product_option_display_order_nonnegative"
        ),
    )


class ProductOptionValue(Base):
    __tablename__ = "product_option_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    option_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_options.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    value = Column(String(100), nullable=False)
    display_order = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    option = relationship("ProductOption", back_populates="values")
    variant_values = relationship("ProductVariantValue", back_populates="option_value")

    __table_args__ = (
        UniqueConstraint("option_id", "value", name="uq_product_option_value"),
        CheckConstraint(
            "display_order >= 0",
            name="ck_product_option_value_display_order_nonnegative",
        ),
    )


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    variant_name = Column(String(255), nullable=False)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    barcode = Column(String(100), unique=True, nullable=True, index=True)
    seller_base_price = Column(Numeric(18, 2), nullable=True)
    seller_sale_price = Column(Numeric(18, 2), nullable=True)
    commission_rate_snapshot = Column(Numeric(10, 4), nullable=True)
    commission_amount_snapshot = Column(Numeric(18, 2), nullable=True)
    price = Column(Numeric(18, 2), nullable=True)
    sale_price = Column(Numeric(18, 2), nullable=True)
    weight = Column(Numeric(10, 3), nullable=True)
    image_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_images.id", ondelete="SET NULL"),
        nullable=True,
    )
    attributes = Column(JSONB, nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    product = relationship("Product", back_populates="variants")
    image = relationship("ProductImage")
    option_values = relationship(
        "ProductVariantValue", back_populates="variant", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "price IS NULL OR price >= 0", name="ck_variant_price_nonnegative"
        ),
        CheckConstraint(
            "sale_price IS NULL OR sale_price >= 0",
            name="ck_variant_sale_price_nonnegative",
        ),
        CheckConstraint(
            "sale_price IS NULL OR price IS NULL OR sale_price <= price",
            name="ck_variant_sale_price_lte_price",
        ),
        CheckConstraint(
            "weight IS NULL OR weight >= 0", name="ck_variant_weight_nonnegative"
        ),
    )


class ProductVariantValue(Base):
    __tablename__ = "product_variant_values"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    variant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_variants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    option_value_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_option_values.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    variant = relationship("ProductVariant", back_populates="option_values")
    option_value = relationship("ProductOptionValue", back_populates="variant_values")

    __table_args__ = (
        UniqueConstraint(
            "variant_id", "option_value_id", name="uq_variant_option_value"
        ),
    )


class ProductTag(Base):
    __tablename__ = "product_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    tag = Column(String(100), index=True, nullable=False)

    product = relationship("Product", back_populates="tags")


#
# CART
#


class Cart(Base):
    __tablename__ = "carts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False
    )
    coupon_code = Column(String(50), nullable=True)
    # Seller-funded marketplace promotion applied to this cart.
    # Kept separate from platform/admin coupons so both funding sources remain auditable.
    promotion_code = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    items = relationship(
        "CartItem", back_populates="cart", cascade="all, delete-orphan"
    )


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id = Column(
        UUID(as_uuid=True),
        ForeignKey("carts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(
        UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True
    )
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")

    __table_args__ = (
        UniqueConstraint(
            "cart_id", "product_id", "variant_id", name="uq_cart_item_product_variant"
        ),
        CheckConstraint("quantity > 0", name="ck_cart_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_cart_item_unit_price_nonnegative"),
    )


#
# SHIPPING CONFIGURATION
#


class LogisticsCompany(Base):
    __tablename__ = "logistics_companies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False, unique=True)
    code = Column(String(80), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    legal_name = Column(String(180), nullable=True)
    registration_number = Column(String(100), nullable=True, unique=True)
    tax_identification_number = Column(String(100), nullable=True, unique=True)
    license_number = Column(String(100), nullable=True)
    logo_url = Column(Text, nullable=True)
    contact_name = Column(String(150), nullable=True)
    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(50), nullable=True)
    website_url = Column(Text, nullable=True)
    address_line1 = Column(String(255), nullable=True)
    address_line2 = Column(String(255), nullable=True)
    city = Column(String(120), nullable=True)
    region = Column(String(120), nullable=True)
    country = Column(String(100), nullable=False, default="Tanzania", server_default="Tanzania")
    postal_code = Column(String(30), nullable=True)
    scope = Column(
        Enum(LogisticsScope),
        nullable=False,
        default=LogisticsScope.local,
        server_default="local",
        index=True,
    )
    status = Column(
        Enum(LogisticsCompanyStatus),
        nullable=False,
        default=LogisticsCompanyStatus.pending,
        server_default="pending",
        index=True,
    )
    supports_cod = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    supports_tracking = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    supports_webhooks = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    multi_seller_pricing_strategy = Column(
        Enum(MultiSellerPricingStrategy),
        nullable=False,
        default=MultiSellerPricingStrategy.farthest_seller,
        server_default="farthest_seller",
        index=True,
    )
    metadata_json = Column(JSONB, nullable=False, default=dict, server_default="{}")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    users = relationship(
        "LogisticsCompanyUser", back_populates="company", cascade="all, delete-orphan"
    )
    services = relationship("ShippingMethod", back_populates="logistics_company")
    zones = relationship("ShippingZone", back_populates="logistics_company")
    integrations = relationship(
        "LogisticsIntegrationConfig",
        back_populates="company",
        cascade="all, delete-orphan",
    )
    webhook_events = relationship(
        "LogisticsWebhookEvent", back_populates="company", cascade="all, delete-orphan"
    )
    shipments = relationship("Shipment", back_populates="logistics_company")


class LogisticsCompanyUser(Base):
    __tablename__ = "logistics_company_users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title = Column(String(120), nullable=True)
    member_role = Column(
        Enum(LogisticsMemberRole),
        nullable=False,
        default=LogisticsMemberRole.viewer,
        server_default="viewer",
        index=True,
    )
    permissions_json = Column(JSONB, nullable=False, default=list, server_default="[]")
    is_primary_contact = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company = relationship("LogisticsCompany", back_populates="users")
    user = relationship("User", back_populates="logistics_memberships")

    __table_args__ = (
        UniqueConstraint(
            "logistics_company_id", "user_id", name="uq_logistics_company_user"
        ),
        UniqueConstraint(
            "user_id", name="uq_logistics_company_user_single_company"
        ),
    )


class LogisticsIntegrationConfig(Base):
    __tablename__ = "logistics_integration_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    api_base_url = Column(Text, nullable=True)
    outbound_webhook_url = Column(Text, nullable=True)
    auth_type = Column(
        Enum(LogisticsIntegrationAuthType),
        nullable=False,
        default=LogisticsIntegrationAuthType.none,
        server_default="none",
    )
    credential_reference = Column(String(255), nullable=True)
    webhook_secret_reference = Column(String(255), nullable=True)
    api_key_header = Column(String(120), nullable=True)
    extra_config = Column(JSONB, nullable=False, default=dict, server_default="{}")
    webhook_enabled_events = Column(JSONB, nullable=False, default=list, server_default="[]")
    last_webhook_sent_at = Column(DateTime(timezone=True), nullable=True)
    last_webhook_received_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=False, server_default="false")
    last_tested_at = Column(DateTime(timezone=True), nullable=True)
    last_test_success = Column(Boolean, nullable=True)
    last_test_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    company = relationship("LogisticsCompany", back_populates="integrations")


class LogisticsWebhookEvent(Base):
    __tablename__ = "logistics_webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    direction = Column(String(20), nullable=False)
    event_type = Column(String(120), nullable=False, index=True)
    external_event_id = Column(String(255), nullable=True)
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    request_payload = Column(JSONB, nullable=True)
    response_payload = Column(JSONB, nullable=True)
    http_status = Column(Integer, nullable=True)
    processed = Column(Boolean, nullable=False, default=False, server_default="false")
    error_message = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    company = relationship("LogisticsCompany", back_populates="webhook_events")

    __table_args__ = (
        UniqueConstraint(
            "logistics_company_id",
            "external_event_id",
            name="uq_logistics_webhook_external_event",
        ),
    )


class ShippingZone(Base):
    __tablename__ = "shipping_zones"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(120), nullable=False)
    country = Column(String(100), nullable=False, server_default="Tanzania")
    scope = Column(
        Enum(LogisticsScope),
        nullable=False,
        default=LogisticsScope.local,
        server_default="local",
        index=True,
    )
    regions = Column(JSONB, nullable=False, default=list, server_default="[]")
    cities = Column(JSONB, nullable=False, default=list, server_default="[]")
    districts = Column(JSONB, nullable=False, default=list, server_default="[]")
    wards = Column(JSONB, nullable=False, default=list, server_default="[]")
    postal_codes = Column(JSONB, nullable=False, default=list, server_default="[]")
    coverage_geojson = Column(JSONB, nullable=True)
    covers_entire_country = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    rates = relationship(
        "ShippingRate", back_populates="zone", cascade="all, delete-orphan"
    )
    logistics_company = relationship("LogisticsCompany", back_populates="zones")

    __table_args__ = (
        UniqueConstraint(
            "logistics_company_id",
            "name",
            name="uq_shipping_zone_company_name",
        ),
    )


class ShippingMethod(Base):
    __tablename__ = "shipping_methods"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    name = Column(String(120), nullable=False)
    service_code = Column(String(100), nullable=True, index=True)
    description = Column(Text, nullable=True)
    carrier_name = Column(String(120), nullable=True)
    scope = Column(
        Enum(LogisticsScope),
        nullable=False,
        default=LogisticsScope.local,
        server_default="local",
        index=True,
    )
    supports_cod = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    supports_tracking = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    min_delivery_days = Column(Integer, nullable=False, default=1)
    max_delivery_days = Column(Integer, nullable=False, default=7)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    rates = relationship(
        "ShippingRate", back_populates="method", cascade="all, delete-orphan"
    )
    logistics_company = relationship("LogisticsCompany", back_populates="services")

    __table_args__ = (
        UniqueConstraint(
            "logistics_company_id", "name", name="uq_shipping_method_company_name"
        ),
        UniqueConstraint(
            "logistics_company_id",
            "service_code",
            name="uq_shipping_method_company_service_code",
        ),
        CheckConstraint(
            "min_delivery_days >= 0", name="ck_shipping_method_min_days_nonnegative"
        ),
        CheckConstraint(
            "max_delivery_days >= min_delivery_days",
            name="ck_shipping_method_days_valid",
        ),
    )


class ShippingRate(Base):
    __tablename__ = "shipping_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    zone_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipping_zones.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    method_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipping_methods.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rate_type = Column(
        Enum(ShippingRateType), nullable=False, default=ShippingRateType.flat
    )
    currency = Column(String(10), nullable=False, default="TZS", server_default="TZS")
    base_amount = Column(Numeric(18, 2), nullable=False, default=0)
    amount_per_kg = Column(Numeric(18, 2), nullable=False, default=0)

    # Phase 2 Task 5: provider-owned distance pricing configuration.
    amount_per_km = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    minimum_fee = Column(Numeric(18, 2), nullable=True)
    maximum_fee = Column(Numeric(18, 2), nullable=True)
    max_distance_km = Column(Numeric(10, 3), nullable=True)

    free_shipping_threshold = Column(Numeric(18, 2), nullable=True)
    min_weight_kg = Column(Numeric(10, 3), nullable=True)
    max_weight_kg = Column(Numeric(10, 3), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    zone = relationship("ShippingZone", back_populates="rates")
    method = relationship("ShippingMethod", back_populates="rates")

    __table_args__ = (
        UniqueConstraint("zone_id", "method_id", name="uq_shipping_rate_zone_method"),
        CheckConstraint("base_amount >= 0", name="ck_shipping_rate_base_nonnegative"),
        CheckConstraint(
            "amount_per_kg >= 0", name="ck_shipping_rate_perkg_nonnegative"
        ),
        CheckConstraint(
            "amount_per_km >= 0", name="ck_shipping_rate_perkm_nonnegative"
        ),
        CheckConstraint(
            "minimum_fee IS NULL OR minimum_fee >= 0",
            name="ck_shipping_rate_minimum_fee_nonnegative",
        ),
        CheckConstraint(
            "maximum_fee IS NULL OR maximum_fee >= minimum_fee",
            name="ck_shipping_rate_maximum_fee_valid",
        ),
        CheckConstraint(
            "max_distance_km IS NULL OR max_distance_km > 0",
            name="ck_shipping_rate_max_distance_positive",
        ),
        CheckConstraint(
            "free_shipping_threshold IS NULL OR free_shipping_threshold >= 0",
            name="ck_shipping_rate_threshold_nonnegative",
        ),
        CheckConstraint(
            "min_weight_kg IS NULL OR min_weight_kg >= 0",
            name="ck_shipping_rate_min_weight_nonnegative",
        ),
        CheckConstraint(
            "max_weight_kg IS NULL OR max_weight_kg >= min_weight_kg",
            name="ck_shipping_rate_weight_range",
        ),
    )



class CheckoutDeliveryQuote(Base):
    """Immutable customer-selected logistics quote used by order checkout.

    The route/pricing JSON snapshots are intentionally stored so later changes
    to seller locations, logistics rates or pricing strategy do not alter a
    quote already shown to the customer.
    """

    __tablename__ = "checkout_delivery_quotes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shipping_address_id = Column(
        UUID(as_uuid=True),
        ForeignKey("addresses.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipping_method_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipping_methods.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    shipping_rate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipping_rates.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    delivery_mode = Column(String(20), nullable=False, index=True)
    pricing_strategy = Column(String(50), nullable=False)
    rate_type = Column(String(50), nullable=False)
    currency = Column(String(10), nullable=False, default="TZS")

    seller_count = Column(Integer, nullable=False)
    billable_distance_km = Column(Numeric(10, 3), nullable=False)
    billable_seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    product_subtotal = Column(Numeric(18, 2), nullable=False)
    delivery_amount = Column(Numeric(18, 2), nullable=False)
    checkout_total_before_discounts = Column(Numeric(18, 2), nullable=False)

    cart_fingerprint = Column(String(64), nullable=False, index=True)

    pricing_breakdown = Column(JSONB, nullable=False, default=dict, server_default="{}")
    seller_routes_snapshot = Column(JSONB, nullable=False, default=list, server_default="[]")
    address_snapshot = Column(JSONB, nullable=False, default=dict, server_default="{}")

    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    used_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User")
    shipping_address = relationship("Address")
    logistics_company = relationship("LogisticsCompany")
    shipping_method = relationship("ShippingMethod")
    shipping_rate = relationship("ShippingRate")
    order = relationship("Order", back_populates="delivery_quote", uselist=False)

    __table_args__ = (
        CheckConstraint("seller_count > 0", name="ck_checkout_delivery_quote_seller_count"),
        CheckConstraint(
            "billable_distance_km >= 0",
            name="ck_checkout_delivery_quote_distance_nonnegative",
        ),
        CheckConstraint(
            "product_subtotal >= 0",
            name="ck_checkout_delivery_quote_subtotal_nonnegative",
        ),
        CheckConstraint(
            "delivery_amount >= 0",
            name="ck_checkout_delivery_quote_delivery_nonnegative",
        ),
        Index(
            "ix_checkout_delivery_quotes_user_expiry",
            "user_id",
            "expires_at",
        ),
    )


#
# ORDERS
#


class OrderStatus(str, enum.Enum):
    pending = "pending"
    paid = "paid"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


class Order(Base):
    __tablename__ = "orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    shipping_address_id = Column(
        UUID(as_uuid=True), ForeignKey("addresses.id"), nullable=True
    )
    delivery_quote_id = Column(
        UUID(as_uuid=True),
        ForeignKey("checkout_delivery_quotes.id", ondelete="RESTRICT"),
        nullable=True,
        unique=True,
        index=True,
    )
    shipping_rate_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipping_rates.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    shipping_method_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipping_methods.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    shipping_method_name = Column(String(120), nullable=True)
    shipping_carrier = Column(String(120), nullable=True)
    estimated_delivery_from = Column(DateTime(timezone=True), nullable=True)
    estimated_delivery_to = Column(DateTime(timezone=True), nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    currency = Column(String(10), default="TZS", nullable=False)
    subtotal = Column(Numeric(18, 2), nullable=False, default=0)

    # Checkout discount snapshots. `discount_amount` remains the combined
    # product-level discount for backward compatibility.
    coupon_discount_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    promotion_discount_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    discount_amount = Column(Numeric(18, 2), nullable=False, default=0)

    original_shipping_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    shipping_discount_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    shipping_amount = Column(Numeric(18, 2), nullable=False, default=0)

    tax_amount = Column(Numeric(18, 2), nullable=False, default=0)
    total = Column(Numeric(18, 2), nullable=False, default=0)

    coupon_code = Column(String(50), nullable=True)
    promotion_code = Column(String(50), nullable=True)
    promotion_seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    delivery_mode = Column(String(20), nullable=True)
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    shipping_address = relationship("Address")
    delivery_quote = relationship(
        "CheckoutDeliveryQuote", back_populates="order", uselist=False
    )
    items = relationship(
        "OrderItem", back_populates="order", cascade="all, delete-orphan"
    )
    status_history = relationship(
        "OrderStatusHistory", back_populates="order", cascade="all, delete-orphan"
    )
    payments = relationship("Payment", back_populates="order")
    shipping_rate = relationship("ShippingRate")
    shipping_method = relationship("ShippingMethod")
    shipments = relationship(
        "Shipment", back_populates="order", cascade="all, delete-orphan"
    )
    inventory_reservations = relationship(
        "InventoryReservation", back_populates="order", cascade="all, delete-orphan"
    )
    refunds = relationship(
        "Refund", back_populates="order", cascade="all, delete-orphan"
    )
    seller_orders = relationship(
        "SellerOrder", back_populates="order", cascade="all, delete-orphan"
    )


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(
        UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True
    )
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=False)

    product_name = Column(String(255), nullable=False)
    variant_name = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)

    # Gross marketplace line amount before seller-funded promotion.
    total_price = Column(Numeric(18, 2), nullable=False)
    # Seller-funded product-promotion amount allocated to this line.
    promotion_discount_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    # Amount the customer owes for this line after seller-funded promotion.
    # Platform coupons are intentionally not deducted here because they are
    # platform-funded and should not reduce seller entitlement.
    customer_total = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")
    seller = relationship("Seller")
    commission = relationship(
        "OrderItemCommission",
        back_populates="order_item",
        uselist=False,
        cascade="all, delete-orphan",
    )
    refund_items = relationship("RefundItem", back_populates="order_item")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_order_item_quantity_positive"),
        CheckConstraint("unit_price >= 0", name="ck_order_item_unit_price_nonnegative"),
        CheckConstraint(
            "total_price >= 0", name="ck_order_item_total_price_nonnegative"
        ),
    )


class SellerOrder(Base):
    __tablename__ = "seller_orders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(SellerOrderStatus),
        nullable=False,
        default=SellerOrderStatus.new,
        server_default="new",
        index=True,
    )
    seller_subtotal = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    item_count = Column(Integer, nullable=False, default=0, server_default="0")
    accepted_at = Column(DateTime(timezone=True), nullable=True)
    processing_at = Column(DateTime(timezone=True), nullable=True)
    ready_to_ship_at = Column(DateTime(timezone=True), nullable=True)
    shipped_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_requested_at = Column(DateTime(timezone=True), nullable=True)
    cancellation_reason = Column(Text, nullable=True)
    seller_notes = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order = relationship("Order", back_populates="seller_orders")
    seller = relationship("Seller")
    packages = relationship(
        "SellerOrderPackage",
        back_populates="seller_order",
        cascade="all, delete-orphan",
    )
    messages = relationship(
        "SellerOrderMessage",
        back_populates="seller_order",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("order_id", "seller_id", name="uq_seller_order_order_seller"),
        CheckConstraint(
            "seller_subtotal >= 0", name="ck_seller_order_subtotal_nonnegative"
        ),
        CheckConstraint(
            "item_count >= 0", name="ck_seller_order_item_count_nonnegative"
        ),
    )


class SellerOrderPackage(Base):
    __tablename__ = "seller_order_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    package_label = Column(String(120), nullable=True)
    package_type = Column(String(50), nullable=False, default="parcel", server_default="parcel", index=True)
    contents_summary = Column(Text, nullable=True)

    weight_kg = Column(Numeric(10, 3), nullable=True)
    length_cm = Column(Numeric(10, 2), nullable=True)
    width_cm = Column(Numeric(10, 2), nullable=True)
    height_cm = Column(Numeric(10, 2), nullable=True)
    package_count = Column(Integer, nullable=False, default=1, server_default="1")

    fragile = Column(Boolean, nullable=False, default=False, server_default="false")
    keep_upright = Column(Boolean, nullable=False, default=False, server_default="false")
    temperature_sensitive = Column(Boolean, nullable=False, default=False, server_default="false")
    handling_instructions = Column(Text, nullable=True)

    declared_value = Column(Numeric(14, 2), nullable=True)
    declared_currency = Column(String(3), nullable=False, default="TZS", server_default="TZS")

    notes = Column(Text, nullable=True)
    is_ready = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    prepared_at = Column(DateTime(timezone=True), nullable=True)
    sealed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    seller_order = relationship("SellerOrder", back_populates="packages")
    attachments = relationship(
        "SellerOrderPackageAttachment",
        back_populates="package",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "package_count > 0", name="ck_seller_order_package_count_positive"
        ),
        CheckConstraint(
            "weight_kg IS NULL OR weight_kg >= 0",
            name="ck_seller_order_package_weight_nonnegative",
        ),
        CheckConstraint(
            "declared_value IS NULL OR declared_value >= 0",
            name="ck_seller_order_package_declared_value_nonnegative",
        ),
        CheckConstraint(
            "package_type IN ('parcel', 'box', 'envelope', 'crate', 'pallet', 'other')",
            name="ck_seller_order_package_type",
        ),
        Index(
            "ix_seller_order_packages_order_ready",
            "seller_order_id",
            "is_ready",
        ),
    )


class SellerOrderPackageAttachment(Base):
    __tablename__ = "seller_order_package_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    package_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_order_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_url = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(120), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    package = relationship("SellerOrderPackage", back_populates="attachments")


class SellerOrderMessage(Base):
    __tablename__ = "seller_order_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sender_role_label = Column(String(60), nullable=True)
    message = Column(Text, nullable=False)
    is_internal = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    seller_order = relationship("SellerOrder", back_populates="messages")
    sender = relationship("User")
    attachments = relationship(
        "SellerOrderMessageAttachment",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class SellerOrderMessageAttachment(Base):
    __tablename__ = "seller_order_message_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    message_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_order_messages.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    file_url = Column(Text, nullable=False)
    file_name = Column(String(255), nullable=True)
    mime_type = Column(String(120), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    message = relationship("SellerOrderMessage", back_populates="attachments")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="status_history")
    created_by = relationship("User")


#
# SHIPMENTS AND TRACKING
#


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shipping_method_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipping_methods.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status = Column(
        Enum(ShipmentStatus),
        nullable=False,
        default=ShipmentStatus.pending,
        server_default="pending",
        index=True,
    )
    carrier_name = Column(String(120), nullable=True)
    tracking_number = Column(String(150), nullable=True, unique=True, index=True)
    estimated_delivery_from = Column(DateTime(timezone=True), nullable=True)
    estimated_delivery_to = Column(DateTime(timezone=True), nullable=True)
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order = relationship("Order", back_populates="shipments")
    seller = relationship("Seller")
    shipping_method = relationship("ShippingMethod")
    logistics_company = relationship("LogisticsCompany", back_populates="shipments")
    items = relationship(
        "ShipmentItem", back_populates="shipment", cascade="all, delete-orphan"
    )
    tracking_events = relationship(
        "ShipmentTrackingEvent",
        back_populates="shipment",
        cascade="all, delete-orphan",
        order_by="ShipmentTrackingEvent.created_at",
    )

    __table_args__ = (
        UniqueConstraint("order_id", "seller_id", name="uq_shipment_order_seller"),
    )


class ShipmentItem(Base):
    __tablename__ = "shipment_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    quantity = Column(Integer, nullable=False)

    shipment = relationship("Shipment", back_populates="items")
    order_item = relationship("OrderItem")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_shipment_item_quantity_positive"),
    )


class ShipmentTrackingEvent(Base):
    __tablename__ = "shipment_tracking_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(Enum(ShipmentStatus), nullable=False)
    location = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    shipment = relationship("Shipment", back_populates="tracking_events")
    created_by = relationship("User")


class LogisticsPickupJob(Base):
    __tablename__ = "logistics_pickup_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    assigned_membership_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_company_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status = Column(
        Enum(PickupJobStatus),
        nullable=False,
        default=PickupJobStatus.scheduled,
        server_default="scheduled",
        index=True,
    )
    scheduled_for = Column(DateTime(timezone=True), nullable=True, index=True)
    pickup_reference = Column(String(120), nullable=False, unique=True, index=True)
    dispatcher_notes = Column(Text, nullable=True)
    courier_notes = Column(Text, nullable=True)
    failure_reason = Column(String(255), nullable=True)
    assigned_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    arrived_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    shipment = relationship("Shipment")
    assigned_membership = relationship("LogisticsCompanyUser")
    created_by = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "status != 'failed' OR failure_reason IS NOT NULL",
            name="ck_logistics_pickup_job_failed_reason",
        ),
    )



class ShipmentPickupProof(Base):
    """Courier pickup evidence reviewed by the customer.

    This is an auditable verification checkpoint. It does NOT release seller
    settlement directly; later settlement logic consumes approved/auto-approved
    proofs together with the seller handover.
    """

    __tablename__ = "shipment_pickup_proofs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    handover_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipment_handovers.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    photo_url = Column(Text, nullable=False)
    original_filename = Column(String(255), nullable=True)
    mime_type = Column(String(120), nullable=False)
    file_size = Column(Integer, nullable=False)

    pickup_latitude = Column(Numeric(10, 7), nullable=False)
    pickup_longitude = Column(Numeric(10, 7), nullable=False)
    courier_reference = Column(String(180), nullable=True)
    notes = Column(Text, nullable=True)

    status = Column(
        String(32),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    review_deadline = Column(DateTime(timezone=True), nullable=False, index=True)

    customer_reviewed_at = Column(DateTime(timezone=True), nullable=True)
    customer_reviewed_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    problem_reason = Column(String(80), nullable=True)
    problem_notes = Column(Text, nullable=True)

    uploaded_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    shipment = relationship("Shipment")
    handover = relationship("ShipmentHandover")
    order = relationship("Order")
    customer = relationship("User", foreign_keys=[customer_id])
    seller = relationship("Seller")
    logistics_company = relationship("LogisticsCompany")
    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
    customer_reviewed_by = relationship("User", foreign_keys=[customer_reviewed_by_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','disputed','auto_approved')",
            name="ck_shipment_pickup_proof_status",
        ),
        CheckConstraint(
            "pickup_latitude BETWEEN -90 AND 90",
            name="ck_shipment_pickup_proof_latitude",
        ),
        CheckConstraint(
            "pickup_longitude BETWEEN -180 AND 180",
            name="ck_shipment_pickup_proof_longitude",
        ),
        CheckConstraint(
            "file_size > 0",
            name="ck_shipment_pickup_proof_file_size_positive",
        ),
        Index(
            "ix_shipment_pickup_proofs_customer_status_created",
            "customer_id",
            "status",
            "created_at",
        ),
    )


class ShipmentHandover(Base):
    """Auditable seller-to-logistics handover checkpoint.

    This record deliberately does not release funds. It captures that the
    assigned logistics company arrived and that the seller confirmed physical
    handover. Later pickup-proof/customer-verification phases can consume this
    immutable checkpoint safely.
    """

    __tablename__ = "shipment_handovers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    seller_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_orders.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    logistics_company_id = Column(
        UUID(as_uuid=True),
        ForeignKey("logistics_companies.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    status = Column(
        String(32),
        nullable=False,
        default="awaiting_courier",
        server_default="awaiting_courier",
        index=True,
    )

    courier_arrived_at = Column(DateTime(timezone=True), nullable=True)
    courier_arrived_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    courier_arrival_latitude = Column(Numeric(10, 7), nullable=True)
    courier_arrival_longitude = Column(Numeric(10, 7), nullable=True)
    courier_arrival_notes = Column(Text, nullable=True)

    seller_confirmed_at = Column(DateTime(timezone=True), nullable=True)
    seller_confirmed_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    seller_confirmation_notes = Column(Text, nullable=True)

    # Immutable operational snapshots. These protect historical handovers if a
    # seller later edits the pickup point or package preparation data.
    pickup_snapshot = Column(JSONB, nullable=False, default=dict, server_default="{}")
    package_snapshot = Column(JSONB, nullable=False, default=list, server_default="[]")

    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    shipment = relationship("Shipment")
    seller_order = relationship("SellerOrder")
    seller = relationship("Seller")
    logistics_company = relationship("LogisticsCompany")
    courier_arrived_by = relationship("User", foreign_keys=[courier_arrived_by_id])
    seller_confirmed_by = relationship("User", foreign_keys=[seller_confirmed_by_id])

    __table_args__ = (
        CheckConstraint(
            "status IN ('awaiting_courier', 'courier_arrived', 'seller_confirmed')",
            name="ck_shipment_handover_status",
        ),
        CheckConstraint(
            "courier_arrival_latitude IS NULL OR courier_arrival_latitude BETWEEN -90 AND 90",
            name="ck_shipment_handover_arrival_latitude",
        ),
        CheckConstraint(
            "courier_arrival_longitude IS NULL OR courier_arrival_longitude BETWEEN -180 AND 180",
            name="ck_shipment_handover_arrival_longitude",
        ),
        Index(
            "ix_shipment_handovers_company_status",
            "logistics_company_id",
            "status",
            "created_at",
        ),
        Index(
            "ix_shipment_handovers_seller_status",
            "seller_id",
            "status",
            "created_at",
        ),
    )


#
# EXTERNAL DELIVERY INTEGRATION
#


class DeliveryJob(Base):
    __tablename__ = "delivery_jobs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    seller_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    provider = Column(String(100), nullable=False, index=True)
    external_delivery_id = Column(String(255), nullable=False, index=True)
    status = Column(
        Enum(DeliveryStatus),
        nullable=False,
        default=DeliveryStatus.created,
        server_default="created",
        index=True,
    )
    tracking_number = Column(String(150), nullable=True, index=True)
    tracking_url = Column(Text, nullable=True)
    delivery_fee = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(10), nullable=False, default="TZS", server_default="TZS")
    courier_name = Column(String(150), nullable=True)
    courier_phone = Column(String(50), nullable=True)
    estimated_pickup_at = Column(DateTime(timezone=True), nullable=True)
    estimated_delivery_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    request_payload = Column(JSONB, nullable=True)
    provider_response = Column(JSONB, nullable=True)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    shipment = relationship("Shipment")
    seller_order = relationship("SellerOrder")

    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_delivery_id",
            name="uq_delivery_job_provider_external_id",
        ),
        CheckConstraint(
            "delivery_fee IS NULL OR delivery_fee >= 0",
            name="ck_delivery_job_fee_nonnegative",
        ),
    )


#
# INVENTORY
#


class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True), ForeignKey("products.id"), nullable=False, index=True
    )
    variant_id = Column(
        UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True
    )

    quantity = Column(Integer, nullable=False, default=0)
    reserved_quantity = Column(Integer, nullable=False, default=0)
    available_quantity = Column(Integer, nullable=False, default=0)

    warehouse_location = Column(String(255), nullable=True)
    low_stock_threshold = Column(Integer, default=10)
    restock_date = Column(DateTime(timezone=True), nullable=True)

    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    updated_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)

    product = relationship("Product")
    variant = relationship("ProductVariant")
    updated_by = relationship("User")
    reservations = relationship("InventoryReservation", back_populates="inventory")

    __table_args__ = (
        CheckConstraint("quantity >= 0", name="ck_inventory_quantity_nonnegative"),
        CheckConstraint(
            "reserved_quantity >= 0", name="ck_inventory_reserved_nonnegative"
        ),
        CheckConstraint(
            "reserved_quantity <= quantity", name="ck_inventory_reserved_lte_quantity"
        ),
        CheckConstraint(
            "available_quantity = quantity - reserved_quantity",
            name="ck_inventory_available_consistent",
        ),
        Index("ix_inventory_product_variant", "product_id", "variant_id", unique=True),
        Index(
            "uq_inventory_product_without_variant",
            "product_id",
            unique=True,
            postgresql_where=(variant_id.is_(None)),
        ),
    )


class InventoryReservation(Base):
    __tablename__ = "inventory_reservations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False)
    status = Column(
        Enum(InventoryReservationStatus),
        nullable=False,
        default=InventoryReservationStatus.active,
        server_default="active",
        index=True,
    )
    expires_at = Column(DateTime(timezone=True), nullable=False, index=True)
    committed_at = Column(DateTime(timezone=True), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    inventory = relationship("Inventory", back_populates="reservations")
    order = relationship("Order", back_populates="inventory_reservations")
    order_item = relationship("OrderItem")
    user = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "quantity > 0", name="ck_inventory_reservation_quantity_positive"
        ),
        Index("ix_inventory_reservation_active_expiry", "status", "expires_at"),
    )


#
# PAYMENTS
#


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    refunded = "refunded"
    cancelled = "cancelled"


class PaymentMethod(str, enum.Enum):
    mobile_money = "mobile_money"
    bank_transfer = "bank_transfer"
    card = "card"
    cash_on_delivery = "cash_on_delivery"
    xerin_pay = "xerin_pay"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), default="TZS", nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    provider = Column(String(100), nullable=True)  # e.g. "mpesa", "airtel_money"
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)

    provider_transaction_id = Column(
        String(255), nullable=True, unique=True, index=True
    )
    provider_response = Column(JSONB, nullable=True)
    failure_reason = Column(Text, nullable=True)

    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order = relationship("Order", back_populates="payments")
    user = relationship("User")
    transactions = relationship(
        "PaymentTransaction", back_populates="payment", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payment_amount_nonnegative"),
    )


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_type = Column(
        String(50), nullable=False
    )  # initiate, callback, refund, etc.
    status = Column(String(50), nullable=False)
    amount = Column(Numeric(18, 2), nullable=True)
    provider_response = Column(JSONB, nullable=True)
    idempotency_key = Column(String(255), nullable=True, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment", back_populates="transactions")


#
# PAYMENT ADMINISTRATION / PROVIDERS / FX / RISK
#


class FinanceSettings(Base):
    __tablename__ = "finance_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_key = Column(
        String(30),
        nullable=False,
        unique=True,
        default="default",
        server_default="default",
    )

    default_payment_provider_code = Column(String(80), nullable=True)
    settlement_currency = Column(
        String(10), nullable=False, default="TZS", server_default="TZS"
    )

    minimum_payout_amount = Column(
        Numeric(18, 2), nullable=False, default=1000, server_default="1000"
    )
    payout_fee_type = Column(
        String(30), nullable=False, default="fixed", server_default="fixed"
    )
    payout_fee_value = Column(
        Numeric(18, 4), nullable=False, default=0, server_default="0"
    )
    payout_processing_days = Column(
        Integer, nullable=False, default=1, server_default="1"
    )
    auto_payout_enabled = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )

    escrow_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    auto_release_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    allow_partial_release = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    hold_commission_until_release = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "minimum_payout_amount >= 0", name="ck_finance_minimum_payout_nonnegative"
        ),
        CheckConstraint(
            "payout_fee_value >= 0", name="ck_finance_payout_fee_nonnegative"
        ),
        CheckConstraint(
            "payout_processing_days >= 0",
            name="ck_finance_payout_processing_days_nonnegative",
        ),
        CheckConstraint(
            "payout_fee_type IN ('fixed','percentage')",
            name="ck_finance_payout_fee_type",
        ),
    )


class EscrowHold(Base):
    __tablename__ = "escrow_holds"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    seller_release_shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seller_release_handover_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipment_handovers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seller_release_proof_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipment_pickup_proofs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    seller_release_trigger = Column(String(40), nullable=True)
    seller_release_verified_at = Column(DateTime(timezone=True), nullable=True, index=True)

    currency = Column(String(10), nullable=False)
    gross_amount = Column(Numeric(18, 2), nullable=False)
    seller_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    commission_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    refunded_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    released_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )

    status = Column(
        String(30), nullable=False, default="held", server_default="held", index=True
    )
    release_after = Column(DateTime(timezone=True), nullable=True, index=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    disputed_at = Column(DateTime(timezone=True), nullable=True)
    refunded_at = Column(DateTime(timezone=True), nullable=True)

    reference = Column(String(180), nullable=False, unique=True, index=True)
    note = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    payment = relationship("Payment")
    order = relationship("Order")
    seller = relationship("Seller")
    seller_release_shipment = relationship("Shipment", foreign_keys=[seller_release_shipment_id])
    seller_release_handover = relationship("ShipmentHandover", foreign_keys=[seller_release_handover_id])
    seller_release_proof = relationship("ShipmentPickupProof", foreign_keys=[seller_release_proof_id])
    events = relationship(
        "EscrowEvent", back_populates="hold", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("gross_amount >= 0", name="ck_escrow_gross_nonnegative"),
        CheckConstraint("seller_amount >= 0", name="ck_escrow_seller_nonnegative"),
        CheckConstraint(
            "commission_amount >= 0", name="ck_escrow_commission_nonnegative"
        ),
        CheckConstraint("refunded_amount >= 0", name="ck_escrow_refunded_nonnegative"),
        CheckConstraint("released_amount >= 0", name="ck_escrow_released_nonnegative"),
        CheckConstraint(
            "seller_amount + commission_amount <= gross_amount",
            name="ck_escrow_allocations_within_gross",
        ),
        CheckConstraint(
            "refunded_amount + released_amount <= gross_amount",
            name="ck_escrow_settled_within_gross",
        ),
        CheckConstraint(
            "(seller_release_shipment_id IS NULL AND seller_release_handover_id IS NULL AND seller_release_proof_id IS NULL) OR (seller_release_shipment_id IS NOT NULL AND seller_release_handover_id IS NOT NULL AND seller_release_proof_id IS NOT NULL)",
            name="ck_escrow_seller_release_evidence_complete",
        ),
    )


class EscrowEvent(Base):
    __tablename__ = "escrow_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    escrow_hold_id = Column(
        UUID(as_uuid=True),
        ForeignKey("escrow_holds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(40), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=True)
    note = Column(Text, nullable=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    hold = relationship("EscrowHold", back_populates="events")
    created_by = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "amount IS NULL OR amount >= 0", name="ck_escrow_event_amount_nonnegative"
        ),
    )


class PaymentProviderConfig(Base):
    __tablename__ = "payment_provider_configs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(120), nullable=False)
    code = Column(String(80), nullable=False, unique=True, index=True)
    provider_type = Column(
        String(50), nullable=False, default="gateway", server_default="gateway"
    )
    status = Column(
        String(30),
        nullable=False,
        default="active",
        server_default="active",
        index=True,
    )
    supported_currencies = Column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    supported_methods = Column(JSONB, nullable=False, default=list, server_default="[]")
    environment = Column(String(30), nullable=True)
    is_default = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class PaymentCurrency(Base):
    __tablename__ = "payment_currencies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(10), nullable=False, unique=True, index=True)
    name = Column(String(80), nullable=False)
    symbol = Column(String(12), nullable=False)
    is_base = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    decimal_places = Column(Integer, nullable=False, default=2, server_default="2")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class PaymentFxRate(Base):
    __tablename__ = "payment_fx_rates"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    base_currency = Column(String(10), nullable=False, index=True)
    quote_currency = Column(String(10), nullable=False, index=True)
    rate = Column(Numeric(20, 8), nullable=False)
    source = Column(String(120), nullable=True)
    effective_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    is_active = Column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (
        CheckConstraint("rate > 0", name="ck_payment_fx_rate_positive"),
        CheckConstraint(
            "base_currency <> quote_currency", name="ck_payment_fx_distinct_currency"
        ),
        UniqueConstraint(
            "base_currency",
            "quote_currency",
            "effective_at",
            name="uq_payment_fx_pair_effective",
        ),
    )


class PaymentCountry(Base):
    __tablename__ = "payment_countries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(3), nullable=False, unique=True, index=True)
    name = Column(String(100), nullable=False)
    currency_code = Column(String(10), nullable=False, index=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    payments_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    payouts_enabled = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class PaymentDispute(Base):
    __tablename__ = "payment_disputes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    reason = Column(Text, nullable=False)
    status = Column(
        String(30), nullable=False, default="open", server_default="open", index=True
    )
    provider = Column(String(100), nullable=True, index=True)
    provider_reference = Column(String(255), nullable=True, index=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    payment = relationship("Payment")
    order = relationship("Order")
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_payment_dispute_amount_nonnegative"),
    )


class PaymentRiskEvent(Base):
    __tablename__ = "payment_risk_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_type = Column(String(80), nullable=False, index=True)
    severity = Column(
        String(20),
        nullable=False,
        default="medium",
        server_default="medium",
        index=True,
    )
    status = Column(
        String(30), nullable=False, default="open", server_default="open", index=True
    )
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    score = Column(Numeric(8, 2), nullable=True)
    reason = Column(Text, nullable=True)
    resolution_note = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    payment = relationship("Payment")
    order = relationship("Order")
    user = relationship("User")


class PaymentReconciliationRecord(Base):
    __tablename__ = "payment_reconciliation_records"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    provider = Column(String(100), nullable=True, index=True)
    provider_reference = Column(String(255), nullable=True, index=True)
    expected_amount = Column(Numeric(18, 2), nullable=False)
    provider_amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    difference = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    status = Column(
        String(30),
        nullable=False,
        default="pending",
        server_default="pending",
        index=True,
    )
    reconciliation_note = Column(Text, nullable=True)
    reconciled_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    payment = relationship("Payment")
    order = relationship("Order")


#
# MARKETPLACE SETTINGS
#


class MarketplaceSettings(Base):
    __tablename__ = "marketplace_settings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    singleton_key = Column(
        Integer, nullable=False, default=1, server_default="1", unique=True
    )
    escrow_release_hours = Column(Integer, nullable=True)
    dispute_period_hours = Column(Integer, nullable=True)
    cod_allowed = Column(Boolean, nullable=True)
    international_delivery_allowed = Column(Boolean, nullable=True)
    updated_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    updated_by = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "singleton_key = 1", name="ck_marketplace_settings_singleton_key"
        ),
        CheckConstraint(
            "escrow_release_hours IS NULL OR escrow_release_hours BETWEEN 1 AND 720",
            name="ck_marketplace_settings_escrow_release_hours",
        ),
        CheckConstraint(
            "dispute_period_hours IS NULL OR dispute_period_hours BETWEEN 1 AND 720",
            name="ck_marketplace_settings_dispute_period_hours",
        ),
    )


#
# MARKETPLACE COMMISSIONS AND LEDGER
#


class CommissionRule(Base):
    __tablename__ = "commission_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(150), nullable=False)
    scope = Column(
        Enum(
            CommissionScope,
            name="commissionscope",
            values_callable=lambda enum_cls: [member.value for member in enum_cls],
            create_type=False,
        ),
        nullable=False,
        index=True,
    )
    rule_type = Column(
        Enum(CommissionRuleType), nullable=False, default=CommissionRuleType.percentage
    )
    rate = Column(Numeric(10, 4), nullable=False)
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    priority = Column(Integer, nullable=False, default=0, server_default="0")
    is_active = Column(
        Boolean, nullable=False, default=True, server_default="true", index=True
    )
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    seller = relationship("Seller", back_populates="commission_rules")
    category = relationship("Category")
    product = relationship("Product")
    created_by = relationship("User")

    __table_args__ = (
        CheckConstraint("rate >= 0", name="ck_commission_rule_rate_nonnegative"),
        CheckConstraint(
            "rule_type <> 'percentage' OR rate <= 100",
            name="ck_commission_percentage_lte_100",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_commission_rule_date_range",
        ),
        CheckConstraint(
            "(scope = 'global' AND seller_id IS NULL AND category_id IS NULL AND product_id IS NULL) OR (scope = 'seller' AND seller_id IS NOT NULL AND category_id IS NULL AND product_id IS NULL) OR (scope = 'category' AND category_id IS NOT NULL AND seller_id IS NULL AND product_id IS NULL) OR (scope = 'product' AND product_id IS NOT NULL AND seller_id IS NULL AND category_id IS NULL)",
            name="ck_commission_rule_scope_target",
        ),
    )


class OrderItemCommission(Base):
    __tablename__ = "order_item_commissions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    commission_rule_id = Column(
        UUID(as_uuid=True),
        ForeignKey("commission_rules.id", ondelete="SET NULL"),
        nullable=True,
    )
    currency = Column(String(10), nullable=False)
    gross_amount = Column(Numeric(18, 2), nullable=False)
    commission_rate = Column(Numeric(10, 4), nullable=False)
    commission_amount = Column(Numeric(18, 2), nullable=False)
    seller_net_amount = Column(Numeric(18, 2), nullable=False)
    processing_fee = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    tax_amount = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    order_item = relationship("OrderItem", back_populates="commission")
    seller = relationship("Seller", back_populates="commission_records")
    rule = relationship("CommissionRule")
    transactions = relationship(
        "MarketplaceTransaction",
        back_populates="commission_record",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "gross_amount >= 0", name="ck_item_commission_gross_nonnegative"
        ),
        CheckConstraint(
            "commission_amount >= 0", name="ck_item_commission_amount_nonnegative"
        ),
        CheckConstraint(
            "seller_net_amount >= 0", name="ck_item_commission_net_nonnegative"
        ),
    )


class MarketplaceTransaction(Base):
    __tablename__ = "marketplace_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    commission_record_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_item_commissions.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    transaction_type = Column(
        Enum(MarketplaceTransactionType), nullable=False, index=True
    )
    currency = Column(String(10), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    reference = Column(String(180), nullable=False, unique=True, index=True)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    commission_record = relationship(
        "OrderItemCommission", back_populates="transactions"
    )

    __table_args__ = (
        CheckConstraint(
            "amount >= 0", name="ck_marketplace_transaction_amount_nonnegative"
        ),
    )


#
# COUPONS
#


class Coupon(Base):
    __tablename__ = "coupons"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(Text, nullable=True)

    discount_type = Column(String(20), nullable=False)  # percentage, fixed_amount
    discount_value = Column(Numeric(18, 2), nullable=False)
    minimum_order_amount = Column(Numeric(18, 2), nullable=True)
    maximum_discount_amount = Column(Numeric(18, 2), nullable=True)

    usage_limit = Column(Integer, nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)
    is_active = Column(Boolean, default=True)

    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    created_by = relationship("User")

    __table_args__ = (
        CheckConstraint("discount_value > 0", name="ck_coupon_discount_value_positive"),
        CheckConstraint(
            "usage_limit IS NULL OR usage_limit >= 0",
            name="ck_coupon_usage_limit_nonnegative",
        ),
        CheckConstraint("usage_count >= 0", name="ck_coupon_usage_count_nonnegative"),
        CheckConstraint(
            "valid_until IS NULL OR valid_from IS NULL OR valid_until > valid_from",
            name="ck_coupon_valid_range",
        ),
    )


class Store(Base):
    __tablename__ = "stores"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        unique=True,
        nullable=False,
        index=True,
    )

    store_name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)

    description = Column(Text, nullable=True)
    about = Column(Text, nullable=True)

    logo_url = Column(Text, nullable=True)
    banner_url = Column(Text, nullable=True)
    theme_color = Column(
        String(7), nullable=False, default="#111827", server_default="#111827"
    )
    secondary_color = Column(
        String(7), nullable=False, default="#ffffff", server_default="#ffffff"
    )

    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(30), nullable=True)
    whatsapp_phone = Column(String(30), nullable=True)
    website_url = Column(Text, nullable=True)

    country = Column(String(100), nullable=True)
    region = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    ward = Column(String(100), nullable=True)
    street = Column(Text, nullable=True)

    latitude = Column(Float, nullable=True)
    longitude = Column(Float, nullable=True)

    opening_time = Column(Time, nullable=True)
    closing_time = Column(Time, nullable=True)

    shipping_policy = Column(Text, nullable=True)
    return_policy = Column(Text, nullable=True)
    privacy_policy = Column(Text, nullable=True)

    facebook_url = Column(Text, nullable=True)
    instagram_url = Column(Text, nullable=True)
    twitter_url = Column(Text, nullable=True)
    tiktok_url = Column(Text, nullable=True)
    youtube_url = Column(Text, nullable=True)

    status = Column(
        Enum(StoreStatus),
        nullable=False,
        default=StoreStatus.draft,
        index=True,
    )

    is_verified = Column(Boolean, default=False, nullable=False)
    is_featured = Column(Boolean, default=False, nullable=False)

    rating = Column(Numeric(3, 2), default=0, nullable=False)
    review_count = Column(Integer, default=0, nullable=False)
    followers_count = Column(Integer, default=0, nullable=False)

    vacation_mode = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    accept_orders = Column(Boolean, nullable=False, default=True, server_default="true")
    processing_days = Column(Integer, nullable=False, default=1, server_default="1")
    seo_title = Column(String(255), nullable=True)
    seo_description = Column(String(500), nullable=True)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    seller = relationship(
        "Seller",
        back_populates="store",
    )

    gallery_images = relationship(
        "StoreGalleryImage",
        back_populates="store",
        cascade="all, delete-orphan",
        order_by="StoreGalleryImage.display_order",
    )

    opening_hours = relationship(
        "StoreOpeningHour",
        back_populates="store",
        cascade="all, delete-orphan",
        order_by="StoreOpeningHour.day_number",
    )
    favorite_entries = relationship(
        "FavoriteStore", back_populates="store", cascade="all, delete-orphan"
    )


class StoreGalleryImage(Base):
    __tablename__ = "store_gallery_images"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    image_url = Column(
        Text,
        nullable=False,
    )

    caption = Column(
        String(255),
        nullable=True,
    )

    display_order = Column(
        Integer,
        nullable=False,
        default=0,
    )

    is_active = Column(
        Boolean,
        nullable=False,
        default=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    store = relationship(
        "Store",
        back_populates="gallery_images",
    )


class StoreOpeningHour(Base):
    __tablename__ = "store_opening_hours"

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    day_of_week = Column(
        Enum(DayOfWeek),
        nullable=False,
    )

    day_number = Column(
        Integer,
        nullable=False,
    )

    open_time = Column(Time, nullable=True)
    close_time = Column(Time, nullable=True)
    is_closed = Column(Boolean, default=False, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    store = relationship(
        "Store",
        back_populates="opening_hours",
    )

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "day_of_week",
            name="uq_store_opening_hours_store_day",
        ),
    )


#
# SELLER WALLETS AND PAYOUTS
#


class SellerWallet(Base):
    __tablename__ = "seller_wallets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    currency = Column(String(10), nullable=False, default="TZS", server_default="TZS")
    pending_balance = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    available_balance = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    reserved_balance = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    paid_out_balance = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    refunded_balance = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    debt_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    is_frozen = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    seller = relationship("Seller", back_populates="wallet")
    transactions = relationship(
        "WalletTransaction", back_populates="wallet", cascade="all, delete-orphan"
    )
    payouts = relationship("PayoutRequest", back_populates="wallet")
    __table_args__ = (
        CheckConstraint(
            "pending_balance >= 0 AND available_balance >= 0 AND reserved_balance >= 0 AND paid_out_balance >= 0 AND refunded_balance >= 0 AND debt_balance >= 0",
            name="ck_wallet_balances_nonnegative",
        ),
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_wallets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    transaction_type = Column(Enum(WalletTransactionType), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    reference = Column(String(180), nullable=False, unique=True, index=True)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    payout_request_id = Column(UUID(as_uuid=True), nullable=True, index=True)
    eligible_at = Column(DateTime(timezone=True), nullable=True, index=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    wallet = relationship("SellerWallet", back_populates="transactions")
    __table_args__ = (
        CheckConstraint("amount >= 0", name="ck_wallet_transaction_amount_nonnegative"),
    )


class PayoutRequest(Base):
    __tablename__ = "payout_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_wallets.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    payout_account_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_payout_accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    status = Column(
        Enum(PayoutStatus),
        nullable=False,
        default=PayoutStatus.pending,
        server_default="pending",
        index=True,
    )
    provider_reference = Column(String(180), nullable=True, unique=True)
    seller_note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    requested_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    processed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    wallet = relationship("SellerWallet", back_populates="payouts")
    seller = relationship("Seller")
    payout_account = relationship("SellerPayoutAccount")
    events = relationship(
        "PayoutEvent", back_populates="payout", cascade="all, delete-orphan"
    )
    __table_args__ = (CheckConstraint("amount > 0", name="ck_payout_amount_positive"),)


class PayoutEvent(Base):
    __tablename__ = "payout_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payout_request_id = Column(
        UUID(as_uuid=True),
        ForeignKey("payout_requests.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(Enum(PayoutStatus), nullable=False)
    note = Column(Text, nullable=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    payout = relationship("PayoutRequest", back_populates="events")
    created_by = relationship("User")


#
# LOGISTICS WALLETS AND PAYOUTS
#


class LogisticsWallet(Base):
    __tablename__ = "logistics_wallets"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(UUID(as_uuid=True), ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    currency = Column(String(10), nullable=False, default="TZS", server_default="TZS")
    pending_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    available_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    reserved_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    paid_out_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    refunded_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    debt_balance = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    is_frozen = Column(Boolean, nullable=False, default=False, server_default="false", index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    transactions = relationship("LogisticsWalletTransaction", back_populates="wallet", cascade="all, delete-orphan")
    payouts = relationship("LogisticsPayoutRequest", back_populates="wallet")
    __table_args__ = (CheckConstraint("pending_balance >= 0 AND available_balance >= 0 AND reserved_balance >= 0 AND paid_out_balance >= 0 AND refunded_balance >= 0 AND debt_balance >= 0", name="ck_logistics_wallet_balances_nonnegative"),)


class LogisticsPayoutAccount(Base):
    __tablename__ = "logistics_payout_accounts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    logistics_company_id = Column(UUID(as_uuid=True), ForeignKey("logistics_companies.id", ondelete="CASCADE"), nullable=False, index=True)
    account_type = Column(String(50), nullable=False)
    provider = Column(String(100), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_number = Column(String(255), nullable=False)
    currency = Column(String(10), nullable=False, default="TZS", server_default="TZS")
    is_default = Column(Boolean, nullable=False, default=False, server_default="false")
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    verification_status = Column(String(30), nullable=False, default="pending", server_default="pending", index=True)
    verification_note = Column(Text, nullable=True)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    __table_args__ = (UniqueConstraint("logistics_company_id", "provider", "account_number", name="uq_logistics_payout_account"), CheckConstraint("verification_status IN ('pending','verified','rejected')", name="ck_logistics_payout_account_verification"),)

    @property
    def masked_account_number(self):
        value = self.account_number or ""
        return "*" * max(0, len(value) - 4) + value[-4:]


class LogisticsPayoutRequest(Base):
    __tablename__ = "logistics_payout_requests"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("logistics_wallets.id", ondelete="RESTRICT"), nullable=False, index=True)
    logistics_company_id = Column(UUID(as_uuid=True), ForeignKey("logistics_companies.id", ondelete="RESTRICT"), nullable=False, index=True)
    payout_account_id = Column(UUID(as_uuid=True), ForeignKey("logistics_payout_accounts.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    status = Column(String(30), nullable=False, default="pending", server_default="pending", index=True)
    provider_reference = Column(String(180), nullable=True, unique=True)
    company_note = Column(Text, nullable=True)
    admin_note = Column(Text, nullable=True)
    requested_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    wallet = relationship("LogisticsWallet", back_populates="payouts")
    account = relationship("LogisticsPayoutAccount")
    events = relationship("LogisticsPayoutEvent", back_populates="payout", cascade="all, delete-orphan")
    __table_args__ = (CheckConstraint("amount > 0", name="ck_logistics_payout_amount_positive"), CheckConstraint("status IN ('pending','approved','processing','completed','rejected','failed','cancelled')", name="ck_logistics_payout_status"),)


class LogisticsPayoutEvent(Base):
    __tablename__ = "logistics_payout_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payout_request_id = Column(UUID(as_uuid=True), ForeignKey("logistics_payout_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False)
    note = Column(Text, nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    payout = relationship("LogisticsPayoutRequest", back_populates="events")


class LogisticsWalletTransaction(Base):
    __tablename__ = "logistics_wallet_transactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    wallet_id = Column(UUID(as_uuid=True), ForeignKey("logistics_wallets.id", ondelete="CASCADE"), nullable=False, index=True)
    transaction_type = Column(String(40), nullable=False, index=True)
    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), nullable=False)
    reference = Column(String(180), nullable=False, unique=True, index=True)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id", ondelete="SET NULL"), nullable=True, index=True)
    payout_request_id = Column(UUID(as_uuid=True), ForeignKey("logistics_payout_requests.id", ondelete="SET NULL"), nullable=True, index=True)
    eligible_at = Column(DateTime(timezone=True), nullable=True, index=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    wallet = relationship("LogisticsWallet", back_populates="transactions")
    __table_args__ = (CheckConstraint("amount >= 0", name="ck_logistics_wallet_transaction_amount_nonnegative"),)


#
# REFUNDS AND REVERSALS
#


class Refund(Base):
    __tablename__ = "refunds"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    requested_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(RefundStatus),
        nullable=False,
        default=RefundStatus.requested,
        server_default="requested",
        index=True,
    )
    reason = Column(Enum(RefundReason), nullable=False)
    reason_details = Column(Text, nullable=True)
    currency = Column(String(10), nullable=False)
    items_amount = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    shipping_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    tax_amount = Column(Numeric(18, 2), nullable=False, default=0, server_default="0")
    total_amount = Column(Numeric(18, 2), nullable=False)
    provider_reference = Column(String(180), nullable=True, unique=True, index=True)
    idempotency_key = Column(String(180), nullable=False, unique=True, index=True)
    admin_note = Column(Text, nullable=True)
    requested_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    reviewed_at = Column(DateTime(timezone=True), nullable=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    order = relationship("Order", back_populates="refunds")
    requested_by = relationship("User")
    items = relationship(
        "RefundItem", back_populates="refund", cascade="all, delete-orphan"
    )
    events = relationship(
        "RefundEvent",
        back_populates="refund",
        cascade="all, delete-orphan",
        order_by="RefundEvent.created_at",
    )
    __table_args__ = (
        CheckConstraint(
            "items_amount >= 0 AND shipping_amount >= 0 AND tax_amount >= 0 AND total_amount > 0",
            name="ck_refund_amounts_valid",
        ),
    )


class RefundItem(Base):
    __tablename__ = "refund_items"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    refund_id = Column(
        UUID(as_uuid=True),
        ForeignKey("refunds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    quantity = Column(Integer, nullable=False)
    unit_amount = Column(Numeric(18, 2), nullable=False)
    refund_amount = Column(Numeric(18, 2), nullable=False)
    commission_reversal = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    seller_reversal = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    seller_debt_amount = Column(
        Numeric(18, 2), nullable=False, default=0, server_default="0"
    )
    restock = Column(Boolean, nullable=False, default=True, server_default="true")
    processed_at = Column(DateTime(timezone=True), nullable=True)
    refund = relationship("Refund", back_populates="items")
    order_item = relationship("OrderItem", back_populates="refund_items")
    seller = relationship("Seller")
    __table_args__ = (
        CheckConstraint(
            "quantity > 0 AND unit_amount >= 0 AND refund_amount > 0 AND commission_reversal >= 0 AND seller_reversal >= 0 AND seller_debt_amount >= 0",
            name="ck_refund_item_values_valid",
        ),
        UniqueConstraint(
            "refund_id", "order_item_id", name="uq_refund_item_per_refund"
        ),
    )


class RefundEvent(Base):
    __tablename__ = "refund_events"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    refund_id = Column(
        UUID(as_uuid=True),
        ForeignKey("refunds.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(Enum(RefundStatus), nullable=False)
    note = Column(Text, nullable=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    refund = relationship("Refund", back_populates="events")
    created_by = relationship("User")


class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    inventory_id = Column(
        UUID(as_uuid=True),
        ForeignKey("inventory.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    refund_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("refund_items.id", ondelete="SET NULL"),
        nullable=True,
        unique=True,
    )
    movement_type = Column(Enum(InventoryMovementType), nullable=False, index=True)
    quantity = Column(Integer, nullable=False)
    before_quantity = Column(Integer, nullable=False)
    after_quantity = Column(Integer, nullable=False)
    note = Column(Text, nullable=True)
    reference = Column(String(255), nullable=True, index=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    inventory = relationship("Inventory")
    refund_item = relationship("RefundItem")
    created_by = relationship("User")
    __table_args__ = (
        CheckConstraint(
            "quantity > 0 AND before_quantity >= 0 AND after_quantity >= 0",
            name="ck_inventory_movement_values_valid",
        ),
    )


#
# PHASE 4 TASK 1: AUDIT LOGS AND SECURITY EVENTS
#


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(120), nullable=False, index=True)
    resource_type = Column(String(120), nullable=True, index=True)
    resource_id = Column(String(180), nullable=True, index=True)
    http_method = Column(String(10), nullable=True)
    request_path = Column(String(500), nullable=True, index=True)
    response_status = Column(Integer, nullable=True, index=True)
    old_values = Column(JSONB, nullable=True)
    new_values = Column(JSONB, nullable=True)
    event_metadata = Column(JSONB, nullable=True)
    ip_address = Column(String(64), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=False, unique=True, index=True)
    severity = Column(
        Enum(AuditSeverity),
        nullable=False,
        default=AuditSeverity.info,
        server_default="info",
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    actor = relationship("User")


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    event_type = Column(Enum(SecurityEventType), nullable=False, index=True)
    severity = Column(
        Enum(AuditSeverity),
        nullable=False,
        default=AuditSeverity.warning,
        server_default="warning",
        index=True,
    )
    description = Column(Text, nullable=False)
    request_path = Column(String(500), nullable=True, index=True)
    http_method = Column(String(10), nullable=True)
    response_status = Column(Integer, nullable=True, index=True)
    ip_address = Column(String(64), nullable=True, index=True)
    user_agent = Column(Text, nullable=True)
    request_id = Column(String(100), nullable=False, unique=True, index=True)
    event_metadata = Column(JSONB, nullable=True)
    resolved = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    resolved_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    actor = relationship("User", foreign_keys=[actor_user_id])
    resolved_by = relationship("User", foreign_keys=[resolved_by_id])


# Phase 3 Task 12: customer reviews and seller ratings
class ProductReview(Base):
    __tablename__ = "product_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_item_id = Column(
        UUID(as_uuid=True),
        ForeignKey("order_items.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating = Column(Integer, nullable=False)
    title = Column(String(150), nullable=True)
    comment = Column(Text, nullable=True)
    verified_purchase = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    status = Column(
        Enum(ReviewStatus),
        nullable=False,
        default=ReviewStatus.pending,
        server_default="pending",
        index=True,
    )
    seller_reply = Column(Text, nullable=True)
    seller_replied_at = Column(DateTime(timezone=True), nullable=True)
    admin_reply = Column(Text, nullable=True)
    helpful_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    product = relationship("Product")
    order_item = relationship("OrderItem")
    customer = relationship("User")
    seller = relationship("Seller")
    images = relationship(
        "ReviewImage", back_populates="product_review", cascade="all, delete-orphan"
    )
    votes = relationship(
        "ReviewVote", back_populates="product_review", cascade="all, delete-orphan"
    )
    reports = relationship(
        "ReviewReport", back_populates="product_review", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_product_review_rating"),
        CheckConstraint("helpful_count >= 0", name="ck_product_review_helpful_count"),
        UniqueConstraint(
            "customer_id", "order_item_id", name="uq_product_review_customer_order_item"
        ),
    )


class StoreReview(Base):
    __tablename__ = "store_reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("seller_orders.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rating = Column(Integer, nullable=False)
    title = Column(String(150), nullable=True)
    comment = Column(Text, nullable=True)
    verified_purchase = Column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    status = Column(
        Enum(ReviewStatus),
        nullable=False,
        default=ReviewStatus.pending,
        server_default="pending",
        index=True,
    )
    seller_reply = Column(Text, nullable=True)
    seller_replied_at = Column(DateTime(timezone=True), nullable=True)
    helpful_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    store = relationship("Store")
    seller_order = relationship("SellerOrder")
    customer = relationship("User")
    reports = relationship(
        "ReviewReport", back_populates="store_review", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_store_review_rating"),
        CheckConstraint("helpful_count >= 0", name="ck_store_review_helpful_count"),
        UniqueConstraint(
            "customer_id",
            "seller_order_id",
            name="uq_store_review_customer_seller_order",
        ),
    )


class ReviewImage(Base):
    __tablename__ = "review_images"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_review_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    image_url = Column(Text, nullable=False)
    display_order = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    product_review = relationship("ProductReview", back_populates="images")


class ReviewVote(Base):
    __tablename__ = "review_votes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_review_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_reviews.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_helpful = Column(Boolean, nullable=False, default=True, server_default="true")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    product_review = relationship("ProductReview", back_populates="votes")
    __table_args__ = (
        UniqueConstraint(
            "product_review_id", "user_id", name="uq_review_vote_review_user"
        ),
    )


class ReviewReport(Base):
    __tablename__ = "review_reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_review_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_reviews.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    store_review_id = Column(
        UUID(as_uuid=True),
        ForeignKey("store_reviews.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    reported_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason = Column(Enum(ReviewReportReason), nullable=False)
    details = Column(Text, nullable=True)
    resolved = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    product_review = relationship("ProductReview", back_populates="reports")
    store_review = relationship("StoreReview", back_populates="reports")
    __table_args__ = (
        CheckConstraint(
            "(product_review_id IS NOT NULL) <> (store_review_id IS NOT NULL)",
            name="ck_review_report_single_target",
        ),
    )


# Customer care / marketplace support tickets.
# Access is controlled in routers by permissions, not hard-coded role names.
class SupportTicket(Base):
    __tablename__ = "support_tickets"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_number = Column(String(40), nullable=False, unique=True, index=True)
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    shipment_id = Column(
        UUID(as_uuid=True),
        ForeignKey("shipments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(80), nullable=True, index=True)
    channel = Column(
        String(50),
        nullable=False,
        default="customer",
        server_default="customer",
        index=True,
    )
    priority = Column(
        String(20),
        nullable=False,
        default="medium",
        server_default="medium",
        index=True,
    )
    status = Column(
        String(30), nullable=False, default="open", server_default="open", index=True
    )
    assigned_to_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    resolution_note = Column(Text, nullable=True)
    first_response_due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    resolution_due_at = Column(DateTime(timezone=True), nullable=False, index=True)
    first_responded_at = Column(DateTime(timezone=True), nullable=True)
    sla_breached_at = Column(DateTime(timezone=True), nullable=True, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    customer = relationship("User", foreign_keys=[customer_id])
    assigned_to = relationship("User", foreign_keys=[assigned_to_id])
    seller = relationship("Seller")
    order = relationship("Order")
    shipment = relationship("Shipment")
    messages = relationship(
        "SupportTicketMessage",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="SupportTicketMessage.created_at",
    )

    __table_args__ = (
        CheckConstraint(
            "priority IN ('low','medium','high','urgent')",
            name="ck_support_ticket_priority",
        ),
        CheckConstraint(
            "status IN ('open','pending','in_progress','processing','resolved','closed')",
            name="ck_support_ticket_status",
        ),
        Index(
            "ix_support_tickets_status_priority_created",
            "status",
            "priority",
            "created_at",
        ),
    )


class SupportTicketMessage(Base):
    __tablename__ = "support_ticket_messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ticket_id = Column(
        UUID(as_uuid=True),
        ForeignKey("support_tickets.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    sender_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    sender_role = Column(String(50), nullable=True)
    message = Column(Text, nullable=False)
    visibility = Column(String(20), nullable=False, default="all", server_default="all")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    ticket = relationship("SupportTicket", back_populates="messages")
    sender = relationship("User")

    __table_args__ = (
        CheckConstraint(
            "visibility IN ('all','internal')",
            name="ck_support_ticket_message_visibility",
        ),
    )


# Phase 3 Task 13: customer wishlist and favorite stores
class WishlistProduct(Base):
    __tablename__ = "wishlist_products"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user = relationship("User", back_populates="wishlist_products")
    product = relationship("Product", back_populates="wishlist_entries")

    __table_args__ = (
        UniqueConstraint(
            "user_id", "product_id", name="uq_wishlist_product_user_product"
        ),
        Index("ix_wishlist_products_user_created", "user_id", "created_at"),
    )


class FavoriteStore(Base):
    __tablename__ = "favorite_stores"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )

    user = relationship("User", back_populates="favorite_stores")
    store = relationship("Store", back_populates="favorite_entries")

    __table_args__ = (
        UniqueConstraint("user_id", "store_id", name="uq_favorite_store_user_store"),
        Index("ix_favorite_stores_user_created", "user_id", "created_at"),
    )


#
# PHASE 3 TASK 14: PROMOTIONS AND CAMPAIGNS
#


class Promotion(Base):
    __tablename__ = "promotions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name = Column(String(180), nullable=False)
    code = Column(String(50), unique=True, nullable=True, index=True)
    description = Column(Text, nullable=True)
    promotion_type = Column(String(40), nullable=False)
    discount_value = Column(Numeric(18, 2), nullable=False, default=0)
    minimum_order_amount = Column(Numeric(18, 2), nullable=True)
    maximum_discount_amount = Column(Numeric(18, 2), nullable=True)
    usage_limit = Column(Integer, nullable=True)
    usage_per_customer = Column(Integer, nullable=True)
    usage_count = Column(Integer, nullable=False, default=0, server_default="0")
    stackable = Column(Boolean, nullable=False, default=False, server_default="false")
    automatic = Column(Boolean, nullable=False, default=False, server_default="false")
    funding_source = Column(
        String(30), nullable=False, default="seller", server_default="seller"
    )
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    rules = relationship(
        "PromotionRule", back_populates="promotion", cascade="all, delete-orphan"
    )
    usages = relationship(
        "PromotionUsage", back_populates="promotion", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "discount_value >= 0", name="ck_promotion_discount_nonnegative"
        ),
        CheckConstraint(
            "usage_limit IS NULL OR usage_limit >= 0",
            name="ck_promotion_usage_limit_nonnegative",
        ),
        CheckConstraint(
            "usage_per_customer IS NULL OR usage_per_customer > 0",
            name="ck_promotion_customer_limit_positive",
        ),
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_promotion_valid_range",
        ),
    )


class PromotionRule(Base):
    __tablename__ = "promotion_rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promotion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("promotions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    rule_type = Column(String(40), nullable=False)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("categories.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    value = Column(JSONB, nullable=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    promotion = relationship("Promotion", back_populates="rules")


class PromotionUsage(Base):
    __tablename__ = "promotion_usages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    promotion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("promotions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    order_id = Column(
        UUID(as_uuid=True),
        ForeignKey("orders.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    discount_amount = Column(Numeric(18, 2), nullable=False)
    used_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    promotion = relationship("Promotion", back_populates="usages")

    __table_args__ = (
        CheckConstraint(
            "discount_amount >= 0", name="ck_promotion_usage_discount_nonnegative"
        ),
    )


class Campaign(Base):
    __tablename__ = "campaigns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(180), nullable=False)
    slug = Column(String(180), unique=True, nullable=False, index=True)
    description = Column(Text, nullable=True)
    banner_url = Column(Text, nullable=True)
    starts_at = Column(DateTime(timezone=True), nullable=True)
    ends_at = Column(DateTime(timezone=True), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True, server_default="true")
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        CheckConstraint(
            "ends_at IS NULL OR starts_at IS NULL OR ends_at > starts_at",
            name="ck_campaign_valid_range",
        ),
    )


class CampaignPromotion(Base):
    __tablename__ = "campaign_promotions"

    campaign_id = Column(
        UUID(as_uuid=True),
        ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    promotion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("promotions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_notifications_user_read_created", "user_id", "is_read", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event = Column(
        Enum(NotificationEvent, name="notificationevent"),
        nullable=False,
        default=NotificationEvent.system_alert,
    )
    title = Column(String(180), nullable=False)
    message = Column(Text, nullable=False)
    data = Column(JSONB, nullable=False, default=dict)
    action_url = Column(Text, nullable=True)
    is_read = Column(Boolean, nullable=False, default=False)
    read_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("User", back_populates="notifications")
    deliveries = relationship(
        "NotificationDelivery",
        back_populates="notification",
        cascade="all, delete-orphan",
    )


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    in_app_enabled = Column(Boolean, nullable=False, default=True)
    email_enabled = Column(Boolean, nullable=False, default=True)
    sms_enabled = Column(Boolean, nullable=False, default=False)
    push_enabled = Column(Boolean, nullable=False, default=False)
    event_preferences = Column(JSONB, nullable=False, default=dict)
    quiet_hours_start = Column(Time, nullable=True)
    quiet_hours_end = Column(Time, nullable=True)
    timezone = Column(String(64), nullable=False, default="UTC")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    user = relationship("User", back_populates="notification_preference")


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    __table_args__ = (
        UniqueConstraint(
            "event", "channel", name="uq_notification_template_event_channel"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event = Column(
        Enum(NotificationEvent, name="notificationevent", create_type=False),
        nullable=False,
    )
    channel = Column(
        Enum(NotificationChannel, name="notificationchannel"), nullable=False
    )
    subject_template = Column(String(255), nullable=True)
    body_template = Column(Text, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "notification_id", "channel", name="uq_notification_delivery_channel"
        ),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    notification_id = Column(
        UUID(as_uuid=True),
        ForeignKey("notifications.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    channel = Column(
        Enum(NotificationChannel, name="notificationchannel", create_type=False),
        nullable=False,
    )
    status = Column(
        Enum(NotificationDeliveryStatus, name="notificationdeliverystatus"),
        nullable=False,
        default=NotificationDeliveryStatus.pending,
    )
    provider = Column(String(100), nullable=True)
    provider_reference = Column(String(255), nullable=True)
    attempts = Column(Integer, nullable=False, default=0)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    failure_reason = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    notification = relationship("Notification", back_populates="deliveries")


class DeviceToken(Base):
    __tablename__ = "device_tokens"
    __table_args__ = (UniqueConstraint("token", name="uq_device_tokens_token"),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    token = Column(Text, nullable=False)
    platform = Column(String(30), nullable=False)
    device_name = Column(String(120), nullable=True)
    is_active = Column(Boolean, nullable=False, default=True)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user = relationship("User", back_populates="device_tokens")


# Phase 3 Task 16: Product Questions and Answers
class ProductQuestion(Base):
    __tablename__ = "product_questions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question = Column(Text, nullable=False)
    status = Column(
        Enum(QuestionStatus),
        nullable=False,
        default=QuestionStatus.published,
        server_default="published",
        index=True,
    )
    helpful_count = Column(Integer, nullable=False, default=0, server_default="0")
    answer_count = Column(Integer, nullable=False, default=0, server_default="0")
    moderated_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    moderated_at = Column(DateTime(timezone=True), nullable=True)
    moderation_note = Column(Text, nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    product = relationship("Product")
    customer = relationship("User", foreign_keys=[customer_id])
    moderated_by = relationship("User", foreign_keys=[moderated_by_id])
    answers = relationship(
        "ProductAnswer", back_populates="question", cascade="all, delete-orphan"
    )
    votes = relationship(
        "QuestionVote", back_populates="question", cascade="all, delete-orphan"
    )
    reports = relationship(
        "QuestionReport", back_populates="question", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(question) >= 5", name="ck_product_question_min_length"
        ),
        CheckConstraint("helpful_count >= 0", name="ck_product_question_helpful_count"),
        CheckConstraint("answer_count >= 0", name="ck_product_question_answer_count"),
    )


class ProductAnswer(Base):
    __tablename__ = "product_answers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    answer = Column(Text, nullable=False)
    is_seller_answer = Column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_official = Column(Boolean, nullable=False, default=False, server_default="false")
    status = Column(
        Enum(QuestionStatus),
        nullable=False,
        default=QuestionStatus.published,
        server_default="published",
        index=True,
    )
    helpful_count = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    question = relationship("ProductQuestion", back_populates="answers")
    user = relationship("User")
    votes = relationship(
        "AnswerVote", back_populates="answer", cascade="all, delete-orphan"
    )
    __table_args__ = (
        CheckConstraint(
            "char_length(answer) >= 2", name="ck_product_answer_min_length"
        ),
        CheckConstraint("helpful_count >= 0", name="ck_product_answer_helpful_count"),
    )


class QuestionVote(Base):
    __tablename__ = "question_votes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    question = relationship("ProductQuestion", back_populates="votes")
    __table_args__ = (
        UniqueConstraint(
            "question_id", "user_id", name="uq_question_vote_question_user"
        ),
    )


class AnswerVote(Base):
    __tablename__ = "answer_votes"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    answer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_answers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    answer = relationship("ProductAnswer", back_populates="votes")
    __table_args__ = (
        UniqueConstraint("answer_id", "user_id", name="uq_answer_vote_answer_user"),
    )


class QuestionReport(Base):
    __tablename__ = "question_reports"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question_id = Column(
        UUID(as_uuid=True),
        ForeignKey("product_questions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reported_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reason = Column(Enum(QuestionReportReason), nullable=False)
    details = Column(Text, nullable=True)
    resolved = Column(Boolean, nullable=False, default=False, server_default="false")
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    question = relationship("ProductQuestion", back_populates="reports")
    __table_args__ = (
        UniqueConstraint(
            "question_id", "reported_by_id", name="uq_question_report_question_user"
        ),
    )


class SearchHistory(Base):
    __tablename__ = "search_history"
    __table_args__ = (
        Index("ix_search_history_user_created", "user_id", "created_at"),
        Index("ix_search_history_query_created", "normalized_query", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    query = Column(String(255), nullable=False)
    normalized_query = Column(String(255), nullable=False, index=True)
    filters = Column(JSONB, nullable=False, default=dict)
    result_count = Column(Integer, nullable=False, default=0)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_search_history_user_created", "user_id", "created_at"),
        Index("ix_search_history_query_created", "normalized_query", "created_at"),
        CheckConstraint("result_count >= 0", name="ck_search_history_result_count"),
    )


class SearchTerm(Base):
    __tablename__ = "search_terms"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    term = Column(String(255), nullable=False, unique=True, index=True)
    search_count = Column(Integer, nullable=False, default=0)
    result_click_count = Column(Integer, nullable=False, default=0)
    last_searched_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at = Column(DateTime(timezone=True), nullable=True, onupdate=func.now())

    __table_args__ = (
        CheckConstraint("search_count >= 0", name="ck_search_term_search_count"),
        CheckConstraint("result_click_count >= 0", name="ck_search_term_click_count"),
    )


class ProductView(Base):
    __tablename__ = "product_views"
    __table_args__ = (
        Index("ix_product_views_product_created", "product_id", "created_at"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    session_id = Column(String(128), nullable=True, index=True)
    source = Column(String(64), nullable=True)
    search_query = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    product = relationship("Product")


class ProductRecommendation(Base):
    __tablename__ = "product_recommendations"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "product_id",
            "recommendation_type",
            name="uq_product_recommendation_user_product_type",
        ),
        CheckConstraint("score >= 0", name="ck_product_recommendation_score"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recommendation_type = Column(String(64), nullable=False, default="personalized")
    score = Column(Float, nullable=False, default=0.0)
    reason = Column(String(255), nullable=True)
    generated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)

    product = relationship("Product")


class RecommendationEvent(Base):
    __tablename__ = "recommendation_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    product_id = Column(
        UUID(as_uuid=True),
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(64), nullable=False, index=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        CheckConstraint(
            "char_length(event_type) >= 2", name="ck_recommendation_event_type"
        ),
    )


# Phase 3 Task 18: Marketplace Administration Dashboard
class AdminDashboardSnapshot(Base):
    __tablename__ = "admin_dashboard_snapshots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period_start = Column(DateTime(timezone=True), nullable=False, index=True)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)
    metrics = Column(JSONB, nullable=False, default=dict)
    generated_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    generated_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    __table_args__ = (
        CheckConstraint(
            "period_end >= period_start", name="ck_admin_dashboard_snapshot_period"
        ),
    )


class SystemAlert(Base):
    __tablename__ = "system_alerts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(80), nullable=False, index=True)
    severity = Column(
        String(20),
        nullable=False,
        default="warning",
        server_default="warning",
        index=True,
    )
    title = Column(String(255), nullable=False)
    message = Column(Text, nullable=False)
    source = Column(String(100), nullable=True, index=True)
    entity_type = Column(String(80), nullable=True)
    entity_id = Column(String(100), nullable=True)
    metadata_json = Column(JSONB, nullable=False, default=dict)
    is_resolved = Column(
        Boolean, nullable=False, default=False, server_default="false", index=True
    )
    resolved_by_id = Column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )
    __table_args__ = (
        CheckConstraint(
            "severity IN ('info','warning','error','critical')",
            name="ck_system_alert_severity",
        ),
    )

class AdminActivityLog(Base):
    __tablename__ = "admin_activity_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    action = Column(String(120), nullable=False, index=True)
    resource_type = Column(String(100), nullable=True, index=True)
    resource_id = Column(String(100), nullable=True)
    details = Column(JSONB, nullable=False, default=dict)
    ip_address = Column(String(64), nullable=True)
    created_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), index=True
    )


     
# PHASE 12: ADVERTISEMENT / SPONSORED PLACEMENTS
     
class Advertisement(Base):
    """Admin-managed sponsored placement.

    Expiration is time-derived: a row can remain status=active in the database,
    but it is no longer live once ends_at <= current time. Public advertisement
    APIs must always filter using the live window. This makes expiry automatic
    at the configured date AND time without relying on a scheduler.
    """

    __tablename__ = "advertisements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    advertiser_name = Column(String(180), nullable=False, index=True)
    title = Column(String(180), nullable=False)
    description = Column(Text, nullable=True)

    image_url = Column(String(1000), nullable=False)
    mobile_image_url = Column(String(1000), nullable=True)
    alt_text = Column(String(255), nullable=True)
    target_url = Column(String(1500), nullable=True)
    cta_label = Column(String(80), nullable=True, default="Shop Now", server_default="Shop Now")

    placement = Column(
        Enum(AdvertisementPlacement),
        nullable=False,
        index=True,
    )
    status = Column(
        Enum(AdvertisementStatus),
        nullable=False,
        default=AdvertisementStatus.draft,
        server_default=AdvertisementStatus.draft.value,
        index=True,
    )

    # Exact timezone-aware campaign window.
    starts_at = Column(DateTime(timezone=True), nullable=False, index=True)
    ends_at = Column(DateTime(timezone=True), nullable=False, index=True)

    # Higher priority wins when several live ads compete for the same slot.
    priority = Column(Integer, nullable=False, default=0, server_default="0")

    # Revenue/accounting foundation. Charging logic comes in a later task.
    billing_type = Column(
        Enum(AdvertisementBillingType),
        nullable=False,
        default=AdvertisementBillingType.fixed,
        server_default=AdvertisementBillingType.fixed.value,
    )
    price = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(3), nullable=False, default="TZS", server_default="TZS")

    # Aggregate counters. Detailed impression/click events will be added later.
    impression_count = Column(Integer, nullable=False, default=0, server_default="0")
    click_count = Column(Integer, nullable=False, default=0, server_default="0")

    metadata_json = Column(JSONB, nullable=False, default=dict, server_default="{}")

    created_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    updated_by_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at = Column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )

    created_by = relationship("User", foreign_keys=[created_by_id])
    updated_by = relationship("User", foreign_keys=[updated_by_id])

    __table_args__ = (
        CheckConstraint(
            "ends_at > starts_at",
            name="ck_advertisement_valid_schedule",
        ),
        CheckConstraint(
            "priority >= 0",
            name="ck_advertisement_priority_nonnegative",
        ),
        CheckConstraint(
            "price IS NULL OR price >= 0",
            name="ck_advertisement_price_nonnegative",
        ),
        CheckConstraint(
            "impression_count >= 0 AND click_count >= 0",
            name="ck_advertisement_counters_nonnegative",
        ),
        Index(
            "ix_advertisements_live_slot",
            "placement",
            "status",
            "starts_at",
            "ends_at",
            "priority",
        ),
    )

    def is_live(self, at=None) -> bool:
        """True only inside the configured active time window."""
        if self.status != AdvertisementStatus.active:
            return False

        now = at or datetime.datetime.now(datetime.timezone.utc)
        starts_at = self.starts_at
        ends_at = self.ends_at

        if starts_at is None or ends_at is None:
            return False

        # SQLAlchemy/PostgreSQL returns aware datetimes for timezone=True.
        return starts_at <= now < ends_at

    def effective_status(self, at=None) -> str:
        """Admin-friendly derived status without mutating the stored state."""
        now = at or datetime.datetime.now(datetime.timezone.utc)

        if self.status == AdvertisementStatus.paused:
            return "paused"
        if self.status == AdvertisementStatus.draft:
            return "draft"
        if self.starts_at and now < self.starts_at:
            return "scheduled"
        if self.ends_at and now >= self.ends_at:
            return "expired"
        if self.status == AdvertisementStatus.active:
            return "active"
        return str(getattr(self.status, "value", self.status))



 
# PHASE 12 TASK 7: ADVERTISEMENT IMPRESSION / CLICK EVENTS
 
class AdvertisementEngagementEvent(Base):
    """Privacy-light advertisement engagement event.

    session_hash is a SHA-256 hash of the browser's opaque session UUID.
    The raw browser session identifier is never persisted.
    event_key is unique and makes impression/click tracking idempotent.
    """

    __tablename__ = "advertisement_engagement_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    advertisement_id = Column(
        UUID(as_uuid=True),
        ForeignKey("advertisements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_type = Column(String(20), nullable=False, index=True)
    placement = Column(Enum(AdvertisementPlacement), nullable=False, index=True)

    session_hash = Column(String(64), nullable=False, index=True)
    event_key = Column(String(160), nullable=False, unique=True, index=True)

    page_path = Column(String(500), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        index=True,
    )

    advertisement = relationship("Advertisement")

    __table_args__ = (
        CheckConstraint(
            "event_type IN ('impression', 'click')",
            name="ck_ad_engagement_event_type",
        ),
        Index(
            "ix_ad_engagement_ad_type_created",
            "advertisement_id",
            "event_type",
            "created_at",
        ),
    )
