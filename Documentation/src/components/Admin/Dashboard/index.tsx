"use client";
import Image from "next/image";

import { ReactNode, useEffect, useState, useMemo } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { authStorage } from "@/lib/auth/storage";
import { canAccessAdminDashboard, canAccessAdminItem, canAccessAdminSection } from "@/lib/auth/admin-access";
import { ApiError } from "@/lib/api/client";
import {
  adminService,
  AdminProduct,
  AdminSeller,
} from "@/lib/api/endpoints/admin";
import AdminProducts from "@/components/Admin/Products";
import AdminCategories from "@/components/Admin/Catalog/Categories";
import AdminBrands from "@/components/Admin/Catalog/Brands";
import AdminReviews from "@/components/Admin/Catalog/Reviews";
import AdminOrdersDashboard from "@/components/Admin/Orders/Dashboard";
import AdminInventoryDashboard from "@/components/Admin/Inventory/Dashboard";
import AdminInventoryWarehouses from "@/components/Admin/Inventory/Warehouses";
import AdminInventoryAdjustments from "@/components/Admin/Inventory/Adjustments";
import AdminInventoryLowStock from "@/components/Admin/Inventory/LowStock";
import AdminProductInventoryDetails from "@/components/Admin/Inventory/ProductDetails";
import AdminWarehouseDetails from "@/components/Admin/Inventory/WarehouseDetails";
import AdminCustomers from "@/components/Admin/Customers/Customers";
import AdminCustomerDetails from "@/components/Admin/Customers/CustomerDetails";
import AdminCustomerAddresses from "@/components/Admin/Customers/Addresses";
import AdminCustomerReviews from "@/components/Admin/Customers/Reviews";
import AdminCustomerSupport from "@/components/Admin/Customers/Support";
import AdminOperationsWorkspace from "@/components/Admin/Operations";
import AdminSellers from "@/components/Admin/Sellers";
import SellerSubWorkspace from "@/components/Admin/Sellers/SubWorkspace";
import AdminPayments, { PaymentView } from "@/components/Admin/Payments";
import AdminPromotions, { PromotionView } from "@/components/Admin/Promotions";
import AdminCommunications, {
  CommunicationView,
} from "@/components/Admin/Communications";
import AdminUserManagement, {
  UserManagementView,
} from "@/components/Admin/UserManagement";
import AdminReports, { ReportView } from "@/components/Admin/Reports";
import AdminSystemManagement, {
  SystemView,
} from "@/components/Admin/SystemManagement";
import AdminAccount, { AccountView } from "@/components/Admin/Account";
import AdminFinance from "@/components/Admin/Finance";
import AdminAnalytics from "@/components/Admin/Analytics";
import AdminConfiguration, { AdminConfigurationView } from "@/components/Admin/Configuration";
import { useTheme } from "@/app/context/ThemeContext";
import { useAuth } from "@/hooks/useAuth";
import { formatCurrency } from "@/lib/formatCurrency";
import {
  BarChart3,
  Bell,
  BookOpen,
  Boxes,
  ChevronDown,
  CircleUserRound,
  CreditCard,
  Gauge,
  LogOut,
  Menu,
  Megaphone,
  Moon,
  Package,
  RefreshCw,
  Search,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Store,
  Truck,
  Globe2,
  Scale,
  LockKeyhole,
  WalletCards,
  Sun,
  Tag,
  Users,
  UserPlus,
  X,
  type LucideIcon,
} from "lucide-react";

type StoredUser = {
  first_name?: string;
  last_name?: string;
  email?: string;
  account_type?: string;
  roles?: string[];
  permissions?: string[];
};

type AdminTab =
  | "overview"
  | "users"
  | "sellers"
  | "products"
  | "categories"
  | "brands"
  | "reviews"
  | "orders"
  | "inventory"
  | "finance"
  | "analytics";

const tabs: Array<{ key: AdminTab; label: string; short: string }> = [
  { key: "overview", label: "Dashboard", short: "Overview" },
  { key: "users", label: "User Management", short: "Users" },
  { key: "sellers", label: "Seller Review", short: "Sellers" },
  { key: "products", label: "Products", short: "Products" },
  { key: "categories", label: "Categories", short: "Categories" },
  { key: "brands", label: "Brands", short: "Brands" },
  { key: "reviews", label: "Reviews", short: "Reviews" },
  { key: "orders", label: "Order & Dispute", short: "Orders" },
  { key: "inventory", label: "Inventory", short: "Inventory" },
  { key: "finance", label: "Financial Management", short: "Finance" },
  { key: "analytics", label: "Analytics Dashboard", short: "Analytics" },
];

type SidebarGroup = {
  title: string;
  key: AdminTab | string;
  items: { label: string; href: string }[];
  icon: LucideIcon;
};

