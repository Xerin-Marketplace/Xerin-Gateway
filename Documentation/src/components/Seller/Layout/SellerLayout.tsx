"use client";
import Image from "next/image";

import { useTheme } from "@/app/context/ThemeContext";
import { authCookies } from "@/lib/auth/cookies";
import { logout } from "@/lib/api/endpoints/auth";
import { sellersApi } from "@/lib/api/endpoints/sellers";
import { authStorage } from "@/lib/auth/storage";
import { useAuthStore } from "@/store/useAuthStore";
import type { Seller } from "@/types/api/seller";
import {
  BarChart3,
  Banknote,
  Bell,
  Box,
  ChevronDown,
  CircleHelp,
  CircleUserRound,
  ClipboardList,
  CreditCard,
  FileCheck2,
  FileText,
  HelpCircle,
  Home,
  LifeBuoy,
  LogOut,
  Menu,
  MessageSquare,
  Moon,
  PackagePlus,
  PanelLeftClose,
  PanelLeftOpen,
  RotateCcw,
  Search,
  Settings,
  ShieldCheck,
  ShoppingBag,
  Star,
  MessageCircle,
  Store,
  Sun,
  Tag,
  WalletCards,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState } from "react";

type User = {
  first_name?: string;
  last_name?: string;
  email?: string;
  account_type?: string;
  roles?: string[];
  seller_status?: string | null;
};
type NavItem = {
  label: string;
  href?: string;
  icon: typeof Home;
  soon?: boolean;
};
const approvedGroups: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "Overview",
    items: [{ label: "Dashboard", href: "/seller/dashboard", icon: Home }],
  },
  {
    label: "Catalog",
    items: [
      { label: "Products", href: "/seller/products", icon: ShoppingBag },
      {
        label: "Add Product",
        href: "/seller/products?create=true",
        icon: PackagePlus,
      },
      { label: "Inventory", href: "/seller/inventory", icon: Box },
    ],
  },
  {
    label: "Sales",
    items: [
      { label: "Orders", href: "/seller/orders", icon: ClipboardList },
      { label: "Returns", href: "/seller/returns", icon: RotateCcw },
      { label: "Cancellations", href: "/seller/cancellations", icon: X },
    ],
  },
  {
    label: "Store Operations",
    items: [
      { label: "Store Profile", href: "/seller/store", icon: Store },
      { label: "Promotions", href: "/seller/promotions", icon: Tag },
      { label: "Reviews", href: "/seller/reviews", icon: Star },
      { label: "Product Q&A", href: "/seller/questions", icon: MessageCircle },
      { label: "Messages", href: "/seller/messages", icon: MessageSquare },
    ],
  },
  {
    label: "Finance",
    items: [
      { label: "Wallet & Earnings", href: "/seller/earnings", icon: BarChart3 },
      { label: "Payout Requests", href: "/seller/payouts", icon: Banknote },
      { label: "Payout Accounts", href: "/seller/kyc?tab=payouts", icon: WalletCards },
      { label: "Transactions", href: "/seller/transactions", icon: CreditCard },
    ],
  },
  {
    label: "Compliance",
    items: [
      { label: "KYC Verification", href: "/seller/kyc", icon: ShieldCheck },
      {
        label: "Business Documents",
        href: "/seller/kyc?tab=documents",
        icon: FileCheck2,
      },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Account Settings", href: "/seller/account", icon: Settings },
      {
        label: "Security",
        href: "/seller/account/security",
        icon: CircleUserRound,
      },
      { label: "Help & Support", href: "/seller/support", icon: LifeBuoy },
    ],
  },
];

const activationGroups: Array<{ label: string; items: NavItem[] }> = [
  {
    label: "Activation",
    items: [
      { label: "Dashboard", href: "/seller/dashboard", icon: Home },
      { label: "KYC Verification", href: "/seller/kyc", icon: ShieldCheck },
      { label: "Business Documents", href: "/seller/documents", icon: FileText },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Account Settings", href: "/seller/account", icon: Settings },
      {
        label: "Security",
        href: "/seller/account/security",
        icon: CircleUserRound,
      },
      { label: "Help & Support", href: "/seller/support", icon: LifeBuoy },
    ],
  },
];

