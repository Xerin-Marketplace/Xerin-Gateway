export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL || "https://api.xerinmarketplace.com/api/v1";

export const API_DOCS_URL =
  process.env.NEXT_PUBLIC_API_DOCS_URL || `${API_BASE_URL}/docs`;

export const API_ENDPOINTS = {
  auth: {
    login: "/auth/login",
    register: "/auth/register",
    registerSeller: "/auth/register-seller",
    logout: "/auth/logout",
    refreshToken: "/auth/refresh-token",
    sendOtp: "/auth/send-otp",
    verifyOtp: "/auth/verify-otp",
    resendVerification: "/auth/resend-verification",
    verifyAccountOtp: "/auth/verify-account-otp",
    forgotPassword: "/auth/forgot-password",
    resetPassword: "/auth/reset-password",
    changePassword: "/auth/change-password",
  },

  users: {
    me: "/users/me",
    addresses: "/addresses",
    addressById: (id: string | number) => `/addresses/${id}`,
    setDefaultAddress: (id: string | number) => `/addresses/${id}/default`,
  },

  sellers: {
    register: "/sellers/register",
    businessCategories: "/admin/business-categories",
    me: "/sellers/me",
    profile: "/sellers/profile",
    kycDocuments: "/sellers/kyc-documents",
    kycStatus: "/sellers/kyc-status",
    payoutAccounts: "/sellers/payout-accounts",
    payoutAccountById: (id: string | number) => `/sellers/payout-accounts/${id}`,
  },

  products: {
    list: "/products",
    byId: (id: string | number) => `/products/${id}`,
    myProducts: "/products/my-products",
    categories: "/products/categories",
    brands: "/products/brands",
    images: (productId: string | number) => `/products/${productId}/images`,
    variants: (productId: string | number) => `/products/${productId}/variants`,
    tags: (productId: string | number) => `/products/${productId}/tags`,
  },
} as const;
