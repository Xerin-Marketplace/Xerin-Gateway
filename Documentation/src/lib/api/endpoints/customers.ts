import axiosInstance from "../client";
import type { AdminUser, Order } from "./admin";

export type Customer = AdminUser & {
  profile_photo?: string | null;
  gender?: string | null;
  date_of_birth?: string | null;
  last_login_at?: string | null;
};

export type CustomerSummary = {
  total_customers: number;
  active_customers: number;
  verified_customers: number;
  new_today: number;
  customers_with_orders: number;
  blocked_customers: number;
  vip_customers: number;
  lifetime_revenue: number;
};

export type CustomerStats = {
  orders: number;
  completed_orders: number;
  cancelled_orders: number;
  total_spent: number;
  average_order: number;
  reviews: number;
  wishlist_items: number;
};

export type CustomerAddress = {
  id: string;
  user_id?: string;
  customer_name?: string | null;
  label: string | null;
  address_type: string;
  country: string;
  region: string;
  city: string;
  street: string;
  postal_code: string | null;
  is_default: boolean;
  is_default_shipping: boolean;
  is_default_billing: boolean;
  created_at: string;
  updated_at: string | null;
};

export type CustomerReview = {
  id: string;
  product_id: string;
  user_id: string;
  rating: number;
  comment: string | null;
  status: string;
  admin_reply: string | null;
  created_at: string;
  updated_at: string | null;
  customer_name?: string | null;
  customer_email?: string | null;
  product_name?: string | null;
  seller_id?: string | null;
  seller_name?: string | null;
  order_id?: string | null;
  reported?: boolean;
  report_count?: number;
  product?: { name: string };
};

export type ListCustomerReviewsParams = {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  rating?: number;
  reported?: boolean;
  date_from?: string;
  date_to?: string;
};

export type PaginatedCustomerReviews = {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: CustomerReview[];
};

export type CustomerPayment = {
  id: string;
  order_id: string;
  method: string;
  transaction_reference: string | null;
  amount: number;
  currency: string;
  status: string;
  paid_at: string | null;
  created_at: string;
};

export type CustomerWishlist = {
  id: string;
  product_id: string;
  product_name: string | null;
  price: number | null;
  is_available: boolean;
  created_at: string;
};

export type CustomerLoginHistory = {
  id: string;
  device: string | null;
  browser: string | null;
  ip_address: string | null;
  country: string | null;
  login_at: string;
};

export type CustomerNote = {
  id: string;
  user_id: string;
  note: string;
  created_by_id: string | null;
  created_at: string;
  updated_at: string | null;
};

export type CustomerDetails = {
  customer: Customer;
  stats: CustomerStats;
  orders: Order[];
  addresses: CustomerAddress[];
  reviews: CustomerReview[];
  payments: CustomerPayment[];
  wishlist: CustomerWishlist[];
  login_history: CustomerLoginHistory[];
  notes: CustomerNote[];
};

export type SupportTicketParticipant = {
  id?: string | null;
  user_id?: string | null;
  name: string | null;
  email?: string | null;
  role: "customer" | "seller" | "logistics" | "admin" | string;
};

export type SupportTicketMessage = {
  id: string;
  sender_id?: string | null;
  sender_name?: string | null;
  sender_role?: string | null;
  message: string;
  visibility?: "all" | "internal" | string;
  created_at: string;
};

export type SupportTicket = {
  id: string;
  ticket_number: string;
  user_id: string;
  customer_name: string | null;
  customer_email?: string | null;
  subject: string;
  description: string | null;
  category?: string | null;
  channel?: string | null;
  priority: string;
  status: string;
  assigned_to_id: string | null;
  assigned_to_name: string | null;
  order_id?: string | null;
  seller_id?: string | null;
  seller_name?: string | null;
  shipment_id?: string | null;
  logistics_provider?: string | null;
  participants?: SupportTicketParticipant[];
  messages?: SupportTicketMessage[];
  resolution_note?: string | null;
  resolved_at?: string | null;
  closed_at?: string | null;
  created_at: string;
  updated_at: string | null;
};

export type ListSupportTicketsParams = {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  priority?: string;
  channel?: string;
  category?: string;
  participant_role?: string;
  date_from?: string;
  date_to?: string;
};

export type PaginatedSupportTickets = {
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
  results: SupportTicket[];
};

export type ListCustomersParams = {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  verification_status?: string;
  has_orders?: boolean;
  customer_type?: string;
  date_from?: string;
  date_to?: string;
};

export type PaginatedCustomers = {
  total: number;
  page: number;
  page_size: number;
  results: Customer[];
};

export const getCustomerSummary = async (): Promise<CustomerSummary> => {
  const res = await axiosInstance.get<CustomerSummary>("/admin/customers/summary");
  return res.data;
};

export const listCustomers = async (params: ListCustomersParams = {}): Promise<PaginatedCustomers> => {
  const res = await axiosInstance.get<PaginatedCustomers>("/admin/customers", { params });
  return res.data;
};

export const getCustomerDetails = async (customerId: string): Promise<CustomerDetails> => {
  const res = await axiosInstance.get<CustomerDetails>(`/admin/customers/${customerId}`);
  return res.data;
};

