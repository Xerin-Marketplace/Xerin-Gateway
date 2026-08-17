import axiosInstance from "../client";
import type {
  SellerPromotion,
  SellerPromotionListParams,
  SellerPromotionListResponse,
  SellerPromotionRequest,
  SellerPromotionUpdateRequest,
  CustomerPromotionOffer,
} from "@/types/api/promotion";

const SELLER_PROMOTIONS = "/seller/promotions";

export const listSellerPromotions = async (
  params: SellerPromotionListParams = {},
): Promise<SellerPromotionListResponse> => {
  const res = await axiosInstance.get<SellerPromotionListResponse>(
    SELLER_PROMOTIONS,
    { params },
  );
  return res.data;
};

export const createSellerPromotion = async (
  payload: SellerPromotionRequest,
): Promise<SellerPromotion> => {
  const res = await axiosInstance.post<SellerPromotion>(
    SELLER_PROMOTIONS,
    payload,
  );
  return res.data;
};

export const updateSellerPromotion = async (
  promotionId: string,
  payload: SellerPromotionUpdateRequest,
): Promise<SellerPromotion> => {
  const res = await axiosInstance.patch<SellerPromotion>(
    `${SELLER_PROMOTIONS}/${promotionId}`,
    payload,
  );
  return res.data;
};

export const deleteSellerPromotion = async (
  promotionId: string,
): Promise<void> => {
  await axiosInstance.delete(`${SELLER_PROMOTIONS}/${promotionId}`);
};

export const sellerPromotionsApi = {
  list: listSellerPromotions,
  create: createSellerPromotion,
  update: updateSellerPromotion,
  delete: deleteSellerPromotion,
};


export const customerPromotionsApi = {
  availableForCart: async (): Promise<CustomerPromotionOffer[]> =>
    (await axiosInstance.get<CustomerPromotionOffer[]>("/cart/promotions/available"))
      .data,
};
