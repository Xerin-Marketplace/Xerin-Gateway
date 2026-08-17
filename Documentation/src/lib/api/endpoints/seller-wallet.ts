import axiosInstance from "../client";
import type {
  PaginatedWalletTransactionResponse,
  SellerEarningsSummary,
  SellerWallet,
  SellerWalletTransactionParams,
  PaginatedSellerPayoutResponse,
  SellerPayoutCreateRequest,
  SellerPayoutListParams,
  SellerPayoutRequest,
} from "@/types/api/seller-wallet";

export const getSellerEarningsSummary =
  async (): Promise<SellerEarningsSummary> => {
    const res = await axiosInstance.get<SellerEarningsSummary>(
      "/commissions/seller/me/summary",
    );
    return res.data;
  };

export const getSellerWallet = async (): Promise<SellerWallet> => {
  const res = await axiosInstance.get<SellerWallet>("/wallet/me");
  return res.data;
};

export const getSellerWalletTransactions = async (
  params: SellerWalletTransactionParams = {},
): Promise<PaginatedWalletTransactionResponse> => {
  const res = await axiosInstance.get<PaginatedWalletTransactionResponse>(
    "/wallet/me/transactions",
    { params },
  );
  return res.data;
};

export const sellerWalletApi = {
  earningsSummary: getSellerEarningsSummary,
  wallet: getSellerWallet,
  transactions: getSellerWalletTransactions,
  payouts: getSellerPayouts,
  requestPayout: requestSellerPayout,
  cancelPayout: cancelSellerPayout,
};


export const getSellerPayouts = async (
  params: SellerPayoutListParams = {},
): Promise<PaginatedSellerPayoutResponse> => {
  const res = await axiosInstance.get<PaginatedSellerPayoutResponse>(
    "/wallet/me/payouts",
    { params },
  );
  return res.data;
};

export const requestSellerPayout = async (
  payload: SellerPayoutCreateRequest,
): Promise<SellerPayoutRequest> => {
  const res = await axiosInstance.post<SellerPayoutRequest>(
    "/wallet/me/payouts",
    payload,
  );
  return res.data;
};

export const cancelSellerPayout = async (
  payoutId: string,
): Promise<SellerPayoutRequest> => {
  const res = await axiosInstance.post<SellerPayoutRequest>(
    `/wallet/me/payouts/${payoutId}/cancel`,
  );
  return res.data;
};
