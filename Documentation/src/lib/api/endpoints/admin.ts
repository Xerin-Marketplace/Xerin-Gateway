import axiosInstance from "../client";

export type AdminUser = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  phone: string | null;
  status: string;
  is_verified: boolean;
  created_at: string;
};

export type PaginatedAdminUsers = {
  total: number;
  page: number;
  page_size: number;
  results: AdminUser[];
};

export type AdminSeller = {
  id: string;
  user_id: string;
  business_name: string;
  contact_email: string | null;
  contact_phone: string | null;
  status: string;
  created_at: string;
  business_description?: string | null;
  business_country?: string | null;
  business_region?: string | null;
  business_city?: string | null;
  business_address?: string | null;
  product_description?: string | null;
  years_in_business?: string | null;
  website_url?: string | null;
  agreement_accepted?: boolean;
};

export type AdminSellerDocument = {
  id: string;
  seller_id: string;
  document_type: string;
  document_url: string;
  mime_type?: string | null;
  status: string;
  rejection_reason?: string | null;
  uploaded_at: string;
};

export type AdminSellerProduct = { id: string; seller_id: string; seller_name: string; name: string; sku: string; price: number; currency: string; status: string; is_active: boolean; created_at: string };
export type AdminSellerOrder = { id: string; order_id: string; order_number: string; seller_id: string; seller_name: string; product_name: string; quantity: number; amount: number; currency: string; status: string; created_at: string };
export type AdminSellerPerformance = { seller_id: string; seller_name: string; status: string; products: number; approved_products: number; orders: number; delivered_orders: number; cancelled_orders: number; revenue: number; currency: string; fulfillment_rate: number };
export type AdminPayment = { id: string; order_id: string; order_number: string; user_id: string; customer_name: string; customer_email: string; amount: number; currency: string; method: string; provider: string | null; status: string; reference: string | null; failure_reason: string | null; paid_at: string | null; created_at: string; updated_at: string | null; transaction_count: number; refund_reason: string | null; refunded_at: string | null };
export type AdminPaymentMethod = { method: string; provider: string; transactions: number; completed: number; failed: number; volume: number; currency: string };

export type PaymentAdminPage<T> = { total:number; page:number; page_size:number; total_pages?:number; results:T[] };
export type PaymentAdminParams = { page?:number; page_size?:number; search?:string; status_filter?:string; provider?:string; currency?:string; date_from?:string; date_to?:string };

export type AdminPaymentProvider = {
  id:string; name:string; code:string; provider_type:string; status:string;
  supported_currencies:string[]; supported_methods:string[];
  environment?:string|null; is_default?:boolean;
};

export type AdminPayout = {
  id:string; seller_id:string; seller_name:string; amount:number; currency:string;
  status:string; payout_method?:string|null; provider?:string|null;
  reference?:string|null; failure_reason?:string|null;
  requested_at?:string|null; processed_at?:string|null; created_at:string;
};

export type AdminPaymentDispute = {
  id:string; payment_id?:string|null; order_id?:string|null; order_number?:string|null;
  customer_name?:string|null; seller_name?:string|null; amount:number; currency:string;
  reason:string; status:string; provider?:string|null; provider_reference?:string|null;
  created_at:string;
};

export type AdminRiskEvent = {
  id:string; event_type:string; severity:string; status:string;
  payment_id?:string|null; order_id?:string|null; user_name?:string|null;
  score?:number|null; reason?:string|null; created_at:string;
};

export type AdminReconciliation = {
  id:string; order_number?:string|null; provider?:string|null;
  provider_reference?:string|null; expected_amount:number; provider_amount:number;
  currency:string; difference:number; status:string; created_at:string;
};

export type AdminCurrency = {
  id:string; code:string; name:string; symbol:string;
  is_base:boolean; is_active:boolean; decimal_places?:number;
};

export type AdminFxRate = {
  id:string; base_currency:string; quote_currency:string; rate:number;
  source?:string|null; effective_at:string; is_active:boolean;
};

export type AdminCountry = {
  id:string; code:string; name:string; currency_code:string;
  is_active:boolean; payments_enabled:boolean; payouts_enabled:boolean;
};

export type AdminFeeCommission = {
  id:string; name:string; scope:string; rate_type:string; rate_value:number;
  currency?:string|null; provider?:string|null; is_active:boolean;
};

export type AdminPaymentDashboard = {
  processed_volume:number; successful_payments:number; pending_payments:number;
  failed_payments:number; refunded_amount:number; pending_payouts:number;
  completed_payouts:number; platform_commission:number; seller_earnings:number;
  currency:string;
};
export type Coupon = { id: string; code: string; description: string | null; discount_type: string; discount_value: number; minimum_order_amount: number | null; maximum_discount_amount: number | null; usage_limit: number | null; usage_count: number; is_active: boolean; valid_from: string | null; valid_until: string | null; created_at: string };
export type DiscountRule = { id: string; name: string; description: string | null; discount_type: string; discount_value: number; applies_to: string; minimum_order_amount: number | null; priority: number; is_active: boolean; valid_from: string | null; valid_until: string | null; created_at: string };
export type PromotionCampaign = { id: string; name: string; objective: string; description: string | null; audience: string; channel: string; budget: number | null; currency: string; status: string; starts_at: string | null; ends_at: string | null; impressions: number; conversions: number; revenue: number; created_at: string };
export type CommunicationMessage = { id: string; channel: "notification" | "email" | "sms"; title: string | null; body: string; audience: string; recipient: string | null; status: string; scheduled_at: string | null; sent_at: string | null; delivered_at: string | null; failure_reason: string | null; created_at: string };
export type AccessUser = AdminUser & {
  roles: string[];
  role_ids: string[];
  permissions: string[];
  active_sessions?: number;
  last_login_at?: string | null;
};

export type PaginatedAccessUsers = {
  total: number;
  page: number;
  page_size: number;
  results: AccessUser[];
};

export type ListAccessUsersParams = {
  page?: number;
  page_size?: number;
  search?: string;
  status_filter?: string;
  role_filter?: string;
};

export type AccessRole = {
  id: string;
  name: string;
  description: string | null;
  users_count: number;
  permissions: string[];
  created_at?: string | null;
};

