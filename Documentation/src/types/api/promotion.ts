import type { ID } from "@/types/api/common";

export type PromotionType =
  | "percentage"
  | "fixed_amount"
  | "free_shipping"
  | "buy_x_get_y";

export type PromotionRuleType =
  | "product"
  | "category"
  | "store"
  | "customer_group"
  | "minimum_quantity";

export type SellerPromotionRuleRequest = {
  rule_type: PromotionRuleType;
  product_id?: ID | null;
  category_id?: ID | null;
  store_id?: ID | null;
  value?: Record<string, unknown> | null;
};

export type SellerPromotionRequest = {
  name: string;
  code?: string | null;
  description?: string | null;
  promotion_type: PromotionType;
  discount_value: number;
  minimum_order_amount?: number | null;
  maximum_discount_amount?: number | null;
  usage_limit?: number | null;
  usage_per_customer?: number | null;
  stackable: boolean;
  automatic: boolean;
  is_active: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
  rules: SellerPromotionRuleRequest[];
};

export type SellerPromotionUpdateRequest = Partial<
  Pick<
    SellerPromotionRequest,
    | "name"
    | "description"
    | "discount_value"
    | "minimum_order_amount"
    | "maximum_discount_amount"
    | "usage_limit"
    | "usage_per_customer"
    | "stackable"
    | "automatic"
    | "is_active"
    | "starts_at"
    | "ends_at"
  >
>;

export type SellerPromotion = {
  id: ID;
  seller_id?: ID | null;
  name: string;
  code?: string | null;
  description?: string | null;
  promotion_type: string;
  discount_value: number | string;
  minimum_order_amount?: number | string | null;
  maximum_discount_amount?: number | string | null;
  usage_limit?: number | null;
  usage_per_customer?: number | null;
  usage_count: number;
  stackable: boolean;
  automatic: boolean;
  funding_source: string;
  is_active: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
  created_at: string;
  updated_at?: string | null;
};

export type SellerPromotionListResponse = {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: SellerPromotion[];
};

export type SellerPromotionListParams = {
  page?: number;
  page_size?: number;
  search?: string;
  active?: boolean;
};


export type CustomerPromotionOffer = {
  promotion_id: string;
  code?: string | null;
  name: string;
  description?: string | null;
  promotion_type: string;
  funding_source: string;
  seller_id?: string | null;
  eligible_subtotal: number | string;
  discount_amount: number | string;
  total_after_discount: number | string;
  stackable: boolean;
  automatic: boolean;
  minimum_order_amount?: number | string | null;
  maximum_discount_amount?: number | string | null;
  starts_at?: string | null;
  ends_at?: string | null;
};
