"use client";

import RouteGuard from "@/guards/RouteGuard";
import { authCookies } from "@/lib/auth/cookies";
import { authStorage } from "@/lib/auth/storage";
import { useAuthStore } from "@/store/useAuthStore";
import {
  Boxes,
  Building2,
  LayoutDashboard,
  LogOut,
  Menu,
  PackageCheck,
  Settings,
  Truck,
  Users,
  WalletCards,
  Webhook,
  X,
} from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";

const nav = [
  { label: "Dashboard", href: "/logistics/dashboard", icon: LayoutDashboard },
  { label: "Shipments", href: "/logistics/shipments", icon: Truck },
  { label: "Pickup jobs", href: "/logistics/pickups", icon: PackageCheck },
  { label: "Zones & rates", href: "/logistics/pricing", icon: Boxes },
  { label: "Team", href: "/logistics/team", icon: Users, soon: true },
  { label: "Wallet", href: "/logistics/wallet", icon: WalletCards, soon: true },
  { label: "Integration", href: "/logistics/integration", icon: Webhook, soon: true },
  { label: "Company settings", href: "/logistics/settings", icon: Settings, soon: true },
];

function Workspace({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const user = useAuthStore((state) => state.user);

  useEffect(() => setMobileOpen(false), [pathname]);

  const title = nav.find((item) => pathname.startsWith(item.href))?.label ?? "Logistics workspace";
  const name = [user?.first_name, user?.last_name].filter(Boolean).join(" ") || user?.email || "Team member";

  const signOut = () => {
    authStorage.clearSession();
    authCookies.clearAll();
    useAuthStore.getState().clearSession();
    router.replace("/signin");
  };

  const sidebar = (
    <div className="flex h-full flex-col bg-slate-950 text-slate-100">
      <div className="flex h-16 items-center justify-between border-b border-white/10 px-4">
        <Link href="/logistics/dashboard" className="flex min-w-0 items-center gap-2 font-semibold">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-xl bg-blue text-white"><Building2 size={19} /></span>
          <span className="truncate">Xerin Logistics</span>
        </Link>
        <button className="rounded-lg p-2 hover:bg-white/10 lg:hidden" onClick={() => setMobileOpen(false)} aria-label="Close navigation"><X size={20} /></button>
      </div>
      <nav className="flex-1 space-y-1 overflow-y-auto p-3" aria-label="Logistics navigation">
        {nav.map(({ label, href, icon: Icon, soon }) => {
          const active = pathname === href || pathname.startsWith(`${href}/`);
          if (soon) return <div key={href} aria-disabled="true" className="flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-500"><Icon size={19} /><span className="flex-1">{label}</span><span className="text-[10px] uppercase">Soon</span></div>;
          return <Link key={href} href={href} className={`flex min-h-11 items-center gap-3 rounded-xl px-3 py-2.5 text-sm transition ${active ? "bg-blue text-white" : "text-slate-300 hover:bg-white/10 hover:text-white"}`}><Icon size={19} /><span>{label}</span></Link>;
        })}
      </nav>
      <div className="border-t border-white/10 p-3">
        <button onClick={signOut} className="flex min-h-11 w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-300 hover:bg-red-500/15 hover:text-red-300"><LogOut size={19} />Sign out</button>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen bg-slate-50 dark:bg-slate-900">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 lg:block">{sidebar}</aside>
      {mobileOpen && <div className="fixed inset-0 z-50 lg:hidden"><button className="absolute inset-0 bg-black/55" onClick={() => setMobileOpen(false)} aria-label="Close navigation overlay" /><aside className="relative h-full w-[min(85vw,20rem)] shadow-2xl">{sidebar}</aside></div>}
      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 flex min-h-16 items-center gap-3 border-b border-slate-200 bg-white/95 px-3 backdrop-blur sm:px-5 dark:border-slate-700 dark:bg-slate-900/95">
          <button onClick={() => setMobileOpen(true)} className="rounded-lg border border-slate-200 p-2.5 lg:hidden dark:border-slate-700" aria-label="Open navigation"><Menu size={20} /></button>
          <div className="min-w-0 flex-1"><h1 className="truncate text-base font-semibold text-slate-900 sm:text-lg dark:text-white">{title}</h1></div>
          <div className="hidden min-w-0 text-right sm:block"><p className="max-w-48 truncate text-sm font-medium text-slate-800 dark:text-slate-100">{name}</p><p className="text-xs text-slate-500">Logistics team</p></div>
        </header>
        <main className="p-3 sm:p-5 xl:p-7">{children}</main>
      </div>
    </div>
  );
}

export default function LogisticsLayout({ children }: { children: React.ReactNode }) {
  return <RouteGuard logisticsOnly fallbackPath="/account"> <Workspace>{children}</Workspace> </RouteGuard>;
}
