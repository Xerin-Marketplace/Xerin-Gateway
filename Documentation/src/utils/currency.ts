export const formatCurrency = (value: number, currency = "TZS") => {
  return new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency,
    maximumFractionDigits: 2,
  }).format(value);
};
