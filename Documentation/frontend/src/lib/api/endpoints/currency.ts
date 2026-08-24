import axiosInstance from "../client";

export type DisplayCurrency = {
  id: string;
  code: string;
  name: string;
  symbol: string;
  decimal_places: number;
  is_base: boolean;
  rate_to_tzs: string;
  rate_source?: string | null;
  effective_at?: string | null;
};

export const getDisplayCurrencies = async (): Promise<DisplayCurrency[]> => {
  const response = await axiosInstance.get<DisplayCurrency[]>("/products/display-currencies");
  return response.data;
};
