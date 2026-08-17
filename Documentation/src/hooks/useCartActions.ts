"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { cartApi } from "@/lib/api/endpoints/commerce";
import { mapApiProductToUiProduct } from "@/lib/products/adapters";
import type { CartItem as BackendCartItem, Cart } from "@/types/api/commerce";
import type { Product as UiProduct } from "@/types/product";
import toast from "react-hot-toast";
import { useAuthStore } from "@/store/useAuthStore";
import { useCartStore } from "@/store/useCartStore";

export type CartItemUi = {
  id: string;
  cartItemId: string;
  productId: string;
  title: string;
  price: number;
  discountedPrice: number;
  quantity: number;
  imgs?: {
    thumbnails: string[];
    previews: string[];
  };
};

export const mapBackendCartToUi = (cart: Cart): CartItemUi[] => {
  if (!cart?.items) return [];
  return cart.items.map((item: BackendCartItem) => {
    const product = mapApiProductToUiProduct(item.product);
    return {
      id: item.product_id,
      cartItemId: item.id,
      productId: item.product_id,
      title: product.title,
      // Cart unit_price is refreshed by the backend and is the financial source of truth.
      price: Number(item.unit_price),
      discountedPrice: Number(item.unit_price),
      quantity: item.quantity,
      imgs: product.imgs,
    };
  });
};

export const useBackendCart = (enabled = true) =>
  useQuery({
    queryKey: ["cart"],
    queryFn: ({ signal }) => cartApi.get(signal),
    enabled,
  });

export const useCartView = () => {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const guestItems = useCartStore((state) => state.items);
  const backend = useBackendCart(isAuthenticated);
  const items: CartItemUi[] = isAuthenticated
    ? (backend.data ? mapBackendCartToUi(backend.data) : [])
    : guestItems.map((item) => ({
        id: String(item.id),
        cartItemId: `guest:${item.id}`,
        productId: item.productId ?? String(item.id).split(":")[0],
        title: item.title,
        price: item.price,
        discountedPrice: item.discountedPrice,
        quantity: item.quantity,
        imgs: item.imgs,
      }));

  return {
    ...backend,
    items,
    isAuthenticated,
    isLoading: isAuthenticated ? backend.isLoading : false,
    total: isAuthenticated
      ? Number(backend.data?.total ?? 0)
      : items.reduce((sum, item) => sum + item.discountedPrice * item.quantity, 0),
    subtotal: isAuthenticated
      ? Number(backend.data?.subtotal ?? 0)
      : items.reduce((sum, item) => sum + item.discountedPrice * item.quantity, 0),
    couponCode: isAuthenticated ? backend.data?.coupon_code ?? null : null,
    promotionCode: isAuthenticated ? backend.data?.promotion_code ?? null : null,
    promotion: isAuthenticated ? backend.data?.promotion ?? null : null,
    couponDiscountAmount: isAuthenticated
      ? Number(backend.data?.coupon_discount_amount ?? 0)
      : 0,
    promotionDiscountAmount: isAuthenticated
      ? Number(backend.data?.promotion_discount_amount ?? 0)
      : 0,
    discountAmount: isAuthenticated
      ? Number(backend.data?.discount_amount ?? 0)
      : 0,
    validationMessages: isAuthenticated
      ? backend.data?.validation_messages ?? []
      : [],
    currency: backend.data?.currency ?? "TZS",
  };
};

export const useAddCartItem = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (payload: ReturnType<typeof addProductToCartPayload>) => {
      if (!useAuthStore.getState().isAuthenticated) {
        useCartStore.getState().addItemToCart(payload.guest_item);
        return null;
      }
      return cartApi.addItem({
        product_id: payload.product_id,
        variant_id: payload.variant_id,
        quantity: payload.quantity,
      });
    },
    onSuccess: (cart) => {
      if (cart) queryClient.setQueryData(["cart"], cart);
      toast.success(cart ? "Added to your cart" : "Saved in your guest cart. Sign in to sync it.");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "Failed to add to cart");
    },
  });
};

