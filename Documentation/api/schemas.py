import re
from api.enums import NotificationChannel, NotificationDeliveryStatus, NotificationEvent, QuestionStatus, QuestionReportReason
from api.enums import AdvertisementStatus, AdvertisementPlacement, AdvertisementBillingType
from api.enums import DeliveryStatus, ReviewStatus, ReviewReportReason
from api.enums import CommissionScope, CommissionRuleType
from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    HttpUrl,
    field_validator,
    model_validator,
)
from uuid import UUID
from datetime import datetime, time as Time
from decimal import Decimal
from typing import Optional, List, Dict, Any, Literal
import enum
from api.enums import DayOfWeek, StoreStatus, ShippingRateType
from api.enums import (
    ShipmentStatus, WalletTransactionType, PayoutStatus, RefundStatus, RefundReason,
    SellerOrderStatus, InventoryMovementType, LogisticsCompanyStatus, LogisticsScope,
    LogisticsMemberRole, LogisticsCompanyPermission,
    LogisticsIntegrationAuthType, MultiSellerPricingStrategy, PickupJobStatus,
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


class ProductStatus(str, enum.Enum):
    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    suspended = "suspended"


class OrderStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    processing = "processing"
    shipped = "shipped"
    delivered = "delivered"
    cancelled = "cancelled"
    refunded = "refunded"


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


# Shared schema configuration and validation helpers.
ORM_CONFIG = ConfigDict(from_attributes=True, populate_by_name=True, extra="forbid")


def _clean_required_text(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Value must not be blank")
    return value


def _clean_optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    return value or None


def _normalise_phone(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().replace(" ", "").replace("-", "")
    if not value:
        return None
    if value.startswith("+"):
        digits = value[1:]
    else:
        digits = value
    if not digits.isdigit() or not 7 <= len(digits) <= 15:
        raise ValueError("Phone number must contain 7 to 15 digits")
    return value


def _validate_password(value: str) -> str:
    if len(value.encode("utf-8")) > 72:
        raise ValueError("Password must not exceed 72 bytes")
    if len(value) < 10:
        raise ValueError("Password must contain at least 10 characters")
    if not any(ch.isupper() for ch in value):
        raise ValueError("Password must contain an uppercase letter")
    if not any(ch.islower() for ch in value):
        raise ValueError("Password must contain a lowercase letter")
    if not any(ch.isdigit() for ch in value):
        raise ValueError("Password must contain a number")
    return value


def _normalise_currency(value: str) -> str:
    value = value.strip().upper()
    if len(value) != 3 or not value.isalpha():
        raise ValueError("Currency must be a three-letter ISO code")
    return value


def _normalise_code(value: str) -> str:
    value = value.strip().upper()
    if not value:
        raise ValueError("Code must not be blank")
    return value


class RegisterRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: Optional[str] = None
    password: str

    _clean_names = field_validator("first_name", "last_name")(_clean_required_text)
    _clean_phone = field_validator("phone")(_normalise_phone)
    _strong_password = field_validator("password")(_validate_password)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    user: dict | None = None


class RefreshRequest(BaseModel):
    refresh_token: str


OtpPurpose = Literal["generic", "register", "register_seller", "password_reset"]


class SendOTPRequest(BaseModel):
    phone: str
    purpose: OtpPurpose = "generic"

    _clean_phone = field_validator("phone")(_normalise_phone)


class VerifyOTPRequest(BaseModel):
    phone: str
    otp_code: str = Field(min_length=4, max_length=10)
    purpose: OtpPurpose = "generic"

    _clean_phone = field_validator("phone")(_normalise_phone)


class ResendVerificationRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)


class VerifyAccountOTPRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=255)
    otp_code: str = Field(min_length=4, max_length=10)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str = Field(min_length=4, max_length=10)
    new_password: str

    _strong_password = field_validator("new_password")(_validate_password)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8, max_length=128)
    new_password: str

    _strong_password = field_validator("new_password")(_validate_password)

    @model_validator(mode="after")
    def passwords_must_differ(self):
        if self.current_password == self.new_password:
            raise ValueError("New password must be different from the current password")
        return self


class UserResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    is_verified: bool
    status: str

    is_seller: bool = False
    seller_status: str | None = None
    account_type: str = "customer"

    model_config = ORM_CONFIG


class RegistrationResponse(BaseModel):
    message: str
    user_id: UUID
    email: EmailStr
    phone: str
    verification_required: Literal[True] = True
    verification_purpose: Literal["register"] = "register"
    otp_expires_in_seconds: int = 300
    resumed_registration: bool = False


class SellerRegistrationResponse(BaseModel):
    message: str
    user_id: UUID
    seller_id: UUID
    email: EmailStr
    phone: str
    seller_status: str
    verification_required: Literal[True] = True
    verification_purpose: Literal["register_seller"] = "register_seller"
    otp_expires_in_seconds: int = 300
    resumed_registration: bool = False


class UpdateUserRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class AddressCreate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=50)
    recipient_name: Optional[str] = Field(default=None, max_length=150)
    recipient_phone: Optional[str] = Field(default=None, max_length=30)

    country: str = Field(default="Tanzania", min_length=2, max_length=100)
    region: str = Field(min_length=2, max_length=100)
    district: Optional[str] = Field(default=None, max_length=100)
    ward: Optional[str] = Field(default=None, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    street: str = Field(min_length=3, max_length=1000)
    landmark: Optional[str] = Field(default=None, max_length=255)
    postal_code: Optional[str] = Field(default=None, max_length=50)

    # Phase 2 Task 1 delivery-location metadata.
    formatted_address: Optional[str] = Field(default=None, max_length=1500)
    place_id: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("-90"),
        le=Decimal("90"),
    )
    longitude: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("-180"),
        le=Decimal("180"),
    )
    delivery_instructions: Optional[str] = Field(default=None, max_length=2000)

    is_default: bool = False
    is_active: bool = True

    @field_validator(
        "label",
        "recipient_name",
        "recipient_phone",
        "country",
        "region",
        "district",
        "ward",
        "city",
        "street",
        "landmark",
        "postal_code",
        "formatted_address",
        "place_id",
        "delivery_instructions",
        mode="before",
    )
    @classmethod
    def clean_address_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        has_lat = self.latitude is not None
        has_lng = self.longitude is not None
        if has_lat != has_lng:
            raise ValueError("latitude and longitude must be provided together")
        if self.is_default and not self.is_active:
            raise ValueError("An inactive delivery address cannot be default")
        return self


class AddressUpdate(BaseModel):
    label: Optional[str] = Field(default=None, max_length=50)
    recipient_name: Optional[str] = Field(default=None, max_length=150)
    recipient_phone: Optional[str] = Field(default=None, max_length=30)

    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    region: Optional[str] = Field(default=None, min_length=2, max_length=100)
    district: Optional[str] = Field(default=None, max_length=100)
    ward: Optional[str] = Field(default=None, max_length=100)
    city: Optional[str] = Field(default=None, min_length=2, max_length=100)
    street: Optional[str] = Field(default=None, min_length=3, max_length=1000)
    landmark: Optional[str] = Field(default=None, max_length=255)
    postal_code: Optional[str] = Field(default=None, max_length=50)

    formatted_address: Optional[str] = Field(default=None, max_length=1500)
    place_id: Optional[str] = Field(default=None, max_length=255)
    latitude: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("-90"),
        le=Decimal("90"),
    )
    longitude: Optional[Decimal] = Field(
        default=None,
        ge=Decimal("-180"),
        le=Decimal("180"),
    )
    delivery_instructions: Optional[str] = Field(default=None, max_length=2000)

    is_default: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator(
        "label",
        "recipient_name",
        "recipient_phone",
        "country",
        "region",
        "district",
        "ward",
        "city",
        "street",
        "landmark",
        "postal_code",
        "formatted_address",
        "place_id",
        "delivery_instructions",
        mode="before",
    )
    @classmethod
    def clean_address_update_text(cls, value):
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None


class AddressResponse(BaseModel):
    id: UUID
    label: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    country: str
    region: str
    district: Optional[str] = None
    ward: Optional[str] = None
    city: str
    street: str
    landmark: Optional[str] = None
    postal_code: Optional[str] = None
    formatted_address: Optional[str] = None
    place_id: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    delivery_instructions: Optional[str] = None
    is_default: bool
    is_active: bool
    is_verified: bool
    location_provider: Optional[str] = None
    location_confirmed_at: Optional[datetime] = None
    delivery_ready: bool
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ORM_CONFIG


class CustomerMapPinConfirmationRequest(BaseModel):
    latitude: Decimal = Field(
        ge=Decimal("-90"),
        le=Decimal("90"),
    )
    longitude: Decimal = Field(
        ge=Decimal("-180"),
        le=Decimal("180"),
    )
    language: Optional[str] = Field(default=None, min_length=2, max_length=12)


class CustomerMapPinConfirmationResponse(BaseModel):
    address: AddressResponse
    resolved_location: "MapResolvedLocation"
    message: str


class PaginatedAddressResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[AddressResponse]


class SellerCreate(BaseModel):
    business_name: str
    business_category: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    agreement_accepted: Literal[True]


class SellerUpdate(BaseModel):
    business_name: str | None = None
    business_category_ids: list[UUID] | None = None
    business_description: str | None = None
    business_location: str | None = None
    business_country: str | None = None
    business_region: str | None = None
    business_city: str | None = None
    business_address: str | None = None
    product_description: str | None = None
    years_in_business: str | None = None
    website_url: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None


class SellerResponse(BaseModel):
    id: UUID
    user_id: UUID
    business_name: str
    business_description: str | None = None
    business_location: str | None = None
    business_country: str | None = None
    business_region: str | None = None
    business_city: str | None = None
    business_address: str | None = None
    product_description: str | None = None
    years_in_business: str | None = None
    website_url: str | None = None
    contact_email: str | None
    contact_phone: str | None
    status: str
    agreement_accepted: bool
    created_at: datetime

    model_config = ORM_CONFIG

    @model_validator(mode="before")
    @classmethod
    def flatten_profile(cls, value):
        if isinstance(value, dict):
            return value
        profile = getattr(value, "profile", None)
        data = {
            "id": getattr(value, "id", None),
            "user_id": getattr(value, "user_id", None),
            "business_name": getattr(value, "business_name", None),
            "contact_email": getattr(value, "contact_email", None),
            "contact_phone": getattr(value, "contact_phone", None),
            "status": getattr(value, "status", None),
            "agreement_accepted": getattr(value, "agreement_accepted", False),
            "created_at": getattr(value, "created_at", None),
        }
        for name in (
            "business_description", "business_country", "business_region",
            "business_city", "business_address", "product_description",
            "years_in_business", "website_url"
        ):
            data[name] = getattr(profile, name, None) if profile is not None else None
        data["business_location"] = data.get("business_address")
        return data


class SellerRegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    password: str

    business_name: str
    business_category_ids: list[UUID]
    business_description: str | None = None
    business_location: str | None = None
    business_country: str | None = None
    business_region: str | None = None
    business_city: str | None = None
    business_address: str | None = None
    product_description: str | None = None
    years_in_business: str | None = None
    website_url: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    agreement_accepted: Literal[True]

    _clean_names = field_validator("first_name", "last_name", "business_name")(_clean_required_text)
    _clean_phones = field_validator("phone", "contact_phone")(_normalise_phone)
    _strong_password = field_validator("password")(_validate_password)

    @field_validator("business_category_ids")
    @classmethod
    def require_categories(cls, value: list[UUID]) -> list[UUID]:
        if not value:
            raise ValueError("At least one business category is required")
        return list(dict.fromkeys(value))

class SellerApplicationRequest(BaseModel):
    """Business details submitted by an authenticated customer becoming a seller."""

    business_name: str
    business_category_ids: list[UUID]
    business_description: str | None = None
    business_country: str | None = None
    business_region: str | None = None
    business_city: str | None = None
    business_address: str | None = None
    product_description: str | None = None
    years_in_business: str | None = None
    website_url: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    agreement_accepted: Literal[True]

    _clean_business_name = field_validator("business_name")(_clean_required_text)
    _clean_contact_phone = field_validator("contact_phone")(_normalise_phone)

    @field_validator("business_category_ids")
    @classmethod
    def require_business_categories(cls, value: list[UUID]) -> list[UUID]:
        if not value:
            raise ValueError("At least one business category is required")
        return list(dict.fromkeys(value))


class SellerApplicationStatusResponse(BaseModel):
    has_application: bool
    seller_id: UUID | None = None
    status: str | None = None
    business_name: str | None = None
    can_access_seller_dashboard: bool = False
    can_upload_kyc: bool = False
    submitted_at: datetime | None = None
    approved_at: datetime | None = None


class SellerKYCCreate(BaseModel):
    document_type: str
    document_url: str


class SellerKYCResponse(BaseModel):
    id: UUID
    seller_id: UUID
    document_type: str
    document_url: str
    status: str
    rejection_reason: str | None
    uploaded_at: datetime
    
    model_config = ORM_CONFIG

class SellerKYCStatusResponse(BaseModel):
    seller_status: str
    required_documents: list[str]
    uploaded_documents: list[str]
    missing_documents: list[str]
    can_submit_for_review: bool

    model_config = ORM_CONFIG


class SellerPayoutCreate(BaseModel):
    account_type: str = Field(min_length=1, max_length=50)
    provider: str = Field(min_length=1, max_length=100)
    account_name: str = Field(min_length=1, max_length=255)
    account_number: str = Field(min_length=1, max_length=255)
    currency: str = "TZS"
    is_default: bool = False

    _currency = field_validator("currency")(_normalise_currency)


class SellerPayoutResponse(BaseModel):
    id: UUID
    seller_id: UUID
    account_type: str
    provider: str
    account_name: str
    account_number: str
    currency: str
    is_default: bool
    is_active: bool = True
    verification_status: str = "pending"
    provider_reference: Optional[str] = None
    verified_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ORM_CONFIG
        
class SellerProfileUpdate(BaseModel):
    business_description: str | None = None
    business_country: str | None = None
    business_region: str | None = None
    business_city: str | None = None
    business_address: str | None = None
    product_description: str | None = None
    years_in_business: str | None = None
    website_url: str | None = None


class SellerProfileResponse(BaseModel):
    id: UUID
    seller_id: UUID
    business_description: str | None
    business_country: str | None
    business_region: str | None
    business_city: str | None
    business_address: str | None
    product_description: str | None
    years_in_business: str | None
    website_url: str | None
    created_at: datetime

    model_config = ORM_CONFIG
        
        
        
class StoreUpdate(BaseModel):
    store_name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)
    about: str | None = Field(default=None, max_length=10000)
    theme_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")
    secondary_color: str | None = Field(default=None, pattern=r"^#[0-9A-Fa-f]{6}$")

    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
    whatsapp_phone: str | None = Field(default=None, max_length=30)
    website_url: str | None = None

    country: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    ward: str | None = Field(default=None, max_length=100)
    street: str | None = None

    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)

    opening_time: Time | None = None
    closing_time: Time | None = None

    shipping_policy: str | None = None
    return_policy: str | None = None
    privacy_policy: str | None = None

    facebook_url: str | None = None
    instagram_url: str | None = None
    twitter_url: str | None = None
    tiktok_url: str | None = None
    youtube_url: str | None = None

    vacation_mode: bool | None = None
    accept_orders: bool | None = None
    processing_days: int | None = Field(default=None, ge=0, le=60)
    seo_title: str | None = Field(default=None, max_length=255)
    seo_description: str | None = Field(default=None, max_length=500)


class StoreResponse(BaseModel):
    id: UUID
    seller_id: UUID

    store_name: str
    slug: str
    description: str | None
    about: str | None

    logo_url: str | None
    banner_url: str | None
    theme_color: str
    secondary_color: str

    contact_email: str | None
    contact_phone: str | None
    whatsapp_phone: str | None
    website_url: str | None

    country: str | None
    region: str | None
    district: str | None
    ward: str | None
    street: str | None

    latitude: float | None
    longitude: float | None

    opening_time: Time | None
    closing_time: Time | None

    shipping_policy: str | None
    return_policy: str | None
    privacy_policy: str | None

    facebook_url: str | None
    instagram_url: str | None
    twitter_url: str | None
    tiktok_url: str | None
    youtube_url: str | None

    status: str
    is_verified: bool
    is_featured: bool

    rating: Decimal
    review_count: int
    followers_count: int
    vacation_mode: bool
    accept_orders: bool
    processing_days: int
    seo_title: str | None
    seo_description: str | None
    
    gallery_images: list["StoreGalleryImageResponse"] = Field(default_factory=list)
    opening_hours: list["StoreOpeningHourResponse"] = Field(default_factory=list)

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StorePublicResponse(BaseModel):
    id: UUID
    seller_id: UUID

    store_name: str
    slug: str
    description: str | None
    about: str | None

    logo_url: str | None
    banner_url: str | None
    theme_color: str
    secondary_color: str

    contact_email: str | None
    contact_phone: str | None
    whatsapp_phone: str | None
    website_url: str | None

    country: str | None
    region: str | None
    district: str | None
    ward: str | None
    street: str | None

    opening_time: Time | None
    closing_time: Time | None

    shipping_policy: str | None
    return_policy: str | None

    facebook_url: str | None
    instagram_url: str | None
    twitter_url: str | None
    tiktok_url: str | None
    youtube_url: str | None

    is_verified: bool
    is_featured: bool

    rating: Decimal
    review_count: int
    followers_count: int
    vacation_mode: bool
    accept_orders: bool
    processing_days: int
    seo_title: str | None
    seo_description: str | None
    
    gallery_images: list["StoreGalleryImageResponse"] = Field(default_factory=list)
    opening_hours: list["StoreOpeningHourResponse"] = Field(default_factory=list)

    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PaginatedAdminStoreResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[StoreResponse]

class PaginatedStoreResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[StorePublicResponse]        


class UserMeResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None
    is_verified: bool
    status: str | None
    is_seller: bool
    seller_status: str | None
    account_type: str
    roles: list[str] = Field(default_factory=list)

    model_config = ORM_CONFIG

class PaginatedSellerResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SellerResponse]


class PaginatedKYCResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SellerKYCResponse]


class PaginatedPayoutResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SellerPayoutResponse]


class CategoryCreate(BaseModel):
    parent_id: Optional[UUID] = None
    name: str
    slug: str


class CategoryUpdate(BaseModel):
    parent_id: Optional[UUID] = None
    name: Optional[str] = None
    slug: Optional[str] = None


class CategoryResponse(BaseModel):
    id: UUID
    parent_id: Optional[UUID]
    name: str
    slug: str
    image_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    created_at: datetime

    model_config = ORM_CONFIG


class BrandCreate(BaseModel):
    name: str
    slug: str


class BrandUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None


class BrandResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime

    model_config = ORM_CONFIG


class ProductCreate(BaseModel):
    category_id: UUID
    brand_id: Optional[UUID] = None
    sku: str
    name: str
    slug: str
    description: Optional[str] = None
    price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    sale_price: Optional[Decimal] = Field(default=None, ge=0, max_digits=18, decimal_places=2)
    currency: str = "TZS"
    weight: Optional[Decimal] = Field(default=None, ge=0)

    _currency = field_validator("currency")(_normalise_currency)

    @model_validator(mode="after")
    def validate_sale_price(self):
        if self.sale_price is not None and self.sale_price > self.price:
            raise ValueError("Sale price cannot be greater than price")
        return self


class ProductUpdate(BaseModel):
    category_id: Optional[UUID] = None
    brand_id: Optional[UUID] = None
    sku: Optional[str] = None
    name: Optional[str] = None
    slug: Optional[str] = None
    description: Optional[str] = None
    price: Optional[Decimal] = None
    sale_price: Optional[Decimal] = None
    currency: Optional[str] = None
    weight: Optional[Decimal] = Field(default=None, ge=0)
    is_active: Optional[bool] = None

    _currency = field_validator("currency")(_normalise_currency)

    @field_validator("price")
    @classmethod
    def positive_price(cls, value):
        if value is not None and value <= 0:
            raise ValueError("Price must be greater than zero")
        return value

    @field_validator("sale_price")
    @classmethod
    def nonnegative_sale_price(cls, value):
        if value is not None and value < 0:
            raise ValueError("Sale price cannot be negative")
        return value

    @model_validator(mode="after")
    def validate_sale_price(self):
        if self.price is not None and self.sale_price is not None and self.sale_price > self.price:
            raise ValueError("Sale price cannot be greater than price")
        return self


class ProductResponse(BaseModel):
    id: UUID
    seller_id: UUID
    category_id: UUID
    brand_id: Optional[UUID]
    sku: str
    name: str
    slug: str
    description: Optional[str]
    seller_base_price: Decimal
    seller_sale_price: Optional[Decimal]
    commission_rate_snapshot: Decimal
    commission_amount_snapshot: Decimal
    price: Decimal
    sale_price: Optional[Decimal]
    currency: str
    weight: Optional[Decimal]
    status: ProductStatus
    rejection_reason: Optional[str]
    is_active: bool
    submitted_at: Optional[datetime] = None
    approved_at: Optional[datetime] = None
    approved_by_user_id: Optional[UUID] = None
    images: list["ProductImageResponse"] = Field(default_factory=list)
    created_at: datetime

    model_config = ORM_CONFIG


class AdminProductReviewDetailResponse(ProductResponse):
    seller_business_name: Optional[str] = None
    seller_contact_email: Optional[str] = None
    seller_contact_phone: Optional[str] = None
    category_name: Optional[str] = None
    brand_name: Optional[str] = None


class AdminCatalogSummaryResponse(BaseModel):
    total_products: int
    pending_products: int
    approved_products: int
    rejected_products: int
    product_categories: int
    business_categories: int
    brands: int


class PaginatedAdminProductResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[AdminProductReviewDetailResponse]


class PaginatedCategoryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[CategoryResponse]


class PaginatedBrandResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[BrandResponse]


class ProductImageCreate(BaseModel):
    """Legacy URL-based image creation. Prefer multipart upload endpoints."""

    image_url: str
    is_primary: bool = False
    alt_text: Optional[str] = Field(default=None, max_length=255)
    display_order: int = Field(default=0, ge=0)


class ProductImageUpdate(BaseModel):
    alt_text: Optional[str] = Field(default=None, max_length=255)
    display_order: Optional[int] = Field(default=None, ge=0)
    is_primary: Optional[bool] = None


class ProductImageOrderItem(BaseModel):
    image_id: UUID
    display_order: int = Field(ge=0)


class ProductImageReorderRequest(BaseModel):
    images: list[ProductImageOrderItem] = Field(min_length=1, max_length=10)


class ProductImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    image_url: str
    thumbnail_url: Optional[str] = None
    storage_key: Optional[str] = None
    original_filename: Optional[str] = None
    mime_type: Optional[str] = None
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    alt_text: Optional[str] = None
    display_order: int = 0
    is_primary: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ORM_CONFIG


class ProductOptionValueInput(BaseModel):
    value: str = Field(min_length=1, max_length=100)
    display_order: int = Field(default=0, ge=0)


class ProductOptionCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    display_order: int = Field(default=0, ge=0)
    values: list[ProductOptionValueInput] = Field(min_length=1, max_length=50)


class ProductOptionUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    display_order: Optional[int] = Field(default=None, ge=0)
    values: Optional[list[ProductOptionValueInput]] = Field(default=None, min_length=1, max_length=50)


class ProductOptionValueResponse(BaseModel):
    id: UUID
    value: str
    display_order: int
    model_config = ORM_CONFIG


class ProductOptionResponse(BaseModel):
    id: UUID
    product_id: UUID
    name: str
    display_order: int
    values: list[ProductOptionValueResponse]
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ORM_CONFIG


class ProductVariantCreate(BaseModel):
    variant_name: str = Field(min_length=1, max_length=255)
    sku: str = Field(min_length=1, max_length=100)
    barcode: Optional[str] = Field(default=None, max_length=100)
    price: Optional[Decimal] = Field(default=None, ge=0)
    sale_price: Optional[Decimal] = Field(default=None, ge=0)
    weight: Optional[Decimal] = Field(default=None, ge=0)
    image_id: Optional[UUID] = None
    attributes: Optional[Dict[str, Any]] = None
    option_value_ids: list[UUID] = Field(default_factory=list)
    stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_variant_prices(self):
        if self.sale_price is not None and self.price is not None and self.sale_price > self.price:
            raise ValueError("sale_price cannot exceed price")
        return self


class ProductVariantUpdate(BaseModel):
    variant_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    sku: Optional[str] = Field(default=None, min_length=1, max_length=100)
    barcode: Optional[str] = Field(default=None, max_length=100)
    price: Optional[Decimal] = Field(default=None, ge=0)
    sale_price: Optional[Decimal] = Field(default=None, ge=0)
    weight: Optional[Decimal] = Field(default=None, ge=0)
    image_id: Optional[UUID] = None
    attributes: Optional[Dict[str, Any]] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    is_active: Optional[bool] = None


class ProductVariantGenerateRequest(BaseModel):
    sku_prefix: str = Field(min_length=1, max_length=60)
    default_price: Optional[Decimal] = Field(default=None, ge=0)
    default_sale_price: Optional[Decimal] = Field(default=None, ge=0)
    default_stock_quantity: int = Field(default=0, ge=0)
    low_stock_threshold: int = Field(default=10, ge=0)

    @model_validator(mode="after")
    def validate_prices(self):
        if self.default_sale_price is not None and self.default_price is not None and self.default_sale_price > self.default_price:
            raise ValueError("default_sale_price cannot exceed default_price")
        return self


class ProductVariantResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_name: str
    sku: str
    barcode: Optional[str] = None
    seller_base_price: Optional[Decimal] = None
    seller_sale_price: Optional[Decimal] = None
    commission_rate_snapshot: Optional[Decimal] = None
    commission_amount_snapshot: Optional[Decimal] = None
    price: Optional[Decimal]
    sale_price: Optional[Decimal] = None
    weight: Optional[Decimal] = None
    image_id: Optional[UUID] = None
    attributes: Optional[Dict[str, Any]]
    is_active: bool = True
    stock_quantity: int = 0
    reserved_quantity: int = 0
    available_quantity: int = 0
    low_stock_threshold: int = 10
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ORM_CONFIG


class ProductTagCreate(BaseModel):
    tag: str


class ProductTagResponse(BaseModel):
    id: UUID
    product_id: UUID
    tag: str

    model_config = ORM_CONFIG
    
class BusinessCategoryCreate(BaseModel):
    name: str
    slug: str
    description: str | None = None
    active: bool = True


class BusinessCategoryUpdate(BaseModel):
    name: str | None = None
    slug: str | None = None
    description: str | None = None
    active: bool | None = None


class BusinessCategoryResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    active: bool
    created_at: datetime

    model_config = ORM_CONFIG


class PaginatedBusinessCategoryResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[BusinessCategoryResponse]
        
