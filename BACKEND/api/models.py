import uuid
import enum

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, Enum, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
import datetime
from sqlalchemy import Float, Time
from sqlalchemy import Numeric, Integer
from sqlalchemy.dialects.postgresql import JSONB
from api.database import Base
from api.enums import DayOfWeek, StoreStatus


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
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True)

    user = relationship("User")
    permission = relationship("Permission")    


class RolePermission(Base):
    __tablename__ = "role_permissions"

    role_id = Column(UUID(as_uuid=True), ForeignKey("roles.id"), primary_key=True)
    permission_id = Column(UUID(as_uuid=True), ForeignKey("permissions.id"), primary_key=True)

    role = relationship("Role")
    permission = relationship("Permission")  

class Session(Base):
    __tablename__ = "sessions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    refresh_token = Column(Text, nullable=False)
    expires_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class OTPRequest(Base):
    __tablename__ = "otp_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    phone = Column(String(30))
    otp_code = Column(String(10))
    # What this OTP is for: "register", "password_reset", "phone_verify", etc.
    # Prevents an OTP issued for one flow (e.g. forgot-password) from being
    # accepted in an unrelated flow (e.g. account verification).
    purpose = Column(String(50), nullable=False, server_default="generic")
    expires_at = Column(DateTime(timezone=True))
    verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Address(Base):
    __tablename__ = "addresses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"))
    country = Column(String(100))
    region = Column(String(100))
    city = Column(String(100))
    street = Column(Text)
    postal_code = Column(String(50))
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="addresses")


class Seller(Base):
    __tablename__ = "sellers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        unique=True,
        nullable=False
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
    "SellerBusinessCategory",
    back_populates="seller",
    cascade="all, delete-orphan"
    )
    kyc_documents = relationship(
        "SellerKYCDocument",
        back_populates="seller",
        cascade="all, delete-orphan"
    )
    payout_accounts = relationship(
        "SellerPayoutAccount",
        back_populates="seller",
        cascade="all, delete-orphan"
    )
    profile = relationship(
    "SellerProfile",
    back_populates="seller",
    uselist=False,
    cascade="all, delete-orphan"
)
    
    store = relationship(
    "Store",
    back_populates="seller",
    uselist=False,
    cascade="all, delete-orphan",
)
    
class SellerProfile(Base):
    __tablename__ = "seller_profiles"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), unique=True, nullable=False)

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
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=False)

    document_type = Column(String(100), nullable=False)
    document_url = Column(Text, nullable=False)
    status = Column(String(50), default="pending")
    rejection_reason = Column(Text, nullable=True)

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

    seller = relationship("Seller", back_populates="kyc_documents")


class SellerPayoutAccount(Base):
    __tablename__ = "seller_payout_accounts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=False)

    account_type = Column(String(50), nullable=False)
    provider = Column(String(100), nullable=False)
    account_name = Column(String(255), nullable=False)
    account_number = Column(String(255), nullable=False)
    currency = Column(String(10), default="TZS")
    is_default = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    seller = relationship("Seller", back_populates="payout_accounts")
    
    
class SellerBusinessCategory(Base):
    __tablename__ = "seller_business_categories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    seller_id = Column(
        UUID(as_uuid=True),
        ForeignKey("sellers.id"),
        nullable=False
    )

    business_category_id = Column(
        UUID(as_uuid=True),
        ForeignKey("business_categories.id"),
        nullable=False
    )

    seller = relationship("Seller", back_populates="business_categories")
    business_category = relationship("BusinessCategory")


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
    category_id = Column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    brand_id = Column(UUID(as_uuid=True), ForeignKey("brands.id"), nullable=True)

    sku = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, index=True, nullable=False)
    description = Column(Text)

    price = Column(Numeric(18, 2), nullable=False)
    sale_price = Column(Numeric(18, 2), nullable=True)
    currency = Column(String(10), default="TZS")
    weight = Column(Numeric(10, 2), nullable=True)

    status = Column(Enum(ProductStatus), default=ProductStatus.pending_review)
    rejection_reason = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    seller = relationship("Seller")
    category = relationship("Category")
    brand = relationship("Brand")
    images = relationship("ProductImage", back_populates="product", cascade="all, delete-orphan")
    variants = relationship("ProductVariant", back_populates="product", cascade="all, delete-orphan")
    tags = relationship("ProductTag", back_populates="product", cascade="all, delete-orphan")


class ProductImage(Base):
    __tablename__ = "product_images"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    image_url = Column(Text, nullable=False)
    is_primary = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="images")