export type AccessPermission = {
  id: string;
  code: string;
  name: string;
  description: string | null;
  created_at?: string | null;
};

export type AccessSession = {
  id: string;
  user_id: string;
  user_name: string;
  email: string;
  created_at: string;
  expires_at: string;
  is_current_user: boolean;
};

export type RoleApiResponse = {
  id: string;
  name: string;
  description: string | null;
  created_at?: string | null;
};

export type RolePermissionsResponse = {
  role_id: string;
  role_name: string;
  permissions: string[];
};

export type UserRolesResponse = {
  user_id: string;
  roles: RoleApiResponse[];
};

export type UserPermissionsResponse = {
  user_id: string;
  permissions: string[];
};

export type CreateRolePayload = {
  name: string;
  description?: string | null;
  permission_codes?: string[];
};

export type CreateStaffPayload = {
  first_name: string;
  last_name: string;
  email: string;
  phone?: string | null;
  password: string;
  role_ids: string[];
  status?: string;
  is_verified?: boolean;
};

export type AdminStaffResponse = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  phone: string | null;
  status: string;
  is_verified: boolean;
  created_at: string;
  roles: string[];
  permissions: string[];
};
export type AdminReport = { type: string; date_from: string; date_to: string; currency: string; metrics: Array<{label:string;value:number;format:"currency"|"number"|"percent"}>; breakdown: Array<{label:string;value:number}>; rows: Array<Record<string,string|number|null>> };
export type AuditLog={id:string;actor_id:string|null;actor_name:string;action:string;resource_type:string;resource_id:string|null;details:Record<string,unknown>;created_at:string};
export type SystemEvent={id:string;source:string;event_type:string;severity:string;message:string;metadata_json:Record<string,unknown>|null;status:string;acknowledged_at:string|null;created_at:string};
export type BackgroundJob={id:string;job_type:string;queue:string;status:string;attempts:number;max_attempts:number;failure_reason:string|null;scheduled_at:string|null;started_at:string|null;completed_at:string|null;created_at:string};
export type ApplicationSetting={id:string|null;key:string;value:unknown;category:string;description:string|null;is_public:boolean;updated_at:string|null};
export type AccountProfile={id:string;first_name:string;last_name:string;email:string;phone:string|null;is_verified:boolean;status:string;account_type:string;roles?:string[]};
export type AccountSession={id:string;created_at:string;expires_at:string};

export type AdminProduct = {
  id: string;
  seller_id: string;
  category_id: string;
  brand_id?: string | null;
  sku: string;
  barcode?: string | null;
  name: string;
  slug: string;
  short_description?: string | null;
  description?: string | null;
  price: number;
  sale_price?: number | null;
  cost_price?: number | null;
  tax_class?: string | null;
  currency: string;
  weight?: number | null;
  featured: boolean;
  track_stock: boolean;
  quantity: number;
  low_stock_threshold: number;
  warehouse_id?: string | null;
  status: string;
  rejection_reason?: string | null;
  is_active: boolean;
  submitted_at?: string | null;
  approved_at?: string | null;
  created_at: string;
  images?: Array<{ id:string; product_id:string; image_url:string; thumbnail_url?:string|null; alt_text?:string|null; is_primary:boolean; display_order?:number; }>;
  seller_business_name?: string | null;
  seller_contact_email?: string | null;
  seller_contact_phone?: string | null;
  category_name?: string | null;
  brand_name?: string | null;
};

export type AdminCatalogSummary = { total_products:number; pending_products:number; approved_products:number; rejected_products:number; product_categories:number; business_categories:number; brands:number; };

export type CatalogPageParams = { page?:number; page_size?:number; search?:string };
export type CatalogProductPageParams = CatalogPageParams & { status_filter?:string };
export type BusinessCategoryPageParams = CatalogPageParams & { active_filter?:"all"|"active"|"inactive" };
export type PaginatedCatalogResponse<T> = { total:number; page:number; page_size:number; total_pages:number; results:T[] };

export type BusinessCategory = {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  active: boolean;
  created_at: string;
};

export type Brand = {
  id: string;
  name: string;
  slug: string;
  description?: string | null;
  logo_url?: string | null;
  website?: string | null;
  is_active: boolean;
  products_count: number;
  created_at: string;
};

export type ListUsersParams = {
  page?: number;
  page_size?: number;
  search?: string;
  status_filter?: string;
};

export type PaginatedAdminProducts = {
  total: number;
  page: number;
  page_size: number;
  results: AdminProduct[];
};

export type ListAllProductsParams = {
  page?: number;
  page_size?: number;
  search?: string;
  category_id?: string;
  brand_id?: string;
  seller_id?: string;
  status?: string;
  is_active?: boolean;
};

export type ProductCategory = {
  id: string;
  parent_id?: string | null;
  name: string;
  slug: string;
  description?: string | null;
  image_url?: string | null;
  display_order: number;
  is_active: boolean;
  products_count: number;
  created_at: string;
};

export type CreateBusinessCategoryPayload = {
  name: string;
  slug: string;
  description?: string;
  active?: boolean;
};

export type CreateProductCategoryPayload = {
  parent_id?: string | null;
  name: string;
  slug: string;
  description?: string;
  image_url?: string;
  display_order?: number;
  is_active?: boolean;
};

export type UpdateProductCategoryPayload = {
  parent_id?: string | null;
  name?: string;
  slug?: string;
  description?: string;
  image_url?: string;
  display_order?: number;
  is_active?: boolean;
};

export type ProductReview = {
  id: string;
  product_id?: string;
  user_id?: string;
  rating: number;
  title?: string | null;
  comment?: string | null;
  status: string;
  seller_reply?: string | null;
  verified_purchase?: boolean;
  helpful_count?: number;
  created_at: string;
};

type ProductReviewListResponse = {
  total: number;
  page: number;
  page_size: number;
  average_rating: number | string;
  results: ProductReview[];
};

export type UpdateProductReviewPayload = {
  rating?: number;
  comment?: string;
  status?: string;
  admin_reply?: string;
};