export const useUpdateCartItem = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ itemId, quantity }: { itemId: string; quantity: number }) => {
      if (itemId.startsWith("guest:")) {
        useCartStore.getState().updateCartItemQuantity(itemId.slice(6), quantity);
        return null;
      }
      return cartApi.updateItem(itemId, quantity);
    },
    onSuccess: (cart) => {
      if (cart) queryClient.setQueryData(["cart"], cart);
    },
    onError: () => {
      toast.error("Failed to update quantity");
    },
  });
};

export const useRemoveCartItem = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (itemId: string) => {
      if (itemId.startsWith("guest:")) {
        useCartStore.getState().removeItemFromCart(itemId.slice(6));
        return null;
      }
      return cartApi.removeItem(itemId);
    },
    onSuccess: (cart) => {
      if (cart) queryClient.setQueryData(["cart"], cart);
      toast.success("Removed from cart");
    },
    onError: () => {
      toast.error("Failed to remove item");
    },
  });
};

export const useClearCart = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      if (!useAuthStore.getState().isAuthenticated) {
        useCartStore.getState().removeAllItemsFromCart();
        return null;
      }
      return cartApi.clear();
    },
    onSuccess: (cart) => {
      if (cart) queryClient.setQueryData(["cart"], cart);
      toast.success("Cart cleared");
    },
    onError: () => {
      toast.error("Failed to clear cart");
    },
  });
};

export const useApplyCoupon = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cartApi.applyCoupon,
    onSuccess: (cart) => {
      queryClient.setQueryData(["cart"], cart);
      toast.success("Coupon applied");
    },
    onError: (error: any) => {
      toast.error(
        error?.response?.data?.detail ||
          error?.message ||
          "Invalid or expired coupon",
      );
    },
  });
};

export const useRemoveCoupon = () => {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: cartApi.removeCoupon,
    onSuccess: (cart) => {
      queryClient.setQueryData(["cart"], cart);
      toast.success("Coupon removed");
    },
  });
};

export const addProductToCartPayload = (product: UiProduct, quantity = 1, variantId?: string | null) => ({
  product_id: String(product.id),
  variant_id: variantId ?? null,
  quantity,
  guest_item: {
    id: variantId ? `${product.id}:${variantId}` : product.id,
    productId: String(product.id),
    variantId: variantId ?? null,
    title: product.title,
    price: product.price,
    discountedPrice: product.discountedPrice,
    quantity,
    imgs: product.imgs,
  },
});


export const useAvailableCartPromotions = (enabled = true) =>
  useQuery({
    queryKey: ["cart-promotions"],
    queryFn: cartApi.availablePromotions,
    enabled:
      enabled &&
      useAuthStore.getState().isAuthenticated,
    retry: false,
  });

export const useApplyPromotion = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: cartApi.applyPromotion,
    onSuccess: (cart) => {
      queryClient.setQueryData(["cart"], cart);
      queryClient.invalidateQueries({ queryKey: ["cart-promotions"] });
      toast.success("Seller promotion applied");
    },
    onError: (error: any) => {
      toast.error(
        error?.response?.data?.detail ||
          error?.message ||
          "Unable to apply promotion",
      );
    },
  });
};

export const useRemovePromotion = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: cartApi.removePromotion,
    onSuccess: (cart) => {
      queryClient.setQueryData(["cart"], cart);
      queryClient.invalidateQueries({ queryKey: ["cart-promotions"] });
      toast.success("Seller promotion removed");
    },
    onError: (error: any) => {
      toast.error(
        error?.response?.data?.detail ||
          error?.message ||
          "Unable to remove promotion",
      );
    },
  });
};

export const useValidateCart = () => {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: cartApi.validate,
    onSuccess: (cart) => {
      queryClient.setQueryData(["cart"], cart);
      queryClient.invalidateQueries({ queryKey: ["cart-promotions"] });

      if (cart.validation_messages?.length) {
        toast.success("Cart refreshed. Please review the notices.");
      } else {
        toast.success("Cart price and stock are up to date.");
      }
    },
    onError: (error: any) => {
      toast.error(
        error?.response?.data?.detail ||
          error?.message ||
          "Unable to validate cart",
      );
    },
  });
};
