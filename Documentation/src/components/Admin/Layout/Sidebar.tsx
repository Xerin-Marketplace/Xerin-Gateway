"use client";

import Image from "next/image";
import Link from "next/link";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { usePathname, useSearchParams } from "next/navigation";
import {
  BarChart3,
  Bell,
  Boxes,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  CircleUserRound,
  ClipboardList,
  CreditCard,
  FileCheck2,
  LayoutDashboard,
  LifeBuoy,
  Menu,
  Moon,
  Package,
  PanelLeftClose,
  PanelLeftOpen,
  Search,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Store,
  Sun,
  Tag,
  Users,
  UserPlus,
  KeyRound,
  LockKeyhole,
  WalletCards,
  Truck,
  Globe2,
  X,
  Megaphone,
  Scale,
  SlidersHorizontal,
  type LucideIcon,
} from "lucide-react";

import { useTheme } from "@/app/context/ThemeContext";
import { authStorage } from "@/lib/auth/storage";
import { canAccessAdminItem, canAccessAdminSection } from "@/lib/auth/admin-access";

export type AdminTab =
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

type AdminUser = {
  first_name?: string;
  last_name?: string;
  email?: string;
  account_type?: string;
  roles?: string[];
  permissions?: string[];
};

type NavItem = {
  label: string;
  href: string;
  icon?: LucideIcon;
};

export type SidebarGroup = {
  title: string;
  key: AdminTab | string;
  items: NavItem[];
  icon: LucideIcon;
};