export type CreateBrandPayload = {
  name: string;
  slug: string;
  description?: string;
  logo_url?: string;
  website?: string;
  is_active?: boolean;
};

export type UpdateBrandPayload = {
  name?: string;
  slug?: string;
  description?: string;
  logo_url?: string;
  website?: string;
  is_active?: boolean;
};

export type CreateProductPayload = {
  seller_id: string;
  category_id: string;
  brand_id?: string | null;
  sku: string;
  barcode?: string;
  name: string;
  slug: string;
  short_description?: string;
  description?: string;
  price: number;
  sale_price?: number | null;
  cost_price?: number | null;
  tax_class?: string;
  currency?: string;
  weight?: number | null;
  featured?: boolean;
  track_stock?: boolean;
  quantity?: number;
  low_stock_threshold?: number;
  warehouse_id?: string;
};

export type UpdateProductPayload = {
  category_id?: string;
  brand_id?: string | null;
  sku?: string;
  barcode?: string;
  name?: string;
  slug?: string;
  short_description?: string;
  description?: string;
  price?: number;
  sale_price?: number | null;
  cost_price?: number | null;
  tax_class?: string;
  currency?: string;
  weight?: number | null;
  featured?: boolean;
  track_stock?: boolean;
  quantity?: number;
  low_stock_threshold?: number;
  warehouse_id?: string;
  is_active?: boolean;
};

export type OrderStatus =
  | "pending"
  | "awaiting_payment"
  | "payment_verification"
  | "confirmed"
  | "processing"
  | "packed"
  | "ready_for_dispatch"
  | "shipped"
  | "out_for_delivery"
  | "delivered"
  | "completed"
  | "cancelled"
  | "rejected"
  | "refunded"
  | "failed";

export type PaymentStatus =
  | "pending"
  | "authorized"
  | "paid"
  | "partially_paid"
  | "failed"
  | "refunded"
  | "partially_refunded";

export type OrderItem = {
  id: string;
  product_id: string;
  variant_id: string | null;
  product_name: string;
  variant_name: string | null;
  sku: string;
  quantity: number;
  unit_price: number;
  discount_amount: number;
  tax_amount: number;
  subtotal: number;
  created_at: string;
};

export type OrderStatusHistoryEntry = {
  id: string;
  order_id: string;
  status: string;
  previous_status: string | null;
  notes: string | null;
  created_by_id: string | null;
  created_at: string;
};

export type OrderPayment = {
  id: string;
  order_id: string;
  user_id: string;
  method: string;
  transaction_reference: string | null;
  amount: number;
  currency: string;
  status: PaymentStatus;
  paid_at: string | null;
  created_at: string;
  updated_at: string;
};

export type OrderAddress = {
  id: string;
  country: string;
  region: string;
  city: string;
  street: string;
  postal_code: string | null;
  is_default: boolean;
};

export type OrderCustomer = {
  id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  phone: string | null;
  is_verified: boolean;
  status: string;
};

export type Order = {
  id: string;
  order_number: string;
  user_id: string;
  address_id: string | null;
  seller_id: string | null;
  status: OrderStatus;
  payment_status: PaymentStatus;
  subtotal: number;
  discount_amount: number;
  shipping_amount: number;
  tax_amount: number;
  total_amount: number;
  currency: string;
  delivery_method: string | null;
  courier_name: string | null;
  tracking_number: string | null;
  estimated_delivery_date: string | null;
  delivered_at: string | null;
  customer_notes: string | null;
  admin_notes: string | null;
  cancellation_reason: string | null;
  refund_notes: string | null;
  created_at: string;
  updated_at: string;
  items: OrderItem[];
  status_history: OrderStatusHistoryEntry[];
  payments: OrderPayment[];
  address: OrderAddress | null;
  user: OrderCustomer | null;
  seller: AdminSeller | null;
};

export type PaginatedOrders = {
  total: number;
  page: number;
  page_size: number;
  results: Order[];
};

export type ListOrdersParams = {
  page?: number;
  page_size?: number;
  status?: string;
  payment_status?: string;
  search?: string;
  customer_id?: string;
  seller_id?: string;
  payment_method?: string;
  min_amount?: number;
  max_amount?: number;
  date_from?: string;
  date_to?: string;
};

export type UpdateOrderStatusPayload = {
  status: string;
  notes?: string;
};

export type CancelOrderPayload = {
  reason: string;
};

export type RefundOrderPayload = {
  amount: number;
  notes?: string;
};

export type UpdateOrderTrackingPayload = {
  courier_name?: string;
  tracking_number?: string;
  estimated_delivery_date?: string;
};

export const listUsers = async (params: ListUsersParams = {}): Promise<PaginatedAdminUsers> => {
  const res = await axiosInstance.get<PaginatedAdminUsers>("/admin/users", { params });
  return res.data;
};

export const listAllSellers = async (): Promise<AdminSeller[]> => {
  const res = await axiosInstance.get<AdminSeller[]>("/admin/sellers");
  return res.data;
};

export const listPendingSellers = async (): Promise<AdminSeller[]> => {
  const res = await axiosInstance.get<AdminSeller[]>("/admin/sellers/pending");
  return res.data;
};

export const getSellerDocuments = async (sellerId: string): Promise<AdminSellerDocument[]> => {
  const res = await axiosInstance.get<AdminSellerDocument[]>(`/admin/sellers/${sellerId}/documents`);
  return res.data;
};
export const startSellerReview = async (sellerId: string): Promise<AdminSeller> => {
  const res = await axiosInstance.post<AdminSeller>(`/admin/sellers/${sellerId}/start-review`);
  return res.data;
};

export const getSellerDocumentViewUrl = (sellerId: string, documentId: string) =>
  `/admin/sellers/${sellerId}/documents/${documentId}/view`;
export const listSellerProducts = async () => (await axiosInstance.get<AdminSellerProduct[]>("/admin/seller-products")).data;
export const listSellerOrders = async () => (await axiosInstance.get<AdminSellerOrder[]>("/admin/seller-orders")).data;
export const listSellerPerformance = async () => (await axiosInstance.get<AdminSellerPerformance[]>("/admin/seller-performance")).data;
const normalizePaymentPage = <T,>(data:T[]|PaymentAdminPage<T>, page=1, pageSize=20):PaymentAdminPage<T> => {
  if (!Array.isArray(data)) return data;
  const total=data.length; const start=(page-1)*pageSize;
  return { total, page, page_size:pageSize, total_pages: total ? Math.ceil(total/pageSize) : 0, results:data.slice(start,start+pageSize) };
};

