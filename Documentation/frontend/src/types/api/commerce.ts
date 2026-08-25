import type { PaginatedResults, TimestampFields } from "./common";
import type { Product } from "./product";

export type CartItem = {
  id: string;
  product_id: string;
  variant_id: string | null;
  quantity: number;
  unit_price: number | string;
  product: Product;
};

export type AppliedCartPromotion = {
  promotion_id: string;
  code: string | null;
  name: string;
  promotion_type: string;
  funding_source: string;
  eligible_subtotal: number | string;
  discount_amount: number | string;
  seller_id?: string | null;
  stackable: boolean;
};

export type Cart = {
  id: string;
  user_id: string;
  coupon_code: string | null;
  promotion_code: string | null;
  promotion: AppliedCartPromotion | null;
  items: CartItem[];
  subtotal: number | string;
  coupon_discount_amount: number | string;
  promotion_discount_amount: number | string;
  discount_amount: number | string;
  total: number | string;
  currency: string;
  validation_messages: string[];
};

export type GuestCartMergeResult = {
  cart: Cart;
  rejected_items: Array<{
    product_id: string;
    reason: string;
    available_quantity?: number;
  }>;
};

export type DeliveryMode = "local" | "international";

export type DetectedDeliveryMode = {
  address_id: string;
  destination_country: string;
  delivery_mode: DeliveryMode;
  route_types: Array<"domestic" | "cross_border" | string>;
  international_delivery_allowed: boolean;
  origins: Array<{
    store_id: string;
    store_name: string;
    origin_country: string;
    destination_country: string;
    route_type: "domestic" | "cross_border";
  }>;
};

export type DeliveryCheckoutConfig = {
  default_country: string;
  local_delivery_allowed: boolean;
  international_delivery_allowed: boolean;
  cod_allowed: boolean;
  configured: boolean;
};

export type ShippingOption = {
  id: string;
  method_id: string;
  logistics_company_id: string | null;
  logistics_company_name: string;
  service_name: string;
  carrier: string;
  scope: DeliveryMode | "both";
  supports_cod: boolean;
  tracking_supported: boolean;
  original_amount: number | string;
  shipping_discount_amount: number | string;
  amount: number | string;
  currency: string;
  estimated_min_days: number;
  estimated_max_days: number;
  free_shipping_applied: boolean;
  promotion_code?: string | null;
  promotion_name?: string | null;
};

export type EligibleLogisticsCompany = {
  logistics_company_id: string;
  name: string;
  code: string;
  scope: DeliveryMode | "both";
  supports_cod: boolean;
  supports_tracking: boolean;
  supports_webhooks: boolean;
  seller_count: number;
  covered_seller_count: number;
  route_types: Array<"domestic" | "cross_border" | string>;
  services: Array<{
    method_id: string;
    method_name: string;
    service_code?: string | null;
    min_delivery_days: number;
    max_delivery_days: number;
    supports_cod: boolean;
    supports_tracking: boolean;
  }>;
};

export type EligibleLogisticsResponse = {
  address_id: string;
  delivery_mode: DeliveryMode;
  destination_country: string;
  seller_count: number;
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: EligibleLogisticsCompany[];
  excluded_companies: Array<{
    logistics_company_id: string;
    name: string;
    code: string;
    reason_codes: string[];
    reasons: string[];
    uncovered_sellers: string[];
  }>;
};

export type MultiSellerDeliveryOption = {
  rate_id: string;
  method_id: string;
  method_name: string;
  service_code?: string | null;
  logistics_company_id: string;
  logistics_company_name: string;
  strategy: "farthest_seller" | "sum_individual" | string;
  rate_type: string;
  currency: string;
  seller_count: number;
  billable_distance_km: number | string;
  billable_seller_id?: string | null;
  delivery_amount: number | string;
  min_delivery_days: number;
  max_delivery_days: number;
  supports_cod: boolean;
  supports_tracking: boolean;
  pricing_breakdown: Record<string, number | string | boolean | null>;
  sellers: Array<{
    seller_id: string;
    seller_name: string;
    store_id?: string | null;
    store_name?: string | null;
    origin_country?: string | null;
    route_type?: "domestic" | "cross_border" | string | null;
    pickup_location_id: string;
    pickup_label: string;
    distance_km: number | string;
    duration_minutes: number | string;
    is_billable_reference: boolean;
  }>;
};

