import type { ID, TimestampFields } from "./common";

export type UserRole = "buyer" | "seller" | "admin" | "super_admin" | "support" | string;

export type User = TimestampFields & {
  id: ID;
  email: string;
  phone?: string | null;
  first_name?: string | null;
  last_name?: string | null;
  full_name?: string | null;
  profile_photo?: string | null;
  role?: UserRole;
  status?: string;
  account_type?: string;
  is_active?: boolean;
  is_verified?: boolean;
  is_seller?: boolean;
  seller_status?: string | null;
  roles?: string[];
  permissions?: string[];
};

export type UpdateUserRequest = {
  first_name?: string | null;
  last_name?: string | null;
  phone?: string | null;
};

export type Address = TimestampFields & {
  id: ID;
  label?: string | null;
  recipient_name?: string | null;
  recipient_phone?: string | null;
  country: string;
  region: string;
  district?: string | null;
  ward?: string | null;
  city: string;
  street: string;
  landmark?: string | null;
  postal_code?: string | null;
  latitude?: number | string | null;
  longitude?: number | string | null;
  is_default?: boolean;
};

export type AddressRequest = {
  label?: string | null;
  recipient_name?: string | null;
  recipient_phone?: string | null;
  country: string;
  region: string;
  district?: string | null;
  ward?: string | null;
  city: string;
  street: string;
  landmark?: string | null;
  postal_code?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  is_default?: boolean;
};

export type PaginatedAddressResponse = {
  total: number;
  page: number;
  page_size: number;
  results: Address[];
};
