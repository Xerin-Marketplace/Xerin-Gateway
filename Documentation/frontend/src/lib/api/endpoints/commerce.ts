import axiosInstance from "../client";
import type {
  Cart,
  GuestCartMergeResult,
  Order,
  OrderPaymentState,
  PaginatedOrders,
  Payment,
  PaymentInitiatePayload,
  PaymentRetryPayload,
  PaginatedPayments,
  PaymentOption,
  ShippingOption,
  DeliveryCheckoutConfig,
  DeliveryMode,
  DetectedDeliveryMode,
  CustomerOrderDetail,
  CustomerEscrowSummary,
  EligibleLogisticsResponse,
  MultiSellerPricingResponse,
  CheckoutDeliveryQuote,
  OrderWorkflow,
} from "@/types/api/commerce";

export const cartApi = {
  get: async (signal?: AbortSignal) =>
    (await axiosInstance.get<Cart>("/cart", { signal })).data,
  addItem: async (payload: { product_id: string; variant_id?: string | null; quantity: number }) =>
    (await axiosInstance.post<Cart>("/cart/items", payload)).data,
  updateItem: async (itemId: string, quantity: number) =>
    (await axiosInstance.put<Cart>(`/cart/items/${itemId}`, { quantity })).data,
  removeItem: async (itemId: string) =>
    (await axiosInstance.delete<Cart>(`/cart/items/${itemId}`)).data,
  clear: async () => (await axiosInstance.delete<Cart>("/cart")).data,
  applyCoupon: async (code: string) =>
    (await axiosInstance.post<Cart>("/cart/apply-coupon", { code })).data,
  removeCoupon: async () => (await axiosInstance.delete<Cart>("/cart/coupon")).data,
  availablePromotions: async () =>
    (
      await axiosInstance.get<
        import("@/types/api/promotion").CustomerPromotionOffer[]
      >("/cart/promotions/available")
    ).data,
  applyPromotion: async (code: string) =>
    (
      await axiosInstance.post<Cart>("/cart/apply-promotion", { code })
    ).data,
  removePromotion: async () =>
    (await axiosInstance.delete<Cart>("/cart/promotion")).data,
  validate: async () => (await axiosInstance.post<Cart>("/cart/validate")).data,
  merge: async (items: Array<{ product_id: string; variant_id?: string | null; quantity: number }>) =>
    (await axiosInstance.post<GuestCartMergeResult>("/cart/merge", { items })).data,
};

export const checkoutApi = {
  deliveryConfig: async (): Promise<DeliveryCheckoutConfig> =>
    (
      await axiosInstance.get<DeliveryCheckoutConfig>(
        "/shipping/checkout-config",
      )
    ).data,

  detectDeliveryMode: async (addressId: string, signal?: AbortSignal): Promise<DetectedDeliveryMode> =>
    (await axiosInstance.post<DetectedDeliveryMode>(
      "/shipping/detect-delivery-mode",
      { address_id: addressId },
      { signal },
    )).data,

  eligibleLogistics: async (
    payload: { address_id: string; delivery_mode: DeliveryMode },
    signal?: AbortSignal,
  ): Promise<EligibleLogisticsResponse> =>
    (await axiosInstance.post<EligibleLogisticsResponse>(
      "/shipping/eligible-logistics",
      payload,
      { params: { page: 1, page_size: 100 }, signal },
    )).data,

  multiSellerPricing: async (
    payload: {
      address_id: string;
      logistics_company_id: string;
      delivery_mode: DeliveryMode;
      method_id?: string;
    },
    signal?: AbortSignal,
  ): Promise<MultiSellerPricingResponse> =>
    (await axiosInstance.post<MultiSellerPricingResponse>(
      "/shipping/multi-seller-pricing",
      payload,
      { signal },
    )).data,

  freezeDeliveryQuote: async (payload: {
    address_id: string;
    logistics_company_id: string;
    rate_id: string;
    delivery_mode: DeliveryMode;
  }): Promise<CheckoutDeliveryQuote> =>
    (await axiosInstance.post<CheckoutDeliveryQuote>(
      "/shipping/checkout-delivery-quote",
      payload,
    )).data,

  shippingOptions: async (
    payload: {
      address_id: string;
      delivery_mode: DeliveryMode;
      logistics_company_id?: string | null;
      method_id?: string | null;
    },
    signal?: AbortSignal,
  ) => {
    type BackendShippingOption = {
      rate_id: string;
      method_id: string;
      logistics_company_id?: string | null;
      logistics_company_name?: string | null;
      method_name: string;
      carrier_name?: string | null;
      scope: DeliveryMode | "both";
      supports_cod: boolean;
      supports_tracking: boolean;
      original_amount: number | string;
      shipping_discount_amount: number | string;
      amount: number | string;
      currency: string;
      min_delivery_days: number;
      max_delivery_days: number;
      free_shipping_applied: boolean;
      promotion_code?: string | null;
      promotion_name?: string | null;
    };

    const response = await axiosInstance.post<BackendShippingOption[]>(
      "/shipping/quote",
      payload,
      { signal },
    );

    return response.data.map(
      (option) =>
        ({
          id: option.rate_id,
          method_id: option.method_id,
          logistics_company_id: option.logistics_company_id || null,
          logistics_company_name:
            option.logistics_company_name ||
            option.carrier_name ||
            "Marketplace delivery",
          service_name: option.method_name,
          carrier:
            option.carrier_name ||
            option.logistics_company_name ||
            "Marketplace delivery",
          scope: option.scope,
          supports_cod: option.supports_cod,
          tracking_supported: option.supports_tracking,
          original_amount: option.original_amount,
          shipping_discount_amount: option.shipping_discount_amount,
          amount: option.amount,
          currency: option.currency,
          estimated_min_days: option.min_delivery_days,
          estimated_max_days: option.max_delivery_days,
          free_shipping_applied: option.free_shipping_applied,
          promotion_code: option.promotion_code,
          promotion_name: option.promotion_name,
        }) satisfies ShippingOption,
    );
  },

  paymentOptions: async (
    supportsCod = false,
  ): Promise<PaymentOption[]> => {
    const methods: PaymentOption[] = [
      {
        id: "mobile_money",
        label: "Mobile Payment",
        requires_phone: true,
        providers: ["M-Pesa", "Airtel Money", "Mixx by Yas", "HaloPesa"],
      },
      {
        id: "card",
        label: "Card Payment",
        requires_phone: false,
        providers: ["azampay"],
      },
    ];

    if (supportsCod) {
      methods.push({
        id: "cash_on_delivery",
        label: "Cash on Delivery",
        requires_phone: false,
        providers: [],
      });
    }

    return methods;
  },
};

