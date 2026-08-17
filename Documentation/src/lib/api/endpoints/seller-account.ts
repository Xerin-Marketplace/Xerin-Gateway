import axiosInstance from "../client";

export type SellerUserProfile = {
  id: string; first_name: string; last_name: string; email: string; phone: string | null;
  is_verified: boolean; status: string | null; account_type: string; roles?: string[];
};
export type SellerSession = { id: string; created_at: string; expires_at: string };

export const sellerAccountApi = {
  getUser: async () => (await axiosInstance.get<SellerUserProfile>("/users/me")).data,
  updateUser: async (payload: Pick<SellerUserProfile, "first_name" | "last_name" | "phone">) =>
    (await axiosInstance.patch<SellerUserProfile>("/users/me", payload)).data,
  changePassword: async (current_password: string, new_password: string) =>
    (await axiosInstance.post<{ message: string }>("/auth/change-password", { current_password, new_password })).data,
  listSessions: async () => (await axiosInstance.get<SellerSession[]>("/users/me/sessions")).data,
  revokeSession: async (id: string) => (await axiosInstance.delete(`/users/me/sessions/${id}`)).data,
};
