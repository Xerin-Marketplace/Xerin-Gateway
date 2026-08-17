import axiosInstance from "../client";
import { API_ENDPOINTS } from "../endpoints";
import type { ApiMessageResponse, ID } from "@/types/api/common";
import type {
  Address,
  AddressRequest,
  PaginatedAddressResponse,
  UpdateUserRequest,
  User,
} from "@/types/api/user";
import type { Product } from "@/types/product";

export const getMe = async (): Promise<User> => {
  const res = await axiosInstance.get<User>(API_ENDPOINTS.users.me);
  return res.data;
};

export const updateMe = async (payload: UpdateUserRequest): Promise<User> => {
  const res = await axiosInstance.patch<User>(API_ENDPOINTS.users.me, payload);
  return res.data;
};

export const getAddresses = async (
  params: { page?: number; page_size?: number } = { page: 1, page_size: 100 },
  signal?: AbortSignal,
): Promise<Address[]> => {
  const res = await axiosInstance.get<PaginatedAddressResponse | Address[]>(
    API_ENDPOINTS.users.addresses,
    { params, signal },
  );

  if (Array.isArray(res.data)) {
    return res.data;
  }

  return res.data.results;
};

export const createAddress = async (payload: AddressRequest): Promise<Address> => {
  const res = await axiosInstance.post<Address>(API_ENDPOINTS.users.addresses, payload);
  return res.data;
};

export const updateAddress = async (
  id: ID,
  payload: AddressRequest
): Promise<Address> => {
  const res = await axiosInstance.patch<Address>(
    API_ENDPOINTS.users.addressById(id),
    payload
  );

  return res.data;
};

export const setDefaultAddress = async (id: ID): Promise<Address> => {
  const res = await axiosInstance.post<Address>(
    API_ENDPOINTS.users.setDefaultAddress(id),
  );
  return res.data;
};

export const deleteAddress = async (id: ID): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.delete<ApiMessageResponse>(
    API_ENDPOINTS.users.addressById(id)
  );

  return res.data;
};

export const getWishlist = async (
  params: { page?: number; page_size?: number } = {},
): Promise<WishlistProductListResponse> => {
  const res = await axiosInstance.get<WishlistProductListResponse>(
    "/wishlist/products",
    { params },
  );
  return res.data;
};

export const addToWishlist = async (
  productId: string,
): Promise<WishlistMutationResponse> => {
  const res = await axiosInstance.post<WishlistMutationResponse>(
    `/wishlist/products/${productId}`,
  );
  return res.data;
};

export const removeFromWishlist = async (
  productId: string,
): Promise<WishlistMutationResponse> => {
  const res = await axiosInstance.delete<WishlistMutationResponse>(
    `/wishlist/products/${productId}`,
  );
  return res.data;
};

export const clearWishlist = async (): Promise<WishlistMutationResponse> => {
  const res = await axiosInstance.delete<WishlistMutationResponse>(
    "/wishlist/clear",
  );
  return res.data;
};

export const usersApi = {
  getMe,
  updateMe,
  getAddresses,
  createAddress,
  updateAddress,
  setDefaultAddress,
  deleteAddress,
  getWishlist,
  addToWishlist,
  removeFromWishlist,
  clearWishlist,
};
