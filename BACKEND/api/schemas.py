from pydantic import BaseModel, EmailStr, Field, HttpUrl, ConfigDict
from uuid import UUID
from datetime import datetime, time as Time
from decimal import Decimal
from typing import Optional, List, Dict, Any
from api.enums import DayOfWeek, StoreStatus


class RegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    password: str
    # password_confirmation: str


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


class SendOTPRequest(BaseModel):
    phone: str


class VerifyOTPRequest(BaseModel):
    phone: str
    otp_code: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    email: EmailStr
    otp_code: str
    new_password: str
    
class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=8)
    new_password: str = Field(min_length=8)    


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

    class Config:
        from_attributes = True


class UpdateUserRequest(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    phone: Optional[str] = None


class AddressCreate(BaseModel):
    country: str
    region: str
    city: str
    street: str
    postal_code: Optional[str] = None
    is_default: bool = False


class AddressResponse(AddressCreate):
    id: UUID

    class Config:
        from_attributes = True
        
        
        from datetime import datetime


class SellerCreate(BaseModel):
    business_name: str
    business_category: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    agreement_accepted: bool = True


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
    business_description: str | None
    business_location: str | None
    business_country: str | None
    business_region: str | None
    business_city: str | None
    business_address: str | None
    product_description: str | None
    years_in_business: str | None
    website_url: str | None
    contact_email: str | None
    contact_phone: str | None
    status: str
    agreement_accepted: bool
    created_at: datetime

    class Config:
        from_attributes = True


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
    agreement_accepted: bool = True

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
    
    class Config:
        from_attributes = True

class SellerKYCStatusResponse(BaseModel):
    seller_status: str
    required_documents: list[str]
    uploaded_documents: list[str]
    missing_documents: list[str]
    can_submit_for_review: bool

    class Config:
        from_attributes = True


class SellerPayoutCreate(BaseModel):
    account_type: str
    provider: str
    account_name: str
    account_number: str
    currency: str = "TZS"
    is_default: bool = False


class SellerPayoutResponse(BaseModel):
    id: UUID
    seller_id: UUID
    account_type: str
    provider: str
    account_name: str
    account_number: str
    currency: str
    is_default: bool
    created_at: datetime

    class Config:
        from_attributes = True
        
        
        from decimal import Decimal
        
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

    class Config:
        from_attributes = True
        
        
        
class StoreUpdate(BaseModel):
    store_name: str | None = Field(default=None, min_length=2, max_length=255)
    description: str | None = Field(default=None, max_length=5000)

    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=30)
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


class StoreResponse(BaseModel):
    id: UUID
    seller_id: UUID

    store_name: str
    slug: str
    description: str | None

    logo_url: str | None
    banner_url: str | None

    contact_email: str | None
    contact_phone: str | None
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
    
    gallery_images: list["StoreGalleryImageResponse"] = []
    opening_hours: list["StoreOpeningHourResponse"] = []

    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class StorePublicResponse(BaseModel):
    id: UUID
    seller_id: UUID

    store_name: str
    slug: str
    description: str | None

    logo_url: str | None
    banner_url: str | None

    contact_email: str | None
    contact_phone: str | None
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
    
    gallery_images: list["StoreGalleryImageResponse"] = []
    opening_hours: list["StoreOpeningHourResponse"] = []

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

    class Config:
        from_attributes = True


class PaginatedAddressResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[AddressResponse]


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


class CategoryResponse(BaseModel):
    id: UUID
    parent_id: Optional[UUID]
    name: str
    slug: str
    created_at: datetime

    class Config:
        from_attributes = True


class BrandCreate(BaseModel):
    name: str
    slug: str


class BrandResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    category_id: UUID
    brand_id: Optional[UUID] = None
    sku: str
    name: str
    slug: str
    description: Optional[str] = None
    price: Decimal
    sale_price: Optional[Decimal] = None
    currency: str = "TZS"
    weight: Optional[Decimal] = None


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
    weight: Optional[Decimal] = None
    is_active: Optional[bool] = None


class ProductResponse(BaseModel):
    id: UUID
    seller_id: UUID
    category_id: UUID
    brand_id: Optional[UUID]
    sku: str
    name: str
    slug: str
    description: Optional[str]
    price: Decimal
    sale_price: Optional[Decimal]
    currency: str
    weight: Optional[Decimal]
    status: str
    rejection_reason: Optional[str]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProductImageCreate(BaseModel):
    image_url: str
    is_primary: bool = False


class ProductImageResponse(BaseModel):
    id: UUID
    product_id: UUID
    image_url: str
    is_primary: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ProductVariantCreate(BaseModel):
    variant_name: str
    sku: str
    price: Optional[Decimal] = None
    attributes: Optional[Dict[str, Any]] = None


class ProductVariantResponse(BaseModel):
    id: UUID
    product_id: UUID
    variant_name: str
    sku: str
    price: Optional[Decimal]
    attributes: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class ProductTagCreate(BaseModel):
    tag: str