class AdminUserCreate(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    password: str
    status: str = "active"
    is_verified: bool = True


class AdminUserUpdate(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: EmailStr | None = None
    phone: str | None = None
    status: str | None = None
    is_verified: bool | None = None
    password: str | None = None


class AdminUserResponse(BaseModel):
    id: UUID
    first_name: str | None
    last_name: str | None
    email: EmailStr
    phone: str | None
    status: str
    is_verified: bool
    created_at: datetime

    model_config = ORM_CONFIG


class PaginatedAdminUserResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[AdminUserResponse]   
    
class AdminCreateAdminRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str | None = None
    password: str


class RoleCreateRequest(BaseModel):
    name: str = Field(min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=1000)
    permission_codes: list[str] = Field(default_factory=list)

    @field_validator("name")
    @classmethod
    def normalize_role_name(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "_").replace("-", "_")
        value = re.sub(r"[^a-z0-9_]", "", value)
        value = re.sub(r"_+", "_", value).strip("_")

        if len(value) < 2:
            raise ValueError("Role name must contain at least 2 valid characters")

        return value

    @field_validator("permission_codes")
    @classmethod
    def clean_permission_codes(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        return list(dict.fromkeys(cleaned))


class RoleUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = Field(default=None, max_length=1000)

    @field_validator("name")
    @classmethod
    def normalize_role_name(cls, value: str | None) -> str | None:
        if value is None:
            return None

        value = value.strip().lower().replace(" ", "_").replace("-", "_")
        value = re.sub(r"[^a-z0-9_]", "", value)
        value = re.sub(r"_+", "_", value).strip("_")

        if len(value) < 2:
            raise ValueError("Role name must contain at least 2 valid characters")

        return value


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None
    created_at: datetime | None = None

    model_config = ORM_CONFIG


class PermissionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None

    model_config = ORM_CONFIG


class AssignUserPermissionsRequest(BaseModel):
    permission_codes: list[str]

    @field_validator("permission_codes")
    @classmethod
    def clean_permissions(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        return list(dict.fromkeys(cleaned))


class UserPermissionsResponse(BaseModel):
    user_id: UUID
    permissions: list[str]


class RolePermissionsUpdateRequest(BaseModel):
    permission_codes: list[str]

    @field_validator("permission_codes")
    @classmethod
    def clean_permissions(cls, value: list[str]) -> list[str]:
        cleaned = [item.strip() for item in value if item and item.strip()]
        return list(dict.fromkeys(cleaned))


class RolePermissionsResponse(BaseModel):
    role_id: UUID
    role_name: str
    permissions: list[str]


class UserRolesUpdateRequest(BaseModel):
    role_ids: list[UUID]

    @field_validator("role_ids")
    @classmethod
    def unique_role_ids(cls, value: list[UUID]) -> list[UUID]:
        return list(dict.fromkeys(value))


class UserRolesResponse(BaseModel):
    user_id: UUID
    roles: list[RoleResponse]


class RoleUsersResponse(BaseModel):
    role_id: UUID
    role_name: str
    user_ids: list[UUID]


class AdminStaffCreateRequest(BaseModel):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=30)
    password: str = Field(min_length=8)
    role_ids: list[UUID]
    status: str = "active"
    is_verified: bool = True

    @field_validator("role_ids")
    @classmethod
    def require_roles(cls, value: list[UUID]) -> list[UUID]:
        value = list(dict.fromkeys(value))
        if not value:
            raise ValueError("At least one role is required")
        return value


class AdminStaffResponse(BaseModel):
    id: UUID
    first_name: str | None
    last_name: str | None
    email: EmailStr
    phone: str | None
    status: str
    is_verified: bool
    created_at: datetime
    roles: list[str]
    permissions: list[str]


class AdminAccessUserResponse(BaseModel):
    id: UUID
    first_name: str | None
    last_name: str | None
    email: EmailStr
    phone: str | None
    status: str
    is_verified: bool
    created_at: datetime
    roles: list[str]
    role_ids: list[UUID]
    permissions: list[str]


class PaginatedAdminAccessUserResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[AdminAccessUserResponse]

  
# CART SCHEMAS
  

class CartItemCreate(BaseModel):
    product_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int = Field(ge=1)


class CartItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class CartItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    quantity: int
    unit_price: Decimal
    product: "ProductResponse"

    model_config = ORM_CONFIG


class AppliedCartPromotion(BaseModel):
    promotion_id: UUID
    code: Optional[str]
    name: str
    promotion_type: str
    funding_source: str
    eligible_subtotal: Decimal
    discount_amount: Decimal
    seller_id: Optional[UUID] = None
    stackable: bool = False


class CartResponse(BaseModel):
    id: UUID
    user_id: UUID
    coupon_code: Optional[str]
    promotion_code: Optional[str] = None
    promotion: Optional[AppliedCartPromotion] = None
    items: list[CartItemResponse]
    subtotal: Decimal
    coupon_discount_amount: Decimal = Decimal("0.00")
    promotion_discount_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal
    total: Decimal
    currency: str = "TZS"
    validation_messages: list[str] = Field(default_factory=list)

    model_config = ORM_CONFIG


class ApplyCouponRequest(BaseModel):
    code: str


class ApplyCartPromotionRequest(BaseModel):
    code: str = Field(min_length=2, max_length=50)

    @field_validator("code")
    @classmethod
    def normalise_cart_promotion_code(cls, value):
        return value.strip().upper()


class CartPromotionOffer(BaseModel):
    promotion_id: UUID
    code: Optional[str]
    name: str
    description: Optional[str] = None
    promotion_type: str
    funding_source: str
    seller_id: Optional[UUID] = None
    eligible_subtotal: Decimal
    discount_amount: Decimal
    total_after_discount: Decimal
    stackable: bool
    automatic: bool
    minimum_order_amount: Optional[Decimal] = None
    maximum_discount_amount: Optional[Decimal] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None


class GuestCartMergeRequest(BaseModel):
    items: list[CartItemCreate] = Field(default_factory=list, max_length=100)


class GuestCartRejectedItem(BaseModel):
    product_id: UUID
    reason: str
    available_quantity: Optional[int] = None


class GuestCartMergeResponse(BaseModel):
    cart: CartResponse
    rejected_items: list[GuestCartRejectedItem]


  
class CheckoutDeliveryQuoteCreateRequest(BaseModel):
    address_id: UUID
    logistics_company_id: UUID
    rate_id: UUID
    delivery_mode: Literal["local", "international"]


class CheckoutDeliveryQuoteResponse(BaseModel):
    id: UUID
    user_id: UUID
    shipping_address_id: UUID
    logistics_company_id: UUID
    shipping_method_id: UUID
    shipping_rate_id: UUID
    delivery_mode: str
    pricing_strategy: str
    rate_type: str
    currency: str
    seller_count: int
    billable_distance_km: Decimal
    billable_seller_id: Optional[UUID] = None
    product_subtotal: Decimal
    delivery_amount: Decimal
    checkout_total_before_discounts: Decimal
    pricing_breakdown: dict = Field(default_factory=dict)
    seller_routes_snapshot: list[dict] = Field(default_factory=list)
    address_snapshot: dict = Field(default_factory=dict)
    expires_at: datetime
    used_at: Optional[datetime] = None
    created_at: datetime

    model_config = ORM_CONFIG


# ORDER SCHEMAS
  

class OrderItemResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    seller_id: UUID
    product_name: str
    variant_name: Optional[str]
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    promotion_discount_amount: Decimal = Decimal("0.00")
    customer_total: Decimal = Decimal("0.00")

    model_config = ORM_CONFIG


class OrderStatusHistoryResponse(BaseModel):
    id: UUID
    status: str
    notes: Optional[str]
    created_by_id: Optional[UUID]
    created_at: datetime

    model_config = ORM_CONFIG


class OrderCreateRequest(BaseModel):
    shipping_address_id: UUID
    shipping_rate_id: Optional[UUID] = None
    delivery_quote_id: Optional[UUID] = None
    delivery_mode: Literal["local", "international"]
    coupon_code: Optional[str] = None
    promotion_code: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_shipping_selection(self):
        if self.shipping_rate_id is None and self.delivery_quote_id is None:
            raise ValueError("shipping_rate_id or delivery_quote_id is required")
        return self


class OrderStatusUpdateRequest(BaseModel):
    status: OrderStatus
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    shipping_address_id: Optional[UUID]
    delivery_quote_id: Optional[UUID] = None
    shipping_rate_id: Optional[UUID]
    shipping_method_id: Optional[UUID]
    shipping_method_name: Optional[str]
    shipping_carrier: Optional[str]
    estimated_delivery_from: Optional[datetime]
    estimated_delivery_to: Optional[datetime]
    status: OrderStatus
    currency: str
    subtotal: Decimal
    coupon_discount_amount: Decimal = Decimal("0.00")
    promotion_discount_amount: Decimal = Decimal("0.00")
    discount_amount: Decimal
    original_shipping_amount: Decimal = Decimal("0.00")
    shipping_discount_amount: Decimal = Decimal("0.00")
    shipping_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    coupon_code: Optional[str]
    promotion_code: Optional[str] = None
    promotion_seller_id: Optional[UUID] = None
    delivery_mode: Optional[str] = None
    logistics_company_id: Optional[UUID] = None
    notes: Optional[str]
    items: list[OrderItemResponse]
    status_history: list[OrderStatusHistoryResponse]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ORM_CONFIG


class OrderWorkflowStageResponse(BaseModel):
    name: Literal["checkout", "payment", "seller_fulfillment", "logistics", "pickup", "delivery"]
    status: Literal["complete", "in_progress", "waiting", "blocked"]
    detail: str


class OrderShipmentWorkflowResponse(BaseModel):
    shipment_id: UUID
    seller_id: UUID
    seller_order_id: Optional[UUID] = None
    seller_order_status: Optional[str] = None
    shipment_status: str
    logistics_company_id: Optional[UUID] = None
    pickup_job_status: Optional[str] = None
    handover_status: Optional[str] = None
    pickup_proof_status: Optional[str] = None
    latest_tracking_status: Optional[str] = None
    tracking_event_count: int


class OrderWorkflowResponse(BaseModel):
    order_id: UUID
    order_status: str
    overall_status: Literal["in_progress", "action_required", "complete", "terminal"]
    delivery_quote_id: Optional[UUID] = None
    payment_ready: bool
    seller_order_count: int
    shipment_count: int
    delivered_shipment_count: int
    stages: list[OrderWorkflowStageResponse]
    shipments: list[OrderShipmentWorkflowResponse]
    blockers: list[str]
    reconciliation_actions: list[str] = Field(default_factory=list)


class PaginatedOrderResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[OrderResponse]


class AdminOrderUserSummary(BaseModel):
    id: UUID
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

    model_config = ORM_CONFIG


class AdminOrderPaymentSummary(BaseModel):
    id: UUID
    method: str
    status: str
    amount: Decimal
    currency: str
    provider: Optional[str] = None
    transaction_reference: Optional[str] = None
    paid_at: Optional[datetime] = None


class AdminOrderAddressSummary(BaseModel):
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    postal_code: Optional[str] = None


class AdminOrderResponse(OrderResponse):
    payment_status: Optional[str] = None
    user: Optional[AdminOrderUserSummary] = None
    payments: list[AdminOrderPaymentSummary] = []
    address: Optional[AdminOrderAddressSummary] = None
    delivery_method: Optional[str] = None
    courier_name: Optional[str] = None
    tracking_number: Optional[str] = None
    estimated_delivery_date: Optional[datetime] = None
    delivered_at: Optional[datetime] = None


class PaginatedAdminOrderResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[AdminOrderResponse]

# INVENTORY SCHEMAS

class InventoryCreate(BaseModel):
    product_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int = Field(ge=0)
    reserved_quantity: int = Field(default=0, ge=0)
    warehouse_location: Optional[str] = None
    low_stock_threshold: int = Field(default=10, ge=0)


class InventoryUpdate(BaseModel):
    quantity: Optional[int] = Field(default=None, ge=0)
    reserved_quantity: Optional[int] = Field(default=None, ge=0)
    warehouse_location: Optional[str] = None
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)


class InventoryResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    quantity: int
    reserved_quantity: int
    available_quantity: int
    warehouse_location: Optional[str]
    low_stock_threshold: int
    restock_date: Optional[datetime]
    updated_at: Optional[datetime]

    model_config = ORM_CONFIG


class SellerInventoryConfigureRequest(BaseModel):
    product_id: UUID
    variant_id: Optional[UUID] = None
    quantity: int = Field(ge=0)
    low_stock_threshold: int = Field(default=5, ge=0)
    warehouse_location: Optional[str] = Field(default=None, max_length=255)
    restock_date: Optional[datetime] = None


class SellerInventoryAdjustmentRequest(BaseModel):
    adjustment: int
    reason: InventoryMovementType
    reference: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def validate_adjustment(self):
        if self.adjustment == 0:
            raise ValueError("Adjustment cannot be zero")
        return self


class SellerInventoryRestockRequest(BaseModel):
    quantity: int = Field(gt=0)
    reference: Optional[str] = Field(default=None, max_length=255)
    note: Optional[str] = Field(default=None, max_length=2000)
    warehouse_location: Optional[str] = Field(default=None, max_length=255)


class SellerInventorySettingsUpdate(BaseModel):
    low_stock_threshold: Optional[int] = Field(default=None, ge=0)
    warehouse_location: Optional[str] = Field(default=None, max_length=255)
    restock_date: Optional[datetime] = None


class SellerInventoryItemResponse(BaseModel):
    inventory_id: UUID
    product_id: UUID
    product_name: str
    product_sku: str
    variant_id: Optional[UUID]
    variant_name: Optional[str]
    variant_sku: Optional[str]
    quantity: int
    reserved_quantity: int
    available_quantity: int
    low_stock_threshold: int
    warehouse_location: Optional[str]
    restock_date: Optional[datetime]
    unit_price: Decimal
    inventory_value: Decimal
    is_low_stock: bool
    is_out_of_stock: bool
    updated_at: Optional[datetime]


class SellerInventorySummaryResponse(BaseModel):
    total_products: int
    total_variants: int
    total_stock_units: int
    reserved_units: int
    available_units: int
    low_stock_variants: int
    out_of_stock_variants: int
    inventory_value: Decimal


class SellerInventoryListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SellerInventoryItemResponse]


class SellerInventoryMovementResponse(BaseModel):
    id: UUID
    inventory_id: UUID
    product_id: UUID
    product_name: str
    variant_id: Optional[UUID]
    variant_name: Optional[str]
    movement_type: InventoryMovementType
    adjustment: int
    before_quantity: int
    after_quantity: int
    reference: Optional[str]
    note: Optional[str]
    created_at: datetime


  
# PAYMENT SCHEMAS
  

class PaymentInitiateRequest(BaseModel):
    order_id: UUID
    method: PaymentMethod
    provider: Optional[str] = Field(default=None, max_length=100)
    phone_number: Optional[str] = None
    success_url: Optional[str] = Field(default=None, max_length=2048)
    failure_url: Optional[str] = Field(default=None, max_length=2048)

    _clean_phone = field_validator("phone_number")(_normalise_phone)

    @model_validator(mode="after")
    def validate_method_details(self):
        if self.method == PaymentMethod.mobile_money and not self.phone_number:
            raise ValueError("Phone number is required for mobile-money payments")
        if self.method == PaymentMethod.mobile_money and not self.provider:
            raise ValueError("Provider is required for mobile-money payments")
        if self.method == PaymentMethod.card and self.provider and self.provider.lower() != "azampay":
            raise ValueError("Card payments currently support provider=azampay")
        return self


class PaymentRetryRequest(BaseModel):
    provider: Optional[str] = Field(default=None, max_length=100)
    phone_number: Optional[str] = None
    success_url: Optional[str] = Field(default=None, max_length=2048)
    failure_url: Optional[str] = Field(default=None, max_length=2048)

    _clean_phone = field_validator("phone_number")(_normalise_phone)


class AzamPayCheckoutCallbackRequest(BaseModel):
    """AzamPay Tanzania Checkout callback payload.

    Field names intentionally match AzamPay's published callback contract.
    Sensitive authentication fields are accepted for compatibility but must
    never be persisted to payment audit JSON.
    """

    message: str = Field(min_length=1)
    user: str = Field(min_length=1)
    password: str = Field(min_length=1)
    clientId: str = Field(min_length=1)
    transactionstatus: str = Field(min_length=1)
    operator: str = Field(min_length=1)
    reference: str = Field(min_length=1)
    externalreference: str = Field(min_length=1)
    utilityref: str = Field(min_length=1)
    amount: str = Field(min_length=1)
    transid: str = Field(min_length=1)
    msisdn: str = Field(min_length=1)
    mnoreference: str = Field(min_length=1)
    submerchantAcc: Optional[str] = None
    additionalProperties: Optional[Dict[str, Any]] = None
    signature: Optional[str] = None

    model_config = ConfigDict(extra="allow")


class ZenoPayWebhookRequest(BaseModel):
    """Public fields documented for a ZenoPay completion webhook.

    The payload is never trusted as payment proof. The payments router verifies
    the order directly with ZenoPay before applying any state transition.
    """

    order_id: str = Field(min_length=1, max_length=128)
    payment_status: Optional[str] = Field(default=None, max_length=50)
    reference: Optional[str] = Field(default=None, max_length=255)
    metadata: Optional[Dict[str, Any]] = None

    model_config = ConfigDict(extra="allow")


class PaymentCallbackRequest(BaseModel):
    payment_id: UUID
    provider: str = Field(min_length=1, max_length=100)
    transaction_id: str = Field(min_length=1, max_length=255)
    status: PaymentStatus
    payload: Optional[Dict[str, Any]] = None


class PaymentTransactionResponse(BaseModel):
    id: UUID
    transaction_type: str
    status: str
    amount: Optional[Decimal]
    provider_response: Optional[Dict[str, Any]]
    idempotency_key: Optional[str] = None
    created_at: datetime

    model_config = ORM_CONFIG


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    method: PaymentMethod
    provider: Optional[str]
    status: PaymentStatus
    provider_transaction_id: Optional[str]
    provider_response: Optional[Dict[str, Any]] = None
    failure_reason: Optional[str] = None
    paid_at: Optional[datetime]
    transactions: list[PaymentTransactionResponse]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ORM_CONFIG


class PaginatedPaymentResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[PaymentResponse]


class OrderPaymentStateResponse(BaseModel):
    order_id: UUID
    order_status: str
    payment_status: Literal[
        "not_started",
        "pending",
        "processing",
        "completed",
        "failed",
        "cancelled",
        "refunded",
    ]
    latest_payment: Optional[PaymentResponse] = None
    retryable: bool = False
    terminal: bool = False
    poll_after_seconds: Optional[int] = None
    message: str



class AzamPayPaymentPartnerResponse(BaseModel):
    logo_url: Optional[str] = None
    partner_name: Optional[str] = None
    provider: Optional[int] = None
    vendor_name: Optional[str] = None
    payment_vendor_id: Optional[str] = None
    payment_partner_id: Optional[str] = None
    currency: Optional[str] = None


class AzamPayDiagnosticsResponse(BaseModel):
    environment: Literal["sandbox", "live"]
    base_url: str
    authentication: Literal["ok", "failed"]
    merchant_configured: bool
    payment_partners_status: Literal["ok", "failed", "skipped"]
    partners: list[AzamPayPaymentPartnerResponse] = Field(default_factory=list)
    provider_names: list[str] = Field(default_factory=list)
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    provider_status: Optional[int] = None


class CustomerEscrowSummary(BaseModel):
    order_id: UUID
    currency: str
    status: Literal[
        "not_applicable",
        "held",
        "partially_released",
        "released",
        "disputed",
    ]
    hold_count: int
    gross_amount: Decimal
    seller_amount: Decimal
    commission_amount: Decimal
    released_amount: Decimal
    remaining_amount: Decimal
    release_after: Optional[datetime] = None
    can_customer_approve: bool = False


class CustomerEscrowApprovalRequest(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


  
# COUPON SCHEMAS
  

class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: Literal["percentage", "fixed_amount"]
    discount_value: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    minimum_order_amount: Optional[Decimal] = Field(default=None, ge=0)
    maximum_discount_amount: Optional[Decimal] = Field(default=None, ge=0)
    usage_limit: Optional[int] = Field(default=None, ge=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True

    _code = field_validator("code")(_normalise_code)

    @model_validator(mode="after")
    def validate_coupon(self):
        if self.discount_type == "percentage" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be later than valid_from")
        return self


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[Literal["percentage", "fixed_amount"]] = None
    discount_value: Optional[Decimal] = Field(default=None, gt=0)
    minimum_order_amount: Optional[Decimal] = Field(default=None, ge=0)
    maximum_discount_amount: Optional[Decimal] = Field(default=None, ge=0)
    usage_limit: Optional[int] = Field(default=None, ge=0)
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None

    @model_validator(mode="after")
    def validate_coupon(self):
        if self.discount_type == "percentage" and self.discount_value is not None and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.valid_from and self.valid_until and self.valid_until <= self.valid_from:
            raise ValueError("valid_until must be later than valid_from")
        return self


class StoreGalleryImageUpdate(BaseModel):
    caption: str | None = Field(
        default=None,
        max_length=500,
    )
    display_order: int | None = Field(
        default=None,
        ge=0,
    )
    is_active: bool | None = None


class StoreGalleryImageResponse(BaseModel):
    id: UUID
    store_id: UUID
    image_url: str
    caption: str | None
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StoreOpeningHourCreate(BaseModel):
    day_of_week: DayOfWeek
    opening_time: Time | None = None
    closing_time: Time | None = None
    is_closed: bool = False

    @model_validator(mode="after")
    def validate_hours(self):
        if self.is_closed:
            self.opening_time = None
            self.closing_time = None
        elif self.opening_time is None or self.closing_time is None:
            raise ValueError("Opening and closing times are required when the store is open")
        elif self.closing_time <= self.opening_time:
            raise ValueError("Closing time must be later than opening time")
        return self


class StoreOpeningHourUpdate(BaseModel):
    opening_time: Time | None = None
    closing_time: Time | None = None
    is_closed: bool | None = None

    @model_validator(mode="after")
    def validate_hours(self):
        if self.is_closed is True:
            self.opening_time = None
            self.closing_time = None
        elif self.opening_time is not None and self.closing_time is not None and self.closing_time <= self.opening_time:
            raise ValueError("Closing time must be later than opening time")
        return self


class StoreOpeningHourResponse(BaseModel):
    id: UUID
    store_id: UUID
    day_of_week: DayOfWeek
    day_position: int = Field(validation_alias=AliasChoices("day_position", "day_number"))
    opening_time: Time | None = Field(validation_alias=AliasChoices("opening_time", "open_time"))
    closing_time: Time | None = Field(validation_alias=AliasChoices("closing_time", "close_time"))
    is_closed: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AdminStoreStatusUpdate(BaseModel):
    status: StoreStatus
    reason: str | None = Field(
        default=None,
        max_length=2000,
    )


class AdminStoreVerificationUpdate(BaseModel):
    is_verified: bool


class AdminStoreFeaturedUpdate(BaseModel):
    is_featured: bool

class CouponResponse(BaseModel):
    id: UUID
    code: str
    description: Optional[str]
    discount_type: str
    discount_value: Decimal
    minimum_order_amount: Optional[Decimal]
    maximum_discount_amount: Optional[Decimal]
    usage_limit: Optional[int]
    usage_count: int
    is_active: bool
    valid_from: Optional[datetime]
    valid_until: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True

  
# SHIPPING SCHEMAS
  

class LogisticsCompanyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=150)
    code: str = Field(min_length=2, max_length=80)
    description: Optional[str] = None
    legal_name: Optional[str] = Field(default=None, max_length=180)
    registration_number: Optional[str] = Field(default=None, max_length=100)
    tax_identification_number: Optional[str] = Field(default=None, max_length=100)
    license_number: Optional[str] = Field(default=None, max_length=100)
    logo_url: Optional[str] = None
    contact_name: Optional[str] = Field(default=None, max_length=150)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=50)
    website_url: Optional[str] = None
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    country: str = Field(default="Tanzania", min_length=2, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=30)
    scope: LogisticsScope = LogisticsScope.local
    status: LogisticsCompanyStatus = LogisticsCompanyStatus.pending
    supports_cod: bool = False
    supports_tracking: bool = True
    supports_webhooks: bool = False
    metadata_json: dict[str, Any] = Field(default_factory=dict)

    @field_validator("code")
    @classmethod
    def normalize_code(cls, value: str) -> str:
        value = value.strip().lower().replace(" ", "-")
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", value):
            raise ValueError("code may contain lowercase letters, numbers, hyphens and underscores")
        return value


class LogisticsCompanyUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = None
    legal_name: Optional[str] = Field(default=None, max_length=180)
    registration_number: Optional[str] = Field(default=None, max_length=100)
    tax_identification_number: Optional[str] = Field(default=None, max_length=100)
    license_number: Optional[str] = Field(default=None, max_length=100)
    logo_url: Optional[str] = None
    contact_name: Optional[str] = Field(default=None, max_length=150)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=50)
    website_url: Optional[str] = None
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=30)
    scope: Optional[LogisticsScope] = None
    status: Optional[LogisticsCompanyStatus] = None
    supports_cod: Optional[bool] = None
    supports_tracking: Optional[bool] = None
    supports_webhooks: Optional[bool] = None
    metadata_json: Optional[dict[str, Any]] = None


class LogisticsCompanyResponse(LogisticsCompanyCreate):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ORM_CONFIG


class PaginatedLogisticsCompanyResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[LogisticsCompanyResponse]