const sidebarGroups: SidebarGroup[] = [
  {
    title: "Catalog",
    key: "products",
    icon: Package,
    items: [
      { label: "Products", href: "?tab=products&menu=catalog&item=products" },
      {
        label: "Categories",
        href: "?tab=categories&menu=catalog&item=categories",
      },
      { label: "Brands", href: "?tab=brands&menu=catalog&item=brands" },
      // {
      //   label: "Product Reviews",
      //   href: "?tab=reviews&menu=catalog&item=product-reviews",
      // },
    ],
  },
  {
    title: "Orders",
    key: "orders",
    icon: ShoppingBag,
    items: [
      {
        label: "All Orders",
        href: "?tab=orders&menu=orders&item=all-orders&orders_tab=all",
      },
      {
        label: "Pending Orders",
        href: "?tab=orders&menu=orders&item=pending-orders&orders_tab=pending",
      },
      {
        label: "Processing Orders",
        href: "?tab=orders&menu=orders&item=processing-orders&orders_tab=processing",
      },
      {
        label: "Completed Orders",
        href: "?tab=orders&menu=orders&item=completed-orders&orders_tab=completed",
      },
      {
        label: "Cancelled Orders",
        href: "?tab=orders&menu=orders&item=cancelled-orders&orders_tab=cancelled",
      },
      {
        label: "Order Tracking",
        href: "?tab=orders&menu=orders&item=order-tracking&orders_tab=tracking",
      },
    ],
  },
  {
    title: "Inventory",
    key: "inventory",
    icon: Boxes,
    items: [
      {
        label: "Stock Overview",
        href: "?tab=inventory&menu=inventory&item=stock-overview&inventory_tab=stock-overview",
      },
      {
        label: "Warehouses",
        href: "?tab=inventory&menu=inventory&item=warehouses&inventory_tab=warehouses",
      },
      {
        label: "Stock Adjustments",
        href: "?tab=inventory&menu=inventory&item=stock-adjustments&inventory_tab=stock-adjustments",
      },
      {
        label: "Low Stock Products",
        href: "?tab=inventory&menu=inventory&item=low-stock-products&inventory_tab=low-stock-products",
      },
    ],
  },
  {
    title: "Customers",
    key: "users",
    icon: Users,
    items: [
      {
        label: "Customer Reviews",
        href: "?tab=users&menu=customers&item=customer-reviews",
      },
      {
        label: "Customer Support",
        href: "?tab=users&menu=customers&item=customer-support",
      },
    ],
  },
  {
    title: "Sellers",
    key: "sellers",
    icon: Store,
    items: [
      {
        label: "All Sellers",
        href: "?tab=sellers&menu=sellers&item=all-sellers",
      },
      {
        label: "Seller Applications",
        href: "?tab=sellers&menu=sellers&item=seller-applications",
      },
      {
        label: "Seller Orders",
        href: "?tab=sellers&menu=sellers&item=seller-orders",
      },
      {
        label: "Seller Performance",
        href: "?tab=sellers&menu=sellers&item=seller-performance",
      },
    ],
  },
  {
    title: "Payments",
    key: "finance",
    icon: CreditCard,
    items: [
      { label: "Payments Dashboard", href: "?tab=finance&menu=payments&item=payments-dashboard" },
      { label: "Transactions", href: "?tab=finance&menu=payments&item=transactions" },
      { label: "Payment Methods", href: "?tab=finance&menu=payments&item=payment-methods" },
      { label: "Payment Providers", href: "?tab=finance&menu=payments&item=payment-providers" },
      { label: "Refunds", href: "?tab=finance&menu=payments&item=refunds" },
      { label: "Disputes & Chargebacks", href: "?tab=finance&menu=payments&item=disputes-chargebacks" },
      { label: "Seller Payouts", href: "?tab=finance&menu=payments&item=seller-payouts" },
      { label: "Pending Payouts", href: "?tab=finance&menu=payments&item=pending-payouts" },
      { label: "Failed Payments", href: "?tab=finance&menu=payments&item=failed-payments" },
      { label: "Fraud & Risk", href: "?tab=finance&menu=payments&item=fraud-risk" },
      { label: "Reconciliation", href: "?tab=finance&menu=payments&item=reconciliation" },
      { label: "Currencies & FX", href: "?tab=finance&menu=payments&item=currencies-fx" },
      { label: "Countries", href: "?tab=finance&menu=payments&item=countries" },
      { label: "Fees & Commissions", href: "?tab=finance&menu=payments&item=fees-commissions" },
      { label: "Payment Reports", href: "?tab=finance&menu=payments&item=payment-reports" },
      { label: "Payment Audit Logs", href: "?tab=finance&menu=payments&item=payment-audit-logs" },
    ],
  },
  {
    title: "Promotions",
    key: "products",
    icon: Tag,
    items: [
      { label: "Coupons", href: "?tab=products&menu=promotions&item=coupons" },
      {
        label: "Discounts",
        href: "?tab=products&menu=promotions&item=discounts",
      },
      {
        label: "Campaigns",
        href: "?tab=products&menu=promotions&item=campaigns",
      },
    ],
  },
  {
    title: "Communications",
    key: "overview",
    icon: Megaphone,
    items: [
      {
        label: "Notifications",
        href: "?tab=overview&menu=communications&item=notifications",
      },
      {
        label: "Email Messages",
        href: "?tab=overview&menu=communications&item=email-messages",
      },
      {
        label: "SMS Messages",
        href: "?tab=overview&menu=communications&item=sms-messages",
      },
    ],
  },
  {
    title: "User Management",
    key: "users",
    icon: ShieldCheck,
    items: [
      { label: "Users", href: "?tab=users&menu=user-management&item=users" },
      { label: "Add New User", href: "?tab=users&menu=user-management&item=add-new-user" },
      { label: "Roles", href: "?tab=users&menu=user-management&item=roles" },
      {
        label: "Permissions",
        href: "?tab=users&menu=user-management&item=permissions",
      },
      {
        label: "Active Sessions",
        href: "?tab=users&menu=user-management&item=active-sessions",
      },
    ],
  },
  {
    title: "Reports & Analytics",
    key: "analytics",
    icon: BarChart3,
    items: [
      {
        label: "Sales Reports",
        href: "?tab=analytics&menu=reports-analytics&item=sales-reports",
      },
      {
        label: "Order Reports",
        href: "?tab=analytics&menu=reports-analytics&item=order-reports",
      },
      {
        label: "Product Reports",
        href: "?tab=analytics&menu=reports-analytics&item=product-reports",
      },
      {
        label: "Inventory Reports",
        href: "?tab=analytics&menu=reports-analytics&item=inventory-reports",
      },
      {
        label: "Customer Reports",
        href: "?tab=analytics&menu=reports-analytics&item=customer-reports",
      },
      {
        label: "Payment Reports",
        href: "?tab=analytics&menu=reports-analytics&item=payment-reports",
      },
    ],
  },
  {
    title: "Marketplace Settings",
    key: "overview",
    icon: Settings,
    items: [
      { label: "Marketplace Rules", href: "?tab=overview&menu=marketplace-settings&item=marketplace-rules" },
      { label: "Commission Rules", href: "?tab=overview&menu=marketplace-settings&item=commission-rules" },
    ],
  },
  {
    title: "Logistics",
    key: "overview",
    icon: Truck,
    items: [
      { label: "Logistics Companies", href: "?tab=overview&menu=logistics&item=logistics-companies" },
      { label: "Delivery Services", href: "?tab=overview&menu=logistics&item=delivery-services" },
      { label: "Shipping Zones", href: "?tab=overview&menu=logistics&item=shipping-zones" },
      { label: "Shipping Rates", href: "?tab=overview&menu=logistics&item=shipping-rates" },
      { label: "API & Webhooks", href: "?tab=overview&menu=logistics&item=api-webhooks" },
    ],
  },
  {
    title: "Finance Configuration",
    key: "finance",
    icon: WalletCards,
    items: [
      { label: "Finance Settings", href: "?tab=finance&menu=finance-configuration&item=finance-settings" },
      { label: "Escrow Holds", href: "?tab=finance&menu=finance-configuration&item=escrow-holds" },
    ],
  },
  {
    title: "System Management",
    key: "overview",
    icon: Settings,
    items: [
      {
        label: "Audit Logs",
        href: "?tab=overview&menu=system-management&item=audit-logs",
      },
      {
        label: "System Events",
        href: "?tab=overview&menu=system-management&item=system-events",
      },
      {
        label: "Background Jobs",
        href: "?tab=overview&menu=system-management&item=background-jobs",
      },
      {
        label: "Application Settings",
        href: "?tab=overview&menu=system-management&item=application-settings",
      },
    ],
  },
  {
    title: "Account",
    key: "overview",
    icon: CircleUserRound,
    items: [
      { label: "Profile", href: "?tab=overview&menu=account&item=profile" },
      { label: "Security", href: "?tab=overview&menu=account&item=security" },
      { label: "Logout", href: "?tab=overview&menu=account&item=logout" },
    ],
  },
];

const tabIcon = (tab: AdminTab): ReactNode => {
  switch (tab) {
    case "overview":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M3 3h6v6H3V3Zm8 0h6v6h-6V3ZM3 11h6v6H3v-6Zm8 0h6v6h-6v-6Z" />
        </svg>
      );
    case "users":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M10 10a4 4 0 1 0 0-8 4 4 0 0 0 0 8Zm-7 8a7 7 0 1 1 14 0H3Z" />
        </svg>
      );
    case "sellers":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M2 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v2H2V5Zm0 4h16v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9Zm6 2v2h4v-2H8Z" />
        </svg>
      );
    case "products":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M10 1 2 5l8 4 8-4-8-4Zm-8 7 8 4 8-4v7l-8 4-8-4V8Z" />
        </svg>
      );
    case "categories":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M4 3h12a1 1 0 0 1 1 1v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V4a1 1 0 0 1 1-1Zm2 3v2h8V6H6Zm0 4v2h8v-2H6Z" />
        </svg>
      );
    case "brands":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M4 4h12v2H4V4Zm0 5h12v2H4V9Zm0 5h12v2H4v-2Z" />
        </svg>
      );
    case "reviews":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M10 2l2.5 5.5h5.5l-4.5 4 1.5 6-5-3.5L4.5 18l1.5-6-4.5-4h5.5L10 2Z" />
        </svg>
      );
    case "orders":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M4 3h12v2H4V3Zm0 4h12v10H4V7Zm3 2v2h6V9H7Zm0 4v2h4v-2H7Z" />
        </svg>
      );
    case "finance":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M10 1a7 7 0 1 0 7 7 7 7 0 0 0-7-7Zm1 11.59V14H9v-1.41a3 3 0 0 1-2-2.82h2a1 1 0 0 0 2 0 .5.5 0 0 0-.5-.5h-1a3 3 0 0 1-.5-5.92V3h2v1.35a3 3 0 0 1 1.85 2.65h-2A1 1 0 0 0 10 6a.5.5 0 0 0 .5.5h1a3 3 0 0 1-.5 5.09Z" />
        </svg>
      );
    case "analytics":
      return (
        <svg
          className="h-4 w-4"
          viewBox="0 0 20 20"
          fill="currentColor"
          aria-hidden="true"
        >
          <path d="M3 17h14v-2H3v2Zm2-4h2V8H5v5Zm4 0h2V4H9v9Zm4 0h2v-6h-2v6Z" />
        </svg>
      );
    default:
      return null;
  }
};

const canAccessAdmin = (user: StoredUser | null) =>
  canAccessAdminDashboard(user);

const normalizeSlug = (value: string) =>
  value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9\s-]/g, "")
    .replace(/\s+/g, "-")
    .replace(/-+/g, "-");

const getErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong. Please try again.";
};

