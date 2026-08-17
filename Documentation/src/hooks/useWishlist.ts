"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { usersApi } from "@/lib/api/endpoints/users";
import type { Product as UiProduct } from "@/types/product";
import type { WishlistProductItem } from "@/types/api/discovery";
import toast from "react-hot-toast";
import { useAuthStore } from "@/store/useAuthStore";

const WISHLIST_QUERY_KEY = ["wishlist"];

export type WishlistItemUi = {
  id: string;
  productId: string;
  title: string;
  price: number;
  discountedPrice: number;
  currency: string;
  status: string;
  quantity: number;
  storeName?: string | null;
  imgs?: {
    thumbnails: string[];
    previews: string[];
  };
};

export const useWishlist = (
  params: { page?: number; page_size?: number } = {},
) => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);

  return useQuery({
    queryKey: [...WISHLIST_QUERY_KEY, params],
    queryFn: () => usersApi.getWishlist(params),
    enabled: isAuthenticated,
    retry: false,
  });
};

export const mapWishlistToUi = (
  items: WishlistProductItem[],
): WishlistItemUi[] =>
  items.map((item) => ({
    id: item.wishlist_id,
    productId: item.product_id,
    title: item.name,
    price: Number(item.price || 0),
    discountedPrice: Number(item.sale_price ?? item.price ?? 0),
    currency: item.currency || "TZS",
    status: !item.is_available
      ? "unavailable"
      : item.is_in_stock
        ? "in_stock"
        : "out_of_stock",
    quantity: 1,
    storeName: item.store_name,
    imgs: {
      thumbnails: [
        item.primary_image_url || "/images/products/placeholder.svg",
      ],
      previews: [
        item.primary_image_url || "/images/products/placeholder.svg",
      ],
    },
  }));

export const useAddToWishlist = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (productId: string) => {
      if (!useAuthStore.getState().isAuthenticated) {
        return Promise.resolve({ message: "Saved on this device" });
      }
      return usersApi.addToWishlist(productId);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WISHLIST_QUERY_KEY });
      toast.success(
        useAuthStore.getState().isAuthenticated
          ? "Added to wishlist"
          : "Saved to your guest wishlist",
      );
    },
    onError: (error: any) => {
      const detail = error?.response?.data?.detail;
      if (
        error?.response?.status === 409 ||
        String(detail || "").toLowerCase().includes("already")
      ) {
        toast("Product is already in your wishlist.");
        return;
      }
      toast.error(detail || "Failed to add to wishlist");
    },
  });
};

export const useRemoveFromWishlist = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (productId: string) =>
      useAuthStore.getState().isAuthenticated
        ? usersApi.removeFromWishlist(productId)
        : Promise.resolve({ message: "Removed from this device" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WISHLIST_QUERY_KEY });
      toast.success("Removed from wishlist");
    },
    onError: (error: any) => {
      toast.error(error?.response?.data?.detail || "Failed to remove from wishlist");
    },
  });
};

export const useClearWishlist = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () =>
      useAuthStore.getState().isAuthenticated
        ? usersApi.clearWishlist()
        : Promise.resolve({ message: "Cleared on this device" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: WISHLIST_QUERY_KEY });
      toast.success("Wishlist cleared");
    },
  });
};

export const productToWishlistItem = (
  product: UiProduct,
): WishlistItemUi => ({
  id: String(product.id),
  productId: String(product.id),
  title: product.title,
  price: product.price,
  discountedPrice: product.discountedPrice,
  currency: "TZS",
  status: "in_stock",
  quantity: 1,
  imgs: product.imgs,
});