export const listAdminPayments = async (params:PaymentAdminParams={}) => {
  const res=await axiosInstance.get<AdminPayment[]|PaymentAdminPage<AdminPayment>>("/admin/payments",{params});
  return normalizePaymentPage(res.data,params.page,params.page_size);
};
export const listAdminPaymentMethods = async () => (await axiosInstance.get<AdminPaymentMethod[]>("/admin/payment-methods")).data;
export const listAdminRefunds = async (params:PaymentAdminParams={}) => {
  const res=await axiosInstance.get<AdminPayment[]|PaymentAdminPage<AdminPayment>>("/admin/refunds",{params});
  return normalizePaymentPage(res.data,params.page,params.page_size);
};
export const listAdminFailedPayments = async (params:PaymentAdminParams={}) => {
  const res=await axiosInstance.get<AdminPayment[]|PaymentAdminPage<AdminPayment>>("/admin/failed-payments",{params});
  return normalizePaymentPage(res.data,params.page,params.page_size);
};

const listPaymentResource = async <T,>(path:string,params:PaymentAdminParams={}) => {
  const res=await axiosInstance.get<T[]|PaymentAdminPage<T>>(path,{params});
  return normalizePaymentPage(res.data,params.page,params.page_size);
};

export const getAdminPaymentDashboard = async () => (await axiosInstance.get<AdminPaymentDashboard>("/admin/payments/dashboard")).data;
export const listAdminPaymentProviders = async (params:PaymentAdminParams={}) => listPaymentResource<AdminPaymentProvider>("/admin/payment-providers",params);
export const listAdminPayouts = async (params:PaymentAdminParams={}) => listPaymentResource<AdminPayout>("/admin/payouts",params);
export const listAdminPaymentDisputes = async (params:PaymentAdminParams={}) => listPaymentResource<AdminPaymentDispute>("/admin/payment-disputes",params);
export const listAdminRiskEvents = async (params:PaymentAdminParams={}) => listPaymentResource<AdminRiskEvent>("/admin/payment-risk-events",params);
export const listAdminReconciliation = async (params:PaymentAdminParams={}) => listPaymentResource<AdminReconciliation>("/admin/reconciliation",params);
export const listAdminCurrencies = async (params:PaymentAdminParams={}) => listPaymentResource<AdminCurrency>("/admin/currencies",params);
export const listAdminFxRates = async (params:PaymentAdminParams={}) => listPaymentResource<AdminFxRate>("/admin/fx-rates",params);
export const listAdminCountries = async (params:PaymentAdminParams={}) => listPaymentResource<AdminCountry>("/admin/payment-countries",params);
export const listAdminFeesCommissions = async (params:PaymentAdminParams={}) => listPaymentResource<AdminFeeCommission>("/admin/fees-commissions",params);
export const refundAdminPayment = async (paymentId:string,reason:string) => (await axiosInstance.post<AdminPayment>(`/admin/payments/${paymentId}/refund`,{reason})).data;
export const listCoupons = async () => (await axiosInstance.get<Coupon[]>("/coupons")).data;
export const createCoupon = async (payload: Partial<Coupon>) => (await axiosInstance.post<Coupon>("/coupons", payload)).data;
export const updateCoupon = async (id: string, payload: Partial<Coupon>) => (await axiosInstance.put<Coupon>(`/coupons/${id}`, payload)).data;
export const listDiscounts = async () => (await axiosInstance.get<DiscountRule[]>("/promotions/discounts")).data;
export const createDiscount = async (payload: Partial<DiscountRule>) => (await axiosInstance.post<DiscountRule>("/promotions/discounts", payload)).data;
export const updateDiscount = async (id: string, payload: Partial<DiscountRule>) => (await axiosInstance.put<DiscountRule>(`/promotions/discounts/${id}`, payload)).data;
export const listPromotionCampaigns = async () => (await axiosInstance.get<PromotionCampaign[]>("/promotions/campaigns")).data;
export const createPromotionCampaign = async (payload: Partial<PromotionCampaign>) => (await axiosInstance.post<PromotionCampaign>("/promotions/campaigns", payload)).data;
export const updatePromotionCampaign = async (id: string, payload: Partial<PromotionCampaign>) => (await axiosInstance.put<PromotionCampaign>(`/promotions/campaigns/${id}`, payload)).data;
export const listCommunicationMessages = async (channel: CommunicationMessage["channel"]) => (await axiosInstance.get<CommunicationMessage[]>("/communications", { params: { channel } })).data;
export const createCommunicationMessage = async (payload: Partial<CommunicationMessage>) => (await axiosInstance.post<CommunicationMessage>("/communications", payload)).data;
export const sendCommunicationMessage = async (id: string) => (await axiosInstance.post<CommunicationMessage>(`/communications/${id}/send`)).data;
export const cancelCommunicationMessage = async (id: string) => (await axiosInstance.post<CommunicationMessage>(`/communications/${id}/cancel`)).data;
export const listAccessPermissions = async (): Promise<AccessPermission[]> =>
  (await axiosInstance.get<AccessPermission[]>("/admin/permissions")).data;

export const getRolePermissions = async (
  roleId: string,
): Promise<RolePermissionsResponse> =>
  (
    await axiosInstance.get<RolePermissionsResponse>(
      `/admin/roles/${roleId}/permissions`,
    )
  ).data;

export const getRoleUsers = async (
  roleId: string,
): Promise<{ role_id: string; role_name: string; user_ids: string[] }> =>
  (
    await axiosInstance.get<{
      role_id: string;
      role_name: string;
      user_ids: string[];
    }>(`/admin/roles/${roleId}/users`)
  ).data;

