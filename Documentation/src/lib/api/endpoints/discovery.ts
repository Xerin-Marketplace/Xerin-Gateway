import axiosInstance from "../client";
import type {
  ProductSearchParams,
  ProductSearchResponse,
  RecommendationListResponse,
  SearchSuggestionResponse,
  TrendingSearchItem,
} from "@/types/api/discovery";

export const discoveryApi = {
  searchProducts: async (
    params: ProductSearchParams = {},
  ): Promise<ProductSearchResponse> =>
    (
      await axiosInstance.get<ProductSearchResponse>("/search/products", {
        params,
      })
    ).data,

  suggestions: async (
    q: string,
    limit = 8,
  ): Promise<SearchSuggestionResponse> =>
    (
      await axiosInstance.get<SearchSuggestionResponse>("/search/suggestions", {
        params: { q, limit },
      })
    ).data,

  trending: async (limit = 10): Promise<TrendingSearchItem[]> =>
    (
      await axiosInstance.get<TrendingSearchItem[]>("/search/trending", {
        params: { limit },
      })
    ).data,

  recordView: async (
    productId: string,
    payload: {
      session_id?: string | null;
      source?: string | null;
      search_query?: string | null;
    } = {},
  ) =>
    (
      await axiosInstance.post(`/products/${productId}/view`, payload)
    ).data,

  related: async (
    productId: string,
    limit = 8,
  ): Promise<RecommendationListResponse> =>
    (
      await axiosInstance.get<RecommendationListResponse>(
        `/products/${productId}/related`,
        { params: { limit } },
      )
    ).data,

  recommendations: async (limit = 8): Promise<RecommendationListResponse> =>
    (
      await axiosInstance.get<RecommendationListResponse>("/recommendations", {
        params: { limit },
      })
    ).data,

  recentlyViewed: async (
    limit = 8,
  ): Promise<RecommendationListResponse> =>
    (
      await axiosInstance.get<RecommendationListResponse>(
        "/recommendations/recently-viewed",
        { params: { limit } },
      )
    ).data,
};
