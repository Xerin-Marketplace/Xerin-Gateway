"use client";
import Link from "next/link";
export default function BuyerAccountFooter(){return <footer className="border-t border-[#e2e8f0] bg-white px-4 py-5 text-sm text-[#64748b] dark:border-white/10 dark:bg-darkTheme-bg"><div className="mx-auto flex max-w-[1170px] flex-col gap-3 sm:flex-row sm:items-center sm:justify-between"><p>© 2026 Xerin Group</p><div className="flex flex-wrap gap-4"><Link href="/contact">Help Center</Link><Link href="/account/orders">Orders</Link><Link href="/privacy-policy">Privacy</Link><Link href="/terms">Terms</Link></div></div></footer>}