export type MultiSellerPricingResponse = {
  address_id: string;
  logistics_company_id: string;
  logistics_company_name: string;
  delivery_mode: DeliveryMode;
  strategy: string;
  seller_count: number;
  options: MultiSellerDeliveryOption[];
  note: string;
};

export type CheckoutDeliveryQuote = {
  id: string;
  shipping_address_id: string;
  logistics_company_id: string;
  shipping_method_id: string;
  shipping_rate_id: string;
  delivery_mode: DeliveryMode;
  pricing_strategy: string;
  rate_type: string;
  currency: string;
  seller_count: number;
  billable_distance_km: number | string;
  product_subtotal: number | string;
  delivery_amount: number | string;
  checkout_total_before_discounts: number | string;
  pricing_breakdown: Record<string, unknown> & {
    route_types?: string[];
    store_count?: number;
  };
  seller_routes_snapshot: Array<{
    seller_id?: string;
    seller_name?: string;
    store_id?: string | null;
    store_name?: string | null;
    origin_country?: string | null;
    route_type?: "domestic" | "cross_border" | string | null;
    pickup_location_id?: string;
    pickup_label?: string;
    distance_km?: number | string;
    duration_minutes?: number | string;
    is_billable_reference?: boolean;
  }>;
  address_snapshot?: {
    country?: string | null;
    region?: string | null;
    city?: string | null;
    district?: string | null;
    ward?: string | null;
    formatted_address?: string | null;
  };
  expires_at: string;
  used_at?: string | null;
};

export type PaymentOption = {
  id: string;
  label: string;
  requires_phone: boolean;
  providers: string[];
};

export type PaymentInitiatePayload = {
  order_id: string;
  method: string;
  provider?: string;
  phone_number?: string;
  success_url?: string;
  failure_url?: string;
};

export type PaymentRetryPayload = {
  provider?: string;
  phone_number?: string;
  success_url?: string;
  failure_url?: string;
};

export type PaymentProviderErrorDetail = {
  code?: string;
  message: string;
  provider?: string;
  provider_status?: number | null;
  order_id?: string;
  payment_id?: string;
  retryable?: boolean;
};

export type CheckoutQuote = {
  cart_id: string;
  currency: string;
  subtotal: number | string;
  discount_amount: number | string;
  shipping_amount: number | string;
  tax_amount: number | string;
  total: number | string;
  shipping_option: ShippingOption;
  validation_messages: string[];
};

export type OrderItem = {
  id: string;
  product_id: string;
  variant_id: string | null;
  seller_id: string;
  store_id: string;
  product_name: string;
  variant_name: string | null;
  quantity: number;
  unit_price: number | string;
  total_price: number | string;
  promotion_discount_amount?: number | string;
  customer_total?: number | string;
};

export type Order = TimestampFields & {
  id: string;
  order_number?: string | null;
  user_id: string;
  shipping_address_id: string | null;
  seller_id?: string | null;
  status: string;
  payment_status?: string | null;
  currency: string;
  subtotal: number | string;
  coupon_discount_amount?: number | string;
  promotion_discount_amount?: number | string;
  discount_amount: number | string;
  original_shipping_amount?: number | string;
  shipping_discount_amount?: number | string;
  shipping_amount: number | string;
  tax_amount: number | string;
  total: number | string;
  coupon_code: string | null;
  promotion_code?: string | null;
  promotion_seller_id?: string | null;
  delivery_mode?: DeliveryMode | null;
  logistics_company_id?: string | null;
  notes: string | null;
  delivery_method?: string | null;
  courier_name?: string | null;
  tracking_number?: string | null;
  estimated_delivery_date?: string | null;
  delivered_at?: string | null;
  cancellation_reason?: string | null;
  refund_notes?: string | null;
  user?: {
    id: string;
    first_name?: string | null;
    last_name?: string | null;
    email?: string | null;
    phone?: string | null;
  } | null;
  payments?: Array<{
    id: string;
    method?: string | null;
    status?: string | null;
    amount?: number | string;
    currency?: string;
    provider?: string | null;
    provider_transaction_id?: string | null;
    transaction_reference?: string | null;
    paid_at?: string | null;
  }>;
  address?: {
    country?: string;
    region?: string;
    city?: string;
    street?: string;
    postal_code?: string | null;
  } | null;
  items: OrderItem[];
  status_history: Array<{ id: string; status: string; notes: string | null; created_at: string }>;
};

