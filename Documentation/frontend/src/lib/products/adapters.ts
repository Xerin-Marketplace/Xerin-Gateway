import type { Product as ApiProduct, Category as ApiCategory } from "@/types/api/product";
import type { Product as UiProduct } from "@/types/product";
import { API_BASE_URL } from "@/lib/api/endpoints";

const PRODUCT_PLACEHOLDER_IMAGE = "/images/products/placeholder.svg";

const resolveProductImageUrl = (imageUrl: string) => {
  if (!imageUrl) return PRODUCT_PLACEHOLDER_IMAGE;

  if (
    imageUrl.startsWith("data:") ||
    imageUrl.startsWith("blob:")
  ) {
    return imageUrl;
  }

  // When the browser uses the same-origin Next.js proxy, keep uploads on that
  // same origin as well. This works on localhost, LAN devices and tunnels.
  if (API_BASE_URL.startsWith("/")) {
    if (imageUrl.startsWith("/uploads/")) {
      return imageUrl.replace(/^\/uploads\//, "/backend-uploads/");
    }

    if (imageUrl.startsWith("uploads/")) {
      return `/backend-uploads/${imageUrl.replace(/^uploads\//, "")}`;
    }

    return imageUrl;
  }

  try {
    const apiUrl = new URL(API_BASE_URL);
    const apiOrigin = apiUrl.origin;

    // Product uploads are static files served from the API host root.
    // The API base itself contains /api/v1, so joining a stored path such as
    // /uploads/products/... to API_BASE_URL incorrectly creates:
    //   https://api.example.com/api/v1/uploads/products/...
    // instead of:
    //   https://api.example.com/uploads/products/...
    if (imageUrl.startsWith("/uploads/")) {
      return `${apiOrigin}${imageUrl}`;
    }

    if (imageUrl.startsWith("uploads/")) {
      return `${apiOrigin}/${imageUrl}`;
    }

    // Also repair older absolute URLs that were built with /api/v1/uploads/.
    if (
      imageUrl.startsWith("http://") ||
      imageUrl.startsWith("https://")
    ) {
      const absolute = new URL(imageUrl);

      if (absolute.pathname.startsWith("/api/v1/uploads/")) {
        absolute.pathname = absolute.pathname.replace(
          /^\/api\/v1\/uploads\//,
          "/uploads/",
        );
      }

      return absolute.toString();
    }

    // Any other relative path is resolved against the API host.
    return `${apiOrigin}/${imageUrl.replace(/^\//, "")}`;
  } catch {
    return imageUrl;
  }
};

const toNumber = (value: number | string | null | undefined, fallback = 0) => {
  if (typeof value === "number") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : fallback;
  }
  return fallback;
};

const getProductImageUrl = (product: ApiProduct) => {
  const primaryImage = product.images?.find((image) => image.is_primary);
  const firstImage = primaryImage || product.images?.[0];

  return firstImage?.image_url
    ? resolveProductImageUrl(firstImage.image_url)
    : PRODUCT_PLACEHOLDER_IMAGE;
};

export const mapApiProductToUiProduct = (product: ApiProduct): UiProduct => {
  const price = toNumber(product.price);
  const discountedPrice = toNumber(product.sale_price, price);
  const primaryImageUrl = getProductImageUrl(product);
  const galleryImages = product.images?.length
    ? [...product.images]
        .sort((a, b) => Number(b.is_primary) - Number(a.is_primary))
        .map((image) => resolveProductImageUrl(image.image_url))
    : [primaryImageUrl];
  const displayPrice = price;
  const displayDiscountedPrice = discountedPrice || price;
  const reviewCount = typeof product.review_count === "number" ? product.review_count : undefined;
  const rating = product.rating == null ? undefined : toNumber(product.rating);

  return {
    id: product.id as UiProduct["id"],
    title: product.name || product.slug || "Untitled product",
    reviews: reviewCount,
    reviewCount,
    rating,
    description: product.description,
    sku: product.sku,
    status: product.status,
    isActive: product.is_active,
    variants: product.variants?.map((variant) => ({
      id: variant.id,
      name: variant.variant_name,
      sku: variant.sku,
      price: variant.price == null ? null : toNumber(variant.price),
      attributes: variant.attributes,
    })),
    price: displayPrice,
    discountedPrice: displayDiscountedPrice,
    currency: product.currency || "TZS",
    imgs: {
      thumbnails: galleryImages,
      previews: galleryImages,
    },
  };
};

export const mapApiProductsToUiProducts = (products: ApiProduct[]) =>
  products.map(mapApiProductToUiProduct);

export type UiCategoryFilter = {
  name: string;
  isRefined: boolean;
  id?: string | number;
};

export const mapApiCategoryToFilter = (
  category: ApiCategory
): UiCategoryFilter => ({
  id: category.id,
  name: category.name,
  isRefined: false,
});

export const mapApiCategoriesToFilters = (categories: ApiCategory[]) =>
  categories.map(mapApiCategoryToFilter);
