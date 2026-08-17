import type { ID, TimestampFields } from "./common";

export type Store = TimestampFields & {
  id: ID;
  seller_id: ID;
  name: string;
  slug: string;
  description: string | null;
  logo_url: string | null;
  banner_url: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  business_country: string | null;
  business_region: string | null;
  business_city: string | null;
  business_address: string | null;
  return_policy: string | null;
  shipping_policy: string | null;
  delivery_time_estimate: string | null;
  is_open: boolean;
  operating_hours: Record<string, string> | null;
  social_links: Record<string, string> | null;
};

export type UpdateStorePayload = Partial<
  Omit<Store, "id" | "seller_id" | "created_at" | "updated_at">
>;