export const listAccessRoles = async (): Promise<AccessRole[]> => {
  const roles = (await axiosInstance.get<RoleApiResponse[]>("/admin/roles")).data;

  return Promise.all(
    roles.map(async (role) => {
      const [permissionResult, usersResult] = await Promise.all([
        getRolePermissions(role.id).catch(() => ({
          role_id: role.id,
          role_name: role.name,
          permissions: [],
        })),
        getRoleUsers(role.id).catch(() => ({
          role_id: role.id,
          role_name: role.name,
          user_ids: [],
        })),
      ]);

      return {
        ...role,
        permissions: permissionResult.permissions,
        users_count: usersResult.user_ids.length,
      };
    }),
  );
};

export const createAccessRole = async (
  payload: CreateRolePayload,
): Promise<RolePermissionsResponse> =>
  (
    await axiosInstance.post<RolePermissionsResponse>("/admin/roles", {
      ...payload,
      permission_codes: payload.permission_codes ?? [],
    })
  ).data;

export const updateAccessRole = async (
  roleId: string,
  payload: { name?: string; description?: string | null },
): Promise<RoleApiResponse> =>
  (
    await axiosInstance.patch<RoleApiResponse>(
      `/admin/roles/${roleId}`,
      payload,
    )
  ).data;

export const deleteAccessRole = async (roleId: string): Promise<void> => {
  await axiosInstance.delete(`/admin/roles/${roleId}`);
};

export const updateAccessRolePermissions = async (
  id: string,
  permission_codes: string[],
): Promise<RolePermissionsResponse> =>
  (
    await axiosInstance.put<RolePermissionsResponse>(
      `/admin/roles/${id}/permissions`,
      { permission_codes },
    )
  ).data;

export const getUserRoles = async (
  userId: string,
): Promise<UserRolesResponse> =>
  (
    await axiosInstance.get<UserRolesResponse>(
      `/admin/users/${userId}/roles`,
    )
  ).data;

export const getUserEffectivePermissions = async (
  userId: string,
): Promise<UserPermissionsResponse> =>
  (
    await axiosInstance.get<UserPermissionsResponse>(
      `/admin/users/${userId}/permissions`,
    )
  ).data;

export const updateUserRoles = async (
  id: string,
  roleIds: string[],
): Promise<UserRolesResponse> =>
  (
    await axiosInstance.put<UserRolesResponse>(
      `/admin/users/${id}/roles`,
      { role_ids: roleIds },
    )
  ).data;

export const listAccessUsers = async (
  params: ListAccessUsersParams = {},
): Promise<PaginatedAccessUsers> => {
  const res = await axiosInstance.get<PaginatedAccessUsers>(
    "/admin/access-users",
    { params },
  );
  return res.data;
};

export const createStaffAccount = async (
  payload: CreateStaffPayload,
): Promise<AdminStaffResponse> =>
  (
    await axiosInstance.post<AdminStaffResponse>(
      "/admin/staff",
      payload,
    )
  ).data;

export const updateAccessUser = async (
  id: string,
  payload: Partial<AdminUser>,
) =>
  (
    await axiosInstance.patch<AdminUser>(
      `/admin/users/${id}`,
      payload,
    )
  ).data;

// Retain the old session hooks for the current Active Sessions screen.
// If the backend does not expose this optional endpoint, the screen will
// display the normal API error without affecting Roles/Users/Permissions.
export const listAccessSessions = async () =>
  (
    await axiosInstance.get<AccessSession[]>(
      "/admin/active-sessions",
    )
  ).data;
export const revokeAccessSession = async (id: string) => (await axiosInstance.delete(`/admin/active-sessions/${id}`)).data;
export const getAdminReport = async (type: string, params: {date_from?:string;date_to?:string}={}) => (await axiosInstance.get<AdminReport>(`/admin/reports/${type}`,{params})).data;
export const listAuditLogs=async()=>(await axiosInstance.get<AuditLog[]>("/system/audit-logs")).data;
export const listSystemEvents=async()=>(await axiosInstance.get<SystemEvent[]>("/system/events")).data;
export const acknowledgeSystemEvent=async(id:string)=>(await axiosInstance.post<SystemEvent>(`/system/events/${id}/acknowledge`)).data;
export const listBackgroundJobs=async()=>(await axiosInstance.get<BackgroundJob[]>("/system/jobs")).data;
export const retryBackgroundJob=async(id:string)=>(await axiosInstance.post<BackgroundJob>(`/system/jobs/${id}/retry`)).data;
export const cancelBackgroundJob=async(id:string)=>(await axiosInstance.post<BackgroundJob>(`/system/jobs/${id}/cancel`)).data;
export const listApplicationSettings=async()=>(await axiosInstance.get<ApplicationSetting[]>("/system/settings")).data;
export const updateApplicationSetting=async(key:string,payload:Partial<ApplicationSetting>)=>(await axiosInstance.put<ApplicationSetting>(`/system/settings/${key}`,payload)).data;
export const getAccountProfile=async()=>(await axiosInstance.get<AccountProfile>("/users/me")).data;
export const updateAccountProfile=async(payload:Pick<AccountProfile,"first_name"|"last_name"|"phone">)=>(await axiosInstance.patch<AccountProfile>("/users/me",payload)).data;
export const changeAccountPassword=async(current_password:string,new_password:string)=>(await axiosInstance.post<{message:string}>("/auth/change-password",{current_password,new_password})).data;
export const listAccountSessions=async()=>(await axiosInstance.get<AccountSession[]>("/users/me/sessions")).data;
export const revokeAccountSession=async(id:string)=>(await axiosInstance.delete(`/users/me/sessions/${id}`)).data;

export const approveSeller = async (sellerId: string): Promise<AdminSeller> => {
  const res = await axiosInstance.post<AdminSeller>(`/admin/sellers/${sellerId}/approve`);
  return res.data;
};