class LogisticsCompanyProfileUpdate(BaseModel):
    """Fields a logistics-company member may maintain for their own company.

    Administrative fields such as code, status, scope and service capabilities
    are intentionally excluded from this self-service contract.
    """

    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    legal_name: Optional[str] = Field(default=None, max_length=180)
    description: Optional[str] = None
    registration_number: Optional[str] = Field(default=None, max_length=100)
    tax_identification_number: Optional[str] = Field(default=None, max_length=100)
    license_number: Optional[str] = Field(default=None, max_length=100)
    logo_url: Optional[str] = None
    contact_name: Optional[str] = Field(default=None, max_length=150)
    contact_email: Optional[EmailStr] = None
    contact_phone: Optional[str] = Field(default=None, max_length=50)
    website_url: Optional[str] = None
    address_line1: Optional[str] = Field(default=None, max_length=255)
    address_line2: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=120)
    region: Optional[str] = Field(default=None, max_length=120)
    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    postal_code: Optional[str] = Field(default=None, max_length=30)


class LogisticsCompanyAccountResponse(BaseModel):
    company: LogisticsCompanyResponse
    membership_id: UUID
    title: Optional[str]
    member_role: LogisticsMemberRole
    effective_permissions: list[LogisticsCompanyPermission]
    is_primary_contact: bool
    can_manage_profile: bool


class LogisticsCompanyUserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: UUID
    title: Optional[str] = Field(default=None, max_length=120)
    member_role: LogisticsMemberRole = LogisticsMemberRole.viewer
    permissions_json: list[LogisticsCompanyPermission] = Field(default_factory=list)
    is_primary_contact: bool = False
    is_active: bool = True


class LogisticsCompanyUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: Optional[str] = Field(default=None, max_length=120)
    member_role: Optional[LogisticsMemberRole] = None
    permissions_json: Optional[list[LogisticsCompanyPermission]] = None
    is_primary_contact: Optional[bool] = None
    is_active: Optional[bool] = None


class LogisticsCompanyUserResponse(BaseModel):
    id: UUID
    logistics_company_id: UUID
    user_id: UUID
    title: Optional[str]
    member_role: LogisticsMemberRole
    permissions_json: list[LogisticsCompanyPermission]
    is_primary_contact: bool
    is_active: bool
    created_at: datetime
    model_config = ORM_CONFIG


class LogisticsCompanyMemberResponse(LogisticsCompanyUserResponse):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: EmailStr
    effective_permissions: list[LogisticsCompanyPermission]


class LogisticsIntegrationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_base_url: Optional[str] = None
    outbound_webhook_url: Optional[str] = None
    auth_type: LogisticsIntegrationAuthType = LogisticsIntegrationAuthType.none
    credential_reference: Optional[str] = Field(default=None, max_length=255)
    webhook_secret_reference: Optional[str] = Field(default=None, max_length=255)
    api_key_header: Optional[str] = Field(default=None, max_length=120)
    extra_config: dict[str, Any] = Field(default_factory=dict)
    webhook_enabled_events: list[str] = Field(default_factory=list)
    is_active: bool = False


class LogisticsIntegrationUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    api_base_url: Optional[str] = None
    outbound_webhook_url: Optional[str] = None
    auth_type: Optional[LogisticsIntegrationAuthType] = None
    credential_reference: Optional[str] = Field(default=None, max_length=255)
    webhook_secret_reference: Optional[str] = Field(default=None, max_length=255)
    api_key_header: Optional[str] = Field(default=None, max_length=120)
    extra_config: Optional[dict[str, Any]] = None
    webhook_enabled_events: Optional[list[str]] = None
    is_active: Optional[bool] = None


class LogisticsIntegrationResponse(LogisticsIntegrationCreate):
    id: UUID
    logistics_company_id: UUID
    last_tested_at: Optional[datetime] = None
    last_test_success: Optional[bool] = None
    last_test_message: Optional[str] = None
    last_webhook_sent_at: Optional[datetime] = None
    last_webhook_received_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ORM_CONFIG


class PartnerCredentialCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=2, max_length=120)
    scopes: list[Literal["shipments:read", "tracking:write"]] = Field(min_length=1)
    allowed_cidrs: list[str] = Field(default_factory=list, max_length=50)
    rate_limit_per_minute: int = Field(default=120, ge=1, le=10000)
    expires_at: datetime | None = None


class PartnerCredentialResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    logistics_company_id: UUID
    name: str
    key_id: str
    secret_fingerprint: str
    scopes: list[str]
    allowed_cidrs: list[str]
    rate_limit_per_minute: int
    status: str
    expires_at: datetime | None = None
    last_used_at: datetime | None = None
    last_used_ip: str | None = None
    rotated_from_id: UUID | None = None
    revoked_at: datetime | None = None
    created_at: datetime


class PartnerCredentialIssuedResponse(BaseModel):
    credential: PartnerCredentialResponse
    secret: str
    signing_algorithm: str = "HMAC-SHA256"
    warning: str = "Store this secret now. It will not be shown again."


class PartnerRequestLogResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    credential_id: UUID | None = None
    request_id: str
    method: str
    path: str
    source_ip: str | None = None
    nonce: str | None = None
    idempotency_key: str | None = None
    body_sha256: str | None = None
    auth_result: str
    response_status: int | None = None
    error_code: str | None = None
    created_at: datetime


class LogisticsWebhookEventResponse(BaseModel):
    id: UUID
    logistics_company_id: UUID
    direction: str
    event_type: str
    external_event_id: Optional[str]
    shipment_id: Optional[UUID]
    http_status: Optional[int]
    processed: bool
    delivery_status: str
    attempt_count: int
    max_attempts: int
    next_attempt_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    dead_lettered_at: Optional[datetime] = None
    error_message: Optional[str]
    created_at: datetime
    model_config = ORM_CONFIG


class PartnerWebhookAttemptResponse(BaseModel):
    id: UUID
    event_id: UUID
    attempt_number: int
    request_url: str
    credential_key_id: Optional[str] = None
    requested_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    http_status: Optional[int] = None
    retryable: bool
    response_excerpt: Optional[str] = None
    error_message: Optional[str] = None
    model_config = ORM_CONFIG


class PaginatedLogisticsWebhookEventResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[LogisticsWebhookEventResponse]


class LogisticsDashboardResponse(BaseModel):
    logistics_company_id: UUID
    members: int
    active_zones: int
    active_services: int
    active_rates: int
    shipments_total: int
    shipments_by_status: dict[str, int]
    pickup_jobs_total: int
    pickup_jobs_by_status: dict[str, int]
    webhook_events_24h: int
    webhook_failures_24h: int
    integration_configured: bool
    integration_active: bool


class PaginatedShippingMethodResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list["ShippingMethodResponse"]


class PaginatedShippingZoneResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list["ShippingZoneResponse"]


class PaginatedShippingRateResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list["ShippingRateResponse"]


class PaginatedShipmentResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list["ShipmentResponse"]


class ShippingZoneCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    logistics_company_id: Optional[UUID] = None
    name: str = Field(min_length=2, max_length=120)
    country: str = Field(default="Tanzania", min_length=2, max_length=100)
    scope: LogisticsScope = LogisticsScope.local
    regions: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    districts: list[str] = Field(default_factory=list)
    wards: list[str] = Field(default_factory=list)
    postal_codes: list[str] = Field(default_factory=list)
    coverage_geojson: Optional[dict[str, Any]] = None
    covers_entire_country: bool = False
    is_active: bool = True

    @field_validator("regions", "cities", "districts", "wards", "postal_codes")
    @classmethod
    def normalise_places(cls, values: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for value in values:
            item = value.strip()
            key = item.lower()
            if item and key not in seen:
                seen.add(key)
                cleaned.append(item)
        return cleaned

    @model_validator(mode="after")
    def validate_coverage(self):
        if self.covers_entire_country:
            return self
        if not any(
            (
                self.regions,
                self.cities,
                self.districts,
                self.wards,
                self.postal_codes,
                self.coverage_geojson,
            )
        ):
            raise ValueError(
                "Provide at least one coverage area or set covers_entire_country=true"
            )
        if self.coverage_geojson is not None and self.coverage_geojson.get("type") not in {
            "Polygon",
            "MultiPolygon",
        }:
            raise ValueError("coverage_geojson must be a Polygon or MultiPolygon")
        return self


class ShippingZoneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    country: Optional[str] = Field(default=None, min_length=2, max_length=100)
    scope: Optional[LogisticsScope] = None
    regions: Optional[list[str]] = None
    cities: Optional[list[str]] = None
    districts: Optional[list[str]] = None
    wards: Optional[list[str]] = None
    postal_codes: Optional[list[str]] = None
    coverage_geojson: Optional[dict[str, Any]] = None
    covers_entire_country: Optional[bool] = None
    is_active: Optional[bool] = None

    @field_validator("regions", "cities", "districts", "wards", "postal_codes")
    @classmethod
    def normalise_optional_places(cls, values: Optional[list[str]]) -> Optional[list[str]]:
        if values is None:
            return None
        cleaned = []
        seen = set()
        for value in values:
            item = value.strip()
            key = item.lower()
            if item and key not in seen:
                seen.add(key)
                cleaned.append(item)
        return cleaned

    @field_validator("coverage_geojson")
    @classmethod
    def validate_optional_geojson(cls, value: Optional[dict[str, Any]]):
        if value is not None and value.get("type") not in {"Polygon", "MultiPolygon"}:
            raise ValueError("coverage_geojson must be a Polygon or MultiPolygon")
        return value


class ShippingZoneResponse(ShippingZoneCreate):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ORM_CONFIG


class ShippingMethodCreate(BaseModel):
    logistics_company_id: Optional[UUID] = None
    name: str = Field(min_length=2, max_length=120)
    service_code: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    carrier_name: Optional[str] = Field(default=None, max_length=120)
    scope: LogisticsScope = LogisticsScope.local
    supports_cod: bool = False
    supports_tracking: bool = True
    min_delivery_days: int = Field(default=1, ge=0, le=365)
    max_delivery_days: int = Field(default=7, ge=0, le=365)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_days(self):
        if self.max_delivery_days < self.min_delivery_days:
            raise ValueError("max_delivery_days must be greater than or equal to min_delivery_days")
        return self


class ShippingMethodUpdate(BaseModel):
    logistics_company_id: Optional[UUID] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=120)
    service_code: Optional[str] = Field(default=None, max_length=100)
    description: Optional[str] = None
    carrier_name: Optional[str] = Field(default=None, max_length=120)
    scope: Optional[LogisticsScope] = None
    supports_cod: Optional[bool] = None
    supports_tracking: Optional[bool] = None
    min_delivery_days: Optional[int] = Field(default=None, ge=0, le=365)
    max_delivery_days: Optional[int] = Field(default=None, ge=0, le=365)
    is_active: Optional[bool] = None


class ShippingMethodResponse(ShippingMethodCreate):
    id: UUID
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ORM_CONFIG


class ShippingRateCreate(BaseModel):
    zone_id: UUID
    method_id: UUID
    rate_type: ShippingRateType = ShippingRateType.flat
    currency: str = Field(default="TZS", min_length=3, max_length=10)
    base_amount: Decimal = Field(default=Decimal("0.00"), ge=0)
    amount_per_kg: Decimal = Field(default=Decimal("0.00"), ge=0)
    amount_per_km: Decimal = Field(default=Decimal("0.00"), ge=0)
    minimum_fee: Optional[Decimal] = Field(default=None, ge=0)
    maximum_fee: Optional[Decimal] = Field(default=None, ge=0)
    max_distance_km: Optional[Decimal] = Field(default=None, gt=0)
    free_shipping_threshold: Optional[Decimal] = Field(default=None, ge=0)
    min_weight_kg: Optional[Decimal] = Field(default=None, ge=0)
    max_weight_kg: Optional[Decimal] = Field(default=None, ge=0)
    is_active: bool = True

    @model_validator(mode="after")
    def validate_weight_range(self):
        if self.min_weight_kg is not None and self.max_weight_kg is not None and self.max_weight_kg < self.min_weight_kg:
            raise ValueError("max_weight_kg must be greater than or equal to min_weight_kg")
        if self.minimum_fee is not None and self.maximum_fee is not None and self.maximum_fee < self.minimum_fee:
            raise ValueError("maximum_fee must be greater than or equal to minimum_fee")
        if self.rate_type in {ShippingRateType.per_km, ShippingRateType.base_plus_per_km} and self.amount_per_km <= 0:
            raise ValueError("amount_per_km must be greater than zero for distance-based rates")
        return self


class ShippingRateResponse(ShippingRateCreate):
    id: UUID
    zone: ShippingZoneResponse
    method: ShippingMethodResponse
    created_at: datetime
    updated_at: Optional[datetime] = None
    model_config = ORM_CONFIG


class LogisticsPricingSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    multi_seller_pricing_strategy: MultiSellerPricingStrategy


class LogisticsPricingSettingsResponse(BaseModel):
    logistics_company_id: UUID
    multi_seller_pricing_strategy: MultiSellerPricingStrategy
    supported_strategies: list[MultiSellerPricingStrategy]


class ShippingCheckoutConfig(BaseModel):
    default_country: str = "Tanzania"
    local_delivery_allowed: bool = True
    international_delivery_allowed: bool = False
    cod_allowed: bool = False
    configured: bool = False


class EligibleLogisticsSelectionRequest(BaseModel):
    address_id: UUID
    delivery_mode: Literal["local", "international"]


class EligibleSellerPickupCoverage(BaseModel):
    seller_id: UUID
    seller_name: str
    pickup_location_id: UUID
    pickup_label: str
    country: str
    region: str
    city: str
    latitude: Decimal
    longitude: Decimal


class EligibleLogisticsServiceSummary(BaseModel):
    method_id: UUID
    method_name: str
    service_code: Optional[str] = None
    scope: LogisticsScope
    min_delivery_days: int
    max_delivery_days: int
    supports_cod: bool
    supports_tracking: bool


class EligibleLogisticsCompanyOption(BaseModel):
    logistics_company_id: UUID
    name: str
    code: str
    scope: LogisticsScope
    supports_cod: bool
    supports_tracking: bool
    supports_webhooks: bool
    seller_count: int
    covered_seller_count: int
    services: list[EligibleLogisticsServiceSummary] = Field(default_factory=list)


class PaginatedEligibleLogisticsCompanyResponse(BaseModel):
    address_id: UUID
    delivery_mode: Literal["local", "international"]
    seller_count: int
    total: int
    page: int
    page_size: int
    total_pages: int
    sellers: list[EligibleSellerPickupCoverage] = Field(default_factory=list)
    results: list[EligibleLogisticsCompanyOption] = Field(default_factory=list)


class DeliveryDistanceQuoteRequest(BaseModel):
    address_id: UUID
    logistics_company_id: UUID
    delivery_mode: Literal["local", "international"]


class SellerRouteDistanceResponse(BaseModel):
    seller_id: UUID
    seller_name: str
    pickup_location_id: UUID
    pickup_label: str
    distance_meters: int
    distance_km: Decimal
    duration_seconds: int
    duration_minutes: Decimal
    provider: str


class DeliveryDistanceQuoteResponse(BaseModel):
    address_id: UUID
    logistics_company_id: UUID
    logistics_company_name: str
    delivery_mode: Literal["local", "international"]
    seller_count: int
    distance_provider: str
    sellers: list[SellerRouteDistanceResponse] = Field(default_factory=list)
    max_distance_km: Decimal
    min_distance_km: Decimal
    average_distance_km: Decimal
    note: str


class MultiSellerDeliveryPricingRequest(BaseModel):
    address_id: UUID
    logistics_company_id: UUID
    delivery_mode: Literal["local", "international"]
    method_id: Optional[UUID] = None


class MultiSellerPricingSellerRoute(BaseModel):
    seller_id: UUID
    seller_name: str
    pickup_location_id: UUID
    pickup_label: str
    distance_km: Decimal
    duration_minutes: Decimal
    is_billable_reference: bool = False


class MultiSellerPricingBreakdown(BaseModel):
    base_amount: Decimal
    amount_per_km: Decimal
    raw_distance_amount: Decimal
    minimum_fee: Optional[Decimal] = None
    maximum_fee: Optional[Decimal] = None
    minimum_fee_applied: bool = False
    maximum_fee_applied: bool = False


class MultiSellerDeliveryOption(BaseModel):
    rate_id: UUID
    method_id: UUID
    method_name: str
    service_code: Optional[str] = None
    logistics_company_id: UUID
    logistics_company_name: str
    strategy: MultiSellerPricingStrategy
    rate_type: ShippingRateType
    currency: str
    seller_count: int
    billable_distance_km: Decimal
    billable_seller_id: Optional[UUID] = None
    delivery_amount: Decimal
    min_delivery_days: int
    max_delivery_days: int
    supports_cod: bool
    supports_tracking: bool
    pricing_breakdown: MultiSellerPricingBreakdown
    sellers: list[MultiSellerPricingSellerRoute] = Field(default_factory=list)


class MultiSellerDeliveryPricingResponse(BaseModel):
    address_id: UUID
    logistics_company_id: UUID
    logistics_company_name: str
    delivery_mode: Literal["local", "international"]
    strategy: MultiSellerPricingStrategy
    seller_count: int
    options: list[MultiSellerDeliveryOption] = Field(default_factory=list)
    note: str


class ShippingQuoteRequest(BaseModel):
    address_id: UUID
    delivery_mode: Literal["local", "international"]
    logistics_company_id: Optional[UUID] = None
    method_id: Optional[UUID] = None
    subtotal: Optional[Decimal] = Field(default=None, ge=0)
    weight_kg: Optional[Decimal] = Field(default=None, ge=0)


class ShippingQuoteOption(BaseModel):
    rate_id: UUID
    method_id: UUID
    logistics_company_id: Optional[UUID] = None
    logistics_company_name: Optional[str] = None
    method_name: str
    carrier_name: Optional[str]
    scope: LogisticsScope = LogisticsScope.local
    supports_cod: bool = False
    supports_tracking: bool = True
    original_amount: Decimal
    shipping_discount_amount: Decimal = Decimal("0.00")
    amount: Decimal
    currency: str = "TZS"
    min_delivery_days: int
    max_delivery_days: int
    free_shipping_applied: bool = False
    promotion_code: Optional[str] = None
    promotion_name: Optional[str] = None


  