export type Payment = TimestampFields & {
  id: string;
  order_id: string;
  user_id: string;
  amount: number | string;
  currency: string;
  method: string;
  provider: string | null;
  status: string;
  provider_transaction_id: string | null;
  failure_reason?: string | null;
  provider_response?: {
    checkout_url?: string | null;
    message?: string | null;
    [key: string]: unknown;
  } | null;
  paid_at: string | null;
  transactions: Array<Record<string, unknown>>;
};

export type PaginatedOrders = PaginatedResults<Order>;
export type PaginatedPayments = PaginatedResults<Payment>;

export type OrderWorkflowStage = {
  name: "checkout" | "payment" | "seller_fulfillment" | "logistics" | "pickup" | "delivery";
  status: "complete" | "in_progress" | "waiting" | "blocked";
  detail: string;
};
export type OrderShipmentWorkflow = {
  shipment_id: string; seller_id: string; store_id: string; seller_order_id?: string | null;
  seller_order_status?: string | null; shipment_status: string; logistics_company_id?: string | null;
  pickup_job_status?: string | null; handover_status?: string | null; pickup_proof_status?: string | null;
  latest_tracking_status?: string | null; tracking_event_count: number;
};
export type OrderWorkflow = {
  order_id: string; order_status: string; overall_status: "in_progress" | "action_required" | "complete" | "terminal";
  delivery_quote_id?: string | null; payment_ready: boolean; seller_order_count: number; shipment_count: number;
  delivered_shipment_count: number; stages: OrderWorkflowStage[]; shipments: OrderShipmentWorkflow[];
  blockers: string[]; reconciliation_actions: string[];
};


export type ShipmentTrackingEvent = {
  id: string;
  shipment_id: string;
  status: string;
  location?: string | null;
  notes?: string | null;
  created_by_id?: string | null;
  created_at: string;
};

export type ShipmentItem = {
  id: string;
  order_item_id: string;
  quantity: number;
};

export type Shipment = {
  id: string;
  order_id: string;
  seller_id: string;
  store_id: string;
  logistics_company_id?: string | null;
  shipping_method_id?: string | null;
  status: string;
  carrier_name?: string | null;
  tracking_number?: string | null;
  estimated_delivery_from?: string | null;
  estimated_delivery_to?: string | null;
  dispatched_at?: string | null;
  delivered_at?: string | null;
  items: ShipmentItem[];
  tracking_events: ShipmentTrackingEvent[];
  created_at: string;
  updated_at?: string | null;
};

export type CustomerOrderPaymentSummary = {
  id: string;
  amount: number | string;
  currency: string;
  method: string;
  provider?: string | null;
  status: string;
  provider_transaction_id?: string | null;
  paid_at?: string | null;
  created_at: string;
};

export type CustomerSellerOrderSummary = {
  id: string;
  seller_id: string;
  store_id: string;
  status: string;
  seller_subtotal: number | string;
  item_count: number;
  accepted_at?: string | null;
  processing_at?: string | null;
  ready_to_ship_at?: string | null;
  shipped_at?: string | null;
  delivered_at?: string | null;
  created_at: string;
};

export type CustomerOrderAddressSummary = {
  label?: string | null;
  recipient_name?: string | null;
  recipient_phone?: string | null;
  country?: string | null;
  region?: string | null;
  district?: string | null;
  ward?: string | null;
  city?: string | null;
  street?: string | null;
  landmark?: string | null;
  postal_code?: string | null;
};

export type CustomerOrderDetail = Omit<Order, "payments"> & {
  payment_status?: string | null;
  payments: CustomerOrderPaymentSummary[];
  shipping_address?: CustomerOrderAddressSummary | null;
  shipments: Shipment[];
  seller_orders: CustomerSellerOrderSummary[];
};


export type CustomerEscrowSummary = {
  order_id: string;
  currency: string;
  status:
    | "not_applicable"
    | "held"
    | "partially_released"
    | "released"
    | "disputed";
  hold_count: number;
  gross_amount: number | string;
  seller_amount: number | string;
  commission_amount: number | string;
  released_amount: number | string;
  remaining_amount: number | string;
  release_after?: string | null;
  can_customer_approve: boolean;
};


export type OrderPaymentState = {
  order_id: string;
  order_status: string;
  payment_status:
    | "not_started"
    | "pending"
    | "processing"
    | "completed"
    | "failed"
    | "cancelled"
    | "refunded";
  latest_payment?: Payment | null;
  retryable: boolean;
  terminal: boolean;
  poll_after_seconds?: number | null;
  message: string;
};