const sidebarGroups: SidebarGroup[] = [
  {
    title: "Catalog",
    key: "products",
    icon: Package,
    items: [
      { label: "Products", href: "/admin/dashboard?tab=products&menu=catalog&item=products", icon: ShoppingBag },
      { label: "Categories", href: "/admin/dashboard?tab=categories&menu=catalog&item=categories", icon: Boxes },
      { label: "Brands", href: "/admin/dashboard?tab=brands&menu=catalog&item=brands", icon: Tag },
      // { label: "Product Reviews", href: "/admin/dashboard?tab=reviews&menu=catalog&item=product-reviews", icon: FileCheck2 },
    ],
  },
  {
    title: "Orders",
    key: "orders",
    icon: ShoppingBag,
    items: [
      { label: "All Orders", href: "/admin/dashboard?tab=orders&menu=orders&item=all-orders&orders_tab=all", icon: ClipboardList },
      { label: "Pending Orders", href: "/admin/dashboard?tab=orders&menu=orders&item=pending-orders&orders_tab=pending", icon: ClipboardList },
      { label: "Processing Orders", href: "/admin/dashboard?tab=orders&menu=orders&item=processing-orders&orders_tab=processing", icon: ClipboardList },
      { label: "Completed Orders", href: "/admin/dashboard?tab=orders&menu=orders&item=completed-orders&orders_tab=completed", icon: ClipboardList },
      { label: "Cancelled Orders", href: "/admin/dashboard?tab=orders&menu=orders&item=cancelled-orders&orders_tab=cancelled", icon: X },
      { label: "Order Tracking", href: "/admin/dashboard?tab=orders&menu=orders&item=order-tracking&orders_tab=tracking", icon: Search },
    ],
  },
  {
    title: "Inventory",
    key: "inventory",
    icon: Boxes,
    items: [
      { label: "Stock Overview", href: "/admin/dashboard?tab=inventory&menu=inventory&item=stock-overview&inventory_tab=stock-overview", icon: Boxes },
      { label: "Warehouses", href: "/admin/dashboard?tab=inventory&menu=inventory&item=warehouses&inventory_tab=warehouses", icon: Store },
      { label: "Stock Adjustments", href: "/admin/dashboard?tab=inventory&menu=inventory&item=stock-adjustments&inventory_tab=stock-adjustments", icon: SlidersHorizontal },
      { label: "Low Stock Products", href: "/admin/dashboard?tab=inventory&menu=inventory&item=low-stock-products&inventory_tab=low-stock-products", icon: Package },
    ],
  },
  {
    title: "Customers",
    key: "users",
    icon: Users,
    items: [
      { label: "Customer Reviews", href: "/admin/customers/reviews", icon: FileCheck2 },
      { label: "Customer Support", href: "/admin/customers/support", icon: LifeBuoy },
    ],
  },
  {
    title: "Sellers",
    key: "sellers",
    icon: Store,
    items: [
      { label: "All Sellers", href: "/admin/dashboard?tab=sellers&menu=sellers&item=all-sellers", icon: Store },
      { label: "Seller Applications", href: "/admin/dashboard?tab=sellers&menu=sellers&item=seller-applications", icon: ShieldCheck },
      { label: "Seller Products", href: "/admin/dashboard?tab=sellers&menu=sellers&item=seller-products", icon: Package },
      { label: "Seller Orders", href: "/admin/dashboard?tab=sellers&menu=sellers&item=seller-orders", icon: ClipboardList },
      { label: "Seller Performance", href: "/admin/dashboard?tab=sellers&menu=sellers&item=seller-performance", icon: BarChart3 },
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
      { label: "Coupons", href: "/admin/dashboard?tab=products&menu=promotions&item=coupons", icon: Tag },
      { label: "Discounts", href: "/admin/dashboard?tab=products&menu=promotions&item=discounts", icon: Tag },
      { label: "Campaigns", href: "/admin/dashboard?tab=products&menu=promotions&item=campaigns", icon: Megaphone },
    ],
  },
  {
    title: "Disputes",
    key: "orders",
    icon: Scale,
    items: [
      { label: "All Disputes", href: "/admin/disputes", icon: Scale },
      { label: "Open Disputes", href: "/admin/disputes?status=open", icon: Scale },
      { label: "Resolved Disputes", href: "/admin/disputes?status=resolved", icon: FileCheck2 },
    ],
  },
  {
    title: "Analytics",
    key: "analytics",
    icon: BarChart3,
    items: [
      { label: "Sales Reports", href: "/admin/analytics?report=sales", icon: BarChart3 },
      { label: "Order Reports", href: "/admin/analytics?report=orders", icon: ClipboardList },
      { label: "Product Reports", href: "/admin/analytics?report=products", icon: Package },
      { label: "Customer Reports", href: "/admin/analytics?report=customers", icon: Users },
    ],
  },
  {
    title: "Communications",
    key: "overview",
    icon: Megaphone,
    items: [
      { label: "Notifications", href: "/admin/dashboard?tab=overview&menu=communications&item=notifications", icon: Bell },
      { label: "Email Messages", href: "/admin/dashboard?tab=overview&menu=communications&item=email-messages", icon: Bell },
      { label: "SMS Messages", href: "/admin/dashboard?tab=overview&menu=communications&item=sms-messages", icon: Bell },
    ],
  },
  {
    title: "User Management",
    key: "users",
    icon: ShieldCheck,
    items: [
      { label: "Users", href: "/admin/dashboard?tab=users&menu=user-management&item=users", icon: Users },
      { label: "Add New User", href: "/admin/dashboard?tab=users&menu=user-management&item=add-new-user", icon: UserPlus },
      { label: "Roles", href: "/admin/dashboard?tab=users&menu=user-management&item=roles", icon: ShieldCheck },
      { label: "Permissions", href: "/admin/dashboard?tab=users&menu=user-management&item=permissions", icon: KeyRound },
      { label: "Active Sessions", href: "/admin/dashboard?tab=users&menu=user-management&item=active-sessions", icon: LockKeyhole },
    ],
  },
  {
    title: "Marketplace Settings",
    key: "overview",
    icon: SlidersHorizontal,
    items: [
      { label: "Marketplace Rules", href: "/admin/dashboard?tab=overview&menu=marketplace-settings&item=marketplace-rules", icon: SlidersHorizontal },
      { label: "Commission Rules", href: "/admin/dashboard?tab=overview&menu=marketplace-settings&item=commission-rules", icon: Scale },
    ],
  },
  {
    title: "Logistics",
    key: "overview",
    icon: Truck,
    items: [
      { label: "Logistics Companies", href: "/admin/dashboard?tab=overview&menu=logistics&item=logistics-companies", icon: Store },
      { label: "Delivery Services", href: "/admin/dashboard?tab=overview&menu=logistics&item=delivery-services", icon: Truck },
      { label: "Shipping Zones", href: "/admin/dashboard?tab=overview&menu=logistics&item=shipping-zones", icon: Globe2 },
      { label: "Shipping Rates", href: "/admin/dashboard?tab=overview&menu=logistics&item=shipping-rates", icon: WalletCards },
      { label: "API & Webhooks", href: "/admin/dashboard?tab=overview&menu=logistics&item=api-webhooks", icon: Settings },
    ],
  },
  {
    title: "Finance Configuration",
    key: "finance",
    icon: WalletCards,
    items: [
      { label: "Finance Settings", href: "/admin/dashboard?tab=finance&menu=finance-configuration&item=finance-settings", icon: Settings },
      { label: "Escrow Holds", href: "/admin/dashboard?tab=finance&menu=finance-configuration&item=escrow-holds", icon: LockKeyhole },
    ],
  },
  {
    title: "System Management",
    key: "overview",
    icon: Settings,
    items: [
      { label: "Audit Logs", href: "/admin/dashboard?tab=overview&menu=system-management&item=audit-logs", icon: FileCheck2 },
      { label: "System Events", href: "/admin/dashboard?tab=overview&menu=system-management&item=system-events", icon: ShieldCheck },
      { label: "Background Jobs", href: "/admin/dashboard?tab=overview&menu=system-management&item=background-jobs", icon: Settings },
      { label: "Application Settings", href: "/admin/dashboard?tab=overview&menu=system-management&item=application-settings", icon: Settings },
    ],
  },
  {
    title: "Account",
    key: "overview",
    icon: CircleUserRound,
    items: [
      { label: "Profile", href: "/my-account", icon: CircleUserRound },
      { label: "Security", href: "/my-account?tab=security", icon: ShieldCheck },
      { label: "Logout", href: "/signout", icon: X },
    ],
  },
];

