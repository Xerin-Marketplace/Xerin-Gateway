"use client";

import React from "react";
import { formatCurrency } from "@/lib/formatCurrency";
import { useCurrency } from "@/app/context/CurrencyContext";

type PriceDisplayProps = {
  amount: number | string | null | undefined;
  sourceCurrency?: string | null;
  className?: string;
  showSettlementTzs?: boolean;
  approximate?: boolean;
};

export default function PriceDisplay({
  amount,
  sourceCurrency = "TZS",
  className,
  showSettlementTzs = false,
  approximate = false,
}: PriceDisplayProps) {
  const { selectedCurrency, convert, toTzs } = useCurrency();
  const numeric = typeof amount === "string" ? Number(amount) : Number(amount ?? 0);
  const safe = Number.isFinite(numeric) ? numeric : 0;
  const source = (sourceCurrency || "TZS").toUpperCase();
  const converted = convert(safe, source, selectedCurrency);
  const tzsAmount = toTzs(safe, source);

  return (
    <span className={className}>
      {approximate && selectedCurrency !== source ? "≈ " : ""}
      {formatCurrency(converted, selectedCurrency)}
      {showSettlementTzs && selectedCurrency !== "TZS" ? (
        <span className="ml-1 text-[0.85em] font-normal opacity-70">
          (pay {formatCurrency(tzsAmount, "TZS")})
        </span>
      ) : null}
    </span>
  );
}
