import axiosInstance from "../client";

export type SellerInventoryItem = {
  inventory_id: string;
  product_id: string;
  product_name: string;
  product_sku: string;
  variant_id: string | null;
  variant_name: string | null;
  variant_sku: string | null;
  quantity: number;
  reserved_quantity: number;
  available_quantity: number;
  low_stock_threshold: number;
  warehouse_location: string | null;
  restock_date: string | null;
  unit_price: number | string;
  inventory_value: number | string;
  is_low_stock: boolean;
  is_out_of_stock: boolean;
  updated_at: string | null;
};

export type SellerInventoryListResponse = {
  total: number;
  page: number;
  page_size: number;
  results: SellerInventoryItem[];
};

export type SellerInventorySummary = {
  total_products: number;
  total_variants: number;
  total_stock_units: number;
  reserved_units: number;
  available_units: number;
  low_stock_variants: number;
  out_of_stock_variants: number;
  inventory_value: number | string;
};

export type SellerInventoryConfigureRequest = {
  product_id: string;
  variant_id?: string | null;
  quantity: number;
  low_stock_threshold?: number;
  warehouse_location?: string | null;
  restock_date?: string | null;
};

export const sellerInventoryApi = {
  list: async (
    params: {
      search?: string;
      low_stock?: boolean;
      out_of_stock?: boolean;
      page?: number;
      page_size?: number;
    } = {},
  ): Promise<SellerInventoryListResponse> =>
    (
      await axiosInstance.get<SellerInventoryListResponse>(
        "/seller/inventory",
        { params },
      )
    ).data,

  summary: async (): Promise<SellerInventorySummary> =>
    (
      await axiosInstance.get<SellerInventorySummary>(
        "/seller/inventory/summary",
      )
    ).data,

  configure: async (
    payload: SellerInventoryConfigureRequest,
  ): Promise<SellerInventoryItem> =>
    (
      await axiosInstance.post<SellerInventoryItem>(
        "/seller/inventory/configure",
        payload,
      )
    ).data,

  updateSettings: async (
    inventoryId: string,
    payload: {
      low_stock_threshold?: number;
      warehouse_location?: string | null;
      restock_date?: string | null;
    },
  ): Promise<SellerInventoryItem> =>
    (
      await axiosInstance.patch<SellerInventoryItem>(
        `/seller/inventory/${inventoryId}`,
        payload,
      )
    ).data,

  restock: async (
    inventoryId: string,
    payload: {
      quantity: number;
      reference?: string | null;
      note?: string | null;
      warehouse_location?: string | null;
    },
  ): Promise<SellerInventoryItem> =>
    (
      await axiosInstance.post<SellerInventoryItem>(
        `/seller/inventory/${inventoryId}/restock`,
        payload,
      )
    ).data,
};
