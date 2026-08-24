import axiosInstance from "../client";
import type { CreateStorePayload, Store, UpdateStorePayload } from "@/types/api/store";

export const listMyStores = async (): Promise<Store[]> => {
  try {
    const res = await axiosInstance.get<Store[]>("/stores/mine");
    return Array.isArray(res.data) ? res.data : [];
  } catch (error: any) {
    const status = error?.response?.status;
    const detail = String(error?.response?.data?.detail ?? error?.message ?? "").toLowerCase();

    // Some deployed backend versions return 404 "Store not found" when an
    // approved seller has not created a store yet. For the multi-store UI this
    // is an empty collection, not a fatal page error.
    if (status === 404 && detail.includes("store not found")) {
      return [];
    }

    throw error;
  }
};

export const createStore = async (payload: CreateStorePayload): Promise<Store> => {
  const res = await axiosInstance.post<Store>("/stores", payload);
  return res.data;
};

export const getMyStoreById = async (storeId: string): Promise<Store> => {
  const res = await axiosInstance.get<Store>(`/stores/mine/${storeId}`);
  return res.data;
};

export const updateMyStoreById = async (storeId: string, payload: UpdateStorePayload): Promise<Store> => {
  const res = await axiosInstance.patch<Store>(`/stores/mine/${storeId}`, payload);
  return res.data;
};

export const uploadStoreLogoById = async (storeId: string, file: File): Promise<Store> => {
  const formData = new FormData();
  formData.append("logo", file);
  const res = await axiosInstance.post<Store>(`/stores/mine/${storeId}/logo`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const uploadStoreBannerById = async (storeId: string, file: File): Promise<Store> => {
  const formData = new FormData();
  formData.append("banner", file);
  const res = await axiosInstance.post<Store>(`/stores/mine/${storeId}/banner`, formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

// Legacy single-store endpoints are intentionally retained during the migration period.
export const getMyStore = async (): Promise<Store> => {
  const res = await axiosInstance.get<Store>("/stores/me");
  return res.data;
};

export const updateMyStore = async (payload: UpdateStorePayload): Promise<Store> => {
  const res = await axiosInstance.patch<Store>("/stores/me", payload);
  return res.data;
};

export const uploadStoreLogo = async (file: File): Promise<Store> => {
  const formData = new FormData();
  formData.append("logo", file);
  const res = await axiosInstance.post<Store>("/stores/me/logo", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const uploadStoreBanner = async (file: File): Promise<Store> => {
  const formData = new FormData();
  formData.append("banner", file);
  const res = await axiosInstance.post<Store>("/stores/me/banner", formData, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
};

export const storeApi = {
  listMyStores,
  createStore,
  getMyStoreById,
  updateMyStoreById,
  uploadStoreLogoById,
  uploadStoreBannerById,
  getMyStore,
  updateMyStore,
  uploadStoreLogo,
  uploadStoreBanner,
};
