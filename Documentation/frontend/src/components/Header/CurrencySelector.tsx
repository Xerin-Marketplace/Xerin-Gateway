"use client";

import React from "react";
import { useCurrency } from "@/app/context/CurrencyContext";

export default function CurrencySelector({ compact = false }: { compact?: boolean }) {
  const { currencies, selectedCurrency, setSelectedCurrency, isLoading } = useCurrency();

  return (
    <label className={`inline-flex items-center gap-1.5 ${compact ? "" : "rounded-lg border border-gray-3 px-2.5 py-2 dark:border-darkTheme-border-color"}`}>
      {!compact ? <span className="text-xs font-medium text-dark-4 dark:text-darkTheme-secondary-muted">Currency</span> : null}
      <select
        aria-label="Display currency"
        value={selectedCurrency}
        disabled={isLoading}
        onChange={(event) => setSelectedCurrency(event.target.value)}
        className="bg-transparent text-xs font-semibold text-dark outline-none dark:text-white"
      >
        {currencies.map((currency) => (
          <option key={currency.code} value={currency.code}>
            {currency.code}
          </option>
        ))}
      </select>
    </label>
  );
}
