import axiosInstance from "../client";
import type {
  SellerProductAnswer,
  SellerQuestionList,
  SellerReview,
  SellerReviewList,
  SellerReviewReportReason,
} from "@/types/api/seller-feedback";

export const sellerFeedbackApi = {
  reviews: async (params: { page?: number; page_size?: number } = {}) =>
    (
      await axiosInstance.get<SellerReviewList>("/seller/reviews", {
        params,
      })
    ).data,

  replyToReview: async (reviewId: string, reply: string) =>
    (
      await axiosInstance.patch<SellerReview>(
        `/seller/reviews/${reviewId}/reply`,
        { reply },
      )
    ).data,

  reportReview: async (
    reviewId: string,
    payload: {
      reason: SellerReviewReportReason;
      details?: string | null;
    },
  ) =>
    (
      await axiosInstance.post<{ reported: boolean; review_id: string }>(
        `/seller/reviews/${reviewId}/report`,
        payload,
      )
    ).data,

  questions: async (
    params: {
      page?: number;
      page_size?: number;
      unanswered_only?: boolean;
    } = {},
  ) =>
    (
      await axiosInstance.get<SellerQuestionList>("/seller/questions", {
        params,
      })
    ).data,

  answerQuestion: async (questionId: string, answer: string) =>
    (
      await axiosInstance.post<SellerProductAnswer>(
        `/seller/questions/${questionId}/answer`,
        { answer },
      )
    ).data,
};
