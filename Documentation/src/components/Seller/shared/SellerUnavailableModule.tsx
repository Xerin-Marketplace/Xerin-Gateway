"use client";

import Link from "next/link";
import { ArrowLeft, type LucideIcon } from "lucide-react";

export type SellerUnavailableModuleProps = {
  title: string;
  description: string;
  icon: LucideIcon;
  action?: string;
  backHref?: string;
  backLabel?: string;
};

export default function SellerUnavailableModule({
  title,
  description,
  icon: Icon,
  action = "This feature is not available yet.",
  backHref = "/seller/dashboard",
  backLabel = "Back to dashboard",
}: SellerUnavailableModuleProps) {
  return (
    <div className="mx-auto max-w-[1280px]">
      <div className="rounded-2xl border border-[#e2e8f0] bg-white p-8 text-center shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-12">
        <div className="mx-auto flex h-16 w-16 items-center justify-center rounded-2xl bg-orange-50 text-[#f7941d] dark:bg-orange-500/10">
          <Icon size={32} />
        </div>
        <h2 className="mt-5 text-2xl font-semibold">{title}</h2>
        <p className="mx-auto mt-2 max-w-xl text-sm leading-6 text-[#64748b]">
          {description}
        </p>
        <p className="mx-auto mt-5 inline-block rounded-xl border border-dashed border-[#cbd5e1] px-5 py-3 text-xs text-[#64748b] dark:border-white/15">
          {action}
        </p>
        <div className="mt-6">
          <Link
            href={backHref}
            className="inline-flex items-center gap-2 rounded-xl bg-[#2d3134] px-5 py-2.5 text-sm font-semibold text-white"
          >
            <ArrowLeft size={16} />
            {backLabel}
          </Link>
        </div>
      </div>
    </div>
  );
}