function isItemActive(
  href: string,
  pathname: string,
  searchParams: ReturnType<typeof useSearchParams>,
) {
  const url = new URL(href, "http://localhost");
  if (url.pathname !== pathname) return false;

  const keys = Array.from(url.searchParams.keys());
  if (!keys.length) return true;

  return keys.every((key) => searchParams.get(key) === url.searchParams.get(key));
}

export default function AdminSidebar({
  children,
  title = "Dashboard Overview",
  breadcrumb,
}: {
  children: ReactNode;
  title?: string;
  breadcrumb?: string;
}) {
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const { theme, toggleTheme } = useTheme();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const user = authStorage.getUser<AdminUser>();
  const visibleSidebarGroups = useMemo(
    () =>
      sidebarGroups
        .map((group) => ({
          ...group,
          items: group.items.filter((item) =>
            canAccessAdminItem(user, item.label)
          ),
        }))
        .filter(
          (group) =>
            canAccessAdminSection(user, group.title) &&
            group.items.length > 0
        ),
    [user],
  );

  const displayName =
    [user?.first_name, user?.last_name].filter(Boolean).join(" ") ||
    user?.email ||
    "Admin account";

  const role =
    user?.account_type ||
    user?.roles?.[0] ||
    "admin";

  const initials =
    [user?.first_name?.[0], user?.last_name?.[0]]
      .filter(Boolean)
      .join("")
      .toUpperCase() ||
    user?.email?.[0]?.toUpperCase() ||
    "A";

  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);

  const activeGroup = useMemo(() => {
    return visibleSidebarGroups.find((group) =>
      group.items.some((item) => isItemActive(item.href, pathname, searchParams)),
    )?.title;
  }, [pathname, searchParams]);

  return (
    <div
      className="min-h-screen bg-[#f6f7f9] text-[#111827] antialiased dark:bg-[#111827] dark:text-white"
      style={{
        fontFamily:
          'Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
      }}
    >
      {mobileOpen && (
        <button
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[1px] lg:hidden"
        />
      )}

      <aside
        className={`${mobileOpen ? "translate-x-0" : "-translate-x-full"} ${
          collapsed ? "lg:w-[88px]" : "lg:w-[270px]"
        } fixed inset-y-0 left-0 z-50 flex w-[282px] flex-col border-r border-[#e7ebf0] bg-white/85 text-[#111827] shadow-[8px_0_30px_rgba(15,23,42,0.035)] backdrop-blur-xl transition-all duration-200 dark:border-white/10 dark:bg-[#1f2937]/90 dark:text-white lg:translate-x-0`}
      >
        {/* Brand */}
        <div className="flex h-[74px] shrink-0 items-center border-b border-[#e7ebf0] px-5 dark:border-white/10">
          {!collapsed && (
            <div className="min-w-0">
              <Image
                src="/images/logo/logo.png"
                alt="Xerin Marketplace logo"
                width={150}
                height={46}
                className="h-10 w-auto object-contain"
                priority
              />
              <p className="mt-0.5 text-xs text-[#94a3b8] dark:text-white/50">
                Admin Center
              </p>
            </div>
          )}
          <button
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
            className="ml-auto rounded-lg p-2 text-[#64748b] hover:bg-slate-100 dark:hover:bg-white/10 lg:hidden"
          >
            <X size={19} />
          </button>
        </div>

        {/* Account card */}
        {!collapsed && (
          <div className="mx-3 mt-4 rounded-2xl border border-[#e7ebf0] bg-white/70 p-4 shadow-sm dark:border-white/10 dark:bg-white/[0.06]">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#f7941d] text-sm font-bold text-white shadow-[0_6px_16px_rgba(247,148,29,0.20)]">
                {initials}
              </div>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-[#111827] dark:text-white">
                  {displayName}
                </p>
                <p className="mt-0.5 truncate text-xs text-[#94a3b8]">
                  {user?.email || "Admin account"}
                </p>
              </div>
            </div>
            <div className="mt-3 flex items-center justify-between">
              <span className="text-[10px] font-semibold uppercase tracking-[.14em] text-[#94a3b8]">
                Account
              </span>
              <span className="rounded-full bg-[#fff1e3] px-2.5 py-1 text-[10px] font-semibold capitalize text-[#d96800] dark:bg-orange-400/10 dark:text-orange-300">
                {role.replace("_", " ")}
              </span>
            </div>
          </div>
        )}

        {/* Navigation */}
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
          <div>
            {!collapsed && (
              <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[.18em] text-[#94a3b8] dark:text-white/35">
                Overview
              </p>
            )}
            <Link
              href="/admin/dashboard"
              title={collapsed ? "Dashboard" : undefined}
              className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-normal transition ${
                pathname === "/admin/dashboard" && !searchParams.get("tab")
                  ? "bg-[#f7941d] font-semibold text-white shadow-[0_6px_18px_rgba(247,148,29,0.18)]"
                  : "text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white"
              }`}
            >
              <LayoutDashboard size={18} strokeWidth={2} />
              {!collapsed && <span>Dashboard</span>}
            </Link>
          </div>

          {visibleSidebarGroups.map((group) => {
            const GroupIcon = group.icon;
            const open = activeGroup === group.title;

            return (
              <div key={group.title}>
                {!collapsed && (
                  <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[.18em] text-[#94a3b8] dark:text-white/35">
                    {group.title}
                  </p>
                )}

                <div className="space-y-1">
                  {group.items.map((item) => {
                    const Icon = item.icon || GroupIcon;
                    const active = isItemActive(item.href, pathname, searchParams);

                    return (
                      <Link
                        key={item.label}
                        href={item.href}
                        title={collapsed ? item.label : undefined}
                        className={`group flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] font-normal transition ${
                          active
                            ? "bg-[#f7941d] font-semibold text-white shadow-[0_6px_18px_rgba(247,148,29,0.18)]"
                            : "text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white"
                        }`}
                      >
                        <Icon
                          size={18}
                          strokeWidth={active ? 2.25 : 1.9}
                          className="shrink-0"
                        />
                        {!collapsed && (
                          <>
                            <span className="truncate">{item.label}</span>
                            {active && (
                              <ChevronRight
                                size={14}
                                className="ml-auto opacity-80"
                              />
                            )}
                          </>
                        )}
                      </Link>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </nav>

        {/* Sidebar controls */}
        <div className="shrink-0 border-t border-[#e7ebf0] p-3 dark:border-white/10">
          <div className="mb-1 flex items-center gap-1">
            <button
              onClick={toggleTheme}
              title="Toggle theme"
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] text-[#64748b] transition hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white ${
                collapsed ? "w-full justify-center" : "flex-1"
              }`}
            >
              {theme === "dark" ? <Sun size={18} /> : <Moon size={18} />}
              {!collapsed && <span>{theme === "dark" ? "Light mode" : "Dark mode"}</span>}
            </button>

            {!collapsed && (
              <Link
                href="/admin/dashboard?tab=overview&menu=account&item=profile"
                title="Settings"
                className="rounded-xl p-2.5 text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white"
              >
                <Settings size={18} />
              </Link>
            )}
          </div>

          <button
            onClick={() => setCollapsed(!collapsed)}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            className="hidden w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] text-[#64748b] transition hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white lg:flex"
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            {!collapsed && <span>Collapse sidebar</span>}
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div
        className={`transition-all duration-200 ${
          collapsed ? "lg:pl-[88px]" : "lg:pl-[270px]"
        }`}
      >
        <header className="sticky top-0 z-30 border-b border-[#e7ebf0] bg-white/90 shadow-[0_1px_0_rgba(15,23,42,0.02)] backdrop-blur-xl dark:border-white/10 dark:bg-[#1f2937]/90">
          <div className="flex h-[74px] items-center gap-3 px-4 sm:px-6 lg:px-7">
            <button
              onClick={() => setMobileOpen(true)}
              aria-label="Open navigation"
              className="rounded-xl p-2 hover:bg-slate-100 dark:hover:bg-white/10 lg:hidden"
            >
              <Menu size={21} />
            </button>

            <div className="min-w-0">
              <div className="hidden items-center gap-1 text-xs text-[#64748b] sm:flex dark:text-white/50">
                <span>Admin Center</span>
                {breadcrumb && (
                  <>
                    <span>/</span>
                    <span>{breadcrumb}</span>
                  </>
                )}
              </div>
              <h1 className="truncate text-lg font-bold tracking-[-0.02em]">
                {title}
              </h1>
            </div>

            <div className="ml-auto flex items-center gap-1 sm:gap-2">
              <label className="hidden items-center gap-2 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2 lg:flex dark:border-white/10 dark:bg-white/5">
                <Search size={17} className="text-[#64748b]" />
                <input
                  aria-label="Search admin records"
                  placeholder="Search"
                  className="w-36 bg-transparent text-sm outline-none placeholder:text-[#98a2b3]"
                />
              </label>

              <Link
                href="/admin/dashboard?tab=overview&menu=communications&item=notifications"
                aria-label="Notifications"
                className="relative rounded-xl p-2.5 hover:bg-slate-100 dark:hover:bg-white/10"
              >
                <Bell size={19} />
              </Link>

              <Link
                href="/admin/dashboard?tab=overview&menu=account&item=profile"
                aria-label="Account"
                className="rounded-xl p-2.5 hover:bg-slate-100 dark:hover:bg-white/10"
              >
                <CircleUserRound size={19} />
              </Link>
            </div>
          </div>
        </header>

        <main className="min-h-[calc(100vh-8.5rem)] p-4 sm:p-6 lg:p-7 2xl:p-8">
          {children}
        </main>

        <footer className="flex flex-col gap-2 border-t border-[#e2e8f0] px-6 py-4 text-xs text-[#64748b] dark:border-white/10 sm:flex-row sm:items-center sm:justify-between">
          <p>© 2026 Xerin Market Admin Center</p>
          <div className="flex gap-4">
            <Link href="/privacy-policy">Privacy Policy</Link>
            <Link href="/terms">Terms</Link>
            <Link href="/admin/support">Support</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}
