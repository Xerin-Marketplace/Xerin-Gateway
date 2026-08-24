"use client";

import React, { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { getDisplayCurrencies, type DisplayCurrency } from "@/lib/api/endpoints/currency";

const STORAGE_KEY = "xerin_display_currency";

type CurrencyContextValue = {
  currencies: DisplayCurrency[];
  selectedCurrency: string;
  setSelectedCurrency: (code: string) => void;
  isLoading: boolean;
  convert: (amount: number, fromCurrency?: string | null, toCurrency?: string | null) => number;
  toTzs: (amount: number, fromCurrency?: string | null) => number;
};

const CurrencyContext = createContext<CurrencyContextValue | null>(null);

const fallbackTzs: DisplayCurrency = {
  id: "tzs",
  code: "TZS",
  name: "Tanzanian Shilling",
  symbol: "TSh",
  decimal_places: 0,
  is_base: true,
  rate_to_tzs: "1",
};

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const [currencies, setCurrencies] = useState<DisplayCurrency[]>([fallbackTzs]);
  const [selectedCurrency, setSelectedCurrencyState] = useState("TZS");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(STORAGE_KEY) : null;
    if (stored) setSelectedCurrencyState(stored.toUpperCase());

    let cancelled = false;
    void getDisplayCurrencies()
      .then((rows) => {
        if (cancelled) return;
        const normalized = rows.length ? rows : [fallbackTzs];
        setCurrencies(normalized);
        const desired = (stored || "TZS").toUpperCase();
        if (!normalized.some((item) => item.code === desired)) {
          setSelectedCurrencyState("TZS");
          window.localStorage.setItem(STORAGE_KEY, "TZS");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setCurrencies([fallbackTzs]);
          setSelectedCurrencyState("TZS");
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, []);

  const setSelectedCurrency = useCallback((code: string) => {
    const normalized = code.toUpperCase();
    setSelectedCurrencyState(normalized);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, normalized);
  }, []);

  const rateMap = useMemo(() => {
    const map = new Map<string, number>();
    for (const currency of currencies) {
      const rate = Number(currency.rate_to_tzs);
      if (Number.isFinite(rate) && rate > 0) map.set(currency.code, rate);
    }
    map.set("TZS", 1);
    return map;
  }, [currencies]);

  const toTzs = useCallback(
    (amount: number, fromCurrency = "TZS") => {
      const source = (fromCurrency || "TZS").toUpperCase();
      const sourceRate = rateMap.get(source);
      if (!sourceRate) return amount;
      return amount * sourceRate;
    },
    [rateMap],
  );

  const convert = useCallback(
    (amount: number, fromCurrency = "TZS", toCurrency?: string | null) => {
      const target = (toCurrency || selectedCurrency || "TZS").toUpperCase();
      const source = (fromCurrency || "TZS").toUpperCase();
      if (source === target) return amount;

      const sourceRate = rateMap.get(source);
      const targetRate = rateMap.get(target);
      if (!sourceRate || !targetRate) return amount;

      return (amount * sourceRate) / targetRate;
    },
    [rateMap, selectedCurrency],
  );

  const value = useMemo(
    () => ({
      currencies,
      selectedCurrency,
      setSelectedCurrency,
      isLoading,
      convert,
      toTzs,
    }),
    [currencies, selectedCurrency, setSelectedCurrency, isLoading, convert, toTzs],
  );

  return <CurrencyContext.Provider value={value}>{children}</CurrencyContext.Provider>;
}

export function useCurrency() {
  const value = useContext(CurrencyContext);
  if (!value) throw new Error("useCurrency must be used inside CurrencyProvider");
  return value;
}
