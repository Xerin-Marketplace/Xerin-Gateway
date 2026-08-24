"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useTheme } from "@/app/context/ThemeContext";
import CurrencySelector from "./CurrencySelector";

export default function MobileStorefrontHeader() {
  const router = useRouter();
  const { theme, toggleTheme } = useTheme();
  const [query, setQuery] = useState("");

  const submitSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const value = query.trim();
    router.push(value ? `/search?q=${encodeURIComponent(value)}` : "/search");
  };

  return (
    <div className="lg:hidden border-b border-[#e9edf2] bg-white dark:border-white/10 dark:bg-darkTheme-bg">
      <div className="xerin-page-shell pb-3 pt-[max(10px,env(safe-area-inset-top))]">
        <div className="flex h-11 items-center justify-between gap-3">
          <a
            href="/"
            aria-label="Xerin Marketplace home"
            className="flex min-w-0 items-center"
          >
            <Image
              src="/images/logo/logo.png"
              alt="Xerin Marketplace"
              width={116}
              height={36}
              priority
              className="h-auto w-[92px] object-contain min-[360px]:w-[104px] sm:w-[116px]"
            />
          </a>

          <div className="flex min-w-0 items-center gap-1.5">
            <a
              href="/account/addresses"
              className="flex min-w-0 items-center gap-1.5 rounded-full px-1.5 py-2 text-xs font-semibold text-[#475569] dark:text-white/70 min-[360px]:max-w-[125px] min-[360px]:px-2 sm:max-w-[145px]"
              aria-label="Delivery location"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" className="shrink-0">
                <path d="M12 21s7-6.1 7-13a7 7 0 10-14 0c0 6.9 7 13 7 13Z" stroke="currentColor" strokeWidth="1.8"/>
                <circle cx="12" cy="8" r="2.5" stroke="currentColor" strokeWidth="1.8"/>
              </svg>
              <span className="hidden truncate min-[360px]:inline">Deliver to Tanzania</span>
            </a>

            <CurrencySelector compact />

            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "Use light theme" : "Use dark theme"}
              className="xerin-touch-target flex h-10 w-10 shrink-0 items-center justify-center rounded-full text-[#475569] hover:bg-[#f1f5f9] dark:text-white/70 dark:hover:bg-white/10"
            >
              {theme === "dark" ? (
                <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
                  <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.8"/>
                  <path d="M12 2v2M12 20v2M4.93 4.93l1.42 1.42M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.42-1.42M17.66 6.34l1.41-1.41" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                </svg>
              ) : (
                <svg width="19" height="19" viewBox="0 0 24 24" fill="none">
                  <path d="M21 15.2A9 9 0 118.8 3 7 7 0 0021 15.2Z" stroke="currentColor" strokeWidth="1.8" strokeLinejoin="round"/>
                </svg>
              )}
            </button>
          </div>
        </div>

        <form onSubmit={submitSearch} className="mt-2">
          <div className="relative">
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              type="search"
              placeholder="Search products, brands, or sellers"
              aria-label="Search marketplace"
              className="h-11 w-full rounded-full border-2 border-[#111827] bg-white pl-4 pr-12 text-base text-[#111827] outline-none placeholder:text-[#94a3b8] focus:border-[#f37522] dark:border-white/30 dark:bg-white/5 dark:text-white"
            />
            <button
              type="submit"
              aria-label="Search"
              className="absolute right-1 top-1 flex h-9 w-9 items-center justify-center rounded-full bg-[#111827] text-white transition hover:bg-[#f37522] dark:bg-[#f37522]"
            >
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                <circle cx="11" cy="11" r="6.5" stroke="currentColor" strokeWidth="2"/>
                <path d="m16 16 4 4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
