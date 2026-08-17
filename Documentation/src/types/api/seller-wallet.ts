export type SellerEarningsSummary = {
  currency: string;
  gross_sales: number | string;
  commission_deducted: number | string;
  net_earnings: number | string;
  transaction_count: number;
};

export type SellerWallet = {
  id: string;
  seller_id: string;
  currency: string;
  pending_balance: number | string;
  available_balance: number | string;
  reserved_balance: number | string;
  paid_out_balance: number | string;
  refunded_balance: number | string;
  debt_balance: number | string;
  is_frozen: boolean;
  created_at: string;
  updated_at?: string | null;
};

export type WalletTransactionType =
  | "sale_credit"
  | "funds_release"
  | "payout_hold"
  | "payout_completed"
  | "payout_released"
  | "refund_debit"
  | "adjustment"
  | string;

export type SellerWalletTransaction = {
  id: string;
  transaction_type: WalletTransactionType;
  amount: number | string;
  currency: string;
  reference: string;
  order_id?: string | null;
  eligible_at?: string | null;
  released_at?: string | null;
  description?: string | null;
  created_at: string;
};

export type PaginatedWalletTransactionResponse = {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: SellerWalletTransaction[];
};

export type SellerWalletTransactionParams = {
  page?: number;
  page_size?: number;
};


export type PayoutStatus =
  | "pending"
  | "approved"
  | "processing"
  | "completed"
  | "rejected"
  | "failed"
  | "cancelled"
  | string;

export type SellerPayoutRequest = {
  id: string;
  seller_id: string;
  payout_account_id: string;
  amount: number | string;
  currency: string;
  status: PayoutStatus;
  provider_reference?: string | null;
  seller_note?: string | null;
  admin_note?: string | null;
  requested_at: string;
  processed_at?: string | null;
  completed_at?: string | null;
};

export type SellerPayoutCreateRequest = {
  payout_account_id: string;
  amount: number;
  note?: string | null;
};

export type PaginatedSellerPayoutResponse = {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: SellerPayoutRequest[];
};

export type SellerPayoutListParams = {
  page?: number;
  page_size?: number;
};