export const rejectSeller = async (sellerId: string, reason: string): Promise<AdminSeller> => {
  const formData = new FormData();
  formData.append("reason", reason);
  const res = await axiosInstance.post<AdminSeller>(`/admin/sellers/${sellerId}/reject`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const listCatalogProducts = async (params:CatalogProductPageParams={}): Promise<PaginatedCatalogResponse<AdminProduct>> => (await axiosInstance.get<PaginatedCatalogResponse<AdminProduct>>("/admin/catalog/products",{params})).data;
export const listPendingProducts = async (): Promise<AdminProduct[]> => (await listCatalogProducts({page:1,page_size:100,status_filter:"pending_review"})).results;

export const getCatalogSummary = async (): Promise<AdminCatalogSummary> => (await axiosInstance.get<AdminCatalogSummary>("/admin/catalog/summary")).data;
export const getProductReviewDetail = async (productId:string): Promise<AdminProduct> => (await axiosInstance.get<AdminProduct>(`/admin/products/${productId}/review`)).data;

export const approveProduct = async (productId: string): Promise<AdminProduct> => {
  const res = await axiosInstance.post<AdminProduct>(`/admin/products/${productId}/approve`);
  return res.data;
};

export const rejectProduct = async (productId: string, reason: string): Promise<AdminProduct> => {
  const formData = new FormData();
  formData.append("reason", reason);
  const res = await axiosInstance.post<AdminProduct>(`/admin/products/${productId}/reject`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const listBusinessCategories = async (): Promise<BusinessCategory[]> => (await axiosInstance.get<BusinessCategory[]>("/admin/business-categories")).data;
export const listBusinessCategoriesPaginated = async (params:BusinessCategoryPageParams={}):Promise<PaginatedCatalogResponse<BusinessCategory>> => (await axiosInstance.get<PaginatedCatalogResponse<BusinessCategory>>("/admin/catalog/business-categories",{params})).data;
export const listProductCategories = async (): Promise<ProductCategory[]> => (await axiosInstance.get<ProductCategory[]>("/admin/product-categories")).data;
export const listProductCategoriesPaginated = async (params:CatalogPageParams={}):Promise<PaginatedCatalogResponse<ProductCategory>> => (await axiosInstance.get<PaginatedCatalogResponse<ProductCategory>>("/admin/catalog/product-categories",{params})).data;

export const createBusinessCategory = async (payload: CreateBusinessCategoryPayload): Promise<BusinessCategory> => {
  const res = await axiosInstance.post<BusinessCategory>("/admin/business-categories", payload);
  return res.data;
};

export const updateBusinessCategory = async (categoryId:string,payload:Partial<CreateBusinessCategoryPayload>):Promise<BusinessCategory> => (await axiosInstance.patch<BusinessCategory>(`/admin/business-categories/${categoryId}`,payload)).data;

export const deleteBusinessCategory = async (categoryId: string): Promise<{ message: string }> => {
  const res = await axiosInstance.delete<{ message: string }>(`/admin/business-categories/${categoryId}`);
  return res.data;
};

export const listBrands = async (): Promise<Brand[]> => (await axiosInstance.get<Brand[]>("/admin/brands")).data;
export const listBrandsPaginated = async (params:CatalogPageParams={}):Promise<PaginatedCatalogResponse<Brand>> => (await axiosInstance.get<PaginatedCatalogResponse<Brand>>("/admin/catalog/brands",{params})).data;

export const createBrand = async (payload: CreateBrandPayload): Promise<Brand> => {
  const res = await axiosInstance.post<Brand>("/admin/brands", payload);
  return res.data;
};

export const updateBrand = async (brandId:string,payload:Partial<CreateBrandPayload>):Promise<Brand> => (await axiosInstance.patch<Brand>(`/admin/brands/${brandId}`,payload)).data;

export const deleteBrand = async (brandId: string): Promise<{ message: string }> => {
  const res = await axiosInstance.delete<{ message: string }>(`/admin/brands/${brandId}`);
  return res.data;
};

export const createProductCategory = async (payload: CreateProductCategoryPayload): Promise<ProductCategory> => {
  const res = await axiosInstance.post<ProductCategory>("/admin/product-categories", payload);
  return res.data;
};

export const updateProductCategory = async (categoryId:string,payload:Partial<CreateProductCategoryPayload>):Promise<ProductCategory> => (await axiosInstance.patch<ProductCategory>(`/admin/product-categories/${categoryId}`,payload)).data;

export const deleteProductCategory = async (categoryId: string): Promise<{ message: string }> => {
  const res = await axiosInstance.delete<{ message: string }>(`/admin/product-categories/${categoryId}`);
  return res.data;
};

export const listProductReviews = async (params: { status?: string } = {}): Promise<ProductReview[]> => {
  const res = await axiosInstance.get<ProductReviewListResponse | ProductReview[]>("/admin/reviews", { params });
  const payload = res.data;
  if (Array.isArray(payload)) return payload;
  return Array.isArray(payload.results) ? payload.results : [];
};

export type FinanceSummary = {
  totalRevenue: number;
  totalCommissions: number;
  totalPayouts: number;
  pendingPayouts: number;
  failedPayments: number;
};

export type AdminTransaction = {
  id: string;
  reference: string;
  method: string;
  amount: number;
  currency: string;
  status: string;
  created_at: string;
};

export type Dispute = {
  id: string;
  order_number: string;
  reason: string;
  status: "open" | "under_review" | "resolved" | "closed";
  created_at: string;
};

export type AnalyticsOverview = {
  totalSales: number;
  totalOrders: number;
  averageOrderValue: number;
  topProducts: { id: string; name: string; sales: number }[];
  newCustomers: number;
  returningCustomers: number;
};

export const adminService = {
  listUsers,
  listAllSellers,
  listPendingSellers,
  getSellerDocuments,
  startSellerReview,
  getSellerDocumentViewUrl,
  listSellerProducts,
  listSellerOrders,
  listSellerPerformance,
  listAdminPayments,
  listAdminPaymentMethods,
  listAdminRefunds,
  listAdminFailedPayments,
  getAdminPaymentDashboard,
  listAdminPaymentProviders,
  listAdminPayouts,
  listAdminPaymentDisputes,
  listAdminRiskEvents,
  listAdminReconciliation,
  listAdminCurrencies,
  listAdminFxRates,
  listAdminCountries,
  listAdminFeesCommissions,
  refundAdminPayment,
  listCoupons,
  createCoupon,
  updateCoupon,
  listDiscounts,
  createDiscount,
  updateDiscount,
  listPromotionCampaigns,
  createPromotionCampaign,
  updatePromotionCampaign,
  listCommunicationMessages,
  createCommunicationMessage,
  sendCommunicationMessage,
  cancelCommunicationMessage,
  listAccessUsers,
  createStaffAccount,
  updateAccessUser,
  getUserRoles,
  getUserEffectivePermissions,
  updateUserRoles,
  listAccessRoles,
  createAccessRole,
  updateAccessRole,
  deleteAccessRole,
  getRolePermissions,
  getRoleUsers,
  listAccessPermissions,
  updateAccessRolePermissions,
  listAccessSessions,
  revokeAccessSession,
  getAdminReport,
  listAuditLogs,listSystemEvents,acknowledgeSystemEvent,listBackgroundJobs,retryBackgroundJob,cancelBackgroundJob,listApplicationSettings,updateApplicationSetting,
  getAccountProfile,updateAccountProfile,changeAccountPassword,listAccountSessions,revokeAccountSession,
  approveSeller,
  rejectSeller,
  listPendingProducts,
  listCatalogProducts,
  getCatalogSummary,
  getProductReviewDetail,
  approveProduct,
  rejectProduct,
  listBusinessCategories,
  listBusinessCategoriesPaginated,
  listProductCategories,
  listProductCategoriesPaginated,
  createBusinessCategory,
  updateBusinessCategory,
  deleteBusinessCategory,
  listBrands,
  listBrandsPaginated,
  createBrand,
  updateBrand,
  deleteBrand,
  createProductCategory,
  updateProductCategory,
  deleteProductCategory,
  listProductReviews,
};


//  ===
// ADMIN PHASE 1-3 CONFIGURATION
// Marketplace Settings, Logistics and Finance
//  ===

export type AdminMarketplaceSettings = {
  id?: string | null;
  escrow_release_hours: number | null;
  dispute_period_hours: number | null;
  cod_allowed: boolean | null;
  international_delivery_allowed: boolean | null;
  configured: boolean;
  updated_by_id?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
};

export type AdminCommissionRule = {
  id: string;
  name: string;
  scope: "global" | "category" | "seller" | "product";
  rule_type: "percentage" | "fixed";
  rate: number;
  seller_id?: string | null;
  category_id?: string | null;
  product_id?: string | null;
  priority: number;
  is_active: boolean;
  starts_at?: string | null;
  ends_at?: string | null;
  created_at: string;
};

export type AdminLogisticsCompany = {
  id: string;
  name: string;
  code: string;
  description?: string | null;
  contact_name?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  website_url?: string | null;
  scope: "local" | "international" | "both";
  status: "pending" | "active" | "suspended" | "inactive";
  supports_cod: boolean;
  supports_tracking: boolean;
  supports_webhooks: boolean;
  metadata_json?: Record<string, unknown>;
  created_at: string;
  updated_at?: string | null;
};

export type AdminLogisticsService = {
  id: string;
  logistics_company_id?: string | null;
  name: string;
  service_code?: string | null;
  description?: string | null;
  carrier_name?: string | null;
  scope: "local" | "international" | "both";
  supports_cod: boolean;
  supports_tracking: boolean;
  min_delivery_days: number;
  max_delivery_days: number;
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
};

export type AdminLogisticsZone = {
  id: string;
  name: string;
  country: string;
  scope: "local" | "international" | "both";
  regions: string[];
  cities: string[];
  is_active: boolean;
  created_at: string;
  updated_at?: string | null;
};

export type AdminLogisticsRate = {
  id: string;
  zone_id: string;
  method_id: string;
  rate_type: "flat" | "weight_based" | "free";
  currency: string;
  base_amount: number;
  amount_per_kg: number;
  free_shipping_threshold?: number | null;
  min_weight_kg?: number | null;
  max_weight_kg?: number | null;
  is_active: boolean;
  zone: AdminLogisticsZone;
  method: AdminLogisticsService;
  created_at: string;
  updated_at?: string | null;
};

export type AdminLogisticsIntegration = {
  id: string;
  logistics_company_id: string;
  api_base_url?: string | null;
  outbound_webhook_url?: string | null;
  auth_type: "none" | "api_key" | "bearer" | "basic" | "oauth2" | "custom";
  credential_reference?: string | null;
  webhook_secret_reference?: string | null;
  api_key_header?: string | null;
  extra_config?: Record<string, unknown>;
  is_active: boolean;
  last_tested_at?: string | null;
  last_test_success?: boolean | null;
  last_test_message?: string | null;
  created_at: string;
  updated_at?: string | null;
};

export type AdminFinanceSettings = {
  id: string;
  singleton_key: string;
  default_payment_provider_code?: string | null;
  settlement_currency: string;
  minimum_payout_amount: number;
  payout_fee_type: "fixed" | "percentage";
  payout_fee_value: number;
  payout_processing_days: number;
  auto_payout_enabled: boolean;
  escrow_enabled: boolean;
  auto_release_enabled: boolean;
  allow_partial_release: boolean;
  hold_commission_until_release: boolean;
  created_at: string;
  updated_at?: string | null;
};

export type AdminEscrowHold = {
  id: string;
  payment_id?: string | null;
  order_id: string;
  order_item_id?: string | null;
  seller_id?: string | null;
  currency: string;
  gross_amount: number;
  seller_amount: number;
  commission_amount: number;
  refunded_amount: number;
  released_amount: number;
  status: string;
  release_after?: string | null;
  released_at?: string | null;
  disputed_at?: string | null;
  refunded_at?: string | null;
  reference: string;
  note?: string | null;
  created_at: string;
  updated_at?: string | null;
};

export type AdminPaged<T> = {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: T[];
};

export const getMarketplaceSettings = async () =>
  (await axiosInstance.get<AdminMarketplaceSettings>("/admin/marketplace-settings")).data;

export const saveMarketplaceSettings = async (payload: {
  escrow_release_hours: number;
  dispute_period_hours: number;
  cod_allowed: boolean;
  international_delivery_allowed: boolean;
}) =>
  (await axiosInstance.put<AdminMarketplaceSettings>("/admin/marketplace-settings", payload)).data;

export const listCommissionRules = async (params: {
  page?: number; page_size?: number; search?: string; scope?: string; active?: boolean;
} = {}) =>
  (await axiosInstance.get<AdminPaged<AdminCommissionRule>>(
    "/admin/marketplace-settings/commission-rules",
    { params },
  )).data;

export const createCommissionRule = async (payload: {
  name: string;
  scope: string;
  rule_type: string;
  rate: number;
  seller_id?: string | null;
  category_id?: string | null;
  product_id?: string | null;
  priority?: number;
  is_active?: boolean;
}) =>
  (await axiosInstance.post<AdminCommissionRule>(
    "/admin/marketplace-settings/commission-rules",
    payload,
  )).data;

export const updateCommissionRule = async (
  id: string,
  payload: Partial<Pick<AdminCommissionRule, "name" | "rate" | "priority" | "is_active">>,
) =>
  (await axiosInstance.patch<AdminCommissionRule>(
    `/admin/marketplace-settings/commission-rules/${id}`,
    payload,
  )).data;

export const deleteCommissionRule = async (id: string) =>
  axiosInstance.delete(`/admin/marketplace-settings/commission-rules/${id}`);

export const listLogisticsCompanies = async (params: {
  page?: number; page_size?: number; search?: string; status?: string; scope?: string;
} = {}) =>
  (await axiosInstance.get<AdminPaged<AdminLogisticsCompany>>("/logistics/companies", { params })).data;

export const createLogisticsCompany = async (payload: Partial<AdminLogisticsCompany> & {
  name: string; code: string;
}) =>
  (await axiosInstance.post<AdminLogisticsCompany>("/logistics/companies", payload)).data;

export const updateLogisticsCompany = async (id: string, payload: Partial<AdminLogisticsCompany>) =>
  (await axiosInstance.patch<AdminLogisticsCompany>(`/logistics/companies/${id}`, payload)).data;

export const deactivateLogisticsCompany = async (id: string) =>
  axiosInstance.delete(`/logistics/companies/${id}`);

export const listLogisticsServices = async (params: {
  page?: number; page_size?: number; search?: string; company_id?: string; scope?: string; active?: boolean;
} = {}) =>
  (await axiosInstance.get<AdminPaged<AdminLogisticsService>>("/logistics/services", { params })).data;

export const createLogisticsService = async (payload: Partial<AdminLogisticsService> & { name: string }) =>
  (await axiosInstance.post<AdminLogisticsService>("/logistics/services", payload)).data;

export const updateLogisticsService = async (id: string, payload: Partial<AdminLogisticsService>) =>
  (await axiosInstance.patch<AdminLogisticsService>(`/logistics/services/${id}`, payload)).data;

export const deactivateLogisticsService = async (id: string) =>
  axiosInstance.delete(`/logistics/services/${id}`);

export const listLogisticsZones = async (params: {
  page?: number; page_size?: number; search?: string; scope?: string; active?: boolean;
} = {}) =>
  (await axiosInstance.get<AdminPaged<AdminLogisticsZone>>("/logistics/zones", { params })).data;

export const createLogisticsZone = async (payload: Partial<AdminLogisticsZone> & {
  name: string; country: string;
}) =>
  (await axiosInstance.post<AdminLogisticsZone>("/logistics/zones", payload)).data;

export const updateLogisticsZone = async (id: string, payload: Partial<AdminLogisticsZone>) =>
  (await axiosInstance.patch<AdminLogisticsZone>(`/logistics/zones/${id}`, payload)).data;

export const deactivateLogisticsZone = async (id: string) =>
  axiosInstance.delete(`/logistics/zones/${id}`);

export const listLogisticsRates = async (params: {
  page?: number; page_size?: number; search?: string; company_id?: string; active?: boolean;
} = {}) =>
  (await axiosInstance.get<AdminPaged<AdminLogisticsRate>>("/logistics/rates", { params })).data;

export const createLogisticsRate = async (payload: {
  zone_id: string; method_id: string; rate_type: string; currency: string;
  base_amount: number; amount_per_kg: number; free_shipping_threshold?: number | null;
  min_weight_kg?: number | null; max_weight_kg?: number | null; is_active: boolean;
}) =>
  (await axiosInstance.post<AdminLogisticsRate>("/logistics/rates", payload)).data;

export const deactivateLogisticsRate = async (id: string) =>
  axiosInstance.delete(`/logistics/rates/${id}`);

export const getLogisticsIntegration = async (companyId: string) =>
  (await axiosInstance.get<AdminLogisticsIntegration>(
    `/logistics/companies/${companyId}/integration`,
  )).data;

export const saveLogisticsIntegration = async (
  companyId: string,
  payload: {
    api_base_url?: string | null;
    outbound_webhook_url?: string | null;
    auth_type: string;
    credential_reference?: string | null;
    webhook_secret_reference?: string | null;
    api_key_header?: string | null;
    extra_config?: Record<string, unknown>;
    is_active: boolean;
  },
) =>
  (await axiosInstance.put<AdminLogisticsIntegration>(
    `/logistics/companies/${companyId}/integration`,
    payload,
  )).data;

export const getFinanceSettings = async () =>
  (await axiosInstance.get<AdminFinanceSettings>("/admin/finance/settings")).data;

export const updateFinanceSettings = async (payload: Partial<AdminFinanceSettings>) =>
  (await axiosInstance.patch<AdminFinanceSettings>("/admin/finance/settings", payload)).data;

export const listEscrowHolds = async (params: {
  page?: number; page_size?: number; search?: string; status?: string; currency?: string;
} = {}) =>
  (await axiosInstance.get<AdminPaged<AdminEscrowHold>>("/admin/finance/escrow-holds", { params })).data;

export const disputeEscrowHold = async (id: string, note?: string) =>
  (await axiosInstance.post<AdminEscrowHold>(
    `/admin/finance/escrow-holds/${id}/dispute`,
    { note: note || null },
  )).data;

export const releaseEscrowHold = async (id: string, amount?: number, note?: string) =>
  (await axiosInstance.post<AdminEscrowHold>(
    `/admin/finance/escrow-holds/${id}/release`,
    { amount: amount ?? null, note: note || null },
  )).data;