class ProductTagResponse(BaseModel):
    id: UUID
    product_id: UUID
    tag: str

    class Config:
        from_attributes = True
    
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

    class Config:
        from_attributes = True
        
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

    class Config:
        from_attributes = True


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


class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None

    class Config:
        from_attributes = True  
        
class PermissionResponse(BaseModel):
    id: UUID
    code: str
    name: str
    description: str | None

    class Config:
        from_attributes = True


class AssignUserPermissionsRequest(BaseModel):
    permission_codes: list[str]


class UserPermissionsResponse(BaseModel):
    user_id: UUID
    permissions: list[str]    
    
class RoleResponse(BaseModel):
    id: UUID
    name: str
    description: str | None

    class Config:
        from_attributes = True


class RolePermissionsUpdateRequest(BaseModel):
    permission_codes: list[str]


class RolePermissionsResponse(BaseModel):
    role_id: UUID
    role_name: str
    permissions: list[str]
# =========================================================
# CART SCHEMAS
# =========================================================

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

    class Config:
        from_attributes = True


class CartResponse(BaseModel):
    id: UUID
    user_id: UUID
    coupon_code: Optional[str]
    items: list[CartItemResponse]
    subtotal: Decimal
    discount_amount: Decimal
    total: Decimal

    class Config:
        from_attributes = True


class ApplyCouponRequest(BaseModel):
    code: str


# =========================================================
# ORDER SCHEMAS
# =========================================================

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

    class Config:
        from_attributes = True


class OrderStatusHistoryResponse(BaseModel):
    id: UUID
    status: str
    notes: Optional[str]
    created_by_id: Optional[UUID]
    created_at: datetime

    class Config:
        from_attributes = True


class OrderCreateRequest(BaseModel):
    shipping_address_id: Optional[UUID] = None
    coupon_code: Optional[str] = None
    notes: Optional[str] = None


class OrderStatusUpdateRequest(BaseModel):
    status: str
    notes: Optional[str] = None


class OrderResponse(BaseModel):
    id: UUID
    user_id: UUID
    shipping_address_id: Optional[UUID]
    status: str
    currency: str
    subtotal: Decimal
    discount_amount: Decimal
    shipping_amount: Decimal
    tax_amount: Decimal
    total: Decimal
    coupon_code: Optional[str]
    notes: Optional[str]
    items: list[OrderItemResponse]
    status_history: list[OrderStatusHistoryResponse]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


class PaginatedOrderResponse(BaseModel):
    total: int
    page: int
    page_size: int
    results: list[OrderResponse]


# =========================================================
# INVENTORY SCHEMAS
# =========================================================

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

    class Config:
        from_attributes = True


# =========================================================
# PAYMENT SCHEMAS
# =========================================================

class PaymentInitiateRequest(BaseModel):
    order_id: UUID
    method: str  # mobile_money, bank_transfer, card, cash_on_delivery
    provider: Optional[str] = None  # mpesa, airtel_money, tigo_pesa
    phone_number: Optional[str] = None


class PaymentCallbackRequest(BaseModel):
    provider: str
    transaction_id: str
    status: str
    payload: Optional[Dict[str, Any]] = None


class PaymentTransactionResponse(BaseModel):
    id: UUID
    transaction_type: str
    status: str
    amount: Optional[Decimal]
    provider_response: Optional[Dict[str, Any]]
    created_at: datetime

    class Config:
        from_attributes = True


class PaymentResponse(BaseModel):
    id: UUID
    order_id: UUID
    user_id: UUID
    amount: Decimal
    currency: str
    method: str
    provider: Optional[str]
    status: str
    provider_transaction_id: Optional[str]
    paid_at: Optional[datetime]
    transactions: list[PaymentTransactionResponse]
    created_at: datetime
    updated_at: Optional[datetime]

    class Config:
        from_attributes = True


# =========================================================
# COUPON SCHEMAS
# =========================================================

class CouponCreate(BaseModel):
    code: str
    description: Optional[str] = None
    discount_type: str  # percentage, fixed_amount
    discount_value: Decimal
    minimum_order_amount: Optional[Decimal] = None
    maximum_discount_amount: Optional[Decimal] = None
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: bool = True


class CouponUpdate(BaseModel):
    description: Optional[str] = None
    discount_type: Optional[str] = None
    discount_value: Optional[Decimal] = None
    minimum_order_amount: Optional[Decimal] = None
    maximum_discount_amount: Optional[Decimal] = None
    usage_limit: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_until: Optional[datetime] = None
    is_active: Optional[bool] = None


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


class StoreOpeningHourUpdate(BaseModel):
    opening_time: Time | None = None
    closing_time: Time | None = None
    is_closed: bool | None = None


class StoreOpeningHourResponse(BaseModel):
    id: UUID
    store_id: UUID
    day_of_week: DayOfWeek
    day_position: int
    opening_time: Time | None
    closing_time: Time | None
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