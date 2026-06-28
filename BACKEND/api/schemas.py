from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime
from decimal import Decimal
from typing import Optional, List, Dict, Any


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


class UserResponse(BaseModel):
    id: UUID
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str]
    is_verified: bool
    status: str

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
    business_category: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None


class SellerResponse(BaseModel):
    id: UUID
    user_id: UUID
    business_name: str
    business_category: str | None
    contact_email: str | None
    contact_phone: str | None
    status: str
    agreement_accepted: bool
    created_at: datetime

    class Config:
        from_attributes = True


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
from typing import Optional, List, Dict, Any


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
        
class SellerRegisterRequest(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    phone: str
    password: str

    business_name: str
    business_category: str | None = None
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    agreement_accepted: bool = True