import axiosInstance from "../client";
import { API_ENDPOINTS } from "../endpoints";
import type { ApiMessageResponse, ID } from "@/types/api/common";
import type {
  Brand,
  Category,
  Product,
  ProductImage,
  ProductImageRequest,
  ProductListQuery,
  ProductRequest,
  ProductTag,
  ProductTagRequest,
  ProductUpdateRequest,
  ProductVariant,
  ProductVariantRequest,
} from "@/types/api/product";

export const getProducts = async (query?: ProductListQuery): Promise<Product[]> => {
  const res = await axiosInstance.get<Product[]>(API_ENDPOINTS.products.list, {
    params: query,
  });
  return Promise.all(
    res.data.map(async (product) => {
      // Current storefront responses already include images. Avoid an extra
      // request per product; only use the legacy image endpoint when needed.
      if (Array.isArray(product.images)) return product;
      return {
        ...product,
        images: await getProductImages(product.id).catch(() => []),
      };
    }),
  );
};

export const getProduct = async (id: ID): Promise<Product> => {
  const res = await axiosInstance.get<Product>(API_ENDPOINTS.products.byId(id));
  if (Array.isArray(res.data.images)) return res.data;
  return {
    ...res.data,
    images: await getProductImages(id).catch(() => []),
  };
};

export const getMyProducts = async (query?: ProductListQuery | string | null): Promise<Product[]> => {
  const params = query && typeof query === "object" ? query : undefined;
  const res = await axiosInstance.get<Product[]>(API_ENDPOINTS.products.myProducts, {
    params,
  });

  return Promise.all(
    res.data.map(async (product) => ({
      ...product,
      images: await getMyProductImages(product.id).catch(() => []),
    })),
  );
};

export const getCategories = async (): Promise<Category[]> => {
  const res = await axiosInstance.get<Category[]>(API_ENDPOINTS.products.categories);
  return res.data;
};

export const getBrands = async (): Promise<Brand[]> => {
  const res = await axiosInstance.get<Brand[]>(API_ENDPOINTS.products.brands);
  return res.data;
};

export const createProduct = async (payload: ProductRequest, _token?: string | null): Promise<Product> => {
  const res = await axiosInstance.post<Product>(API_ENDPOINTS.products.list, payload);
  return res.data;
};

export const updateProduct = async (
  id: ID,
  payload: ProductUpdateRequest,
  _token?: string | null
): Promise<Product> => {
  const res = await axiosInstance.patch<Product>(API_ENDPOINTS.products.byId(id), payload);
  return res.data;
};

export const deleteProduct = async (id: ID, _token?: string | null): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.delete<ApiMessageResponse>(API_ENDPOINTS.products.byId(id));
  return res.data;
};

export const uploadProductImage = async (
  productId: ID,
  payload: ProductImageRequest
): Promise<ProductImage> => {
  const res = await axiosInstance.post<ProductImage>(
    API_ENDPOINTS.products.images(productId),
    payload
  );
  return res.data;
};

export const getProductImages = async (productId: ID): Promise<ProductImage[]> => {
  const res = await axiosInstance.get<ProductImage[]>(
    API_ENDPOINTS.products.images(productId)
  );
  return res.data;
};


export const getMyProductImages = async (
  productId: ID,
): Promise<ProductImage[]> => {
  const res = await axiosInstance.get<ProductImage[]>(
    `/products/my-products/${productId}/images`,
  );
  return res.data;
};

export const uploadProductImageFiles = async (
  productId: ID,
  files: File[],
  altText?: string,
): Promise<ProductImage[]> => {
  const formData = new FormData();

  files.forEach((file) => {
    formData.append("files", file);
  });

  if (altText?.trim()) {
    formData.append("alt_text", altText.trim());
  }

  formData.append("make_first_primary", "true");

  const res = await axiosInstance.post<ProductImage[]>(
    `/products/${productId}/images/upload`,
    formData,
  );

  return res.data;
};

export const submitProductForReview = async (
  productId: ID,
): Promise<Product> => {
  const res = await axiosInstance.post<Product>(
    `/products/${productId}/submit`,
  );
  return res.data;
};

export const uploadProductImages = async (
  productId: ID,
  imageUrls: string[],
): Promise<ProductImage[]> => {
  return Promise.all(
    imageUrls.map((imageUrl, index) =>
      uploadProductImage(productId, {
        image_url: imageUrl,
        is_primary: index === 0,
      }),
    ),
  );
};

export const deleteProductImage = async (
  productId: ID,
  imageId: ID,
): Promise<ApiMessageResponse> => {
  const res = await axiosInstance.delete<ApiMessageResponse>(
    `/products/${productId}/images/${imageId}`,
  );
  return res.data;
};

export const addProductVariant = async (
  productId: ID,
  payload: ProductVariantRequest
): Promise<ProductVariant> => {
  const res = await axiosInstance.post<ProductVariant>(
    API_ENDPOINTS.products.variants(productId),
    payload
  );
  return res.data;
};

export const getProductVariants = async (productId: ID): Promise<ProductVariant[]> => {
  const res = await axiosInstance.get<ProductVariant[]>(
    API_ENDPOINTS.products.variants(productId)
  );
  return res.data;
};

export const addProductTag = async (
  productId: ID,
  payload: ProductTagRequest
): Promise<ProductTag> => {
  const res = await axiosInstance.post<ProductTag>(
    API_ENDPOINTS.products.tags(productId),
    payload
  );
  return res.data;
};

export const getProductTags = async (productId: ID): Promise<ProductTag[]> => {
  const res = await axiosInstance.get<ProductTag[]>(
    API_ENDPOINTS.products.tags(productId)
  );
  return res.data;
};

export const productsApi = {
  list: getProducts,
  getById: getProduct,
  getMyProducts,
  getCategories,
  getBrands,
  create: createProduct,
  update: updateProduct,
  delete: deleteProduct,
  uploadImage: uploadProductImage,
  getImages: getProductImages,
  getMyImages: getMyProductImages,
  uploadImageFiles: uploadProductImageFiles,
  uploadImages: uploadProductImages,
  submitForReview: submitProductForReview,
  deleteImage: deleteProductImage,
  addVariant: addProductVariant,
  getVariants: getProductVariants,
  addTag: addProductTag,
  getTags: getProductTags,
};
