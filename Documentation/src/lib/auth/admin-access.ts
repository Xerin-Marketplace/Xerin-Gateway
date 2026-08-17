import type { GuardUser } from "@/guards/permissions";

const BASIC_NON_STAFF_ROLES = new Set(["buyer", "customer", "seller"]);

export const normalizePermissionList = (
  user?: GuardUser | null,
): string[] => user?.permissions ?? [];

export const isSuperAdmin = (user?: GuardUser | null): boolean =>
  (user?.roles ?? []).includes("super_admin") ||
  user?.account_type === "super_admin";

export const isStaffUser = (user?: GuardUser | null): boolean => {
  if (!user) return false;

  if (
    user.account_type === "admin" ||
    user.account_type === "super_admin" ||
    isSuperAdmin(user)
  ) {
    return true;
  }

  const roles = (user.roles ?? []).map((role) => role.toLowerCase());

  // Any custom role that is not a normal marketplace customer/seller role
  // is treated as a staff role. Backend permission checks remain authoritative.
  return roles.some((role) => !BASIC_NON_STAFF_ROLES.has(role));
};

export const can = (
  user: GuardUser | null | undefined,
  permission: string,
): boolean => {
  if (isSuperAdmin(user)) return true;
  return normalizePermissionList(user).includes(permission);
};

export const canAny = (
  user: GuardUser | null | undefined,
  permissions: string[],
): boolean => {
  if (!permissions.length || isSuperAdmin(user)) return true;
  return permissions.some((permission) => can(user, permission));
};

export const canAll = (
  user: GuardUser | null | undefined,
  permissions: string[],
): boolean => {
  if (!permissions.length || isSuperAdmin(user)) return true;
  return permissions.every((permission) => can(user, permission));
};

export const ADMIN_SECTION_PERMISSIONS: Record<string, string[]> = {
  Dashboard: [
    "admin_dashboard:read",
    "admin_dashboard_operations:read",
    "admin_dashboard_finance:read",
    "admin_dashboard_security:read",
  ],
  Catalog: [
    "can_view_products",
    "manage_products",
    "can_view_product_categories",
    "can_view_brands",
    "admin_reviews:read",
    "admin_reviews:moderate",
  ],
  Orders: ["orders:read"],
  Inventory: ["inventory:manage"],
  Customers: [
    "view_all_users",
    "can_view_users",
    "manage_users",
    "manage_addresses",
    "admin_reviews:read",
  ],
  Sellers: [
    "can_view_sellers",
    "can_view_pending_sellers",
    "can_view_seller_documents",
    "can_approve_sellers",
    "can_reject_sellers",
  ],
  Payments: [
    "payments:dashboard", "payments:read", "payment_methods:read",
    "payment_providers:read", "refunds:read", "refunds:review",
    "refunds:process", "payment_disputes:read", "payouts:read",
    "payouts:approve", "fraud_risk:read", "reconciliation:read",
    "currencies:read", "countries:read", "commissions:read",
    "finance_reports:read", "payment_audit:read",
  ],
  Promotions: [
    "promotions:read",
    "promotions:create",
    "promotions:update",
    "promotions:delete",
    "campaigns:manage",
    "coupons:read",
    "coupons:write",
  ],
  Disputes: ["orders:read", "refunds:review"],
  Analytics: [
    "analytics:admin_read",
    "admin_dashboard_finance:read",
    "admin_dashboard_operations:read",
  ],
  "Reports & Analytics": [
    "analytics:admin_read",
    "admin_dashboard_finance:read",
    "admin_dashboard_operations:read",
  ],
  Communications: [
    "admin_notifications:read",
    "admin_notifications:manage",
    "notifications:manage",
  ],
  "User Management": [
    "view_all_users",
    "can_view_users",
    "can_create_users",
    "can_update_users",
    "can_delete_users",
    "can_assign_permissions",
  ],
  "System Management": [
    "audit_logs:read",
    "security_events:read",
    "admin_activity_logs:read",
    "admin_system_alerts:manage",
  ],
  "Marketplace Settings": [
    "marketplace_settings:read",
    "marketplace_settings:manage",
    "commissions:read",
    "commissions:manage",
  ],
  Logistics: [
    "logistics_companies:read",
    "logistics_companies:manage",
    "logistics_services:read",
    "logistics_services:manage",
    "logistics_zones:read",
    "logistics_zones:manage",
    "logistics_rates:read",
    "logistics_rates:manage",
    "logistics_integrations:read",
    "logistics_integrations:manage",
  ],
  "Finance Configuration": [
    "finance_settings:read",
    "finance_settings:manage",
    "escrow:read",
    "escrow:manage",
    "escrow:release",
    "payment_providers:read",
    "currencies:read",
  ],
  Account: [],
};

export const canAccessAdminSection = (
  user: GuardUser | null | undefined,
  section: string,
): boolean => {
  if (isSuperAdmin(user)) return true;
  if (section === "Account") return isStaffUser(user);

  return canAny(user, ADMIN_SECTION_PERMISSIONS[section] ?? []);
};