# SHIPMENT SCHEMAS
  

class ShipmentItemResponse(BaseModel):
    id: UUID
    order_item_id: UUID
    quantity: int
    model_config = ORM_CONFIG


class ShipmentTrackingEventCreate(BaseModel):
    status: ShipmentStatus
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = None
    tracking_number: Optional[str] = Field(default=None, max_length=150)
    carrier_name: Optional[str] = Field(default=None, max_length=120)


class ShipmentTrackingEventResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    status: ShipmentStatus
    location: Optional[str]
    notes: Optional[str]
    created_by_id: Optional[UUID]
    created_at: datetime
    model_config = ORM_CONFIG


class ShipmentResponse(BaseModel):
    id: UUID
    order_id: UUID
    seller_id: UUID
    logistics_company_id: Optional[UUID] = None
    shipping_method_id: Optional[UUID]
    status: ShipmentStatus
    carrier_name: Optional[str]
    tracking_number: Optional[str]
    estimated_delivery_from: Optional[datetime]
    estimated_delivery_to: Optional[datetime]
    dispatched_at: Optional[datetime]
    delivered_at: Optional[datetime]
    items: list[ShipmentItemResponse] = Field(default_factory=list)
    tracking_events: list[ShipmentTrackingEventResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime]
    model_config = ORM_CONFIG


class DeliveryProofEventResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    action: str
    note: str | None = None
    created_by_id: UUID | None = None
    created_at: datetime


class DeliveryProofResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    shipment_id: UUID
    order_id: UUID
    customer_id: UUID
    logistics_company_id: UUID
    status: str
    recipient_name: str
    recipient_phone_last4: str | None = None
    photo_url: str
    delivery_latitude: Decimal
    delivery_longitude: Decimal
    destination_latitude: Decimal
    destination_longitude: Decimal
    distance_from_destination_meters: Decimal
    otp_expires_at: datetime
    otp_attempts: int
    notes: str | None = None
    verified_at: datetime | None = None
    disputed_at: datetime | None = None
    dispute_reason: str | None = None
    dispute_notes: str | None = None
    logistics_release_transaction_id: UUID | None = None
    settlement_status: str
    created_at: datetime
    updated_at: datetime | None = None
    events: list[DeliveryProofEventResponse] = Field(default_factory=list)


class DeliveryProofStartResponse(BaseModel):
    proof: DeliveryProofResponse
    otp_delivery_channels: list[str]
    dev_otp: str | None = None


class DeliveryProofVerifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    otp_code: str = Field(pattern=r"^\d{6}$")


class DeliveryProofDisputeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: Literal["not_received", "wrong_recipient", "damaged", "wrong_location", "other"]
    notes: str | None = Field(default=None, max_length=2000)


class LogisticsPickupJobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_membership_id: Optional[UUID] = None
    scheduled_for: Optional[datetime] = None
    dispatcher_notes: Optional[str] = Field(default=None, max_length=2000)


class LogisticsPickupJobAssign(BaseModel):
    model_config = ConfigDict(extra="forbid")
    assigned_membership_id: UUID
    scheduled_for: Optional[datetime] = None
    dispatcher_notes: Optional[str] = Field(default=None, max_length=2000)


class LogisticsPickupJobStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: PickupJobStatus
    notes: Optional[str] = Field(default=None, max_length=2000)
    failure_reason: Optional[str] = Field(default=None, max_length=255)

    @model_validator(mode="after")
    def validate_failure_reason(self):
        if self.status == PickupJobStatus.failed and not self.failure_reason:
            raise ValueError("failure_reason is required when pickup fails")
        return self


class LogisticsPickupJobResponse(BaseModel):
    id: UUID
    logistics_company_id: UUID
    shipment_id: UUID
    assigned_membership_id: Optional[UUID]
    status: PickupJobStatus
    scheduled_for: Optional[datetime]
    pickup_reference: str
    dispatcher_notes: Optional[str]
    courier_notes: Optional[str]
    failure_reason: Optional[str]
    assigned_at: Optional[datetime]
    started_at: Optional[datetime]
    arrived_at: Optional[datetime]
    completed_at: Optional[datetime]
    cancelled_at: Optional[datetime]
    created_by_id: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]
    model_config = ORM_CONFIG


class PaginatedLogisticsPickupJobResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[LogisticsPickupJobResponse]


class CustomerOrderAddressSummary(BaseModel):
    label: Optional[str] = None
    recipient_name: Optional[str] = None
    recipient_phone: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    city: Optional[str] = None
    street: Optional[str] = None
    landmark: Optional[str] = None
    postal_code: Optional[str] = None

    model_config = ORM_CONFIG


class CustomerOrderPaymentSummary(BaseModel):
    id: UUID
    amount: Decimal
    currency: str
    method: str
    provider: Optional[str] = None
    status: str
    provider_transaction_id: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime

    model_config = ORM_CONFIG


class CustomerSellerOrderSummary(BaseModel):
    id: UUID
    seller_id: UUID
    status: str
    seller_subtotal: Decimal
    item_count: int
    accepted_at: Optional[datetime] = None
    processing_at: Optional[datetime] = None
    ready_to_ship_at: Optional[datetime] = None
    shipped_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None
    created_at: datetime

    model_config = ORM_CONFIG


class CustomerOrderDetailResponse(OrderResponse):
    payment_status: Optional[str] = None
    payments: list[CustomerOrderPaymentSummary] = Field(default_factory=list)
    shipping_address: Optional[CustomerOrderAddressSummary] = None
    shipments: list[ShipmentResponse] = Field(default_factory=list)
    seller_orders: list[CustomerSellerOrderSummary] = Field(default_factory=list)


# Phase 3 Task 2: commission engine schemas
class CommissionRuleCreate(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    scope: CommissionScope
    rule_type: CommissionRuleType = CommissionRuleType.percentage
    rate: Decimal = Field(ge=0)
    seller_id: UUID | None = None
    category_id: UUID | None = None
    product_id: UUID | None = None
    priority: int = 0
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None

    @model_validator(mode="after")
    def validate_scope_target(self):
        targets = {"seller": self.seller_id, "category": self.category_id, "product": self.product_id}
        if self.scope.value == "global" and any(targets.values()):
            raise ValueError("Global commission cannot have a target")
        if self.scope.value != "global" and targets[self.scope.value] is None:
            raise ValueError(f"{self.scope.value}_id is required")
        if self.rule_type == CommissionRuleType.percentage and self.rate > 100:
            raise ValueError("Percentage commission cannot exceed 100")
        if self.ends_at and self.starts_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self

class CommissionRuleUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=150)
    rate: Decimal | None = Field(default=None, ge=0)
    priority: int | None = None
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None

class CommissionRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str
    scope: CommissionScope
    rule_type: CommissionRuleType
    rate: Decimal
    seller_id: UUID | None
    category_id: UUID | None
    product_id: UUID | None
    priority: int
    is_active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime

class PaginatedCommissionRuleResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[CommissionRuleResponse]


class MarketplaceSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    escrow_release_hours: int = Field(ge=1, le=720)
    dispute_period_hours: int = Field(ge=1, le=720)
    cod_allowed: bool
    international_delivery_allowed: bool


class MarketplaceSettingsResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID | None = None
    escrow_release_hours: int | None = None
    dispute_period_hours: int | None = None
    cod_allowed: bool | None = None
    international_delivery_allowed: bool | None = None
    configured: bool = False
    updated_by_id: UUID | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CommissionPricingPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    seller_base_price: Decimal = Field(ge=0, max_digits=18, decimal_places=2)
    currency: str = Field(default="TZS", min_length=3, max_length=10)
    seller_id: UUID | None = None
    category_id: UUID | None = None
    product_id: UUID | None = None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class CommissionPricingPreviewResponse(BaseModel):
    seller_base_price: Decimal
    commission_rule_id: UUID | None = None
    commission_scope: CommissionScope | None = None
    commission_rule_type: CommissionRuleType | None = None
    commission_rate: Decimal
    commission_amount: Decimal
    customer_price: Decimal
    seller_receivable_before_other_adjustments: Decimal
    currency: str


class OrderItemCommissionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    order_id: UUID
    order_item_id: UUID
    seller_id: UUID
    commission_rule_id: UUID | None
    currency: str
    gross_amount: Decimal
    commission_rate: Decimal
    commission_amount: Decimal
    seller_net_amount: Decimal
    processing_fee: Decimal
    tax_amount: Decimal
    created_at: datetime

class SellerEarningsSummary(BaseModel):
    currency: str
    gross_sales: Decimal
    commission_deducted: Decimal
    net_earnings: Decimal
    transaction_count: int


class SellerWalletResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    seller_id: UUID
    currency: str
    pending_balance: Decimal
    available_balance: Decimal
    reserved_balance: Decimal
    paid_out_balance: Decimal
    refunded_balance: Decimal
    debt_balance: Decimal
    is_frozen: bool
    created_at: datetime
    updated_at: datetime | None = None

class WalletTransactionResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    transaction_type: WalletTransactionType
    amount: Decimal
    currency: str
    reference: str
    order_id: UUID | None = None
    eligible_at: datetime | None = None
    released_at: datetime | None = None
    description: str | None = None
    created_at: datetime

class PayoutRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payout_account_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    note: str | None = Field(default=None, max_length=1000)

class PayoutRequestResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    seller_id: UUID
    payout_account_id: UUID
    amount: Decimal
    currency: str
    status: PayoutStatus
    provider_reference: str | None = None
    seller_note: str | None = None
    admin_note: str | None = None
    requested_at: datetime
    processed_at: datetime | None = None
    completed_at: datetime | None = None

class PayoutAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: PayoutStatus
    provider_reference: str | None = Field(default=None, max_length=180)
    note: str | None = Field(default=None, max_length=1000)

class WalletAdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)


class LogisticsWalletResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    logistics_company_id: UUID
    currency: str
    pending_balance: Decimal
    available_balance: Decimal
    reserved_balance: Decimal
    paid_out_balance: Decimal
    refunded_balance: Decimal
    debt_balance: Decimal
    is_frozen: bool
    created_at: datetime
    updated_at: datetime | None = None


class LogisticsWalletTransactionResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    transaction_type: str
    amount: Decimal
    currency: str
    reference: str
    order_id: UUID | None = None
    payout_request_id: UUID | None = None
    eligible_at: datetime | None = None
    released_at: datetime | None = None
    description: str | None = None
    created_at: datetime


class PaginatedLogisticsWalletTransactionResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[LogisticsWalletTransactionResponse]


class LogisticsPayoutAccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    account_type: Literal["bank", "mobile_money"]
    provider: str = Field(min_length=2, max_length=100)
    account_name: str = Field(min_length=2, max_length=255)
    account_number: str = Field(min_length=4, max_length=255)
    currency: str = Field(default="TZS", min_length=3, max_length=10)
    is_default: bool = False


class LogisticsPayoutAccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str | None = Field(default=None, min_length=2, max_length=100)
    account_name: str | None = Field(default=None, min_length=2, max_length=255)
    account_number: str | None = Field(default=None, min_length=4, max_length=255)
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    is_default: bool | None = None
    is_active: bool | None = None


class LogisticsPayoutAccountResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    logistics_company_id: UUID
    account_type: str
    provider: str
    account_name: str
    masked_account_number: str
    currency: str
    is_default: bool
    is_active: bool
    verification_status: str
    verification_note: str | None = None
    verified_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None