export default function AdminDashboard() {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { theme, toggleTheme } = useTheme();
  const { logout } = useAuth();
  const adminUser = authStorage.getUser<StoredUser>();
  const visibleSidebarGroups = useMemo(
    () =>
      sidebarGroups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) =>
            canAccessAdminItem(adminUser, item.label),
          ),
        }))
        .filter(
          (group) =>
            canAccessAdminSection(adminUser, group.title) &&
            group.items.length > 0,
        ),
    [adminUser],
  );
  const adminName =
    [adminUser?.first_name, adminUser?.last_name].filter(Boolean).join(" ") ||
    "Administrator";
  const [activeTab, setActiveTab] = useState<AdminTab>("overview");
  const [isCheckingAccess, setIsCheckingAccess] = useState(true);
  const [isAuthorized, setIsAuthorized] = useState(false);

  const [isLoading, setIsLoading] = useState(false);
  const [totalUsers, setTotalUsers] = useState<number | null>(null);
  const [pendingSellers, setPendingSellers] = useState<AdminSeller[]>([]);
  const [pendingProducts, setPendingProducts] = useState<AdminProduct[]>([]);
  const [overviewError, setOverviewError] = useState("");

  const [surfaceSearch, setSurfaceSearch] = useState("");
  const [openSidebarGroup, setOpenSidebarGroup] = useState<string | null>(null);
  const [activeSidebarItem, setActiveSidebarItem] =
    useState<string>("Dashboard");
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const [isSidebarCollapsed, setIsSidebarCollapsed] = useState(false);
  const [isProfileOpen, setIsProfileOpen] = useState(false);

  const hiddenOverviewMenuGroups = [
    "Communications",
    "System Management",
    "Marketplace Settings",
    "Logistics",
    "Finance Configuration",
    "Account",
  ];
  const isOverviewHiddenByMenuSelection = hiddenOverviewMenuGroups.some(
    (group) =>
      activeSidebarItem === group || activeSidebarItem.startsWith(`${group}:`),
  );

  const activeMenuLabel =
    activeSidebarItem === "Dashboard"
      ? "Overview"
      : activeSidebarItem.includes(":")
        ? activeSidebarItem.split(":")[1]
        : activeSidebarItem;

  const activeMenuContextLabel =
    activeSidebarItem === "Dashboard"
      ? "Dashboard"
      : activeSidebarItem.includes(":")
        ? activeSidebarItem.replace(":", " - ")
        : activeSidebarItem;

  const legacyVisualGroup =
    activeSidebarItem === "Dashboard"
      ? "Dashboard"
      : (["Catalog", "Orders", "Inventory", "Customers", "Sellers"].find(
          (group) =>
            activeSidebarItem === group ||
            activeSidebarItem.startsWith(`${group}:`),
        ) ?? null);
  const legacyTheme: Record<
    string,
    { icon: LucideIcon; eyebrow: string; gradient: string }
  > = {
    Dashboard: {
      icon: Gauge,
      eyebrow: "Platform command center",
      gradient: "from-[#111827] via-[#263244] to-[#f47524]",
    },
    Catalog: {
      icon: Package,
      eyebrow: "Catalog operations",
      gradient: "from-[#111827] via-[#263244] to-[#f47524]",
    },
    Orders: {
      icon: ShoppingBag,
      eyebrow: "Order fulfillment",
      gradient: "from-[#111827] via-[#263244] to-[#f47524]",
    },
    Inventory: {
      icon: Boxes,
      eyebrow: "Stock control",
      gradient: "from-[#111827] via-[#263244] to-[#f47524]",
    },
    Customers: {
      icon: Users,
      eyebrow: "Customer operations",
      gradient: "from-[#111827] via-[#263244] to-[#f47524]",
    },
    Sellers: {
      icon: Store,
      eyebrow: "Marketplace partners",
      gradient: "from-[#111827] via-[#263244] to-[#f47524]",
    },
  };

  const dynamicSearchPlaceholder =
    activeTab === "orders" || activeTab === "inventory" || activeTab === "users"
      ? "Global search"
      : `Search in ${activeMenuContextLabel.toLowerCase()}...`;

  const isPaymentsWorkspace =
    activeSidebarItem === "Payments" ||
    activeSidebarItem.startsWith("Payments:");
  const paymentView: PaymentView =
    activeSidebarItem === "Payments:Payments Dashboard" ? "dashboard"
    : activeSidebarItem === "Payments:Payment Methods" ? "methods"
    : activeSidebarItem === "Payments:Payment Providers" ? "providers"
    : activeSidebarItem === "Payments:Refunds" ? "refunds"
    : activeSidebarItem === "Payments:Disputes & Chargebacks" ? "disputes"
    : activeSidebarItem === "Payments:Seller Payouts" ? "payouts"
    : activeSidebarItem === "Payments:Pending Payouts" ? "pending-payouts"
    : activeSidebarItem === "Payments:Failed Payments" ? "failed"
    : activeSidebarItem === "Payments:Fraud & Risk" ? "risk"
    : activeSidebarItem === "Payments:Reconciliation" ? "reconciliation"
    : activeSidebarItem === "Payments:Currencies & FX" ? "currencies"
    : activeSidebarItem === "Payments:Countries" ? "countries"
    : activeSidebarItem === "Payments:Fees & Commissions" ? "fees"
    : activeSidebarItem === "Payments:Payment Reports" ? "reports"
    : activeSidebarItem === "Payments:Payment Audit Logs" ? "audit"
    : "transactions";
  const isPromotionsWorkspace =
    activeSidebarItem === "Promotions" ||
    activeSidebarItem.startsWith("Promotions:");
  const promotionView: PromotionView =
    activeSidebarItem === "Promotions:Discounts"
      ? "discounts"
      : activeSidebarItem === "Promotions:Campaigns"
        ? "campaigns"
        : "coupons";
  const isCommunicationsWorkspace =
    activeSidebarItem === "Communications" ||
    activeSidebarItem.startsWith("Communications:");
  const communicationView: CommunicationView =
    activeSidebarItem === "Communications:Email Messages"
      ? "email"
      : activeSidebarItem === "Communications:SMS Messages"
        ? "sms"
        : "notification";
  const isUserManagementWorkspace =
    activeSidebarItem === "User Management" ||
    activeSidebarItem.startsWith("User Management:");
  const userManagementView: UserManagementView =
    activeSidebarItem === "User Management:Add New User"
      ? "create-user"
      : activeSidebarItem === "User Management:Roles"
      ? "roles"
      : activeSidebarItem === "User Management:Permissions"
        ? "permissions"
        : activeSidebarItem === "User Management:Active Sessions"
          ? "sessions"
          : "users";
  const isReportsWorkspace =
    activeSidebarItem === "Reports & Analytics" ||
    activeSidebarItem.startsWith("Reports & Analytics:");
  const reportView: ReportView =
    activeSidebarItem === "Reports & Analytics:Order Reports"
      ? "orders"
      : activeSidebarItem === "Reports & Analytics:Product Reports"
        ? "products"
        : activeSidebarItem === "Reports & Analytics:Inventory Reports"
          ? "inventory"
          : activeSidebarItem === "Reports & Analytics:Customer Reports"
            ? "customers"
            : activeSidebarItem === "Reports & Analytics:Payment Reports"
              ? "payments"
              : "sales";
  const isSystemWorkspace =
    activeSidebarItem === "System Management" ||
    activeSidebarItem.startsWith("System Management:");
  const systemView: SystemView =
    activeSidebarItem === "System Management:System Events"
      ? "events"
      : activeSidebarItem === "System Management:Background Jobs"
        ? "jobs"
        : activeSidebarItem === "System Management:Application Settings"
          ? "settings"
          : "audit";
  const isAccountWorkspace =
    activeSidebarItem === "Account" || activeSidebarItem.startsWith("Account:");
  const accountView: AccountView =
    activeSidebarItem === "Account:Security"
      ? "security"
      : activeSidebarItem === "Account:Logout"
        ? "logout"
        : "profile";
  const isConfigurationWorkspace =
    activeSidebarItem.startsWith("Marketplace Settings:") ||
    activeSidebarItem.startsWith("Logistics:") ||
    activeSidebarItem.startsWith("Finance Configuration:");

  const configurationView: AdminConfigurationView =
    activeSidebarItem === "Marketplace Settings:Commission Rules"
      ? "commissions"
      : activeSidebarItem === "Marketplace Settings:Marketplace Rules"
        ? "marketplace"
        : activeSidebarItem === "Logistics:Delivery Services"
          ? "logistics-services"
          : activeSidebarItem === "Logistics:Shipping Zones"
            ? "logistics-zones"
            : activeSidebarItem === "Logistics:Shipping Rates"
              ? "logistics-rates"
              : activeSidebarItem === "Logistics:API & Webhooks"
                ? "logistics-integration"
                : activeSidebarItem === "Logistics:Logistics Companies"
                  ? "logistics-companies"
                  : activeSidebarItem === "Finance Configuration:Escrow Holds"
                    ? "escrow"
                    : "finance-settings";

  const operationsWorkspace = null;
  const sellerView =
    activeSidebarItem === "Sellers:Seller Applications"
      ? "applications"
      : activeSidebarItem === "Sellers:Seller Products"
        ? "products"
        : activeSidebarItem === "Sellers:Seller Orders"
          ? "orders"
          : activeSidebarItem === "Sellers:Seller Performance"
            ? "performance"
            : "all";

  const [busyAction, setBusyAction] = useState<string | null>(null);

  const syncSidebarUrl = (tab: AdminTab, sidebarItem: string) => {
    const params = new URLSearchParams(searchParams.toString());

    params.set("tab", tab);

    if (sidebarItem === "Dashboard") {
      params.set("menu", "dashboard");
      params.delete("item");
    } else if (sidebarItem.includes(":")) {
      const [group, item] = sidebarItem.split(":");
      params.set("menu", normalizeSlug(group));
      params.set("item", normalizeSlug(item));
      if (tab === "inventory") {
        params.set("inventory_tab", normalizeSlug(item));
      }
    } else {
      params.set("menu", normalizeSlug(sidebarItem));
      params.delete("item");
    }

    const query = params.toString();
    router.replace(query ? `${pathname}?${query}` : pathname, {
      scroll: false,
    });
  };

  const resolveTab = (tabOrGroup: AdminTab | string): AdminTab => {
    const catalogMap: Record<string, AdminTab> = {
      "Catalog:Products": "products",
      "Catalog:Categories": "categories",
      "Catalog:Brands": "brands",
      "Catalog:Product Reviews": "reviews",
      "Orders:All Orders": "orders",
      "Orders:Pending Orders": "orders",
      "Orders:Processing Orders": "orders",
      "Orders:Completed Orders": "orders",
      "Orders:Cancelled Orders": "orders",
      "Orders:Order Tracking": "orders",
      "Inventory:Stock Overview": "inventory",
      "Inventory:Warehouses": "inventory",
      "Inventory:Stock Adjustments": "inventory",
      "Inventory:Low Stock Products": "inventory",
      "Customers:All Customers": "users",
      "Customers:Customer Addresses": "users",
      "Customers:Customer Reviews": "users",
      "Customers:Customer Support": "users",
      "User Management:Users": "users",
      "User Management:Add New User": "users",
      "User Management:Roles": "users",
      "User Management:Permissions": "users",
      "User Management:Active Sessions": "users",
    };

    return catalogMap[tabOrGroup] ?? (tabOrGroup as AdminTab);
  };

  const applySidebarSelection = (
    tabOrGroup: AdminTab | string,
    sidebarItem: string,
    sidebarGroup: string | null = null,
    shouldSyncUrl = true,
  ) => {
    const nextTab = resolveTab(tabOrGroup);

    setActiveTab(nextTab);
    setActiveSidebarItem(sidebarItem);
    setOpenSidebarGroup(sidebarGroup);
    setIsMobileSidebarOpen(false);

    if (shouldSyncUrl) {
      syncSidebarUrl(nextTab, sidebarItem);
    }
  };

  const loadOverviewData = async () => {
    setIsLoading(true);
    setOverviewError("");

    try {
      const [usersResponse, sellersResponse, productsResponse] =
        await Promise.all([
          adminService.listUsers({ page: 1, page_size: 8 }),
          adminService.listPendingSellers(),
          adminService.listPendingProducts(),
        ]);

      setTotalUsers(usersResponse.total);
      setPendingSellers(sellersResponse);
      setPendingProducts(productsResponse);
    } catch (error) {
      const message = getErrorMessage(error);
      setTotalUsers(null);
      setOverviewError(message);
      toast.error(message);
    } finally {
      setIsLoading(false);
    }
  };

  const refreshModerationQueues = async () => {
    try {
      const [sellersResponse, productsResponse] = await Promise.all([
        adminService.listPendingSellers(),
        adminService.listPendingProducts(),
      ]);

      setPendingSellers(sellersResponse);
      setPendingProducts(productsResponse);
    } catch (error) {
      toast.error(getErrorMessage(error));
    }
  };

  useEffect(() => {
    const token = authStorage.getAccessToken();
    const user = authStorage.getUser<StoredUser>();

    if (!token) {
      router.replace("/signin?redirect=/admin/dashboard");
      return;
    }

    if (!canAccessAdmin(user)) {
      setIsAuthorized(false);
      setIsCheckingAccess(false);
      return;
    }

    setIsAuthorized(true);
    setIsCheckingAccess(false);
    void loadOverviewData();
  }, [router]);

  useEffect(() => {
    if (isCheckingAccess || !isAuthorized) return;

    const menuParam = searchParams.get("menu");
    const itemParam = searchParams.get("item");

    if (!menuParam) {
      if (pathname.startsWith("/admin/inventory")) {
        applySidebarSelection("inventory", "Inventory", "Inventory", false);
      } else if (pathname.startsWith("/admin/customers")) {
        const customerItem = pathname.includes("/addresses")
          ? "Customer Addresses"
          : pathname.includes("/reviews")
            ? "Customer Reviews"
            : pathname.includes("/support")
              ? "Customer Support"
              : "All Customers";
        applySidebarSelection(
          "users",
          `Customers:${customerItem}`,
          "Customers",
          false,
        );
      }
      return;
    }

    if (menuParam === "dashboard") {
      applySidebarSelection("overview", "Dashboard", null, false);
      return;
    }

    const matchedGroup = visibleSidebarGroups.find(
      (group) => normalizeSlug(group.title) === menuParam,
    );

    if (!matchedGroup) return;

    if (itemParam) {
      const matchedItem = matchedGroup.items.find(
        (item) => normalizeSlug(item.label) === itemParam,
      );

      if (matchedItem) {
        const subItemKey = `${matchedGroup.title}:${matchedItem.label}`;
        const mappedTab = resolveTab(subItemKey);
        const nextTab = tabs.some((tab) => tab.key === mappedTab)
          ? mappedTab
          : resolveTab(matchedGroup.key);
        applySidebarSelection(nextTab, subItemKey, matchedGroup.title, false);
        return;
      }
    }

    applySidebarSelection(
      matchedGroup.key,
      matchedGroup.title,
      matchedGroup.title,
      false,
    );
  }, [isAuthorized, isCheckingAccess, searchParams]);

  const handleApproveSeller = async (sellerId: string) => {
    setBusyAction(`approve-seller-${sellerId}`);
    try {
      await adminService.approveSeller(sellerId);
      toast.success("Seller approved successfully.");
      await refreshModerationQueues();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyAction(null);
    }
  };

  const handleRejectSeller = async (sellerId: string) => {
    const reason = window.prompt("Andika sababu ya kumkataa seller:");

    if (!reason || !reason.trim()) {
      return;
    }

    setBusyAction(`reject-seller-${sellerId}`);
    try {
      await adminService.rejectSeller(sellerId, reason.trim());
      toast.success("Seller rejected.");
      await refreshModerationQueues();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyAction(null);
    }
  };

  const handleApproveProduct = async (productId: string) => {
    setBusyAction(`approve-product-${productId}`);
    try {
      await adminService.approveProduct(productId);
      toast.success("Product approved successfully.");
      await refreshModerationQueues();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyAction(null);
    }
  };

  const handleRejectProduct = async (productId: string) => {
    const reason = window.prompt("Andika sababu ya kukataa product:");

    if (!reason || !reason.trim()) {
      return;
    }

    setBusyAction(`reject-product-${productId}`);
    try {
      await adminService.rejectProduct(productId, reason.trim());
      toast.success("Product rejected.");
      await refreshModerationQueues();
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyAction(null);
    }
  };

  if (isCheckingAccess) {
    return (
      <section className="py-20">
        <div className="max-w-[1170px] mx-auto px-4 sm:px-8 xl:px-0">
          Loading admin panel...
        </div>
      </section>
    );
  }

  if (!isAuthorized) {
    return (
      <section className="py-20 bg-gray-1 dark:bg-darkTheme-secondary-bg min-h-screen">
        <div className="max-w-[760px] mx-auto px-4 sm:px-8 xl:px-0">
          <div className="rounded-xl border border-red-light-4 bg-white dark:bg-darkTheme-card p-7 text-center">
            <h2 className="text-2xl font-semibold text-dark dark:text-white mb-2">
              Access denied
            </h2>
            <p className="text-dark-4 dark:text-darkTheme-body-color">
              Hii page ni ya admin pekee. Hakikisha ume-login kwa admin account.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const LegacyIcon = legacyVisualGroup
    ? legacyTheme[legacyVisualGroup].icon
    : Gauge;

  return (
    <section className="admin-dashboard-shell min-h-screen overflow-x-hidden bg-[#f6f7f9] text-[#111827] antialiased dark:bg-[#111827] dark:text-white" style={{ fontFamily: 'Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif' }}>
      {isMobileSidebarOpen ? (
        <button
          aria-label="Close admin navigation"
          onClick={() => setIsMobileSidebarOpen(false)}
          className="fixed inset-0 z-40 bg-black/50 xl:hidden"
        />
      ) : null}
      <div className="w-full">
        <div
          className={`grid min-h-screen grid-cols-1 gap-0 ${isSidebarCollapsed ? "xl:grid-cols-[88px_minmax(0,1fr)]" : "xl:grid-cols-[270px_minmax(0,1fr)]"}`}
        >
          <aside
            className={`${isMobileSidebarOpen ? "translate-x-0" : "-translate-x-full"} fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col overflow-y-auto border-r border-[#e7ebf0] bg-white/85 text-[#111827] shadow-[8px_0_30px_rgba(15,23,42,0.035)] backdrop-blur-xl transition-all xl:sticky xl:top-0 xl:h-screen xl:w-auto xl:translate-x-0 dark:border-white/10 dark:bg-[#1f2937]/90 dark:text-white`}
          >
            <div className="flex h-[74px] shrink-0 items-center border-b border-[#e7ebf0] px-5 dark:border-white/10">
              <div className="flex items-center">
                {!isSidebarCollapsed && (
                  <div>
                    <Image
                      src="/images/logo/logo.png"
                      alt="Xerin Marketplace logo"
                      width={150}
                      height={46}
                      className="h-10 w-auto object-contain"
                      priority
                    />
                    <h2 className="mt-1 text-xs text-[#94a3b8] dark:text-white/50">
                      Admin Center
                    </h2>
                  </div>
                )}
                <button
                  onClick={() => setIsMobileSidebarOpen(false)}
                  className="ml-auto text-gray-400 hover:text-gray-600 xl:hidden"
                >
                  <X size={20} />
                </button>
              </div>
            </div>

            <div className="mt-3">
              <button
                type="button"
                onClick={() => {
                  applySidebarSelection("overview", "Dashboard", null);
                }}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-left text-[13px] transition ${
                  activeSidebarItem === "Dashboard"
                    ? "bg-[#f7941d] font-semibold text-white shadow-[0_6px_18px_rgba(247,148,29,0.18)]"
                    : "text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white"
                }`}
              >
                <span className="inline-flex items-center gap-3 text-[13px]">
                  <span className="inline-flex h-5 w-5 items-center justify-center shrink-0">
                    {tabIcon("overview")}
                  </span>
                  {!isSidebarCollapsed && "Dashboard"}
                </span>
              </button>
            </div>

            <nav className="mt-4 flex-1 space-y-3 overflow-y-auto px-1 pb-3">
              {visibleSidebarGroups.map((group) => {
                const GroupIcon = group.icon;
                const isOpen =
                  openSidebarGroup === group.title ||
                  group.items.some((item) => {
                    if (item.href.startsWith("/admin/")) {
                      return pathname.startsWith(item.href.split("?")[0]);
                    }
                    const params = new URLSearchParams(
                      item.href.replace("?", ""),
                    );
                    const menu = params.get("menu");
                    const itemParam = params.get("item");
                    if (!menu) return false;
                    const currentMenu = searchParams.get("menu");
                    const currentItem = searchParams.get("item");
                    return (
                      currentMenu === menu &&
                      (!itemParam || currentItem === itemParam)
                    );
                  });
                const isGroupActive =
                  activeSidebarItem === group.title ||
                  activeSidebarItem.startsWith(`${group.title}:`);

                return (
                  <div key={group.title} className="px-1">
                    <button
                      type="button"
                      title={isSidebarCollapsed ? group.title : undefined}
                      onClick={() => {
                        if (isSidebarCollapsed) {
                          setIsSidebarCollapsed(false);
                          setOpenSidebarGroup(group.title);
                          return;
                        }
                        const nextOpenGroup =
                          openSidebarGroup === group.title ? null : group.title;
                        setOpenSidebarGroup(nextOpenGroup);
                      }}
                      className={`w-full rounded-xl px-3 py-2.5 text-left text-[13px] transition ${
                        isGroupActive || isOpen
                          ? "bg-slate-100 font-semibold text-[#111827] dark:bg-white/[0.08] dark:text-white"
                          : "text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white"
                      }`}
                    >
                      <span className="flex items-center justify-between gap-2">
                        <span className="inline-flex items-center gap-2.5">
                          <span
                            className="inline-flex h-5 w-5 items-center justify-center text-base leading-none shrink-0"
                            aria-hidden="true"
                          >
                            <GroupIcon size={18} />
                          </span>
                          {!isSidebarCollapsed && <span>{group.title}</span>}
                        </span>
                        {!isSidebarCollapsed && (
                          <svg
                            className={`h-4 w-4 transition-transform ${isOpen ? "rotate-180" : "rotate-0"}`}
                            viewBox="0 0 20 20"
                            fill="currentColor"
                            aria-hidden="true"
                          >
                            <path d="M5.23 7.21a.75.75 0 0 1 1.06.02L10 11.17l3.71-3.94a.75.75 0 0 1 1.1 1.02l-4.25 4.5a.75.75 0 0 1-1.1 0l-4.25-4.5a.75.75 0 0 1 .02-1.06Z" />
                          </svg>
                        )}
                      </span>
                    </button>

                    {isOpen && !isSidebarCollapsed ? (
                      <div className="mt-1 space-y-1 border-l border-[#e7ebf0] pl-3 dark:border-white/10">
                        {group.items.map((item) => {
                          const subItemKey = `${group.title}:${item.label}`;
                          const isSelected = activeSidebarItem === subItemKey;
                          const isExternal = item.href.startsWith("/admin/");

                          return isExternal ? (
                            <Link
                              key={item.label}
                              href={item.href}
                              className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-[13px] transition ${
                                pathname.startsWith(item.href.split("?")[0])
                                  ? "bg-[#f7941d] font-semibold text-white shadow-[0_5px_14px_rgba(247,148,29,0.15)]"
                                  : "text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/60 dark:hover:bg-white/[0.08] dark:hover:text-white"
                              }`}
                            >
                              <span className="inline-flex items-center gap-2">
                                <span
                                  className={`h-1.5 w-1.5 rounded-full ${pathname.startsWith(item.href.split("?")[0]) ? "bg-white" : "bg-slate-300 dark:bg-white/30"}`}
                                />
                                <span>{item.label}</span>
                              </span>
                            </Link>
                          ) : (
                            <button
                              key={item.label}
                              type="button"
                              onClick={() => {
                                if (group.title === "Catalog") {
                                  applySidebarSelection(
                                    subItemKey,
                                    subItemKey,
                                    group.title,
                                  );
                                  return;
                                }
                                if (group.title === "Orders") {
                                  const orderTabMap: Record<string, string> = {
                                    "All Orders": "all",
                                    "Pending Orders": "pending",
                                    "Processing Orders": "processing",
                                    "Completed Orders": "completed",
                                    "Cancelled Orders": "cancelled",
                                    "Order Tracking": "tracking",
                                  };
                                  const ordersTab =
                                    orderTabMap[item.label] ?? "all";
                                  const itemSlug = normalizeSlug(item.label);
                                  setIsMobileSidebarOpen(false);
                                  router.push(
                                    `/admin/dashboard?tab=orders&menu=orders&item=${itemSlug}&orders_tab=${ordersTab}`,
                                  );
                                  return;
                                }
                                applySidebarSelection(
                                  group.key,
                                  subItemKey,
                                  group.title,
                                );
                              }}
                              className={`flex w-full items-center gap-2.5 rounded-xl px-3 py-2 text-left text-[13px] transition ${
                                isSelected
                                  ? "bg-[#f7941d] font-semibold text-white shadow-[0_5px_14px_rgba(247,148,29,0.15)]"
                                  : "text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/60 dark:hover:bg-white/[0.08] dark:hover:text-white"
                              }`}
                            >
                              <span className="inline-flex items-center gap-2">
                                <span
                                  className={`h-1.5 w-1.5 rounded-full ${isSelected ? "bg-white" : "bg-slate-300 dark:bg-white/30"}`}
                                />
                                <span>{item.label}</span>
                              </span>
                            </button>
                          );
                        })}
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </nav>

            {!isSidebarCollapsed && (
              <div className="mt-6 rounded-2xl border border-[#e7ebf0] bg-white/65 p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.06]">
                <p className="text-[10px] font-semibold uppercase tracking-[.16em] text-[#94a3b8]">Quick Moderation Queue</p>
                <div className="mt-3 space-y-1.5 text-sm text-[#475467] dark:text-white/70">
                  <p>
                    Sellers:{" "}
                    <span className="font-semibold text-[#111827] dark:text-white">
                      {pendingSellers.length}
                    </span>
                  </p>
                  <p>
                    Products:{" "}
                    <span className="font-semibold text-[#111827] dark:text-white">
                      {pendingProducts.length}
                    </span>
                  </p>
                </div>
              </div>
            )}

            <button
              type="button"
              onClick={() => setIsSidebarCollapsed((v) => !v)}
              className="mt-4 hidden w-full rounded-xl border border-[#e7ebf0] px-3 py-2.5 text-sm font-medium text-[#64748b] transition hover:bg-slate-50 hover:text-[#111827] dark:border-white/10 dark:text-white/65 dark:hover:bg-white/10 dark:hover:text-white xl:block"
            >
              {isSidebarCollapsed ? "Expand" : "Collapse sidebar"}
            </button>
          </aside>

          <main className="min-w-0 space-y-5 px-4 pb-10 pt-4 sm:px-5 lg:px-6 xl:px-7">
            <header className="sticky top-0 z-30 -mx-4 border-b border-[#e7ebf0]/90 bg-white/90 px-4 py-3 backdrop-blur-xl dark:border-white/10 dark:bg-[#1f2937]/90 sm:-mx-5 sm:px-5 lg:-mx-6 lg:px-6 xl:-mx-7 xl:px-7">
              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={() => setIsMobileSidebarOpen(true)}
                  className="rounded-xl p-2 hover:bg-slate-100 dark:hover:bg-white/10 xl:hidden"
                >
                  <Menu size={21} />
                </button>
                <div className="min-w-0">
                  <p className="hidden text-xs text-[#64748b] sm:block">
                    Admin Center / {activeMenuContextLabel}
                  </p>
                  <h2 className="truncate text-base font-bold">
                    {activeMenuLabel}
                  </h2>
                </div>
                <div className="ml-auto flex items-center gap-1 sm:gap-2">
                  <button
                    type="button"
                    onClick={() =>
                      applySidebarSelection(
                        "overview",
                        "System Management:System Events",
                        "System Management",
                      )
                    }
                    aria-label="System notifications"
                    className="relative rounded-xl p-2.5 hover:bg-slate-100 dark:hover:bg-white/10"
                  >
                    <Bell size={19} />
                    {pendingSellers.length + pendingProducts.length > 0 && (
                      <span className="absolute right-2 top-2 h-2 w-2 rounded-full bg-[#f7941d]" />
                    )}
                  </button>
                  <button
                    type="button"
                    onClick={toggleTheme}
                    aria-label="Toggle theme"
                    className="rounded-xl p-2.5 hover:bg-slate-100 dark:hover:bg-white/10"
                  >
                    {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
                  </button>
                  <div className="relative">
                    <button
                      type="button"
                      onClick={() => setIsProfileOpen((v) => !v)}
                      className="flex items-center gap-2 rounded-xl border border-[#e2e8f0] px-2 py-1.5 dark:border-white/10"
                    >
                      <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f7941d] text-sm font-bold text-white">
                        {adminName[0]}
                      </span>
                      <span className="hidden max-w-32 truncate text-sm font-semibold sm:block">
                        {adminName}
                      </span>
                      <ChevronDown size={15} />
                    </button>
                    {isProfileOpen && (
                      <div className="absolute right-0 mt-2 w-64 rounded-2xl border border-[#e2e8f0] bg-white p-2 shadow-xl dark:border-white/10 dark:bg-[#2d3134]">
                        <div className="border-b border-[#e2e8f0] p-3 dark:border-white/10">
                          <p className="font-semibold">{adminName}</p>
                          <p className="truncate text-xs text-[#64748b]">
                            {adminUser?.email}
                          </p>
                          <p className="mt-1 text-xs font-semibold text-green-600">
                            Administrator
                          </p>
                        </div>
                        <button
                          onClick={() => {
                            applySidebarSelection(
                              "overview",
                              "Account:Profile",
                              "Account",
                            );
                            setIsProfileOpen(false);
                          }}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-white/10"
                        >
                          <CircleUserRound size={16} />
                          Profile
                        </button>
                        <button
                          onClick={() => {
                            applySidebarSelection(
                              "overview",
                              "Account:Security",
                              "Account",
                            );
                            setIsProfileOpen(false);
                          }}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-white/10"
                        >
                          <ShieldCheck size={16} />
                          Security
                        </button>
                        <button
                          onClick={() => void logout()}
                          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-red-600 hover:bg-red-50"
                        >
                          <LogOut size={16} />
                          Logout
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </header>
            <div className="border-b border-gray-200 bg-transparent px-0 pb-4 pt-1 dark:border-white/10">
              <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
                <div className="flex min-w-0 items-center gap-4">
                  {legacyVisualGroup ? (
                    <span
                      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-[#fff1e6] text-[#f7941d]"
                      aria-hidden="true"
                    >
                      <LegacyIcon size={22} />
                    </span>
                  ) : null}
                  <div className="min-w-0">
                    {legacyVisualGroup ? (
                      <p className="text-[11px] font-semibold uppercase tracking-[.16em] text-gray-400">
                        {legacyTheme[legacyVisualGroup].eyebrow}
                      </p>
                    ) : null}
                    <h1 className="mt-0.5 truncate text-xl font-bold tracking-[-0.02em] text-[#111827] sm:text-2xl dark:text-white">
                      {isPaymentsWorkspace
                        ? activeMenuLabel
                        : activeTab === "orders"
                          ? "Order Management"
                          : activeTab === "inventory"
                            ? "Inventory Overview"
                            : activeTab === "users" &&
                                activeSidebarItem !== "Dashboard"
                              ? "Customer Management"
                              : "Dashboard Overview"}
                    </h1>
                    <p className="mt-1 truncate text-sm text-gray-500">
                      {isPaymentsWorkspace
                        ? `Admin / Payments / ${activeMenuLabel}`
                        : activeTab === "orders"
                          ? `Admin / Orders / ${activeMenuLabel}`
                          : activeTab === "inventory"
                            ? `Admin / Inventory / ${activeMenuLabel}`
                            : activeTab === "users" &&
                                activeSidebarItem !== "Dashboard"
                              ? `Manage customer accounts, addresses, orders and engagement`
                              : `Tab: ${activeMenuLabel}`}
                    </p>
                  </div>
                </div>

                <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                  <input
                    value={surfaceSearch}
                    onChange={(event) => setSurfaceSearch(event.target.value)}
                    placeholder={dynamicSearchPlaceholder}
                    className="w-full rounded-xl border border-[#e7ebf0] bg-white/80 px-4 py-2.5 text-sm text-[#344054] shadow-sm outline-none transition placeholder:text-[#98a2b3] focus:border-[#f7941d] focus:ring-2 focus:ring-[#f7941d]/10 dark:border-white/10 dark:bg-white/[0.05] dark:text-white dark:placeholder:text-white/40 sm:w-[250px]"
                  />
                  <button
                    type="button"
                    onClick={loadOverviewData}
                    className="inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl bg-[#f7941d] px-4 py-2.5 text-sm font-semibold text-white shadow-sm transition hover:bg-[#e6810f]"
                  >
                    <RefreshCw size={15} />
                    Refresh Data
                  </button>
                </div>
              </div>
            </div>

            {(activeTab === "overview" ||
              activeTab === "users" ||
              activeTab === "sellers" ||
              activeTab === "products" ||
              activeTab === "categories" ||
              activeTab === "brands" ||
              activeTab === "reviews" ||
              activeTab === "orders" ||
              activeTab === "inventory" ||
              activeTab === "finance" ||
              activeTab === "analytics") &&
            isLoading ? (
              <div className="rounded-2xl border border-gray-200 bg-white p-8 text-center text-gray-600 shadow-sm">
                Loading dashboard data...
              </div>
            ) : null}

            {activeTab === "overview" &&
            !isLoading &&
            !isOverviewHiddenByMenuSelection ? (
              <>
                {overviewError ? (
                  <div className="flex items-center justify-between gap-3 rounded-xl border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
                    <span>Unable to load dashboard statistics: {overviewError}</span>
                    <button
                      onClick={() => void loadOverviewData()}
                      className="shrink-0 whitespace-nowrap font-semibold text-red-700 hover:text-red-800"
                    >
                      Retry
                    </button>
                  </div>
                ) : null}

                <div className="grid gap-4 2xl:grid-cols-[minmax(0,1.55fr)_minmax(330px,.75fr)]">
                  <section className="overflow-hidden rounded-xl border border-[#e2e7ee] bg-white shadow-[0_1px_2px_rgba(15,23,42,.03)] dark:border-white/10 dark:bg-[#1f2937]">
                    <div className="border-b border-[#edf0f4] px-5 py-5 dark:border-white/10 sm:px-6">
                      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                        <div>
                          <p className="text-[11px] font-bold uppercase tracking-[.16em] text-[#f47524]">
                            Ecommerce operations
                          </p>
                          <h2 className="mt-1 text-2xl font-bold tracking-[-.02em] text-[#101828] dark:text-white sm:text-[28px]">
                            Ecommerce Dashboard
                          </h2>
                          <p className="mt-1 text-sm text-[#667085] dark:text-gray-300">
                            Here&apos;s what is happening across your marketplace right now.
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={loadOverviewData}
                          className="inline-flex h-10 items-center justify-center gap-2 self-start rounded-lg border border-[#dfe4eb] bg-white px-3.5 text-sm font-semibold text-[#344054] transition hover:border-[#f47524] hover:text-[#f47524] dark:border-white/10 dark:bg-white/5 dark:text-white"
                        >
                          <RefreshCw size={15} />
                          Refresh
                        </button>
                      </div>

                      <div className="mt-6 grid gap-3 sm:grid-cols-3">
                        {[
                          {
                            label: "Registered users",
                            value: totalUsers ?? "—",
                            hint: "Platform accounts",
                            icon: Users,
                            badge: "bg-[#eef4ff] text-[#2f6bff]",
                          },
                          {
                            label: "Seller reviews",
                            value: pendingSellers.length,
                            hint: "Awaiting approval",
                            icon: Store,
                            badge: "bg-[#fff4e8] text-[#f47524]",
                          },
                          {
                            label: "Product reviews",
                            value: pendingProducts.length,
                            hint: "Awaiting moderation",
                            icon: Package,
                            badge: "bg-[#f4efff] text-[#7c3aed]",
                          },
                        ].map((metric) => (
                          <div
                            key={metric.label}
                            className="flex min-w-0 items-center gap-3 rounded-xl border border-[#edf0f4] bg-[#fbfcfe] p-4 dark:border-white/10 dark:bg-white/[.03]"
                          >
                            <span className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl ${metric.badge}`}>
                              <metric.icon size={20} />
                            </span>
                            <div className="min-w-0">
                              <p className="truncate text-xs font-medium text-[#667085] dark:text-gray-300">
                                {metric.label}
                              </p>
                              <div className="mt-0.5 flex items-baseline gap-2">
                                <strong className="text-xl font-bold text-[#101828] dark:text-white">
                                  {metric.value}
                                </strong>
                                <span className="truncate text-[11px] text-[#98a2b3]">
                                  {metric.hint}
                                </span>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>

                    <div className="p-5 sm:p-6">
                      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                        <div>
                          <h3 className="text-lg font-bold text-[#101828] dark:text-white">
                            Moderation workload
                          </h3>
                          <p className="text-sm text-[#667085] dark:text-gray-300">
                            Live approval queues returned by your backend.
                          </p>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-[#667085]">
                          <span className="inline-flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-full bg-[#f47524]" /> Sellers
                          </span>
                          <span className="inline-flex items-center gap-1.5">
                            <span className="h-2 w-2 rounded-full bg-[#2f6bff]" /> Products
                          </span>
                        </div>
                      </div>

                      <div className="mt-6 rounded-xl border border-[#edf0f4] bg-[#fcfdff] p-4 dark:border-white/10 dark:bg-white/[.02] sm:p-5">
                        <div className="grid h-48 grid-cols-7 items-end gap-3 border-b border-l border-[#e7ebf0] px-4 pb-0 pt-4 dark:border-white/10">
                          {[42, 58, 50, 72, 61, 84, 70].map((height, index) => {
                            const sellerFactor = Math.max(18, Math.min(92, height + Math.min(pendingSellers.length * 2, 12)));
                            const productFactor = Math.max(16, Math.min(88, height - 12 + Math.min(pendingProducts.length * 2, 14)));
                            return (
                              <div key={index} className="flex h-full items-end justify-center gap-1.5">
                                <span
                                  className="w-2.5 rounded-t bg-[#f47524]/85 transition-all"
                                  style={{ height: `${sellerFactor}%` }}
                                />
                                <span
                                  className="w-2.5 rounded-t bg-[#2f6bff]/85 transition-all"
                                  style={{ height: `${productFactor}%` }}
                                />
                              </div>
                            );
                          })}
                        </div>
                        <div className="mt-2 grid grid-cols-7 px-3 text-center text-[10px] font-medium text-[#98a2b3]">
                          {["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"].map((day) => (
                            <span key={day}>{day}</span>
                          ))}
                        </div>
                      </div>
                    </div>
                  </section>

                  <div className="grid gap-4 sm:grid-cols-2 2xl:grid-cols-1">
                    <section className="rounded-xl border border-[#e2e7ee] bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,.03)] dark:border-white/10 dark:bg-[#1f2937]">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold text-[#101828] dark:text-white">Approval queues</p>
                          <p className="mt-0.5 text-xs text-[#667085] dark:text-gray-300">Items requiring administrator action</p>
                        </div>
                        <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-[#fff4e8] text-[#f47524]">
                          <ShieldCheck size={18} />
                        </span>
                      </div>
                      <div className="mt-5 space-y-4">
                        <button
                          type="button"
                          onClick={() => applySidebarSelection("sellers", "Sellers:Seller Applications", "Sellers")}
                          className="group w-full text-left"
                        >
                          <div className="mb-1.5 flex items-center justify-between text-sm">
                            <span className="font-semibold text-[#344054] group-hover:text-[#f47524] dark:text-white">Seller applications</span>
                            <span className="font-bold text-[#101828] dark:text-white">{pendingSellers.length}</span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-[#f2f4f7] dark:bg-white/10">
                            <div className="h-full rounded-full bg-[#f47524]" style={{ width: `${Math.min(100, Math.max(8, pendingSellers.length * 12))}%` }} />
                          </div>
                        </button>
                        <button
                          type="button"
                          onClick={() => applySidebarSelection("products", "Catalog:Products", "Catalog")}
                          className="group w-full text-left"
                        >
                          <div className="mb-1.5 flex items-center justify-between text-sm">
                            <span className="font-semibold text-[#344054] group-hover:text-[#2f6bff] dark:text-white">Product approvals</span>
                            <span className="font-bold text-[#101828] dark:text-white">{pendingProducts.length}</span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-[#f2f4f7] dark:bg-white/10">
                            <div className="h-full rounded-full bg-[#2f6bff]" style={{ width: `${Math.min(100, Math.max(8, pendingProducts.length * 10))}%` }} />
                          </div>
                        </button>
                      </div>
                    </section>

                    <section className="rounded-xl border border-[#e2e7ee] bg-white p-5 shadow-[0_1px_2px_rgba(15,23,42,.03)] dark:border-white/10 dark:bg-[#1f2937]">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-sm font-bold text-[#101828] dark:text-white">Platform shortcuts</p>
                          <p className="mt-0.5 text-xs text-[#667085] dark:text-gray-300">Jump into key operations</p>
                        </div>
                        <Gauge size={20} className="text-[#2f6bff]" />
                      </div>
                      <div className="mt-4 grid grid-cols-2 gap-2">
                        {[
                          { label: "Orders", icon: ShoppingBag, tab: "orders" as AdminTab, item: "Orders:All Orders", group: "Orders" },
                          { label: "Inventory", icon: Boxes, tab: "inventory" as AdminTab, item: "Inventory:Stock Overview", group: "Inventory" },
                          { label: "Customers", icon: Users, tab: "users" as AdminTab, item: "Customers:All Customers", group: "Customers" },
                          { label: "Analytics", icon: BarChart3, tab: "analytics" as AdminTab, item: "Reports & Analytics:Sales Reports", group: "Reports & Analytics" },
                        ].map((shortcut) => (
                          <button
                            key={shortcut.label}
                            type="button"
                            onClick={() => applySidebarSelection(shortcut.tab, shortcut.item, shortcut.group)}
                            className="flex items-center gap-2 rounded-lg border border-[#edf0f4] px-3 py-3 text-left text-xs font-semibold text-[#475467] transition hover:border-[#f47524] hover:text-[#f47524] dark:border-white/10 dark:text-gray-200"
                          >
                            <shortcut.icon size={16} />
                            {shortcut.label}
                          </button>
                        ))}
                      </div>
                    </section>
                  </div>
                </div>

                <section className="overflow-hidden rounded-xl border border-[#e2e7ee] bg-white shadow-[0_1px_2px_rgba(15,23,42,.03)] dark:border-white/10 dark:bg-[#1f2937]">
                  <div className="flex flex-col gap-3 border-b border-[#edf0f4] px-5 py-4 dark:border-white/10 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <h3 className="text-lg font-bold text-[#101828] dark:text-white">Latest moderation items</h3>
                      <p className="text-xs text-[#667085] dark:text-gray-300">Recent seller and product submissions waiting for review.</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => applySidebarSelection("sellers", "Sellers:Seller Applications", "Sellers")}
                      className="text-sm font-semibold text-[#f47524] hover:text-[#d85f13]"
                    >
                      View moderation queue
                    </button>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[760px] text-left">
                      <thead className="bg-[#fbfcfe] text-[11px] font-bold uppercase tracking-[.08em] text-[#98a2b3] dark:bg-white/[.03]">
                        <tr>
                          <th className="px-5 py-3">Type</th>
                          <th className="px-5 py-3">Name</th>
                          <th className="px-5 py-3">Reference</th>
                          <th className="px-5 py-3">Status</th>
                          <th className="px-5 py-3">Action</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[#edf0f4] dark:divide-white/10">
                        {[
                          ...pendingSellers.slice(0, 3).map((seller) => ({
                            key: `seller-${seller.id}`,
                            type: "Seller",
                            name: seller.business_name,
                            reference: seller.contact_email || seller.id.slice(0, 8),
                            status: seller.status,
                            action: () => applySidebarSelection("sellers", "Sellers:Seller Applications", "Sellers"),
                          })),
                          ...pendingProducts.slice(0, 3).map((product) => ({
                            key: `product-${product.id}`,
                            type: "Product",
                            name: product.name,
                            reference: product.sku,
                            status: product.status,
                            action: () => applySidebarSelection("products", "Catalog:Products", "Catalog"),
                          })),
                        ].slice(0, 5).map((row) => (
                          <tr key={row.key} className="hover:bg-[#fbfcfe] dark:hover:bg-white/[.03]">
                            <td className="px-5 py-3.5">
                              <span className="inline-flex rounded-md bg-[#f2f4f7] px-2 py-1 text-xs font-semibold text-[#475467] dark:bg-white/10 dark:text-gray-200">{row.type}</span>
                            </td>
                            <td className="max-w-[280px] truncate px-5 py-3.5 text-sm font-semibold text-[#344054] dark:text-white">{row.name}</td>
                            <td className="px-5 py-3.5 text-sm text-[#667085] dark:text-gray-300">{row.reference}</td>
                            <td className="px-5 py-3.5">
                              <span className="inline-flex rounded-full bg-[#fff4e8] px-2.5 py-1 text-xs font-semibold capitalize text-[#c85b10]">{row.status.replaceAll("_", " ")}</span>
                            </td>
                            <td className="px-5 py-3.5">
                              <button type="button" onClick={row.action} className="text-sm font-semibold text-[#2f6bff] hover:underline">Review</button>
                            </td>
                          </tr>
                        ))}
                        {pendingSellers.length === 0 && pendingProducts.length === 0 ? (
                          <tr>
                            <td colSpan={5} className="px-5 py-10 text-center text-sm text-[#667085] dark:text-gray-300">
                              No moderation items are waiting right now.
                            </td>
                          </tr>
                        ) : null}
                      </tbody>
                    </table>
                  </div>
                </section>
              </>
            ) : null}

            {operationsWorkspace && !isLoading ? (
              <AdminOperationsWorkspace workspace={operationsWorkspace} />
            ) : null}

            {isConfigurationWorkspace && !isLoading ? (
              <AdminConfiguration view={configurationView} />
            ) : null}

            {isPaymentsWorkspace && !isLoading ? (
              <AdminPayments view={paymentView} />
            ) : null}
            {isPromotionsWorkspace && !isLoading ? (
              <AdminPromotions view={promotionView} />
            ) : null}
            {isCommunicationsWorkspace && !isLoading ? (
              <AdminCommunications view={communicationView} />
            ) : null}
            {isUserManagementWorkspace && !isLoading ? (
              <AdminUserManagement view={userManagementView} />
            ) : null}
            {isReportsWorkspace && !isLoading ? (
              <AdminReports view={reportView} />
            ) : null}
            {isSystemWorkspace && !isLoading ? (
              <AdminSystemManagement view={systemView} />
            ) : null}
            {isAccountWorkspace && !isLoading ? (
              <AdminAccount view={accountView} />
            ) : null}

            {activeTab === "products" &&
            !isLoading &&
            !operationsWorkspace &&
            !isPromotionsWorkspace ? (
              <AdminProducts />
            ) : null}
            {activeTab === "categories" && !isLoading ? (
              <AdminCategories />
            ) : null}
            {activeTab === "brands" && !isLoading ? <AdminBrands /> : null}
            {activeTab === "reviews" && !isLoading ? <AdminReviews /> : null}
            {activeTab === "orders" && !isLoading ? (
              <AdminOrdersDashboard
                initialTab={searchParams.get("orders_tab") ?? "all"}
              />
            ) : null}

            {activeTab === "inventory" && !isLoading ? (
              <>
                {pathname.includes("/admin/inventory/products/") ? (
                  <AdminProductInventoryDetails
                    productId={
                      pathname
                        .split("/admin/inventory/products/")[1]
                        ?.split("/")[0] ?? ""
                    }
                  />
                ) : pathname.includes("/admin/inventory/warehouses/") ? (
                  <AdminWarehouseDetails
                    warehouseId={
                      pathname
                        .split("/admin/inventory/warehouses/")[1]
                        ?.split("/")[0] ?? ""
                    }
                  />
                ) : (
                  <>
                    {(searchParams.get("inventory_tab") ?? "stock-overview") ===
                      "stock-overview" && <AdminInventoryDashboard />}
                    {searchParams.get("inventory_tab") === "warehouses" && (
                      <AdminInventoryWarehouses />
                    )}
                    {searchParams.get("inventory_tab") ===
                      "stock-adjustments" && <AdminInventoryAdjustments />}
                    {searchParams.get("inventory_tab") ===
                      "low-stock-products" && <AdminInventoryLowStock />}
                  </>
                )}
              </>
            ) : null}

            {activeTab === "users" &&
            !isLoading &&
            !operationsWorkspace &&
            !isUserManagementWorkspace ? (
              <>
                {pathname.includes("/admin/customers/") &&
                pathname.split("/admin/customers/")[1]?.length &&
                !pathname.includes("/addresses") &&
                !pathname.includes("/reviews") &&
                !pathname.includes("/support") ? (
                  <AdminCustomerDetails
                    customerId={
                      pathname.split("/admin/customers/")[1]?.split("/")[0] ??
                      ""
                    }
                  />
                ) : activeSidebarItem === "Customers:Customer Addresses" ||
                  pathname.includes("/admin/customers/addresses") ? (
                  <AdminCustomerAddresses />
                ) : activeSidebarItem === "Customers:Customer Reviews" ||
                  pathname.includes("/admin/customers/reviews") ? (
                  <AdminCustomerReviews />
                ) : activeSidebarItem === "Customers:Customer Support" ||
                  pathname.includes("/admin/customers/support") ? (
                  <AdminCustomerSupport />
                ) : (
                  <AdminCustomers />
                )}
              </>
            ) : null}

            {activeTab === "finance" && !isLoading && !isPaymentsWorkspace && !isConfigurationWorkspace ? (
              <AdminFinance />
            ) : null}

            {activeTab === "analytics" && !isLoading && !isReportsWorkspace ? (
              <AdminAnalytics />
            ) : null}

            {activeTab === "sellers" && !isLoading && !operationsWorkspace ? (
              sellerView === "all" || sellerView === "applications" ? (
                <AdminSellers mode={sellerView} />
              ) : (
                <SellerSubWorkspace view={sellerView} />
              )
            ) : null}
            {false &&
            activeTab === "sellers" &&
            !isLoading &&
            !operationsWorkspace ? (
              <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
                <h3 className="text-xl font-semibold text-[#111827] mb-4">
                  Pending Seller Applications
                </h3>
                <div className="space-y-3">
                  {pendingSellers.length === 0 ? (
                    <p className="text-gray-500">
                      No pending seller applications right now.
                    </p>
                  ) : (
                    pendingSellers.map((seller) => (
                      <div
                        key={seller.id}
                        className="rounded-xl border border-gray-200 p-4 flex flex-col md:flex-row md:items-center md:justify-between gap-4"
                      >
                        <div>
                          <h4 className="font-medium text-[#111827]">
                            {seller.business_name}
                          </h4>
                          <p className="text-sm text-gray-500">
                            Email: {seller.contact_email ?? "-"}
                          </p>
                          <p className="text-sm text-gray-500">
                            Phone: {seller.contact_phone ?? "-"}
                          </p>
                          <p className="text-sm text-gray-500 capitalize">
                            Status: {seller.status}
                          </p>
                        </div>
                        <div className="flex gap-2">
                          <button
                            type="button"
                            onClick={() => void handleApproveSeller(seller.id)}
                            disabled={
                              busyAction === `approve-seller-${seller.id}`
                            }
                            className="rounded-lg bg-[#d9f4e1] px-3 py-2 text-[#165c30] hover:opacity-90 disabled:opacity-60"
                          >
                            Approve
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleRejectSeller(seller.id)}
                            disabled={
                              busyAction === `reject-seller-${seller.id}`
                            }
                            className="rounded-lg bg-[#fde2e2] px-3 py-2 text-[#8f2727] hover:opacity-90 disabled:opacity-60"
                          >
                            Reject
                          </button>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ) : null}
          </main>
        </div>
      </div>
    </section>
  );
}
