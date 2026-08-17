import type { ID, TimestampFields } from "./common";

export type SellerStatus = "pending" | "under_review" | "approved";

export type SellerBusinessCategory = {
  id: ID;
  name: string;
  slug?: string;
  description?: string | null;
  active?: boolean;
};

export type SellerDocumentType =
  | "tin"
  | "business_registration"
  | "business_profile";

export type Seller = TimestampFields & {
  id: ID;
  user_id?: ID;
  business_name: string;
  business_category?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  status: SellerStatus;
  is_verified?: boolean;
  rejection_reason?: string | null;
};

export type SellerBusinessProfile = {
  id: ID;
  seller_id: ID;
  business_description: string | null;
  business_country: string | null;
  business_region: string | null;
  business_city: string | null;
  business_address: string | null;
  product_description: string | null;
  years_in_business: string | null;
  website_url: string | null;
  created_at: string;
};

export type UpdateSellerRequest = {
  business_name?: string;
  business_category?: string;
  contact_email?: string;
  contact_phone?: string;
};

export type SellerKycDocument = TimestampFields & {
  id: ID;
  seller_id?: ID;
  document_type: SellerDocumentType | string;
  document_url?: string;
  file_url?: string;
  mime_type?: string | null;
  status?: "pending" | "under_review" | "approved" | "rejected" | string;
  rejection_reason?: string | null;
};

export type UploadSellerKycDocumentRequest = {
  document_type: SellerDocumentType;
  file: File;
};

export type PayoutAccount = TimestampFields & {
  id: ID;
  seller_id?: ID;
  account_type: "bank" | "mobile_money" | string;
  provider: string;
  account_name: string;
  account_number: string;
  currency: string;
  is_default?: boolean;

  // Seller Phase 2 payout verification state.
  is_active?: boolean;
  verification_status?: "pending" | "verified" | "rejected" | string;
  provider_reference?: string | null;
  verified_at?: string | null;
};

export type PayoutAccountRequest = Omit<
  PayoutAccount,
  "id" | "seller_id" | "created_at" | "updated_at"
>;

export type SellerKycStatus = {
  seller_status: string | null;
  required_documents: string[];
  uploaded_documents: string[];
  missing_documents: string[];
  can_submit_for_review: boolean;
};


export type SellerPricingPreviewRequest = {
  seller_base_price: number;
  seller_sale_price?: number | null;
  category_id: ID;
  product_id?: ID | null;
  currency?: string;
};

export type SellerPricingPreviewResponse = {
  seller_base_price: number | string;
  seller_sale_price?: number | string | null;
  commission_rate: number | string;
  commission_amount: number | string;
  customer_price: number | string;
  customer_sale_price?: number | string | null;
  commission_scope?: string | null;
  currency: string;
};


export type SellerDashboardPerformance = {
  products_total: number;
  products_approved: number;
  products_pending_review: number;
  active_promotions: number;

  orders_total: number;
  orders_new: number;
  orders_processing: number;
  orders_ready_to_ship: number;

  wallet_currency: string;
  wallet_pending: number | string;
  wallet_available: number | string;
  wallet_reserved: number | string;
  pending_payouts: number;

  rating_average: number | string;
  review_count: number;
  unanswered_questions: number;
};