class LogisticsPayoutAccountVerification(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["pending", "verified", "rejected"]
    note: str | None = Field(default=None, max_length=1000)


class LogisticsPayoutRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    payout_account_id: UUID
    amount: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    note: str | None = Field(default=None, max_length=1000)


class LogisticsPayoutRequestResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    logistics_company_id: UUID
    payout_account_id: UUID
    amount: Decimal
    currency: str
    status: str
    provider_reference: str | None = None
    company_note: str | None = None
    admin_note: str | None = None
    requested_at: datetime
    processed_at: datetime | None = None
    completed_at: datetime | None = None


class PaginatedLogisticsPayoutResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[LogisticsPayoutRequestResponse]


class LogisticsPayoutAdminUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["approved", "processing", "completed", "rejected", "failed"]
    provider_reference: str | None = Field(default=None, max_length=180)
    note: str | None = Field(default=None, max_length=1000)


class LogisticsWalletAdjustmentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Decimal = Field(max_digits=18, decimal_places=2)
    reason: str = Field(min_length=3, max_length=500)


# Phase 3 Task 4: refund and reversal schemas
class RefundItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_item_id: UUID
    quantity: int = Field(gt=0)
    restock: bool = True

class RefundCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    order_id: UUID
    reason: RefundReason
    reason_details: str | None = Field(default=None, max_length=2000)
    items: list[RefundItemCreate] = Field(min_length=1)
    refund_shipping: bool = False
    refund_tax: bool = False
    idempotency_key: str = Field(min_length=8, max_length=180)

class RefundReview(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=2000)

class RefundProcess(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider_reference: str | None = Field(default=None, max_length=180)
    note: str | None = Field(default=None, max_length=2000)

class RefundItemResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    order_item_id: UUID
    seller_id: UUID
    quantity: int
    unit_amount: Decimal
    refund_amount: Decimal
    commission_reversal: Decimal
    seller_reversal: Decimal
    seller_debt_amount: Decimal
    restock: bool
    processed_at: datetime | None = None

class RefundEventResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    status: RefundStatus
    note: str | None = None
    created_by_id: UUID | None = None
    created_at: datetime

class RefundResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    order_id: UUID
    requested_by_id: UUID
    status: RefundStatus
    reason: RefundReason
    reason_details: str | None = None
    currency: str
    items_amount: Decimal
    shipping_amount: Decimal
    reverse_logistics_entitlement: bool
    logistics_reversal: Decimal
    logistics_debt_amount: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    provider_reference: str | None = None
    idempotency_key: str
    admin_note: str | None = None
    requested_at: datetime
    reviewed_at: datetime | None = None
    processed_at: datetime | None = None
    completed_at: datetime | None = None
    items: list[RefundItemResponse] = Field(default_factory=list)
    events: list[RefundEventResponse] = Field(default_factory=list)


# Phase 3 Task 5: marketplace analytics schemas
class AnalyticsMoneySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: str = "TZS"
    gross_sales: Decimal = Decimal("0")
    commission_revenue: Decimal = Decimal("0")
    seller_net_earnings: Decimal = Decimal("0")
    refunds_completed: Decimal = Decimal("0")
    payouts_completed: Decimal = Decimal("0")

class AnalyticsCountSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    orders: int = 0
    paid_orders: int = 0
    refunded_orders: int = 0
    active_sellers: int = 0
    products: int = 0
    units_sold: int = 0

class AnalyticsOverviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_at: datetime
    end_at: datetime
    money: AnalyticsMoneySummary
    counts: AnalyticsCountSummary
    average_order_value: Decimal = Decimal("0")
    refund_rate_percent: Decimal = Decimal("0")
    pending_wallet_balance: Decimal = Decimal("0")
    available_wallet_balance: Decimal = Decimal("0")
    pending_payout_amount: Decimal = Decimal("0")

class AnalyticsSeriesPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    period: str
    amount: Decimal = Decimal("0")
    order_count: int = 0
    units: int = 0

class AnalyticsRankingRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: UUID
    name: str
    gross_sales: Decimal = Decimal("0")
    net_earnings: Decimal = Decimal("0")
    commission: Decimal = Decimal("0")
    refunds: Decimal = Decimal("0")
    order_count: int = 0
    units: int = 0

class ReconciliationResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    currency: str = "TZS"
    completed_payments: Decimal = Decimal("0")
    order_totals: Decimal = Decimal("0")
    commission_gross: Decimal = Decimal("0")
    commission_revenue: Decimal = Decimal("0")
    seller_net_earnings: Decimal = Decimal("0")
    completed_refunds: Decimal = Decimal("0")
    wallet_sale_credits: Decimal = Decimal("0")
    completed_payouts: Decimal = Decimal("0")
    payment_order_difference: Decimal = Decimal("0")
    commission_split_difference: Decimal = Decimal("0")
    seller_credit_difference: Decimal = Decimal("0")
    is_balanced: bool = False


# Phase 4 Task 1: audit and security schemas
from api.enums import AuditSeverity, SecurityEventType

class AuditLogResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    actor_user_id: UUID | None = None
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    http_method: str | None = None
    request_path: str | None = None
    response_status: int | None = None
    old_values: dict | None = None
    new_values: dict | None = None
    event_metadata: dict | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str
    severity: AuditSeverity
    created_at: datetime

class SecurityEventResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    actor_user_id: UUID | None = None
    event_type: SecurityEventType
    severity: AuditSeverity
    description: str
    request_path: str | None = None
    http_method: str | None = None
    response_status: int | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str
    event_metadata: dict | None = None
    resolved: bool
    resolved_by_id: UUID | None = None
    resolved_at: datetime | None = None
    created_at: datetime

class SecurityEventResolve(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: str | None = Field(default=None, max_length=1000)


# Phase 3 Task 8: seller order management and fulfilment
class SellerPricingPreviewRequest(BaseModel):
    seller_base_price: Decimal = Field(gt=0, max_digits=18, decimal_places=2)
    seller_sale_price: Optional[Decimal] = Field(default=None, gt=0, max_digits=18, decimal_places=2)
    category_id: UUID
    product_id: Optional[UUID] = None
    currency: str = "TZS"

    @model_validator(mode="after")
    def validate_sale(self):
        if self.seller_sale_price is not None and self.seller_sale_price > self.seller_base_price:
            raise ValueError("seller_sale_price cannot exceed seller_base_price")
        return self


class SellerPricingPreviewResponse(BaseModel):
    seller_base_price: Decimal
    seller_sale_price: Optional[Decimal] = None
    commission_rate: Decimal
    commission_amount: Decimal
    customer_price: Decimal
    customer_sale_price: Optional[Decimal] = None
    commission_scope: Optional[str] = None
    currency: str


class SellerOrderMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=5000)
    is_internal: bool = False
    attachment_urls: list[str] = Field(default_factory=list, max_length=10)


class SellerOrderMessageAttachmentResponse(BaseModel):
    id: UUID
    file_url: str
    file_name: Optional[str]
    mime_type: Optional[str]
    created_at: datetime
    model_config = ORM_CONFIG


class SellerOrderMessageResponse(BaseModel):
    id: UUID
    seller_order_id: UUID
    sender_user_id: Optional[UUID]
    sender_role_label: Optional[str]
    message: str
    is_internal: bool
    attachments: list[SellerOrderMessageAttachmentResponse] = Field(default_factory=list)
    created_at: datetime
    model_config = ORM_CONFIG


SellerPackageType = Literal["parcel", "box", "envelope", "crate", "pallet", "other"]


class SellerOrderPackageBase(BaseModel):
    package_label: Optional[str] = Field(default=None, max_length=120)
    package_type: SellerPackageType = "parcel"
    contents_summary: Optional[str] = Field(default=None, max_length=2000)

    weight_kg: Optional[Decimal] = Field(default=None, gt=0)
    length_cm: Optional[Decimal] = Field(default=None, gt=0)
    width_cm: Optional[Decimal] = Field(default=None, gt=0)
    height_cm: Optional[Decimal] = Field(default=None, gt=0)
    package_count: int = Field(default=1, gt=0, le=1000)

    fragile: bool = False
    keep_upright: bool = False
    temperature_sensitive: bool = False
    handling_instructions: Optional[str] = Field(default=None, max_length=2000)

    declared_value: Optional[Decimal] = Field(default=None, ge=0)
    declared_currency: str = Field(default="TZS", min_length=3, max_length=3)

    notes: Optional[str] = Field(default=None, max_length=2000)
    is_ready: bool = False
    attachment_urls: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("package_label", "contents_summary", "handling_instructions", "notes")
    @classmethod
    def clean_package_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("declared_currency")
    @classmethod
    def clean_package_currency(cls, value: str) -> str:
        return _normalise_currency(value)

    @model_validator(mode="after")
    def validate_ready_package(self):
        if self.is_ready and self.weight_kg is None:
            raise ValueError("weight_kg is required when package is marked ready")
        return self


class SellerOrderPackageCreate(SellerOrderPackageBase):
    pass


class SellerOrderPackageUpsert(SellerOrderPackageBase):
    """Backward-compatible legacy single-package upsert contract."""
    pass


class SellerOrderPackageUpdate(BaseModel):
    package_label: Optional[str] = Field(default=None, max_length=120)
    package_type: Optional[SellerPackageType] = None
    contents_summary: Optional[str] = Field(default=None, max_length=2000)
    weight_kg: Optional[Decimal] = Field(default=None, gt=0)
    length_cm: Optional[Decimal] = Field(default=None, gt=0)
    width_cm: Optional[Decimal] = Field(default=None, gt=0)
    height_cm: Optional[Decimal] = Field(default=None, gt=0)
    package_count: Optional[int] = Field(default=None, gt=0, le=1000)
    fragile: Optional[bool] = None
    keep_upright: Optional[bool] = None
    temperature_sensitive: Optional[bool] = None
    handling_instructions: Optional[str] = Field(default=None, max_length=2000)
    declared_value: Optional[Decimal] = Field(default=None, ge=0)
    declared_currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    notes: Optional[str] = Field(default=None, max_length=2000)
    is_ready: Optional[bool] = None
    attachment_urls: Optional[list[str]] = Field(default=None, max_length=20)

    @field_validator("package_label", "contents_summary", "handling_instructions", "notes")
    @classmethod
    def clean_package_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("declared_currency")
    @classmethod
    def clean_package_update_currency(cls, value: str | None) -> str | None:
        return _normalise_currency(value) if value is not None else None


class SellerOrderPackageAttachmentResponse(BaseModel):
    id: UUID
    file_url: str
    file_name: Optional[str]
    mime_type: Optional[str]
    created_at: datetime
    model_config = ORM_CONFIG


class SellerOrderPackageResponse(BaseModel):
    id: UUID
    seller_order_id: UUID
    package_label: Optional[str]
    package_type: SellerPackageType
    contents_summary: Optional[str]
    weight_kg: Optional[Decimal]
    length_cm: Optional[Decimal]
    width_cm: Optional[Decimal]
    height_cm: Optional[Decimal]
    package_count: int
    fragile: bool
    keep_upright: bool
    temperature_sensitive: bool
    handling_instructions: Optional[str]
    declared_value: Optional[Decimal]
    declared_currency: str
    notes: Optional[str]
    is_ready: bool
    prepared_at: Optional[datetime]
    sealed_at: Optional[datetime]
    attachments: list[SellerOrderPackageAttachmentResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: Optional[datetime]
    model_config = ORM_CONFIG


class PaginatedSellerOrderPackageResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[SellerOrderPackageResponse]


class SellerDashboardResponse(BaseModel):
    products_total: int
    products_approved: int
    products_pending_review: int
    active_promotions: int
    orders_total: int
    orders_new: int
    orders_processing: int
    orders_ready_to_ship: int
    wallet_currency: str
    wallet_pending: Decimal
    wallet_available: Decimal
    wallet_reserved: Decimal
    pending_payouts: int
    rating_average: Decimal
    review_count: int
    unanswered_questions: int


class PaginatedWalletTransactionResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[WalletTransactionResponse]


class PaginatedPayoutRequestResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[PayoutRequestResponse]


class PaginatedPromotionResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list["PromotionResponse"]


class SellerOrderActionRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=2000)

class SellerOrderCancellationRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)
    notes: Optional[str] = Field(default=None, max_length=2000)

class SellerOrderDispatchRequest(BaseModel):
    carrier_name: str = Field(min_length=2, max_length=120)
    tracking_number: str = Field(min_length=2, max_length=150)
    tracking_url: Optional[str] = Field(default=None, max_length=500)
    location: Optional[str] = Field(default=None, max_length=255)
    notes: Optional[str] = Field(default=None, max_length=2000)

class SellerOrderItemView(BaseModel):
    id: UUID
    product_id: UUID
    variant_id: Optional[UUID]
    product_name: str
    variant_name: Optional[str]
    quantity: int
    unit_price: Decimal
    total_price: Decimal
    model_config = ORM_CONFIG

class SellerOrderView(BaseModel):
    id: UUID
    order_id: UUID
    seller_id: UUID
    order_status: OrderStatus
    seller_status: SellerOrderStatus
    currency: str
    seller_subtotal: Decimal
    item_count: int
    customer_name: str
    customer_phone: Optional[str]
    shipping_address: Optional[Dict[str, Any]]
    shipping_method_name: Optional[str]
    shipping_carrier: Optional[str]
    estimated_delivery_from: Optional[datetime]
    estimated_delivery_to: Optional[datetime]
    seller_notes: Optional[str]
    cancellation_reason: Optional[str]
    items: list[SellerOrderItemView]
    shipment: Optional[ShipmentResponse] = None
    created_at: datetime
    updated_at: Optional[datetime]

class SellerOrderListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SellerOrderView]

class SellerOrderSummaryResponse(BaseModel):
    total_orders: int
    new_orders: int
    accepted_orders: int
    processing_orders: int
    ready_to_ship_orders: int
    shipped_orders: int
    delivered_orders: int
    cancellation_requests: int
    gross_sales: Decimal
    units_sold: int


# Phase 3 Task 10: external delivery integration
class DeliveryQuoteRequest(BaseModel):
    pickup: dict
    dropoff: dict
    package: dict
    currency: str = "TZS"

class DeliveryQuoteResponse(BaseModel):
    provider: str
    quote_id: str | None = None
    fee: Decimal
    currency: str
    estimated_pickup_at: datetime | None = None
    estimated_delivery_at: datetime | None = None
    raw_response: dict | None = None

class DeliveryRequestResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    shipment_id: UUID
    seller_order_id: UUID
    provider: str
    external_delivery_id: str
    status: DeliveryStatus
    tracking_number: str | None = None
    tracking_url: str | None = None
    delivery_fee: Decimal | None = None
    currency: str
    courier_name: str | None = None
    courier_phone: str | None = None
    estimated_pickup_at: datetime | None = None
    estimated_delivery_at: datetime | None = None
    last_synced_at: datetime | None = None
    created_at: datetime

class DeliveryWebhookResponse(BaseModel):
    accepted: bool
    delivery_id: str
    status: DeliveryStatus


# Phase 3 Task 12: reviews
class ReviewCreate(BaseModel):
    order_item_id: UUID
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = Field(default=None, max_length=150)
    comment: Optional[str] = Field(default=None, max_length=5000)

class StoreReviewCreate(BaseModel):
    seller_order_id: UUID
    rating: int = Field(ge=1, le=5)
    title: Optional[str] = Field(default=None, max_length=150)
    comment: Optional[str] = Field(default=None, max_length=5000)

class ReviewUpdate(BaseModel):
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    title: Optional[str] = Field(default=None, max_length=150)
    comment: Optional[str] = Field(default=None, max_length=5000)

class SellerReviewReply(BaseModel):
    reply: str = Field(min_length=1, max_length=3000)

class ReviewModerationRequest(BaseModel):
    status: ReviewStatus
    reason: Optional[str] = Field(default=None, max_length=1000)

class ReviewReportRequest(BaseModel):
    reason: ReviewReportReason
    details: Optional[str] = Field(default=None, max_length=2000)

class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    rating: int
    title: Optional[str]
    comment: Optional[str]
    verified_purchase: bool
    status: ReviewStatus
    seller_reply: Optional[str]
    seller_replied_at: Optional[datetime]
    helpful_count: int
    created_at: datetime
    updated_at: Optional[datetime]

class ReviewListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    average_rating: Decimal
    results: list[ReviewResponse]


class AdminReviewResponse(BaseModel):
    id: UUID
    product_id: UUID
    user_id: UUID
    seller_id: UUID
    order_id: Optional[UUID] = None
    rating: int
    title: Optional[str] = None
    comment: Optional[str] = None
    status: ReviewStatus
    admin_reply: Optional[str] = None
    seller_reply: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    product_name: Optional[str] = None
    seller_name: Optional[str] = None
    reported: bool = False
    report_count: int = 0


class PaginatedAdminReviewResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    average_rating: Decimal
    results: list[AdminReviewResponse]


class AdminReviewUpdateRequest(BaseModel):
    status: Optional[ReviewStatus] = None
    admin_reply: Optional[str] = Field(default=None, max_length=3000)



class SupportTicketCreate(BaseModel):
    subject: str = Field(min_length=3, max_length=255)
    description: Optional[str] = Field(default=None, max_length=10000)
    category: Optional[str] = Field(default=None, max_length=80)
    channel: str = Field(default="customer", max_length=50)
    priority: str = Field(default="medium")
    order_id: Optional[UUID] = None
    seller_id: Optional[UUID] = None
    shipment_id: Optional[UUID] = None


class SupportTicketUpdate(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to_id: Optional[UUID] = None
    resolution_note: Optional[str] = Field(default=None, max_length=10000)


class SupportTicketMessageCreate(BaseModel):
    message: str = Field(min_length=1, max_length=10000)
    visibility: str = Field(default="all")


class SupportTicketParticipantResponse(BaseModel):
    id: Optional[UUID] = None
    user_id: Optional[UUID] = None
    name: Optional[str] = None
    email: Optional[str] = None
    role: str


class SupportTicketMessageResponse(BaseModel):
    id: UUID
    sender_id: Optional[UUID] = None
    sender_name: Optional[str] = None
    sender_role: Optional[str] = None
    message: str
    visibility: str
    created_at: datetime


class SupportTicketResponse(BaseModel):
    id: UUID
    ticket_number: str
    user_id: UUID
    customer_name: Optional[str] = None
    customer_email: Optional[str] = None
    subject: str
    description: Optional[str] = None
    category: Optional[str] = None
    channel: Optional[str] = None
    priority: str
    status: str
    assigned_to_id: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    order_id: Optional[UUID] = None
    seller_id: Optional[UUID] = None
    seller_name: Optional[str] = None
    shipment_id: Optional[UUID] = None
    logistics_provider: Optional[str] = None
    participants: list[SupportTicketParticipantResponse] = Field(default_factory=list)
    messages: list[SupportTicketMessageResponse] = Field(default_factory=list)
    resolution_note: Optional[str] = None
    first_response_due_at: datetime
    resolution_due_at: datetime
    first_responded_at: Optional[datetime] = None
    sla_breached_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: Optional[datetime] = None


class PaginatedSupportTicketResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[SupportTicketResponse]


class OperationsExceptionResponse(BaseModel):
    type: str
    severity: Literal["warning", "critical"]
    resource_id: str
    title: str
    age_minutes: int
    action_url: Optional[str] = None


class OperationsOverviewResponse(BaseModel):
    generated_at: datetime
    open_support_tickets: int
    unassigned_support_tickets: int
    breached_support_tickets: int
    urgent_support_tickets: int
    failed_notification_deliveries: int
    stale_notification_deliveries: int
    unresolved_security_events: int
    failed_payments: int
    pending_refunds: int
    failed_deliveries: int
    exceptions: list[OperationsExceptionResponse]


# Phase 3 Task 13: wishlist and favorite stores
class WishlistProductItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    wishlist_id: UUID
    product_id: UUID
    name: str
    slug: str
    sku: str
    price: Decimal
    sale_price: Optional[Decimal] = None
    currency: str
    primary_image_url: Optional[str] = None
    store_name: Optional[str] = None
    store_slug: Optional[str] = None
    is_available: bool
    is_in_stock: bool
    created_at: datetime


class WishlistProductListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[WishlistProductItemResponse]


class FavoriteStoreItemResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    favorite_id: UUID
    store_id: UUID
    store_name: str
    slug: str
    logo_url: Optional[str] = None
    banner_url: Optional[str] = None
    rating: Decimal
    review_count: int
    followers_count: int
    is_available: bool
    created_at: datetime


class FavoriteStoreListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[FavoriteStoreItemResponse]


class WishlistSummaryResponse(BaseModel):
    product_count: int
    favorite_store_count: int


class WishlistMutationResponse(BaseModel):
    message: str


  
# PHASE 3 TASK 14: PROMOTION SCHEMAS
  

PromotionTypeLiteral = Literal[
    "percentage", "fixed_amount", "free_shipping", "buy_x_get_y",
    "flash_sale", "category_discount", "store_wide", "first_order",
    "loyalty", "referral",
]

class PromotionRuleInput(BaseModel):
    rule_type: Literal["product", "category", "store", "customer_group", "minimum_quantity"]
    product_id: UUID | None = None
    category_id: UUID | None = None
    store_id: UUID | None = None
    value: dict[str, Any] | None = None


class PromotionCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    code: str | None = Field(default=None, min_length=2, max_length=50)
    description: str | None = None
    promotion_type: PromotionTypeLiteral
    discount_value: Decimal = Field(default=0, ge=0)
    minimum_order_amount: Decimal | None = Field(default=None, ge=0)
    maximum_discount_amount: Decimal | None = Field(default=None, ge=0)
    usage_limit: int | None = Field(default=None, ge=0)
    usage_per_customer: int | None = Field(default=None, gt=0)
    stackable: bool = False
    automatic: bool = False
    is_active: bool = True
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    rules: list[PromotionRuleInput] = Field(default_factory=list)

    @field_validator("code")
    @classmethod
    def normalise_promotion_code(cls, value):
        return value.strip().upper() if value else value

    @model_validator(mode="after")
    def validate_promotion(self):
        if self.promotion_type == "percentage" and self.discount_value > 100:
            raise ValueError("Percentage discount cannot exceed 100")
        if self.promotion_type not in {"free_shipping", "buy_x_get_y"} and self.discount_value <= 0:
            raise ValueError("discount_value must be greater than zero")
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class PromotionUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=180)
    description: str | None = None
    discount_value: Decimal | None = Field(default=None, ge=0)
    minimum_order_amount: Decimal | None = Field(default=None, ge=0)
    maximum_discount_amount: Decimal | None = Field(default=None, ge=0)
    usage_limit: int | None = Field(default=None, ge=0)
    usage_per_customer: int | None = Field(default=None, gt=0)
    stackable: bool | None = None
    automatic: bool | None = None
    is_active: bool | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None


