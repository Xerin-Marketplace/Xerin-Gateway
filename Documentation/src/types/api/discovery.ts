export type SearchSort =
  | "relevance"
  | "newest"
  | "price_asc"
  | "price_desc"
  | "popular";

export type SearchProductItem = {
  id: string;
  seller_id: string;
  category_id: string;
  brand_id?: string | null;
  name: string;
  slug: string;
  price: number | string;
  sale_price?: number | string | null;
  currency: string;
  primary_image_url?: string | null;
};

export type ProductSearchParams = {
  q?: string;
  category_id?: string;
  seller_id?: string;
  brand_id?: string;
  min_price?: number;
  max_price?: number;
  in_stock?: boolean;
  sort?: SearchSort;
  page?: number;
  page_size?: number;
};

export type ProductSearchResponse = {
  total: number;
  page: number;
  page_size: number;
  results: SearchProductItem[];
};

export type SearchSuggestionResponse = {
  suggestions: string[];
};

export type TrendingSearchItem = {
  term: string;
  search_count: number;
};

export type RecommendationListResponse = {
  total: number;
  results: SearchProductItem[];
};

export type WishlistProductItem = {
  wishlist_id: string;
  product_id: string;
  name: string;
  slug: string;
  sku: string;
  price: number | string;
  sale_price?: number | string | null;
  currency: string;
  primary_image_url?: string | null;
  store_name?: string | null;
  store_slug?: string | null;
  is_available: boolean;
  is_in_stock: boolean;
  created_at: string;
};

export type WishlistProductListResponse = {
  total: number;
  page: number;
  page_size: number;
  results: WishlistProductItem[];
};

export type WishlistMutationResponse = {
  message: string;
};
