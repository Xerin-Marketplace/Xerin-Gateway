export type DashboardModuleStatus = "ready" | "planned";

export type DashboardModuleAccess = {
  publicToAuthenticated?: boolean;
  sellerOnly?: boolean;
  roles?: string[];
  accountTypes?: string[];
  anyPermissions?: string[];
  permissions?: string[];
};

export type DashboardModule = {
  id: string;
  title: string;
  description: string;
  href?: string;
  group: "buyer" | "seller" | "admin" | "logistics" | "support";
  status: DashboardModuleStatus;
  access?: DashboardModuleAccess;
};

export const dashboardModules: DashboardModule[] = [
  {
    id: "buyer-account",
    title: "My Account",
    description: "Manage profile, addresses, account details, and buyer preferences.",
    href: "/my-account",
    group: "buyer",
    status: "ready",
    access: {
      publicToAuthenticated: true,
    },
  },
  {
    id: "buyer-orders",
    title: "Orders",
    description: "View order history, order status, and order tracking.",
    href: "/orders",
    group: "buyer",
    status: "ready",
    access: {
      anyPermissions: ["view_orders"],
    },
  },
  {
    id: "seller-products",
    title: "Seller Products",
    description: "Create, update, and manage seller product listings.",
    group: "seller",
    status: "planned",
    access: {
      sellerOnly: true,
      roles: ["seller"],
      accountTypes: ["seller"],
      anyPermissions: ["manage_products", "view_seller_products"],
    },
  },
  {
    id: "seller-orders",
    title: "Seller Orders",
    description: "Manage incoming seller orders and fulfillment workflow.",
    group: "seller",
    status: "planned",
    access: {
      sellerOnly: true,
      roles: ["seller"],
      accountTypes: ["seller"],
      anyPermissions: ["view_seller_orders", "manage_seller_orders"],
    },
  },
  {
    id: "admin-users",
    title: "Users",
    description: "Manage customers, sellers, admins, and support users.",
    group: "admin",
    status: "planned",
    access: {
      roles: ["admin", "super_admin"],
      accountTypes: ["admin", "super_admin"],
      anyPermissions: ["view_users", "manage_users"],
    },
  },
  {
    id: "admin-seller-approvals",
    title: "Seller Approvals",
    description: "Review seller onboarding, KYC, and approval status.",
    group: "admin",
    status: "planned",
    access: {
      roles: ["admin", "super_admin"],
      accountTypes: ["admin", "super_admin"],
      anyPermissions: ["approve_sellers", "review_sellers"],
    },
  },
  {
    id: "admin-finance",
    title: "Finance",
    description: "Review payments, payouts, commissions, and financial reports.",
    group: "admin",
    status: "planned",
    access: {
      roles: ["admin", "super_admin"],
      accountTypes: ["admin", "super_admin"],
      anyPermissions: ["view_finance", "manage_finance"],
    },
  },
  {
    id: "logistics-deliveries",
    title: "Deliveries",
    description: "View assigned deliveries, shipment status, and proof of delivery.",
    group: "logistics",
    status: "planned",
    access: {
      roles: ["logistics", "delivery", "logistics_partner"],
      accountTypes: ["logistics", "delivery", "logistics_partner"],
      anyPermissions: ["view_deliveries", "manage_deliveries"],
    },
  },
  {
    id: "support-tickets",
    title: "Support",
    description: "Handle support tickets, disputes, returns, and customer issues.",
    group: "support",
    status: "planned",
    access: {
      roles: ["support", "support_agent"],
      accountTypes: ["support", "support_agent"],
      anyPermissions: ["view_support_tickets", "manage_support_tickets"],
    },
  },
];
