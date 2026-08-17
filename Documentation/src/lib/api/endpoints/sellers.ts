import axiosInstance from "../client";
import { API_ENDPOINTS } from "../endpoints";
import type { ApiMessageResponse, ID, PaginatedResults } from "@/types/api/common";
import type {
  PayoutAccount,
  PayoutAccountRequest,
  Seller,
  SellerBusinessCategory,
  SellerDocumentType,
  SellerBusinessProfile,
  SellerKycDocument,
  SellerKycStatus,
  UpdateSellerRequest,
  UploadSellerKycDocumentRequest,
  SellerPricingPreviewRequest,
  SellerPricingPreviewResponse,
  SellerDashboardPerformance,
} from "@/types/api/seller";

export const getBusinessCategories = async (): Promise<SellerBusinessCategory[]> => {
  const res = await axiosInstance.get<SellerBusinessCategory[]>(API_ENDPOINTS.sellers.businessCategories);
  return res.data;
};

export const registerSeller = async (payload: Omit<Seller, "id" | "status">): Promise<Seller> => {
  const res = await axiosInstance.post<Seller>(API_ENDPOINTS.sellers.register, payload);
  return res.data;
};

export const getSellerMe = async (token?: string | null): Promise<Seller> => {
  const res = await axiosInstance.get<Seller>(API_ENDPOINTS.sellers.me);
  return res.data;
};

export const getSellerBusinessProfile = async (): Promise<SellerBusinessProfile> => {
  const res = await axiosInstance.get<SellerBusinessProfile>(API_ENDPOINTS.sellers.profile);
  return res.data;
};

export const updateSellerBusinessProfile = async (
  payload: Partial<Omit<SellerBusinessProfile, "id" | "seller_id" | "created_at">>
): Promise<SellerBusinessProfile> => {
  const res = await axiosInstance.patch<SellerBusinessProfile>(API_ENDPOINTS.sellers.profile, payload);
  return res.data;
};

export const updateSellerMe = async (
  payload: UpdateSellerRequest,
  token?: string | null
): Promise<Seller> => {
  const res = await axiosInstance.patch<Seller>(API_ENDPOINTS.sellers.me, payload);
  return res.data;
};

export const getKycDocuments = async (token?: string | null): Promise<SellerKycDocument[]> => {
  const res = await axiosInstance.get<PaginatedResults<SellerKycDocument> | SellerKycDocument[]>(
    API_ENDPOINTS.sellers.kycDocuments
  );
  return Array.isArray(res.data) ? res.data : res.data.results ?? [];
};

export const getKycStatus = async (token?: string | null): Promise<SellerKycStatus> => {
  const res = await axiosInstance.get<SellerKycStatus>(API_ENDPOINTS.sellers.kycStatus);
  return res.data;
};

export const uploadKycDocument = async (
  payload: UploadSellerKycDocumentRequest,
  token?: string | null
): Promise<SellerKycDocument> => {
  const formData = new FormData();
  formData.append("document_type", payload.document_type);
  formData.append("file", payload.file);

  const res = await axiosInstance.post<SellerKycDocument>(API_ENDPOINTS.sellers.kycDocuments, formData, {
    headers: {
      "Content-Type": "multipart/form-data",
    },
  });
  return res.data;
};

export const uploadKycDocuments = async (
  payloads: UploadSellerKycDocumentRequest[],
  token?: string | null
): Promise<SellerKycDocument[]> => {
  // The current backend endpoint accepts one KYC document per multipart POST.
  // Send all selected documents concurrently from one "Submit all" action.
  return Promise.all(
    payloads.map((payload) => uploadKycDocument(payload, token))
  );
};

export const uploadBulkKycDocuments = async (
  files: { tin: File; business_profile: File; business_registration: File },
  token?: string | null
): Promise<SellerKycDocument[]> => {
  const formData = new FormData();
  formData.append("tin_file", files.tin);
  formData.append("business_profile_file", files.business_profile);
  formData.append("business_registration_file", files.business_registration);
  const res = await axiosInstance.post<SellerKycDocument[]>(
    `${API_ENDPOINTS.sellers.kycDocuments}/bulk`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return res.data;
};

export const updateKycDocument = async (
  documentId: ID,
  payload: { file?: File; document_type?: SellerDocumentType },
  token?: string | null
): Promise<SellerKycDocument> => {
  const formData = new FormData();
  if (payload.document_type) formData.append("document_type", payload.document_type);
  if (payload.file) formData.append("file", payload.file);
  const res = await axiosInstance.put<SellerKycDocument>(
    `${API_ENDPOINTS.sellers.kycDocuments}/${documentId}`,
    formData,
    { headers: { "Content-Type": "multipart/form-data" } }
  );
  return res.data;
};

export const getKycDocumentViewUrl = (documentId: ID) =>
  `${API_ENDPOINTS.sellers.kycDocuments}/${documentId}/view`;

export const getPayoutAccounts = async (token?: string | null): Promise<PayoutAccount[]> => {
  const res = await axiosInstance.get<PaginatedResults<PayoutAccount> | PayoutAccount[]>(
    API_ENDPOINTS.sellers.payoutAccounts
  );
  return Array.isArray(res.data) ? res.data : res.data.results ?? [];
};

export const createPayoutAccount = async (
  payload: PayoutAccountRequest,
  token?: string | null
): Promise<PayoutAccount> => {
  const res = await axiosInstance.post<PayoutAccount>(API_ENDPOINTS.sellers.payoutAccounts, payload);
  return res.data;
};

export const deletePayoutAccount = async (id: ID, token?: string | null): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.delete<ApiMessageResponse>(API_ENDPOINTS.sellers.payoutAccountById(id));
  return res.data;
};


export const previewSellerPricing = async (
  payload: SellerPricingPreviewRequest,
): Promise<SellerPricingPreviewResponse> => {
  const res = await axiosInstance.post<SellerPricingPreviewResponse>(
    "/seller/pricing/preview",
    payload,
  );
  return res.data;
};


export const getSellerDashboardPerformance =
  async (): Promise<SellerDashboardPerformance> => {
    const res = await axiosInstance.get<SellerDashboardPerformance>(
      "/seller/dashboard",
    );
    return res.data;
  };

export const sellersApi = {
  getBusinessCategories,
  register: registerSeller,
  getMe: getSellerMe,
  getProfile: getSellerBusinessProfile,
  updateProfile: updateSellerBusinessProfile,
  updateMe: updateSellerMe,
  getKycDocuments,
  getKycStatus,
  uploadKycDocument,
  uploadKycDocuments,
  uploadBulkKycDocuments,
  updateKycDocument,
  getKycDocumentViewUrl,
  getPayoutAccounts,
  createPayoutAccount,
  deletePayoutAccount,
  previewPricing: previewSellerPricing,
  getDashboardPerformance: getSellerDashboardPerformance,
};
