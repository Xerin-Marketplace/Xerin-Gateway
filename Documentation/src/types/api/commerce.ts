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

export type CustomerOrderDetail = Order & {
  payment_status?: string | null;
  payments: CustomerOrderPaymentSummary[];
  shipping_address?: CustomerOrderAddressSummary | null;
  shipments: Shipment[];
  seller_orders: CustomerSellerOrderSummary[];
};
