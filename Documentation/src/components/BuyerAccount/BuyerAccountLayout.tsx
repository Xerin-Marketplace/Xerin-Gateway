"use client";
import RouteGuard from "@/guards/RouteGuard";
import { isAdminUser, isSellerUser } from "@/guards/permissions";
import { useAuthStore } from "@/store/useAuthStore";
import {
  Bell,
  CreditCard,
  Heart,
  LayoutDashboard,
  LogOut,
  MapPin,
  Package,
  Shield,
  ShoppingCart,
  Star,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";

const nav = [
  ["Dashboard", "/account", LayoutDashboard],
  ["Orders", "/account/orders", Package],
  ["Payments", "/account/payments", CreditCard],
  ["Addresses", "/account/addresses", MapPin],
  ["Cart", "/cart", ShoppingCart],
  ["Reviews", "/account/reviews", Star],
  ["Notifications", "/account/notifications", Bell],
  ["Security", "/account/security", Shield],
  ["Account Details", "/account/details", UserRound],
] as const;
export default function BuyerAccountLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const hydrated = useAuthStore((s) => s.hasHydrated);
  const { logout } = useAuth();
  useEffect(() => {
    if (!hydrated) return;
    if (isSellerUser(user)) router.replace("/seller/account");
    else if (isAdminUser(user)) router.replace("/admin/dashboard");
  }, [hydrated, router, user]);
  if (!hydrated || isSellerUser(user) || isAdminUser(user))
    return (
      <div className="min-h-[50vh] pt-52 text-center text-[#64748b]">
        Loading your account...
      </div>
    );
  return (
    <RouteGuard accountTypes={["customer"]} fallbackPath="/signin">
      <div className="bg-[#f8fafc] pt-[190px] dark:bg-darkTheme-bg lg:pt-[175px]">
        <div className="mx-auto max-w-[1170px] px-4 py-5 sm:px-8">
          <p className="text-sm text-[#64748b]">
            Home /{" "}
            <span className="font-semibold text-[#0f172a] dark:text-white">
              My Account
            </span>
            {pathname !== "/account" &&
              ` / ${nav.find((n) => n[1] === pathname)?.[0] || "Account"}`}
          </p>
        </div>
        <div className="mx-auto grid max-w-[1170px] gap-6 px-4 pb-12 sm:px-8 lg:grid-cols-[240px_1fr]">
          <aside className="min-w-0">
            <div className="flex gap-2 overflow-x-auto rounded-2xl border border-[#e2e8f0] bg-white p-2 shadow-sm dark:border-white/10 dark:bg-darkTheme-card lg:sticky lg:top-44 lg:flex-col lg:p-3">
              {nav.map(([label, href, Icon]) => (
                <Link
                  key={href}
                  href={href}
                  className={`flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold ${pathname === href ? "bg-[#f7941d] text-white" : "text-[#4a4f54] hover:bg-orange-50 dark:text-white/70 dark:hover:bg-white/5"}`}
                >
                  <Icon size={18} />
                  {label}
                </Link>
              ))}
              <button
                onClick={() => void logout()}
                className="flex shrink-0 items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50"
              >
                <LogOut size={18} />
                Logout
              </button>
            </div>
          </aside>
          <main className="min-w-0">{children}</main>
        </div>
      </div>
    </RouteGuard>
  );
}
