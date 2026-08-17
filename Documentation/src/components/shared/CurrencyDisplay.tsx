"use client";

import { formatCurrency } from "@/utils/currency";

export default function CurrencyDisplay({ amount, currency = "TZS" }: { amount: number; currency?: string }) {
  return <span>{formatCurrency(amount, currency)}</span>;
}