class ProductVariant(Base):
    __tablename__ = "product_variants"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_name = Column(String(100), nullable=False)
    sku = Column(String(100), unique=True, index=True, nullable=False)
    price = Column(Numeric(18, 2), nullable=True)
    attributes = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    product = relationship("Product", back_populates="variants")


class ProductTag(Base):
    __tablename__ = "product_tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    tag = Column(String(100), index=True, nullable=False)

    product = relationship("Product", back_populates="tags")


# =========================================================
# CART
# =========================================================

class Cart(Base):
    __tablename__ = "carts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), unique=True, nullable=False)
    coupon_code = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    items = relationship("CartItem", back_populates="cart", cascade="all, delete-orphan")


class CartItem(Base):
    __tablename__ = "cart_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    cart_id = Column(UUID(as_uuid=True), ForeignKey("carts.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Numeric(18, 2), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    cart = relationship("Cart", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")


# =========================================================
# ORDERS
# =========================================================

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
    shipping_address_id = Column(UUID(as_uuid=True), ForeignKey("addresses.id"), nullable=True)

    status = Column(Enum(OrderStatus), default=OrderStatus.pending, nullable=False)
    currency = Column(String(10), default="TZS", nullable=False)
    subtotal = Column(Numeric(18, 2), nullable=False, default=0)
    discount_amount = Column(Numeric(18, 2), nullable=False, default=0)
    shipping_amount = Column(Numeric(18, 2), nullable=False, default=0)
    tax_amount = Column(Numeric(18, 2), nullable=False, default=0)
    total = Column(Numeric(18, 2), nullable=False, default=0)

    coupon_code = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User")
    shipping_address = relationship("Address")
    items = relationship("OrderItem", back_populates="order", cascade="all, delete-orphan")
    status_history = relationship("OrderStatusHistory", back_populates="order", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="order")


class OrderItem(Base):
    __tablename__ = "order_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True)
    seller_id = Column(UUID(as_uuid=True), ForeignKey("sellers.id"), nullable=False)

    product_name = Column(String(255), nullable=False)
    variant_name = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False)
    unit_price = Column(Numeric(18, 2), nullable=False)
    total_price = Column(Numeric(18, 2), nullable=False)

    order = relationship("Order", back_populates="items")
    product = relationship("Product")
    variant = relationship("ProductVariant")
    seller = relationship("Seller")


class OrderStatusHistory(Base):
    __tablename__ = "order_status_history"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    status = Column(String(50), nullable=False)
    notes = Column(Text, nullable=True)
    created_by_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    order = relationship("Order", back_populates="status_history")
    created_by = relationship("User")


# =========================================================
# INVENTORY
# =========================================================

class Inventory(Base):
    __tablename__ = "inventory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    product_id = Column(UUID(as_uuid=True), ForeignKey("products.id"), nullable=False)
    variant_id = Column(UUID(as_uuid=True), ForeignKey("product_variants.id"), nullable=True, unique=True)

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


# =========================================================
# PAYMENTS
# =========================================================

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
    order_id = Column(UUID(as_uuid=True), ForeignKey("orders.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    amount = Column(Numeric(18, 2), nullable=False)
    currency = Column(String(10), default="TZS", nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False)
    provider = Column(String(100), nullable=True)  # e.g. "mpesa", "airtel_money"
    status = Column(Enum(PaymentStatus), default=PaymentStatus.pending, nullable=False)

    provider_transaction_id = Column(String(255), nullable=True)
    provider_response = Column(JSONB, nullable=True)
    failure_reason = Column(Text, nullable=True)

    paid_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    order = relationship("Order", back_populates="payments")
    user = relationship("User")
    transactions = relationship("PaymentTransaction", back_populates="payment", cascade="all, delete-orphan")


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    payment_id = Column(UUID(as_uuid=True), ForeignKey("payments.id"), nullable=False)
    transaction_type = Column(String(50), nullable=False)  # initiate, callback, refund, etc.
    status = Column(String(50), nullable=False)
    amount = Column(Numeric(18, 2), nullable=True)
    provider_response = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    payment = relationship("Payment", back_populates="transactions")


# =========================================================
# COUPONS
# =========================================================

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

    logo_url = Column(Text, nullable=True)
    banner_url = Column(Text, nullable=True)

    contact_email = Column(String(255), nullable=True)
    contact_phone = Column(String(30), nullable=True)
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

    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "day_of_week",
            name="uq_store_opening_hours_store_day",
        ),
    )

    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )

    store_id = Column(
        UUID(as_uuid=True),
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable