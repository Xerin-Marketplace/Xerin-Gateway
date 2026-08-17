export type Product = {
  title: string;
  reviews?: number;
  reviewCount?: number;
  rating?: number;
  description?: string | null;
  sku?: string;
  status?: string;
  isActive?: boolean;
  variants?: Array<{
    id: string | number;
    name: string;
    sku: string;
    price?: number | null;
    attributes?: Record<string, unknown> | null;
  }>;
  price: number;
  discountedPrice: number;
  id: number | string;
  imgs?: {
    thumbnails: string[];
    previews: string[];
  };
};
