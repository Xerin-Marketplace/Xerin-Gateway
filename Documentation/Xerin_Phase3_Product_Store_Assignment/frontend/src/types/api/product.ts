import type { ID, TimestampFields } from "./common";

export type ProductStatus =
  | "draft"
  | "pending_review"
  | "approved"
  | "rejected"
  | "inactive"
  | string;

export type Category = {
  id: ID;
  parent_id: ID | null;
  name: string;
  slug: string;
  created_at: string;
};

export type Brand = {
  id: ID;
  name: string;
  slug: string;
  created_at: string;
};

export type ProductImage = {
  id: ID;
  product_id: ID;
  image_url: string;
  thumbnail_url?: string | null;
  storage_key?: string | null;
  original_filename?: string | null;
  mime_type?: string | null;
  file_size?: number | null;
  width?: number | null;
  height?: number | null;
  alt_text?: string | null;
  display_order?: number;
  is_primary: boolean;
  created_at: string;
};

export type ProductVariant = {
  id: ID;
  product_id: ID;
  variant_name: string;
  sku: string;
  seller_base_price?: string | null;
  seller_sale_price?: string | null;
  commission_rate_snapshot?: string | null;
  commission_amount_snapshot?: string | null;
  price: string | null;
  sale_price?: string | null;
  attributes: Record<string, unknown> | null;
  created_at: string;
};

export type ProductTag = {
  id: ID;
  product_id: ID;
  tag: string;
};

export type Product = TimestampFields & {
  id: ID;
  seller_id: ID;
  store_id: ID;
  category_id: ID;
  brand_id: ID | null;
  sku: string;
  name: string;
  slug: string;
  description: string | null;

  // Seller-entered prices are preserved separately from customer-facing prices.
  seller_base_price?: string;
  seller_sale_price?: string | null;
  commission_rate_snapshot?: string;
  commission_amount_snapshot?: string;

  // Marketplace/customer-facing prices.
  price: string;
  sale_price: string | null;
  currency: string;
  weight: string | null;
  status: ProductStatus;
  rejection_reason: string | null;
  is_active: boolean;

  // Optional frontend-enriched fields when fetched separately.
  images?: ProductImage[];
  variants?: ProductVariant[];
  tags?: ProductTag[];
  category?: Category;
  brand?: Brand;

  // Optional storefront fields returned by some endpoints.
  rating?: number | string | null;
  review_count?: number | null;
  is_featured?: boolean;
  is_best_seller?: boolean;
};

export type ProductListQuery = {
  search?: string;
  store_id?: ID;
  category_id?: ID;
  brand_id?: ID;
  seller_id?: ID;
  skip?: number;
  limit?: number;
};

export type ProductRequest = {
  store_id: ID;
  category_id: ID;
  brand_id?: ID | null;
  sku: string;
  name: string;
  slug: string;
  description?: string | null;
  price: number | string;
  sale_price?: number | string | null;
  currency?: string;
  weight?: number | string | null;
};

export type ProductUpdateRequest = Partial<
  ProductRequest & {
    is_active: boolean | null;
  }
>;

export type ProductImageRequest = {
  image_url: string;
  is_primary?: boolean;
};

export type ProductVariantRequest = {
  variant_name: string;
  sku: string;
  price?: number | string | null;
  attributes?: Record<string, unknown> | null;
};

export type ProductTagRequest = {
  tag: string;
};
