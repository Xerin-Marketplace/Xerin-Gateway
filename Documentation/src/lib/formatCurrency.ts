export const DEFAULT_CURRENCY = "TZS";

export function formatCurrency(
  amount: number | string | null | undefined,
  currency = DEFAULT_CURRENCY,
) {
  const value = typeof amount === "string" ? Number(amount) : amount ?? 0;
  return new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency,
    currencyDisplay: currency === "TZS" ? "narrowSymbol" : "symbol",
    maximumFractionDigits: 0,
  }).format(Number.isFinite(value) ? value : 0);
}
