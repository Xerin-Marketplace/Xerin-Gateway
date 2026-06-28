from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID


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