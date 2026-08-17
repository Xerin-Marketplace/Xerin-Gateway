import axiosInstance from "../client";
import type { Store, UpdateStorePayload } from "@/types/api/store";

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
  getMyStore,
  updateMyStore,
  uploadStoreLogo,
  uploadStoreBanner,
};