const pendingAllowedPaths = [
  "/seller/dashboard",
  "/seller/kyc",
  "/seller/documents",
  "/seller/account",
  "/seller/account/profile",
  "/seller/account/security",
  "/seller/support",
];

export default function SellerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const user = authStorage.getUser<User>();
  const [seller, setSeller] = useState<Seller | null>(null);
  const [sellerLoaded, setSellerLoaded] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [profileOpen, setProfileOpen] = useState(false);
  const profileRef = useRef<HTMLDivElement>(null);
  const title = pathname.includes("/account/security")
    ? "Security"
    : pathname.includes("/account/notifications")
      ? "Notifications"
      : pathname.includes("/account/profile")
        ? "Seller Profile"
        : pathname.includes("/account")
          ? "Account Settings"
          : pathname.includes("/store")
            ? "Store Settings"
            : pathname.includes("/support")
              ? "Help & Support"
              : pathname.includes("/products")
                ? "Products"
                : pathname.includes("/inventory")
                  ? "Inventory"
                  : pathname.includes("/documents")
                    ? "Business Documents"
                    : pathname.includes("/kyc")
                      ? "KYC Verification"
                    : pathname.includes("/orders/")
                      ? "Order Details"
                      : pathname.includes("/orders")
                        ? "Orders"
                        : pathname.includes("/returns")
                          ? "Returns"
                          : pathname.includes("/cancellations")
                            ? "Cancellations"
                            : pathname.includes("/promotions")
                              ? "Promotions"
                              : pathname.includes("/reviews")
                                ? "Reviews"
                                : pathname.includes("/messages")
                                  ? "Messages"
                                  : pathname.includes("/payouts")
                                    ? "Payout Requests"
                                    : pathname.includes("/earnings")
                                      ? "Wallet & Earnings"
                                      : pathname.includes("/transactions")
                                      ? "Transactions"
                                      : "Seller Dashboard";
  const crumbs = useMemo(
    () =>
      pathname.includes("/account/")
        ? ["Seller Center", "Account", title]
        : ["Seller Center", title],
    [pathname, title],
  );
  useEffect(() => {
    setMobileOpen(false);
  }, [pathname]);
  useEffect(() => {
    let active = true;

    sellersApi
      .getMe()
      .then((value) => {
        if (!active) return;
        setSeller(value);
        setSellerLoaded(true);
      })
      .catch(() => {
        if (!active) return;
        setSeller(null);
        setSellerLoaded(true);
      });

    return () => {
      active = false;
    };
  }, []);

  const sellerStatus = seller?.status || user?.seller_status || "pending";
  const isApprovedSeller = sellerStatus === "approved";
  const groups = isApprovedSeller ? approvedGroups : activationGroups;

  useEffect(() => {
    if (!sellerLoaded || isApprovedSeller) return;

    const allowed = pendingAllowedPaths.some(
      (path) => pathname === path || pathname.startsWith(`${path}/`),
    );

    if (!allowed) {
      router.replace("/seller/dashboard");
    }
  }, [isApprovedSeller, pathname, router, sellerLoaded]);
  useEffect(() => {
    const close = (event: MouseEvent) => {
      if (
        profileRef.current &&
        !profileRef.current.contains(event.target as Node)
      )
        setProfileOpen(false);
    };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  const signOut = async () => {
    try {
      const refresh = authStorage.getRefreshToken();
      if (refresh) await logout({ refresh_token: refresh });
    } catch {
    } finally {
      authStorage.clearSession();
      authCookies.clearAll();
      useAuthStore.getState().clearSession();
      window.location.assign("/signin");
    }
  };
  const storeName = seller?.business_name || [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.email || "Seller account";
  return (
    <div className="min-h-screen bg-[#f6f7f9] text-[#111827] antialiased dark:bg-[#111827] dark:text-white" style={{ fontFamily: 'Inter, "Segoe UI", Roboto, Helvetica, Arial, sans-serif' }}>
      {mobileOpen && (
        <button
          aria-label="Close navigation"
          onClick={() => setMobileOpen(false)}
          className="fixed inset-0 z-40 bg-black/45 lg:hidden"
        />
      )}
      <aside
        className={`${mobileOpen ? "translate-x-0" : "-translate-x-full"} ${collapsed ? "lg:w-[88px]" : "lg:w-[270px]"} fixed inset-y-0 left-0 z-50 flex w-[280px] flex-col border-r border-[#e7ebf0] dark:border-white/10 border-r border-[#e7ebf0] bg-white/85 text-[#111827] shadow-[8px_0_30px_rgba(15,23,42,0.035)] backdrop-blur-xl transition-all dark:border-[#e7ebf0] dark:border-white/10 dark:bg-[#1f2937]/90 dark:text-white lg:translate-x-0`}
      >
        <div className="flex h-[74px] items-center border-b border-[#e7ebf0] px-5 dark:border-[#e7ebf0] dark:border-white/10">
          {!collapsed && (
            <div>
              <div className="flex flex-col">
                <Image
                  src="/images/logo/logo.png"
                  alt="Xerin Marketplace logo"
                  width={150}
                  height={46}
                  className="h-10 w-auto object-contain"
                  priority
                />
                <p className="mt-1 text-xs text-[#94a3b8] dark:text-white/50">Seller Center</p>
              </div>
            </div>
          )}
          <button
            onClick={() => setMobileOpen(false)}
            className="ml-auto lg:hidden"
          >
            <X size={20} />
          </button>
        </div>
        {!collapsed && (
          <div className="mx-3 mt-4 rounded-2xl border border-[#e7ebf0] bg-white/65 p-4 shadow-sm dark:border-[#e7ebf0] dark:border-white/10 dark:bg-white/[0.06]">
            <p className="truncate text-sm font-semibold">{storeName}</p>
            <p className="mt-1 truncate text-xs text-[#94a3b8] dark:text-white/50">{user?.email}</p>
            <div className="mt-3 flex gap-2">
              <Badge
                label={`Account: ${sellerStatus}`}
                tone={isApprovedSeller ? "green" : "amber"}
              />
            </div>
          </div>
        )}
        <nav className="flex-1 space-y-5 overflow-y-auto px-3 py-4">
          {groups.map((group) => (
            <div key={group.label}>
              {!collapsed && (
                <p className="mb-2 px-3 text-[10px] font-semibold uppercase tracking-[.18em] text-white/35">
                  {group.label}
                </p>
              )}
              <div className="space-y-1">
                {group.items.map((item) => (
                  <Nav
                    key={item.label}
                    item={item}
                    active={Boolean(
                      item.href && pathname === item.href.split("?")[0],
                    )}
                    collapsed={collapsed}
                  />
                ))}
              </div>
            </div>
          ))}
        </nav>
        <div className="border-t border-[#e7ebf0] dark:border-white/10 p-3">
          <button
            onClick={() => setCollapsed(!collapsed)}
            className="hidden w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-[#64748b] dark:text-white/65 hover:bg-slate-100 dark:hover:bg-white/10 hover:text-white lg:flex"
          >
            {collapsed ? (
              <PanelLeftOpen size={18} />
            ) : (
              <>
                <PanelLeftClose size={18} />
                <span>Collapse sidebar</span>
              </>
            )}
          </button>
          {/* <button
            onClick={() => void signOut()}
            className="mt-1 flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-red-300 hover:bg-red-500/10"
          >
            {" "}
            <LogOut size={18} />
            {!collapsed && <span>Logout</span>}
          </button> */}
        </div>
      </aside>
      <div
        className={`transition-all ${collapsed ? "lg:pl-[88px]" : "lg:pl-[270px]"}`}
      >
        <header className="sticky top-0 z-30 border-b border-[#e7ebf0] bg-white/90 shadow-[0_1px_0_rgba(15,23,42,0.02)] backdrop-blur-xl dark:border-[#e7ebf0] dark:border-white/10 dark:bg-[#1f2937]/90">
          <div className="flex h-[74px] items-center gap-3 px-4 sm:px-6 lg:px-7">
            <button
              onClick={() => setMobileOpen(true)}
              className="rounded-lg p-2 hover:bg-slate-100 dark:hover:bg-slate-100 dark:hover:bg-white/10 lg:hidden"
            >
              <Menu size={21} />
            </button>
            <div className="min-w-0">
              <div className="hidden items-center gap-1 text-xs text-[#64748b] sm:flex">
                {crumbs.map((crumb, index) => (
                  <span key={crumb}>
                    {index > 0 && <span className="mr-1">/</span>}
                    {crumb}
                  </span>
                ))}
              </div>
              <h1 className="truncate text-lg font-bold tracking-[-0.02em]">{title}</h1>
            </div>
            <div className="ml-auto flex items-center gap-1 sm:gap-2">
              {isApprovedSeller && (
                <label className="hidden items-center gap-2 rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-3 py-2 lg:flex dark:border-[#e7ebf0] dark:border-white/10 dark:bg-white/5">
                  <Search size={17} className="text-[#64748b]" />
                  <input
                    aria-label="Search seller records"
                    placeholder="Search seller records"
                    className="w-44 bg-transparent text-sm outline-none"
                  />
                </label>
              )}
              <Link
                href="/seller/support"
                aria-label="Help"
                className="rounded-xl p-2.5 hover:bg-slate-100 dark:hover:bg-slate-100 dark:hover:bg-white/10"
              >
                <CircleHelp size={19} />
              </Link>
              <Link
                href="/seller/account/notifications"
                aria-label="Notifications"
                className="relative rounded-xl p-2.5 hover:bg-slate-100 dark:hover:bg-slate-100 dark:hover:bg-white/10"
              >
                <Bell size={19} />
              </Link>
              <button
                aria-label="Toggle theme"
                onClick={toggleTheme}
                className="rounded-xl p-2.5 hover:bg-slate-100 dark:hover:bg-slate-100 dark:hover:bg-white/10"
              >
                {theme === "dark" ? <Sun size={19} /> : <Moon size={19} />}
              </button>
              <div ref={profileRef} className="relative">
                <button
                  onClick={() => setProfileOpen(!profileOpen)}
                  className="flex items-center gap-2 rounded-xl border border-[#e2e8f0] px-2 py-1.5 dark:border-[#e7ebf0] dark:border-white/10"
                >
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#f7941d] text-sm font-bold text-white">
                    {user?.first_name?.[0] || user?.email?.[0]?.toUpperCase() || "?"}
                  </span>
                  <span className="hidden max-w-28 truncate text-sm font-semibold sm:block">
                    {user?.first_name || user?.email || "Seller account"}
                  </span>
                  <ChevronDown size={15} />
                </button>
                {profileOpen && (
                  <div className="absolute right-0 mt-2 w-64 rounded-2xl border border-[#e2e8f0] bg-white p-2 shadow-xl dark:border-[#e7ebf0] dark:border-white/10 dark:bg-[#2d3134]">
                    <div className="border-b border-[#e2e8f0] p-3 dark:border-[#e7ebf0] dark:border-white/10">
                      <p className="font-semibold">{storeName}</p>
                      <p className="truncate text-xs text-[#64748b]">
                        {user?.email}
                      </p>
                      <p className="mt-2 text-xs capitalize text-green-600">
                        {sellerStatus}
                      </p>
                    </div>
                    <Drop href="/seller/account/profile" icon={CircleUserRound} label="Seller Profile" />
                    <Drop href="/seller/account" icon={Settings} label="Account Settings" />
                    {!isApprovedSeller && (
                      <>
                        <Drop href="/seller/kyc" icon={ShieldCheck} label="KYC Verification" />
                        <Drop href="/seller/documents" icon={FileText} label="Business Documents" />
                      </>
                    )}
                    {isApprovedSeller && (
                      <>
                        <Drop href="/seller/store" icon={Store} label="Store Settings" />
                        <Drop href="/shop-with-sidebar" icon={Store} label="View storefront" />
                      </>
                    )}
                    <Drop href="/seller/account/security" icon={ShieldCheck} label="Security" />
                    <Drop href="/seller/support" icon={LifeBuoy} label="Help & Support" />
                    <button
                      onClick={() => void signOut()}
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
        <main className="min-h-[calc(100vh-8.5rem)] p-4 sm:p-6 lg:p-7 2xl:p-8">
          {!isApprovedSeller && sellerLoaded && pathname !== "/seller/dashboard" && (
            <div className="mb-5 flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-4 py-3.5 text-amber-900 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-200">
              <ShieldCheck className="mt-0.5 shrink-0" size={19} />
              <div>
                <p className="text-sm font-semibold">Seller activation in progress</p>
                <p className="mt-0.5 text-xs leading-5 opacity-80">
                  Complete KYC and required business documents. Commerce features will unlock after your seller account is approved.
                </p>
              </div>
            </div>
          )}
          {children}
        </main>
        <footer className="flex flex-col gap-2 border-t border-[#e2e8f0] px-6 py-4 text-xs text-[#64748b] dark:border-[#e7ebf0] dark:border-white/10 sm:flex-row sm:items-center sm:justify-between">
          <p>© 2026 Xerin Market Seller Center</p>
          <div className="flex gap-4">
            <Link href="/privacy-policy">Privacy Policy</Link>
            <Link href="/terms">Terms</Link>
            <Link href="/seller/support">Support</Link>
          </div>
        </footer>
      </div>
    </div>
  );
}

function Nav({
  item,
  active,
  collapsed,
}: {
  item: NavItem;
  active: boolean;
  collapsed: boolean;
}) {
  const Icon = item.icon;
  const classes = `flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-[13px] transition ${active ? "bg-[#f7941d] font-semibold text-white shadow-[0_6px_18px_rgba(247,148,29,0.18)]" : "text-[#64748b] hover:bg-slate-100 hover:text-[#111827] dark:text-white/65 dark:hover:bg-white/[0.08] dark:hover:text-white"}`;
  if (item.soon)
    return (
      <div
        title={`${item.label} — coming soon`}
        className={`${classes} cursor-not-allowed opacity-45`}
      >
        <Icon size={18} />
        {!collapsed && (
          <>
            <span>{item.label}</span>
            <span className="ml-auto text-[9px] uppercase">Soon</span>
          </>
        )}
      </div>
    );
  return (
    <Link
      href={item.href!}
      title={collapsed ? item.label : undefined}
      className={classes}
    >
      <Icon size={18} />
      {!collapsed && <span>{item.label}</span>}
    </Link>
  );
}
function Badge({ label, tone }: { label: string; tone: "green" | "amber" }) {
  return (
    <span
      className={`rounded-full px-2 py-1 text-[10px] font-semibold capitalize ${tone === "green" ? "bg-green-400/15 text-green-300" : "bg-amber-400/15 text-amber-300"}`}
    >
      {label}
    </span>
  );
}
function Drop({
  href,
  icon: Icon,
  label,
}: {
  href: string;
  icon: typeof Home;
  label: string;
}) {
  return (
    <Link
      href={href}
      className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm hover:bg-slate-50 dark:hover:bg-slate-100 dark:hover:bg-white/10"
    >
      <Icon size={16} />
      {label}
    </Link>
  );
}
