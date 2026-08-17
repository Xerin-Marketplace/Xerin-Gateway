import type { User } from "./user";

export type LoginRequest = {
  email: string;
  password: string;
};

export type RegisterBuyerRequest = {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string;
  password: string;
};

export type RegisterSellerRequest = RegisterBuyerRequest & {
  business_name: string;
  business_category_ids: string[];
  business_description?: string;
  business_location?: string;
  business_country?: string;
  business_region?: string;
  business_city?: string;
  business_address?: string;
  product_description?: string;
  years_in_business?: string;
  website_url?: string;
  contact_email?: string;
  contact_phone?: string;
  agreement_accepted: boolean;
};

export type RegistrationResponse = {
  message: string;
  user_id: string;
  email: string;
  phone: string;
  verification_required: true;
  verification_purpose: "register";
  otp_expires_in_seconds: number;
  resumed_registration: boolean;
};

export type SellerRegistrationResponse = {
  message: string;
  user_id: string;
  seller_id: string;
  email: string;
  phone: string;
  seller_status: string;
  verification_required: true;
  verification_purpose: "register_seller";
  otp_expires_in_seconds: number;
  resumed_registration: boolean;
};

export type AuthTokenResponse = {
  access_token: string;
  refresh_token?: string;
  token_type?: string;
  expires_in?: number;
  user?: User;
};

export type RefreshTokenRequest = {
  refresh_token: string;
};

export type OtpPurpose = "generic" | "register" | "register_seller" | "password_reset";

export type SendOtpRequest = {
  phone: string;
  purpose: OtpPurpose;
};

export type VerifyOtpRequest = {
  phone: string;
  otp_code: string;
  purpose: OtpPurpose;
};


export type ResendVerificationRequest = {
  identifier: string;
};

export type VerifyAccountOtpRequest = {
  identifier: string;
  otp_code: string;
};

export type ForgotPasswordRequest = {
  email: string;
};

export type ResetPasswordRequest = {
  email: string;
  otp_code: string;
  new_password: string;
};

export type ChangePasswordRequest = {
  current_password: string;
  new_password: string;
};