export const ordersApi = {
  mine: async (
    params: {
      page?: number;
      page_size?: number;
      search?: string;
      status?: string;
      payment_status?: string;
    } = {},
    signal?: AbortSignal,
  ) =>
    (
      await axiosInstance.get<PaginatedOrders>("/orders/my-orders", {
        params,
        signal,
      })
    ).data,
  get: async (id: string, signal?: AbortSignal) =>
    (await axiosInstance.get<Order>(`/orders/${id}`, { signal })).data,
  invoice: async (id: string) =>
    (
      await axiosInstance.get<Blob>(`/orders/${id}/invoice.pdf`, {
        responseType: "blob",
      })
    ).data,
  receipt: async (id: string) =>
    (
      await axiosInstance.get<Blob>(`/orders/${id}/receipt.pdf`, {
        responseType: "blob",
      })
    ).data,
  customerDetail: async (id: string, signal?: AbortSignal) =>
    (
      await axiosInstance.get<CustomerOrderDetail>(
        `/orders/${id}/customer-detail`,
        { signal },
      )
    ).data,
  create: async (payload: {
    shipping_address_id: string;
    shipping_rate_id?: string;
    delivery_quote_id?: string;
    delivery_mode: DeliveryMode;
    coupon_code?: string;
    promotion_code?: string;
    notes?: string;
  }) =>
    (await axiosInstance.post<Order>("/orders", payload)).data,
  updateStatus: async (id: string, payload: { status: string; notes?: string }) =>
    (await axiosInstance.patch<Order>(`/orders/${id}/status`, payload)).data,
  escrowStatus: async (id: string, signal?: AbortSignal) =>
    (
      await axiosInstance.get<CustomerEscrowSummary>(
        `/orders/${id}/escrow`,
        { signal },
      )
    ).data,
  approveReceipt: async (id: string, note?: string) =>
    (
      await axiosInstance.post<CustomerEscrowSummary>(
        `/orders/${id}/approve-receipt`,
        { note: note || undefined },
      )
    ).data,
  adminList: async (
    params: {
      page?: number;
      page_size?: number;
      status?: string;
      search?: string;
      payment_status?: string;
      date_from?: string;
      date_to?: string;
    } = {},
    signal?: AbortSignal,
  ) =>
    (
      await axiosInstance.get<PaginatedOrders>("/orders/admin/all", {
        params,
        signal,
      })
    ).data,
  workflow: async (id: string) =>
    (await axiosInstance.get<OrderWorkflow>(`/orders/${id}/workflow`)).data,
  reconcileWorkflow: async (id: string) =>
    (await axiosInstance.post<OrderWorkflow>(`/orders/${id}/workflow/reconcile`)).data,
};

export const paymentsApi = {
  mine: async (
    params: {
      page?: number;
      page_size?: number;
      search?: string;
      payment_status?: string;
      method?: string;
    } = {},
    signal?: AbortSignal,
  ) =>
    (
      await axiosInstance.get<PaginatedPayments>(
        "/payments/my-payments",
        { params, signal },
      )
    ).data,
  get: async (id: string, signal?: AbortSignal) =>
    (await axiosInstance.get<Payment>(`/payments/${id}`, { signal })).data,
  initiate: async (payload: PaymentInitiatePayload) =>
    (await axiosInstance.post<Payment>("/payments/initiate", payload)).data,
  retry: async (id: string, payload: PaymentRetryPayload) =>
    (await axiosInstance.post<Payment>(`/payments/${id}/retry`, payload)).data,
  orderState: async (orderId: string, signal?: AbortSignal) =>
    (
      await axiosInstance.get<OrderPaymentState>(
        `/payments/orders/${orderId}/state`,
        { signal },
      )
    ).data,
};
