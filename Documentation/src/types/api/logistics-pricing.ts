export type LogisticsScope = "local" | "international" | "both";
export type ShippingRateType = "flat" | "weight_based" | "free" | "per_km" | "base_plus_per_km" | "provider_quote";
export type PricingStrategy = "farthest_seller" | "sum_individual";

export type ShippingZone = {
  id: string; logistics_company_id?: string | null; name: string; country: string; scope: LogisticsScope;
  regions: string[]; cities: string[]; districts: string[]; wards: string[]; postal_codes: string[];
  coverage_geojson?: Record<string, unknown> | null; covers_entire_country: boolean; is_active: boolean;
  created_at: string; updated_at?: string | null;
};
export type ShippingZonePayload = Omit<ShippingZone, "id" | "logistics_company_id" | "created_at" | "updated_at" | "coverage_geojson">;

export type ShippingService = {
  id: string; logistics_company_id?: string | null; name: string; service_code?: string | null; description?: string | null;
  carrier_name?: string | null; scope: LogisticsScope; supports_cod: boolean; supports_tracking: boolean;
  min_delivery_days: number; max_delivery_days: number; is_active: boolean; created_at: string; updated_at?: string | null;
};
export type ShippingServicePayload = Omit<ShippingService, "id" | "logistics_company_id" | "created_at" | "updated_at">;

export type ShippingRate = {
  id: string; zone_id: string; method_id: string; rate_type: ShippingRateType; currency: string;
  base_amount: number | string; amount_per_kg: number | string; amount_per_km: number | string;
  minimum_fee?: number | string | null; maximum_fee?: number | string | null; max_distance_km?: number | string | null;
  free_shipping_threshold?: number | string | null; min_weight_kg?: number | string | null; max_weight_kg?: number | string | null;
  is_active: boolean; zone: ShippingZone; method: ShippingService; created_at: string; updated_at?: string | null;
};
export type ShippingRatePayload = Omit<ShippingRate, "id" | "zone" | "method" | "created_at" | "updated_at">;

export type PricingSettings = { logistics_company_id: string; multi_seller_pricing_strategy: PricingStrategy; supported_strategies: PricingStrategy[] };
export type PricingPage<T> = { total: number; page: number; page_size: number; total_pages: number; results: T[] };
