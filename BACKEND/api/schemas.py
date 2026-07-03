from pydantic import BaseModel, EmailStr
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


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