export const updateCustomerStatus = async (customerId: string, status: string): Promise<Customer> => {
  const res = await axiosInstance.patch<Customer>(`/admin/users/${customerId}`, { status });
  return res.data;
};

export const listAllAddresses = async (params: { search?: string } = {}): Promise<CustomerAddress[]> => {
  const res = await axiosInstance.get<CustomerAddress[]>("/admin/customer-addresses", { params });
  return res.data;
};

const pageFromArray = <T,>(
  rows: T[],
  page = 1,
  pageSize = 20,
): { total: number; page: number; page_size: number; total_pages: number; results: T[] } => {
  const total = rows.length;
  const totalPages = total === 0 ? 0 : Math.ceil(total / pageSize);
  const start = (page - 1) * pageSize;

  return {
    total,
    page,
    page_size: pageSize,
    total_pages: totalPages,
    results: rows.slice(start, start + pageSize),
  };
};

export const listCustomerReviews = async (
  params: ListCustomerReviewsParams = {},
): Promise<PaginatedCustomerReviews> => {
  const res = await axiosInstance.get<
    CustomerReview[] | PaginatedCustomerReviews
  >("/admin/reviews", { params });

  if (Array.isArray(res.data)) {
    let rows = res.data;

    const search = params.search?.trim().toLowerCase();
    if (search) {
      rows = rows.filter((review) =>
        [
          review.customer_name,
          review.customer_email,
          review.product_name,
          review.product?.name,
          review.comment,
          review.seller_name,
          review.id,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(search),
      );
    }

    if (params.status) {
      rows = rows.filter((review) => review.status === params.status);
    }

    if (params.rating) {
      rows = rows.filter((review) => review.rating === params.rating);
    }

    if (params.reported !== undefined) {
      rows = rows.filter(
        (review) =>
          Boolean(review.reported || review.status === "flagged") ===
          params.reported,
      );
    }

    return pageFromArray(
      rows,
      params.page ?? 1,
      params.page_size ?? 20,
    );
  }

  return res.data;
};

export const getCustomerReview = async (
  reviewId: string,
): Promise<CustomerReview> => {
  const res = await axiosInstance.get<CustomerReview>(
    `/admin/reviews/${reviewId}`,
  );
  return res.data;
};

export const moderateCustomerReview = async (
  reviewId: string,
  payload: {
    status?: string;
    admin_reply?: string | null;
  },
): Promise<CustomerReview> => {
  const res = await axiosInstance.patch<CustomerReview>(
    `/admin/reviews/${reviewId}`,
    payload,
  );
  return res.data;
};

export const listSupportTickets = async (
  params: ListSupportTicketsParams = {},
): Promise<PaginatedSupportTickets> => {
  const res = await axiosInstance.get<
    SupportTicket[] | PaginatedSupportTickets
  >("/admin/support-tickets", { params });

  if (Array.isArray(res.data)) {
    let rows = res.data;

    const search = params.search?.trim().toLowerCase();
    if (search) {
      rows = rows.filter((ticket) =>
        [
          ticket.ticket_number,
          ticket.customer_name,
          ticket.customer_email,
          ticket.subject,
          ticket.description,
          ticket.seller_name,
          ticket.logistics_provider,
          ticket.order_id,
        ]
          .filter(Boolean)
          .join(" ")
          .toLowerCase()
          .includes(search),
      );
    }

    if (params.status) {
      rows = rows.filter((ticket) => ticket.status === params.status);
    }

    if (params.priority) {
      rows = rows.filter((ticket) => ticket.priority === params.priority);
    }

    if (params.channel) {
      rows = rows.filter((ticket) => ticket.channel === params.channel);
    }

    return pageFromArray(
      rows,
      params.page ?? 1,
      params.page_size ?? 20,
    );
  }

  return res.data;
};

export const getSupportTicket = async (
  ticketId: string,
): Promise<SupportTicket> => {
  const res = await axiosInstance.get<SupportTicket>(
    `/admin/support-tickets/${ticketId}`,
  );
  return res.data;
};

export const updateSupportTicket = async (
  ticketId: string,
  payload: {
    status?: string;
    priority?: string;
    assigned_to_id?: string | null;
    resolution_note?: string | null;
  },
): Promise<SupportTicket> => {
  const res = await axiosInstance.patch<SupportTicket>(
    `/admin/support-tickets/${ticketId}`,
    payload,
  );
  return res.data;
};

export const addSupportTicketMessage = async (
  ticketId: string,
  payload: {
    message: string;
    visibility?: "all" | "internal";
  },
): Promise<SupportTicketMessage> => {
  const res = await axiosInstance.post<SupportTicketMessage>(
    `/admin/support-tickets/${ticketId}/messages`,
    payload,
  );
  return res.data;
};

export const getCustomer = getCustomerDetails;

export const getSummary = getCustomerSummary;

export const customersService = {
  getCustomerSummary,
  getSummary,
  listCustomers,
  getCustomerDetails,
  updateCustomerStatus,
  getCustomer,
  listAllAddresses,
  listCustomerReviews,
  getCustomerReview,
  moderateCustomerReview,
  listSupportTickets,
  getSupportTicket,
  updateSupportTicket,
  addSupportTicketMessage,
};
