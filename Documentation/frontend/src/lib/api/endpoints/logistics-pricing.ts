import axiosInstance from "../client";
import type { CountryOption, PricingPage, PricingSettings, PricingStrategy, ShippingRate, ShippingRatePayload, ShippingService, ShippingServicePayload, ShippingZone, ShippingZonePayload } from "@/types/api/logistics-pricing";

const ROOT = "/logistics/me";
export const logisticsPricingApi = {
  countryOptions: async () => (await axiosInstance.get<CountryOption[]>("/logistics/country-options")).data,
  zones: async () => (await axiosInstance.get<PricingPage<ShippingZone>>(`${ROOT}/zones`, { params: { page: 1, page_size: 100 } })).data,
  createZone: async (payload: ShippingZonePayload) => (await axiosInstance.post<ShippingZone>(`${ROOT}/zones`, payload)).data,
  updateZone: async (id: string, payload: Partial<ShippingZonePayload>) => (await axiosInstance.patch<ShippingZone>(`${ROOT}/zones/${id}`, payload)).data,
  deactivateZone: async (id: string) => (await axiosInstance.delete(`${ROOT}/zones/${id}`)).data,
  services: async () => (await axiosInstance.get<PricingPage<ShippingService>>(`${ROOT}/services`, { params: { page: 1, page_size: 100 } })).data,
  createService: async (payload: ShippingServicePayload) => (await axiosInstance.post<ShippingService>(`${ROOT}/services`, payload)).data,
  updateService: async (id: string, payload: Partial<ShippingServicePayload>) => (await axiosInstance.patch<ShippingService>(`${ROOT}/services/${id}`, payload)).data,
  deactivateService: async (id: string) => (await axiosInstance.delete(`${ROOT}/services/${id}`)).data,
  rates: async () => (await axiosInstance.get<PricingPage<ShippingRate>>(`${ROOT}/rates`, { params: { page: 1, page_size: 100 } })).data,
  createRate: async (payload: ShippingRatePayload) => (await axiosInstance.post<ShippingRate>(`${ROOT}/rates`, payload)).data,
  updateRate: async (id: string, payload: ShippingRatePayload) => (await axiosInstance.patch<ShippingRate>(`${ROOT}/rates/${id}`, payload)).data,
  deactivateRate: async (id: string) => (await axiosInstance.delete(`${ROOT}/rates/${id}`)).data,
  settings: async () => (await axiosInstance.get<PricingSettings>(`${ROOT}/pricing`)).data,
  updateSettings: async (strategy: PricingStrategy) => (await axiosInstance.patch<PricingSettings>(`${ROOT}/pricing`, { multi_seller_pricing_strategy: strategy })).data,
};
