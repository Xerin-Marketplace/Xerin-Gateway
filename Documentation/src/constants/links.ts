export const ROUTES = {
  home: "/",
  shop: "/shop-with-sidebar",
  productDetails: (id: string | number) => `/products/${id}`,
  cart: "/cart",
  wishlist: "/wishlist",
  checkout: "/checkout",
  signin: "/signin",
  adminLogin: "/admin/login",
  signup: "/signup",
  account: "/my-account",
  contact: "/contact",

  blogGrid: "/blogs/blog-grid",
  blogDetails: "/blogs/blog-details",
  blogGridWithSidebar: "/blogs/blog-grid-with-sidebar",
  blogDetailsWithSidebar: "/blogs/blog-details-with-sidebar",

  // Temporary routes until final pages are built
  trackOrder: "/my-account",
  returnsRefunds: "/contact",
  helpCenter: "/contact",
  sellerRegister: "/seller/register",

  // Future routes
  sellerDashboard: "/seller/dashboard",
  sellerKyc: "/seller/kyc",
  sellerProducts: "/seller/products",

  adminDashboard: "/admin/dashboard",
  adminSellerApprovals: "/admin/sellers/approvals",
  adminProductModeration: "/admin/products/moderation",
  adminDisputes: "/admin/disputes",
  adminFinance: "/admin/finance",
} as const;

export const APP_LINKS = {
  appStore: "#",
  googlePlay: "#",
} as const;

export const SOCIAL_LINKS = {
  facebook: "#",
  twitter: "#",
  instagram: "#",
  linkedin: "#",
} as const;

export const PAYMENT_LINKS = {
  visa: "#",
  paypal: "#",
  mastercard: "#",
  applePay: "#",
  googlePay: "#",
} as const;

export const CONTACT_LINKS = {
  supportEmail: "mailto:support@xerinmarket.com",
  supportPage: "/contact",
} as const;
