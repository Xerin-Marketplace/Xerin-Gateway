import axiosInstance from "@/lib/api/client";

export const PAYMENT_STATUSES = [
  "pending",
  "processing",
  "completed",
  "failed",
  "refunded",
  "cancelled",
] as const;

export const REFUND_STATUSES = [
  "requested",
  "under_review",
  "approved",
  "processing",
  "completed",
  "rejected",
  "failed",
  "cancelled",
] as const;

export type PaymentStatus = (typeof PAYMENT_STATUSES)[number];
export type RefundStatus = (typeof REFUND_STATUSES)[number];

export type PaymentTransaction = {
  id: string;
  transaction_type: string;
  status: string;
  amount: string | null;
  provider_response: Record<string, unknown> | null;
  created_at: string;
};

export type Payment = {
  id: string;
  order_id: string;
  user_id: string;
  amount: string;
  currency: string;
  method:
    | "mobile_money"
    | "bank_transfer"
    | "card"
    | "cash_on_delivery"
    | "xerin_pay";
  provider: string | null;
  status: PaymentStatus;
  provider_transaction_id: string | null;
  paid_at: string | null;
  transactions: PaymentTransaction[];
  created_at: string;
  updated_at: string | null;
};

export type RefundEvent = {
  id: string;
  status: RefundStatus;
  note?: string | null;
  created_by_id?: string | null;
  created_at: string;
};

export type RefundItem = {
  id: string;
  order_item_id: string;
  seller_id: string;
  quantity: number;
  unit_amount: string;
  refund_amount: string;
  commission_reversal: string;
  seller_reversal: string;
  seller_debt_amount: string;
  restock: boolean;
  processed_at?: string | null;
};

export type Refund = {
  id: string;
  order_id: string;
  requested_by_id: string;
  status: RefundStatus;
  reason:
    | "changed_mind"
    | "damaged"
    | "defective"
    | "wrong_item"
    | "not_received"
    | "duplicate_payment"
    | "other";
  reason_details?: string | null;
  currency: string;
  items_amount: string;
  shipping_amount: string;
  tax_amount: string;
  total_amount: string;
  provider_reference?: string | null;
  idempotency_key: string;
  admin_note?: string | null;
  requested_at: string;
  reviewed_at?: string | null;
  processed_at?: string | null;
  completed_at?: string | null;
  items?: RefundItem[];
  events?: RefundEvent[];
};

export type PaymentListParams = {
  order_id?: string;
  payment_status?: PaymentStatus;
  signal?: AbortSignal;
};

export type RefundListParams = {
  refund_status?: RefundStatus;
  signal?: AbortSignal;
};

export const paymentsService = {
  async listPayments(params: PaymentListParams = {}): Promise<Payment[]> {
    const { signal, ...query } = params;
    const response = await axiosInstance.get<Payment[]>("/payments/admin/all", {
      params: query,
      signal,
    });
    return response.data;
  },

  async getPayment(id: string, signal?: AbortSignal): Promise<Payment> {
    const response = await axiosInstance.get<Payment>(`/payments/${id}`, {
      signal,
    });
    return response.data;
  },

  async listRefunds(params: RefundListParams = {}): Promise<Refund[]> {
    const { signal, ...query } = params;
    const response = await axiosInstance.get<Refund[]>("/refunds/admin", {
      params: query,
      signal,
    });
    return response.data;
  },

  async getRefund(id: string, signal?: AbortSignal): Promise<Refund> {
    const response = await axiosInstance.get<Refund>(`/refunds/${id}`, {
      signal,
    });
    return response.data;
  },
};