export const canAccessAdminDashboard = (
  user?: GuardUser | null,
): boolean =>
  isStaffUser(user) &&
  (
    isSuperAdmin(user) ||
    canAny(user, ADMIN_SECTION_PERMISSIONS.Dashboard) ||
    // Staff with a limited operational role still needs an admin shell
    // to reach the specific pages assigned to them.
    (user?.permissions?.length ?? 0) > 0
  );


export const ADMIN_ITEM_PERMISSIONS: Record<string, string[]> = {
  // Catalog
  Products: ["can_view_products", "manage_products"],
  Categories: ["can_view_product_categories"],
  Brands: ["can_view_brands"],
  "Product Reviews": ["admin_reviews:read", "admin_reviews:moderate"],

  // Orders / inventory
  "All Orders": ["orders:read"],
  "Pending Orders": ["orders:read"],
  "Processing Orders": ["orders:read"],
  "Completed Orders": ["orders:read"],
  "Cancelled Orders": ["orders:read"],
  "Order Tracking": ["orders:read"],
  "Stock Overview": ["inventory:manage"],
  Warehouses: ["inventory:manage"],
  "Stock Adjustments": ["inventory:manage"],
  "Low Stock Products": ["inventory:manage"],

  // Customers
  "All Customers": ["view_all_users", "can_view_users"],
  "Customer Addresses": ["manage_addresses", "can_view_users"],
  "Customer Reviews": ["admin_reviews:read"],
  "Customer Support": ["can_view_users"],

  // Sellers
  "All Sellers": ["can_view_sellers"],
  "Seller Applications": [
    "can_view_pending_sellers",
    "can_view_seller_documents",
    "can_approve_sellers",
    "can_reject_sellers",
  ],
  "Seller Products": ["can_view_products", "manage_products"],
  "Seller Orders": ["orders:read", "seller_orders:read"],
  "Seller Performance": ["analytics:admin_read", "can_view_sellers"],

  // Payments / Finance
  "Payments Dashboard": ["payments:dashboard", "payments:read"],
  Transactions: ["payments:read"],
  "Payment Methods": ["payment_methods:read", "payments:read"],
  "Payment Providers": ["payment_providers:read", "payments:read"],
  Refunds: ["refunds:read", "refunds:review", "refunds:process"],
  "Disputes & Chargebacks": ["payment_disputes:read", "refunds:review"],
  "Seller Payouts": ["payouts:read", "commissions:read"],
  "Pending Payouts": ["payouts:read", "payouts:approve"],
  "Failed Payments": ["payments:read"],
  "Fraud & Risk": ["fraud_risk:read", "payments:read"],
  Reconciliation: ["reconciliation:read", "payments:read"],
  "Currencies & FX": ["currencies:read", "payments:read"],
  Countries: ["countries:read", "payments:read"],
  "Fees & Commissions": ["commissions:read", "payments:read"],
  "Payment Audit Logs": ["payment_audit:read", "audit_logs:read"],

  // Promotions
  Coupons: ["coupons:read", "coupons:write"],
  Discounts: ["promotions:read", "promotions:update"],
  Campaigns: ["campaigns:manage", "promotions:read"],

  // Disputes
  "All Disputes": ["orders:read", "refunds:review"],
  "Open Disputes": ["orders:read", "refunds:review"],
  "Resolved Disputes": ["orders:read", "refunds:review"],

  // Analytics
  "Sales Reports": ["analytics:admin_read"],
  "Order Reports": ["analytics:admin_read", "orders:read"],
  "Product Reports": ["analytics:admin_read", "can_view_products"],
  "Inventory Reports": ["analytics:admin_read", "inventory:manage"],
  "Customer Reports": ["analytics:admin_read", "can_view_users"],
  "Payment Reports": ["finance_reports:read", "analytics:admin_read", "payments:read"],

  // Communications
  Notifications: ["admin_notifications:read", "admin_notifications:manage"],
  "Email Messages": ["admin_notifications:manage", "notifications:manage"],
  "SMS Messages": ["admin_notifications:manage", "notifications:manage"],

  // User management
  Users: ["view_all_users", "can_view_users", "can_update_users"],
  "Add New User": ["can_create_users", "can_assign_permissions"],
  Roles: ["can_assign_permissions"],
  Permissions: ["can_assign_permissions"],
  "Active Sessions": ["can_assign_permissions", "admin_dashboard_security:read"],

  // System
  "Audit Logs": ["audit_logs:read", "admin_activity_logs:read"],
  "System Events": ["security_events:read", "admin_system_alerts:manage"],
  "Background Jobs": ["admin_system_alerts:manage"],
  "Application Settings": ["admin_system_alerts:manage"],

  // Account items are always available inside the staff shell.
  Profile: [],
  Security: [],
  Logout: [],
};

export const canAccessAdminItem = (
  user: GuardUser | null | undefined,
  itemLabel: string,
): boolean => {
  if (isSuperAdmin(user)) return true;

  const required = ADMIN_ITEM_PERMISSIONS[itemLabel];

  // Unknown items inherit the group-level decision rather than silently
  // becoming inaccessible.
  if (!required) return true;

  if (required.length === 0) return isStaffUser(user);

  return canAny(user, required);
};
