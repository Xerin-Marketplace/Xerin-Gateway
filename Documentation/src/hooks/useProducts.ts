import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  getProducts as apiGetProducts,
  getProduct as apiGetProduct,
  getMyProducts as apiGetMyProducts,
  getCategories as apiGetCategories,
  getBrands as apiGetBrands,
  createProduct as apiCreateProduct,
  updateProduct as apiUpdateProduct,
  deleteProduct as apiDeleteProduct,
  uploadProductImage as apiUploadProductImage,
  addProductVariant as apiAddProductVariant,
  addProductTag as apiAddProductTag,
} from "@/lib/api/endpoints/products";
import type { ProductImageRequest, ProductListQuery, ProductRequest, ProductTagRequest, ProductUpdateRequest, ProductVariantRequest } from "@/types/api/product";
import type { ID } from "@/types/api/common";

export const useProducts = (query?: ProductListQuery) => {
  return useQuery({
    queryKey: ["products", query],
    queryFn: () => apiGetProducts(query),
    retry: false,
    staleTime: 30_000,
  });
};

export const useProduct = (id: ID) => {
  return useQuery({
    queryKey: ["product", id],
    queryFn: () => apiGetProduct(id),
    enabled: Boolean(id),
    retry: false,
  });
};

export const useMyProducts = (query?: ProductListQuery) => {
  return useQuery({
    queryKey: ["my-products", query],
    queryFn: () => apiGetMyProducts(query),
    retry: false,
  });
};

export const useCategories = () => {
  return useQuery({
    queryKey: ["categories"],
    queryFn: apiGetCategories,
    staleTime: 60_000,
    retry: false,
  });
};

export const useBrands = () => {
  return useQuery({
    queryKey: ["brands"],
    queryFn: apiGetBrands,
    retry: false,
  });
};

export const useCreateProduct = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: ProductRequest) => apiCreateProduct(payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["my-products"] });
    },
  });
};

export const useUpdateProduct = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ id, payload }: { id: ID; payload: ProductUpdateRequest }) =>
      apiUpdateProduct(id, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["product", variables.id] });
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["my-products"] });
    },
  });
};

export const useDeleteProduct = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: ID) => apiDeleteProduct(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["products"] });
      queryClient.invalidateQueries({ queryKey: ["my-products"] });
    },
  });
};

export const useUploadProductImage = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({
      productId,
      payload,
    }: {
      productId: ID;
      payload: ProductImageRequest;
    }) => apiUploadProductImage(productId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["product", variables.productId] });
    },
  });
};


export const useAddProductVariant = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      productId,
      payload,
    }: {
      productId: ID;
      payload: ProductVariantRequest;
    }) => apiAddProductVariant(productId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["product", variables.productId] });
    },
  });
};

export const useAddProductTag = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      productId,
      payload,
    }: {
      productId: ID;
      payload: ProductTagRequest;
    }) => apiAddProductTag(productId, payload),
    onSuccess: (_, variables) => {
      queryClient.invalidateQueries({ queryKey: ["product", variables.productId] });
    },
  });
};