class PromotionResponse(BaseModel):
    id: UUID
    seller_id: UUID | None
    name: str
    code: str | None
    description: str | None
    promotion_type: str
    discount_value: Decimal
    minimum_order_amount: Decimal | None
    maximum_discount_amount: Decimal | None
    usage_limit: int | None
    usage_per_customer: int | None
    usage_count: int
    stackable: bool
    automatic: bool
    funding_source: str = "seller"
    is_active: bool
    starts_at: datetime | None
    ends_at: datetime | None
    created_at: datetime
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class PromotionApplyRequest(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    subtotal: Decimal = Field(gt=0)

    @field_validator("code")
    @classmethod
    def normalise_code(cls, value):
        return value.strip().upper()


class PromotionApplyResponse(BaseModel):
    promotion_id: UUID
    code: str | None
    subtotal: Decimal
    discount_amount: Decimal
    total_after_discount: Decimal
    promotion_type: str


class CampaignCreate(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    slug: str = Field(min_length=2, max_length=180, pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
    description: str | None = None
    banner_url: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    is_active: bool = True
    promotion_ids: list[UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_dates(self):
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class CampaignResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    banner_url: str | None
    starts_at: datetime | None
    ends_at: datetime | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    model_config = ConfigDict(from_attributes=True)


class NotificationResponse(BaseModel):
    id: UUID
    event: NotificationEvent
    title: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)
    action_url: str | None = None
    is_read: bool
    read_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSummary(BaseModel):
    total: int
    unread: int
    read: int


class NotificationPreferenceUpdate(BaseModel):
    in_app_enabled: bool | None = None
    email_enabled: bool | None = None
    sms_enabled: bool | None = None
    push_enabled: bool | None = None
    event_preferences: dict[str, dict[str, bool]] | None = None
    quiet_hours_start: Time | None = None
    quiet_hours_end: Time | None = None
    timezone: str | None = Field(default=None, min_length=1, max_length=64)

    @field_validator("event_preferences")
    @classmethod
    def validate_events(cls, value):
        if value is None:
            return value
        valid_events = {item.value for item in NotificationEvent}
        valid_channels = {item.value for item in NotificationChannel}
        for event, channels in value.items():
            if event not in valid_events:
                raise ValueError(f"Unknown notification event: {event}")
            unknown = set(channels) - valid_channels
            if unknown:
                raise ValueError(f"Unknown notification channels: {sorted(unknown)}")
        return value


class NotificationPreferenceResponse(BaseModel):
    in_app_enabled: bool
    email_enabled: bool
    sms_enabled: bool
    push_enabled: bool
    event_preferences: dict[str, Any] = Field(default_factory=dict)
    quiet_hours_start: Time | None = None
    quiet_hours_end: Time | None = None
    timezone: str

    model_config = ConfigDict(from_attributes=True)


class NotificationTemplateCreate(BaseModel):
    event: NotificationEvent
    channel: NotificationChannel
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str = Field(min_length=1)
    is_active: bool = True


class NotificationTemplateUpdate(BaseModel):
    subject_template: str | None = Field(default=None, max_length=255)
    body_template: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None


class NotificationTemplateResponse(BaseModel):
    id: UUID
    event: NotificationEvent
    channel: NotificationChannel
    subject_template: str | None
    body_template: str
    is_active: bool
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DeviceTokenCreate(BaseModel):
    token: str = Field(min_length=10)
    platform: str = Field(pattern="^(android|ios|web)$")
    device_name: str | None = Field(default=None, max_length=120)


class DeviceTokenResponse(BaseModel):
    id: UUID
    platform: str
    device_name: str | None
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


# Phase 3 Task 16: Product Questions and Answers schemas
class ProductQuestionCreate(BaseModel):
    question: str = Field(min_length=5, max_length=2000)

    @field_validator("question")
    @classmethod
    def clean_question(cls, value: str) -> str:
        return _clean_required_text(value)


class ProductQuestionUpdate(ProductQuestionCreate):
    pass


class ProductAnswerCreate(BaseModel):
    answer: str = Field(min_length=2, max_length=4000)

    @field_validator("answer")
    @classmethod
    def clean_answer(cls, value: str) -> str:
        return _clean_required_text(value)


class ProductAnswerUpdate(ProductAnswerCreate):
    pass


class QuestionReportCreate(BaseModel):
    reason: QuestionReportReason
    details: Optional[str] = Field(default=None, max_length=2000)


class QuestionModerationRequest(BaseModel):
    status: QuestionStatus
    note: Optional[str] = Field(default=None, max_length=2000)


class ProductAnswerResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    question_id: UUID
    user_id: UUID
    answer: str
    is_seller_answer: bool
    is_official: bool
    status: QuestionStatus
    helpful_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None


class ProductQuestionResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    product_id: UUID
    customer_id: UUID
    question: str
    status: QuestionStatus
    helpful_count: int
    answer_count: int
    created_at: datetime
    updated_at: Optional[datetime] = None
    answers: List[ProductAnswerResponse] = Field(default_factory=list)


class ProductQuestionListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: List[ProductQuestionResponse]


class SearchProductItem(BaseModel):
    id: UUID
    seller_id: UUID
    category_id: UUID
    brand_id: Optional[UUID] = None
    name: str
    slug: str
    price: Decimal
    sale_price: Optional[Decimal] = None
    currency: str
    primary_image_url: Optional[str] = None
    model_config = ORM_CONFIG


class ProductSearchResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[SearchProductItem]


class SearchSuggestionResponse(BaseModel):
    suggestions: list[str]


class TrendingSearchItem(BaseModel):
    term: str
    search_count: int


class ProductViewCreate(BaseModel):
    session_id: Optional[str] = Field(default=None, max_length=128)
    source: Optional[str] = Field(default=None, max_length=64)
    search_query: Optional[str] = Field(default=None, max_length=255)


class ProductViewResponse(BaseModel):
    id: UUID
    product_id: UUID
    user_id: Optional[UUID] = None
    session_id: Optional[str] = None
    source: Optional[str] = None
    created_at: datetime
    model_config = ORM_CONFIG


class RecommendationListResponse(BaseModel):
    total: int
    results: list[SearchProductItem]


class SellerSearchAnalyticsItem(BaseModel):
    query: str
    searches: int
    product_views: int


class SellerProductPerformanceItem(BaseModel):
    product_id: UUID
    product_name: str
    views: int
    
class NameLookupRequest(BaseModel):
    account_number: str
    provider: str


class NameLookupResponse(BaseModel):
    success: bool
    account_name: str | None = None
    provider: str | None = None
    account_number: str
    message: str | None = None    

  
# PAYMENT ADMINISTRATION
  

class PaymentAdminPage(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[dict]


class FinanceSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    default_payment_provider_code: Optional[str] = Field(default=None, max_length=80)
    settlement_currency: Optional[str] = Field(default=None, min_length=3, max_length=10)

    minimum_payout_amount: Optional[Decimal] = Field(default=None, ge=0)
    payout_fee_type: Optional[Literal["fixed", "percentage"]] = None
    payout_fee_value: Optional[Decimal] = Field(default=None, ge=0)
    payout_processing_days: Optional[int] = Field(default=None, ge=0, le=90)
    auto_payout_enabled: Optional[bool] = None

    escrow_enabled: Optional[bool] = None
    auto_release_enabled: Optional[bool] = None
    allow_partial_release: Optional[bool] = None
    hold_commission_until_release: Optional[bool] = None

    @field_validator("settlement_currency")
    @classmethod
    def normalise_settlement_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().upper()
        if len(value) != 3 or not value.isalpha():
            raise ValueError("settlement_currency must be a three-letter currency code")
        return value

    @field_validator("default_payment_provider_code")
    @classmethod
    def normalise_provider_code(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        return value or None


class FinanceSettingsResponse(BaseModel):
    id: UUID
    singleton_key: str
    default_payment_provider_code: Optional[str]
    settlement_currency: str
    minimum_payout_amount: Decimal
    payout_fee_type: str
    payout_fee_value: Decimal
    payout_processing_days: int
    auto_payout_enabled: bool
    escrow_enabled: bool
    auto_release_enabled: bool
    allow_partial_release: bool
    hold_commission_until_release: bool
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ORM_CONFIG


class FxConversionRequest(BaseModel):
    amount: Decimal = Field(gt=0)
    from_currency: str = Field(min_length=3, max_length=10)
    to_currency: str = Field(min_length=3, max_length=10)
    at: Optional[datetime] = None

    @field_validator("from_currency", "to_currency")
    @classmethod
    def normalise_currency_code(cls, value: str) -> str:
        return value.strip().upper()


class FxConversionResponse(BaseModel):
    from_currency: str
    to_currency: str
    original_amount: Decimal
    converted_amount: Decimal
    rate: Decimal
    rate_source: Optional[str]
    effective_at: datetime


class OrderFinanceLifecycleResponse(BaseModel):
    order_id: UUID
    currency: str
    order_total: Decimal
    completed_payment_total: Decimal
    commission_total: Decimal
    seller_net_total: Decimal
    escrow_gross_total: Decimal
    escrow_released_total: Decimal
    escrow_refunded_total: Decimal
    completed_refund_total: Decimal
    wallet_sale_credit_total: Decimal
    wallet_release_total: Decimal
    wallet_refund_debit_total: Decimal
    logistics_delivery_credit_total: Decimal
    logistics_refund_debit_total: Decimal
    payment_count: int
    commission_count: int
    escrow_hold_count: int
    refund_count: int
    wallet_transaction_count: int
    logistics_transaction_count: int
    balanced: bool
    blockers: list[str]


class EscrowHoldResponse(BaseModel):
    id: UUID
    payment_id: Optional[UUID]
    order_id: UUID
    order_item_id: Optional[UUID]
    seller_id: Optional[UUID]
    seller_release_shipment_id: Optional[UUID] = None
    seller_release_handover_id: Optional[UUID] = None
    seller_release_proof_id: Optional[UUID] = None
    seller_release_trigger: Optional[str] = None
    seller_release_verified_at: Optional[datetime] = None
    currency: str
    gross_amount: Decimal
    seller_amount: Decimal
    commission_amount: Decimal
    refunded_amount: Decimal
    released_amount: Decimal
    status: str
    release_after: Optional[datetime]
    released_at: Optional[datetime]
    disputed_at: Optional[datetime]
    refunded_at: Optional[datetime]
    reference: str
    note: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime] = None

    model_config = ORM_CONFIG


class PaginatedEscrowHoldResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[EscrowHoldResponse]


class EscrowStatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    note: Optional[str] = Field(default=None, max_length=2000)


class EscrowReleaseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    amount: Optional[Decimal] = Field(default=None, gt=0)
    note: Optional[str] = Field(default=None, max_length=2000)


class PaymentProviderCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    code: str = Field(min_length=2, max_length=80)
    provider_type: str = "gateway"
    status: str = "active"
    supported_currencies: list[str] = Field(default_factory=list)
    supported_methods: list[str] = Field(default_factory=list)
    environment: str | None = None
    is_default: bool = False


class PaymentProviderUpdate(BaseModel):
    name: str | None = None
    provider_type: str | None = None
    status: str | None = None
    supported_currencies: list[str] | None = None
    supported_methods: list[str] | None = None
    environment: str | None = None
    is_default: bool | None = None


class PaymentCurrencyCreate(BaseModel):
    code: str = Field(min_length=3, max_length=10)
    name: str
    symbol: str
    is_base: bool = False
    is_active: bool = True
    decimal_places: int = Field(default=2, ge=0, le=8)


class PaymentCurrencyUpdate(BaseModel):
    name: str | None = None
    symbol: str | None = None
    is_base: bool | None = None
    is_active: bool | None = None
    decimal_places: int | None = Field(default=None, ge=0, le=8)


class PaymentFxRateCreate(BaseModel):
    base_currency: str
    quote_currency: str
    rate: Decimal = Field(gt=0)
    source: str | None = None
    effective_at: datetime | None = None
    is_active: bool = True


class PaymentCountryCreate(BaseModel):
    code: str = Field(min_length=2, max_length=3)
    name: str
    currency_code: str
    is_active: bool = True
    payments_enabled: bool = True
    payouts_enabled: bool = True


class PaymentCountryUpdate(BaseModel):
    name: str | None = None
    currency_code: str | None = None
    is_active: bool | None = None
    payments_enabled: bool | None = None
    payouts_enabled: bool | None = None


class PaymentDisputeUpdate(BaseModel):
    status: str | None = None
    resolution_note: str | None = None


class PaymentRiskUpdate(BaseModel):
    status: str | None = None
    resolution_note: str | None = None


class PaymentReconciliationUpdate(BaseModel):
    status: str | None = None
    reconciliation_note: str | None = None


class FinancialReconciliationCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=8, max_length=180)


class FinancialReconciliationEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action: Literal["acknowledged", "resolved", "reopened"]
    note: str = Field(min_length=3, max_length=2000)


class FinancialReconciliationEventResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    action: str
    note: str | None = None
    created_by_id: UUID | None = None
    created_at: datetime


class FinancialReconciliationResponse(BaseModel):
    model_config = ORM_CONFIG
    id: UUID
    order_id: UUID
    idempotency_key: str
    currency: str
    status: str
    snapshot: dict[str, Any]
    findings: list[str]
    snapshot_hash: str
    created_by_id: UUID | None = None
    created_at: datetime
    events: list[FinancialReconciliationEventResponse] = Field(default_factory=list)


class PaginatedFinancialReconciliationResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[FinancialReconciliationResponse]


         
# PHASE 12: ADVERTISEMENT / SPONSORED PLACEMENTS
         
class AdvertisementCreate(BaseModel):
    advertiser_name: str = Field(min_length=2, max_length=180)
    title: str = Field(min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)

    image_url: str = Field(min_length=1, max_length=1000)
    mobile_image_url: Optional[str] = Field(default=None, max_length=1000)
    alt_text: Optional[str] = Field(default=None, max_length=255)
    target_url: Optional[str] = Field(default=None, max_length=1500)
    cta_label: Optional[str] = Field(default="Shop Now", max_length=80)

    placement: AdvertisementPlacement
    status: AdvertisementStatus = AdvertisementStatus.draft

    # Required exact campaign window. Both values must include a timezone.
    starts_at: datetime
    ends_at: datetime

    priority: int = Field(default=0, ge=0)
    billing_type: AdvertisementBillingType = AdvertisementBillingType.fixed
    price: Optional[Decimal] = Field(default=None, ge=0)
    currency: str = Field(default="TZS", min_length=3, max_length=3)
    metadata_json: Dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "advertiser_name",
        "title",
        "image_url",
    )
    @classmethod
    def clean_required_ad_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator(
        "description",
        "mobile_image_url",
        "alt_text",
        "target_url",
        "cta_label",
    )
    @classmethod
    def clean_optional_ad_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("currency")
    @classmethod
    def clean_ad_currency(cls, value: str) -> str:
        return _normalise_currency(value)

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_ad_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("Advertisement dates and times must include a timezone")
        return value

    @model_validator(mode="after")
    def validate_advertisement_schedule(self):
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be later than starts_at")
        return self


class AdvertisementUpdate(BaseModel):
    advertiser_name: Optional[str] = Field(default=None, min_length=2, max_length=180)
    title: Optional[str] = Field(default=None, min_length=2, max_length=180)
    description: Optional[str] = Field(default=None, max_length=5000)

    image_url: Optional[str] = Field(default=None, min_length=1, max_length=1000)
    mobile_image_url: Optional[str] = Field(default=None, max_length=1000)
    alt_text: Optional[str] = Field(default=None, max_length=255)
    target_url: Optional[str] = Field(default=None, max_length=1500)
    cta_label: Optional[str] = Field(default=None, max_length=80)

    placement: Optional[AdvertisementPlacement] = None
    status: Optional[AdvertisementStatus] = None
    starts_at: Optional[datetime] = None
    ends_at: Optional[datetime] = None

    priority: Optional[int] = Field(default=None, ge=0)
    billing_type: Optional[AdvertisementBillingType] = None
    price: Optional[Decimal] = Field(default=None, ge=0)
    currency: Optional[str] = Field(default=None, min_length=3, max_length=3)
    metadata_json: Optional[Dict[str, Any]] = None

    @field_validator(
        "advertiser_name",
        "title",
        "image_url",
    )
    @classmethod
    def clean_required_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        if not value:
            raise ValueError("Value must not be blank")
        return value

    @field_validator(
        "description",
        "mobile_image_url",
        "alt_text",
        "target_url",
        "cta_label",
    )
    @classmethod
    def clean_optional_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None

    @field_validator("currency")
    @classmethod
    def clean_update_currency(cls, value: str | None) -> str | None:
        return _normalise_currency(value) if value is not None else None

    @field_validator("starts_at", "ends_at")
    @classmethod
    def require_update_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("Advertisement dates and times must include a timezone")
        return value


class AdvertisementResponse(BaseModel):
    id: UUID
    advertiser_name: str
    title: str
    description: Optional[str]

    image_url: str
    mobile_image_url: Optional[str]
    alt_text: Optional[str]
    target_url: Optional[str]
    cta_label: Optional[str]

    placement: AdvertisementPlacement
    status: AdvertisementStatus
    effective_status: Literal["draft", "scheduled", "active", "paused", "expired"]

    starts_at: datetime
    ends_at: datetime
    priority: int

    billing_type: AdvertisementBillingType
    price: Optional[Decimal]
    currency: str

    impression_count: int
    click_count: int
    metadata_json: Dict[str, Any]

    created_by_id: Optional[UUID]
    updated_by_id: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]


class PaginatedAdvertisementResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[AdvertisementResponse]


class AdvertisementActionResponse(BaseModel):
    id: UUID
    status: AdvertisementStatus
    effective_status: Literal["draft", "scheduled", "active", "paused", "expired"]
    message: str



         
# PHASE 12 TASK 3: PUBLIC ADVERTISEMENT DELIVERY
         
class PublicAdvertisementResponse(BaseModel):
    id: UUID
    advertiser_name: str
    title: str
    description: Optional[str] = None
    image_url: str
    mobile_image_url: Optional[str] = None
    alt_text: Optional[str] = None
    target_url: Optional[str] = None
    cta_label: Optional[str] = None
    placement: AdvertisementPlacement
    starts_at: datetime
    ends_at: datetime
    sponsored: Literal[True] = True


class PublicAdvertisementSlotResponse(BaseModel):
    placement: AdvertisementPlacement
    advertisement: Optional[PublicAdvertisementResponse] = None



class AdvertisementImageUploadResponse(BaseModel):
    image_url: str
    original_filename: str
    mime_type: str
    file_size: int
    width: int
    height: int
    variant: Literal["desktop", "mobile"]



  
# PHASE 12 TASK 7: ADVERTISEMENT TRACKING
  
class AdvertisementTrackingRequest(BaseModel):
    session_id: str = Field(min_length=16, max_length=128)
    client_event_id: Optional[str] = Field(default=None, min_length=8, max_length=128)
    page_path: Optional[str] = Field(default=None, max_length=500)

    @field_validator("session_id", "client_event_id", "page_path")
    @classmethod
    def clean_ad_tracking_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class AdvertisementTrackingResponse(BaseModel):
    accepted: bool
    duplicate: bool = False
    event_type: Literal["impression", "click"]
    impression_count: int
    click_count: int



    
# PHASE 12 TASK 8: ADVERTISEMENT REVENUE & ANALYTICS
    
class AdvertisementRevenueByCurrency(BaseModel):
    currency: str
    estimated_revenue: Decimal


class AdvertisementAnalyticsStatusCounts(BaseModel):
    total: int
    draft: int
    scheduled: int
    active: int
    paused: int
    expired: int


class AdvertisementAnalyticsCampaignRow(BaseModel):
    id: UUID
    advertiser_name: str
    title: str
    placement: AdvertisementPlacement
    effective_status: Literal["draft", "scheduled", "active", "paused", "expired"]
    billing_type: AdvertisementBillingType
    price: Optional[Decimal]
    currency: str
    impressions: int
    clicks: int
    ctr_percent: float
    estimated_revenue: Decimal
    starts_at: datetime
    ends_at: datetime


class AdvertisementAnalyticsDailyPoint(BaseModel):
    date: str
    impressions: int
    clicks: int


class AdvertisementAnalyticsAdvertiserRow(BaseModel):
    advertiser_name: str
    campaigns: int
    impressions: int
    clicks: int
    ctr_percent: float
    revenue_by_currency: list[AdvertisementRevenueByCurrency]


class AdvertisementAnalyticsOverview(BaseModel):
    generated_at: datetime
    days: int
    status_counts: AdvertisementAnalyticsStatusCounts
    total_impressions: int
    total_clicks: int
    ctr_percent: float
    revenue_by_currency: list[AdvertisementRevenueByCurrency]
    daily_engagement: list[AdvertisementAnalyticsDailyPoint]
    top_campaigns: list[AdvertisementAnalyticsCampaignRow]
    advertisers: list[AdvertisementAnalyticsAdvertiserRow]
    revenue_note: str


    
# PHASE 1 TASK 1: SELLER PICKUP LOCATIONS
    
class SellerPickupLocationCreate(BaseModel):
    label: str = Field(default="Main pickup", min_length=2, max_length=120)
    formatted_address: str = Field(min_length=3, max_length=1000)
    country: str = Field(default="Tanzania", min_length=2, max_length=100)
    region: str = Field(min_length=2, max_length=100)
    city: str = Field(min_length=2, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    ward: str | None = Field(default=None, max_length=100)
    street: str | None = Field(default=None, max_length=1000)
    landmark: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=50)
    place_id: str | None = Field(default=None, max_length=255)
    latitude: Decimal = Field(ge=Decimal("-90"), le=Decimal("90"))
    longitude: Decimal = Field(ge=Decimal("-180"), le=Decimal("180"))
    pickup_contact_name: str = Field(min_length=2, max_length=180)
    pickup_phone: str = Field(min_length=7, max_length=30)
    pickup_instructions: str | None = Field(default=None, max_length=3000)
    is_default: bool = False
    is_active: bool = True

    @field_validator(
        "label", "formatted_address", "country", "region", "city", "pickup_contact_name"
    )
    @classmethod
    def clean_required_pickup_text(cls, value: str) -> str:
        return _clean_required_text(value)

    @field_validator(
        "district", "ward", "street", "landmark", "postal_code", "place_id", "pickup_instructions"
    )
    @classmethod
    def clean_optional_pickup_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("pickup_phone")
    @classmethod
    def clean_pickup_phone(cls, value: str) -> str:
        cleaned = _normalise_phone(value)
        if cleaned is None:
            raise ValueError("Pickup phone is required")
        return cleaned


class SellerPickupLocationUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=2, max_length=120)
    formatted_address: str | None = Field(default=None, min_length=3, max_length=1000)
    country: str | None = Field(default=None, min_length=2, max_length=100)
    region: str | None = Field(default=None, min_length=2, max_length=100)
    city: str | None = Field(default=None, min_length=2, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    ward: str | None = Field(default=None, max_length=100)
    street: str | None = Field(default=None, max_length=1000)
    landmark: str | None = Field(default=None, max_length=255)
    postal_code: str | None = Field(default=None, max_length=50)
    place_id: str | None = Field(default=None, max_length=255)
    latitude: Decimal | None = Field(default=None, ge=Decimal("-90"), le=Decimal("90"))
    longitude: Decimal | None = Field(default=None, ge=Decimal("-180"), le=Decimal("180"))
    pickup_contact_name: str | None = Field(default=None, min_length=2, max_length=180)
    pickup_phone: str | None = Field(default=None, min_length=7, max_length=30)
    pickup_instructions: str | None = Field(default=None, max_length=3000)
    is_default: bool | None = None
    is_active: bool | None = None

    @field_validator("label", "formatted_address", "country", "region", "city", "pickup_contact_name")
    @classmethod
    def clean_required_pickup_update_text(cls, value: str | None) -> str | None:
        return _clean_required_text(value) if value is not None else None

    @field_validator("district", "ward", "street", "landmark", "postal_code", "place_id", "pickup_instructions")
    @classmethod
    def clean_optional_pickup_update_text(cls, value: str | None) -> str | None:
        return _clean_optional_text(value)

    @field_validator("pickup_phone")
    @classmethod
    def clean_pickup_update_phone(cls, value: str | None) -> str | None:
        return _normalise_phone(value)


class SellerPickupLocationResponse(BaseModel):
    id: UUID
    seller_id: UUID
    label: str
    formatted_address: str
    country: str
    region: str
    city: str
    district: str | None
    ward: str | None
    street: str | None
    landmark: str | None
    postal_code: str | None
    place_id: str | None
    latitude: Decimal
    longitude: Decimal
    pickup_contact_name: str
    pickup_phone: str
    pickup_instructions: str | None
    is_default: bool
    is_verified: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime | None

    model_config = ORM_CONFIG


class SellerPickupLocationListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[SellerPickupLocationResponse]


    
# PHASE 1 TASK 2: MAP / LOCATION PROVIDER CONTRACT
    
class MapAutocompleteSuggestion(BaseModel):
    place_id: str
    description: str
    main_text: str | None = None
    secondary_text: str | None = None


class MapAutocompleteResponse(BaseModel):
    provider: Literal["google"]
    query: str
    session_token: str | None = None
    results: list[MapAutocompleteSuggestion]


class MapResolvedLocation(BaseModel):
    provider: Literal["google"]
    place_id: str | None = None
    display_name: str | None = None
    formatted_address: str
    latitude: Decimal
    longitude: Decimal
    country: str | None = None
    country_code: str | None = None
    region: str | None = None
    city: str | None = None
    district: str | None = None
    ward: str | None = None
    street: str | None = None
    postal_code: str | None = None


class MapProviderConfigResponse(BaseModel):
    provider: Literal["google"]
    enabled: bool
    default_country_code: str
    default_language: str


    
# PHASE 1 TASK 3: SELLER FULFILLMENT READINESS
    
class SellerFulfillmentReadinessCheck(BaseModel):
    code: str
    label: str
    ready: bool
    blocking: bool
    detail: Optional[str] = None


class SellerFulfillmentReadinessResponse(BaseModel):
    seller_order_id: UUID
    ready_to_ship: bool
    pickup_location_id: Optional[UUID] = None
    package_id: Optional[UUID] = None
    package_ids: list[UUID] = Field(default_factory=list)
    package_groups: int = 0
    physical_package_count: int = 0
    total_weight_kg: Decimal = Decimal("0")
    shipment_id: Optional[UUID] = None
    blockers: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    checks: list[SellerFulfillmentReadinessCheck] = Field(default_factory=list)



    
# PHASE 1 TASK 6: SELLER HANDOVER CONFIRMATION
    
class LogisticsCourierArrivalRequest(BaseModel):
    latitude: Optional[Decimal] = Field(default=None, ge=-90, le=90)
    longitude: Optional[Decimal] = Field(default=None, ge=-180, le=180)
    notes: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def validate_coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError("latitude and longitude must be supplied together")
        return self


class SellerHandoverConfirmationRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=1000)


class ShipmentHandoverResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    seller_order_id: UUID
    seller_id: UUID
    logistics_company_id: Optional[UUID]
    status: Literal["awaiting_courier", "courier_arrived", "seller_confirmed"]

    courier_arrived_at: Optional[datetime]
    courier_arrived_by_id: Optional[UUID]
    courier_arrival_latitude: Optional[Decimal]
    courier_arrival_longitude: Optional[Decimal]
    courier_arrival_notes: Optional[str]

    seller_confirmed_at: Optional[datetime]
    seller_confirmed_by_id: Optional[UUID]
    seller_confirmation_notes: Optional[str]

    pickup_snapshot: Dict[str, Any]
    package_snapshot: list[Dict[str, Any]]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ORM_CONFIG



   
# PHASE 2 TASK 8: CUSTOMER MULTI-SELLER SHIPMENT TRACKING

class CustomerTrackingProductItem(BaseModel):
    order_item_id: UUID
    product_name: str
    quantity: int
    unit_price: Decimal


class CustomerTrackingEventItem(BaseModel):
    id: UUID
    status: ShipmentStatus
    location: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class CustomerPickupProofTrackingState(BaseModel):
    proof_id: UUID
    status: Literal["pending", "approved", "disputed", "auto_approved"]
    photo_url: str
    review_deadline: datetime
    customer_reviewed_at: Optional[datetime] = None
    problem_reason: Optional[str] = None
    requires_customer_action: bool = False


class CustomerShipmentTrackingItem(BaseModel):
    shipment_id: UUID
    seller_id: UUID
    seller_name: str

    status: ShipmentStatus
    status_label: str
    progress_percent: int

    logistics_company_id: Optional[UUID] = None
    logistics_company_name: Optional[str] = None
    carrier_name: Optional[str] = None
    tracking_number: Optional[str] = None

    estimated_delivery_from: Optional[datetime] = None
    estimated_delivery_to: Optional[datetime] = None
    dispatched_at: Optional[datetime] = None
    delivered_at: Optional[datetime] = None

    item_count: int
    items: list[CustomerTrackingProductItem] = Field(default_factory=list)

    pickup_proof: Optional[CustomerPickupProofTrackingState] = None
    latest_event: Optional[CustomerTrackingEventItem] = None
    recent_events: list[CustomerTrackingEventItem] = Field(default_factory=list)

    requires_customer_action: bool = False


class CustomerOrderTrackingSummary(BaseModel):
    order_id: UUID
    order_status: OrderStatus
    overall_tracking_status: str
    overall_progress_percent: int

    shipment_count: int
    pending_count: int
    ready_count: int
    dispatched_count: int
    in_transit_count: int
    out_for_delivery_count: int
    delivered_count: int
    failed_or_returned_count: int

    pending_pickup_reviews: int
    disputed_pickup_proofs: int
    requires_customer_action: bool

    created_at: datetime
    estimated_delivery_from: Optional[datetime] = None
    estimated_delivery_to: Optional[datetime] = None


class CustomerOrderTrackingResponse(BaseModel):
    summary: CustomerOrderTrackingSummary
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[CustomerShipmentTrackingItem] = Field(default_factory=list)


class PaginatedCustomerTrackingEventResponse(BaseModel):
    shipment_id: UUID
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[CustomerTrackingEventItem] = Field(default_factory=list)


# PHASE 2 TASK 7: CUSTOMER PICKUP PROOF VERIFICATION

class PickupProofProblemRequest(BaseModel):
    reason: Literal[
        "wrong_product",
        "wrong_variant",
        "wrong_quantity",
        "damaged",
        "photo_unclear",
        "other",
    ]
    notes: Optional[str] = Field(default=None, max_length=2000)


class PickupProofResponse(BaseModel):
    id: UUID
    shipment_id: UUID
    handover_id: UUID
    order_id: UUID
    customer_id: UUID
    seller_id: UUID
    logistics_company_id: UUID

    photo_url: str
    original_filename: Optional[str]
    mime_type: str
    file_size: int

    pickup_latitude: Decimal
    pickup_longitude: Decimal
    courier_reference: Optional[str]
    notes: Optional[str]

    status: Literal["pending", "approved", "disputed", "auto_approved"]
    review_deadline: datetime
    customer_reviewed_at: Optional[datetime]
    customer_reviewed_by_id: Optional[UUID]
    problem_reason: Optional[str]
    problem_notes: Optional[str]

    uploaded_by_id: Optional[UUID]
    created_at: datetime
    updated_at: Optional[datetime]

    model_config = ORM_CONFIG


class PaginatedPickupProofResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[PickupProofResponse] = Field(default_factory=list)


# PHASE 1 TASK 7: SELLER FULFILLMENT VIEW
   
class SellerFulfillmentPickupView(BaseModel):
    id: Optional[UUID] = None
    label: Optional[str] = None
    formatted_address: Optional[str] = None
    country: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    district: Optional[str] = None
    ward: Optional[str] = None
    landmark: Optional[str] = None
    latitude: Optional[Decimal] = None
    longitude: Optional[Decimal] = None
    pickup_contact_name: Optional[str] = None
    pickup_phone: Optional[str] = None
    pickup_instructions: Optional[str] = None
    is_default: Optional[bool] = None
    is_verified: Optional[bool] = None


class SellerFulfillmentLogisticsCompanyView(BaseModel):
    id: UUID
    name: str
    code: str
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    supports_tracking: bool
    supports_webhooks: bool


class SellerFulfillmentPackageView(BaseModel):
    id: UUID
    package_label: Optional[str]
    package_type: str
    contents_summary: Optional[str]
    weight_kg: Optional[Decimal]
    length_cm: Optional[Decimal]
    width_cm: Optional[Decimal]
    height_cm: Optional[Decimal]
    package_count: int
    fragile: bool
    keep_upright: bool
    temperature_sensitive: bool
    handling_instructions: Optional[str]
    declared_value: Optional[Decimal]
    declared_currency: str
    is_ready: bool
    prepared_at: Optional[datetime]
    sealed_at: Optional[datetime]


class SellerFulfillmentHandoverView(BaseModel):
    id: UUID
    status: str
    courier_arrived_at: Optional[datetime]
    courier_arrival_latitude: Optional[Decimal]
    courier_arrival_longitude: Optional[Decimal]
    courier_arrival_notes: Optional[str]
    seller_confirmed_at: Optional[datetime]
    seller_confirmation_notes: Optional[str]


class SellerFulfillmentSettlementView(BaseModel):
    state: str
    gross_held: Decimal = Decimal("0")
    seller_amount: Decimal = Decimal("0")
    commission_amount: Decimal = Decimal("0")
    released_amount: Decimal = Decimal("0")
    refunded_amount: Decimal = Decimal("0")
    currency: Optional[str] = None
    hold_count: int = 0
    note: str


class SellerFulfillmentTrackingItem(BaseModel):
    id: UUID
    status: ShipmentStatus
    location: Optional[str]
    notes: Optional[str]
    created_at: datetime


class SellerFulfillmentTrackingListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[SellerFulfillmentTrackingItem]


class SellerFulfillmentListItem(BaseModel):
    seller_order_id: UUID
    order_id: UUID
    seller_status: SellerOrderStatus
    order_status: OrderStatus
    customer_name: str
    customer_phone: Optional[str]
    currency: str
    seller_subtotal: Decimal
    item_count: int
    package_groups: int
    physical_package_count: int
    total_weight_kg: Decimal
    packages_ready: int
    shipment_id: Optional[UUID]
    shipment_status: Optional[ShipmentStatus]
    logistics_company_id: Optional[UUID]
    logistics_company_name: Optional[str]
    handover_status: Optional[str]
    readiness_ready: bool
    readiness_blocker_count: int
    tracking_number: Optional[str]
    created_at: datetime
    updated_at: Optional[datetime]


class SellerFulfillmentListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    total_pages: int
    results: list[SellerFulfillmentListItem]


class SellerFulfillmentDashboardSummary(BaseModel):
    total: int
    new: int
    processing: int
    ready_to_ship: int
    awaiting_courier: int
    courier_arrived: int
    seller_confirmed: int
    shipped: int
    delivered: int
    blocked_readiness: int


class SellerFulfillmentDetailResponse(BaseModel):
    seller_order_id: UUID
    order_id: UUID
    seller_id: UUID
    seller_status: SellerOrderStatus
    order_status: OrderStatus
    currency: str
    seller_subtotal: Decimal
    item_count: int

    customer_name: str
    customer_phone: Optional[str]
    delivery_address: Optional[Dict[str, Any]]

    pickup_location: Optional[SellerFulfillmentPickupView]
    packages: list[SellerFulfillmentPackageView]
    package_groups: int
    physical_package_count: int
    total_weight_kg: Decimal

    readiness: SellerFulfillmentReadinessResponse

    shipment: Optional[ShipmentResponse]
    logistics_company: Optional[SellerFulfillmentLogisticsCompanyView]
    handover: Optional[SellerFulfillmentHandoverView]

    settlement: SellerFulfillmentSettlementView
    recent_tracking: list[SellerFulfillmentTrackingItem] = Field(default_factory=list)

    created_at: datetime
    updated_at: Optional[datetime]
    CustomerMapPinConfirmationResponse.model_rebuild()
