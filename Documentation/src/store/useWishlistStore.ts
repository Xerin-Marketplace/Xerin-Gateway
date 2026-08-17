import { create } from "zustand";
import { persist } from "zustand/middleware";

export type WishListItem = {
  id: number | string;
  title: string;
  price: number;
  discountedPrice: number;
  quantity: number;
  status?: string;
  imgs?: {
    thumbnails: string[];
    previews: string[];
  };
};

interface WishlistState {
  items: WishListItem[];
  addItemToWishlist: (item: WishListItem) => void;
  removeItemFromWishlist: (id: number | string) => void;
  removeAllItemsFromWishlist: () => void;
  setItems: (items: WishListItem[]) => void;
  isInWishlist: (id: number | string) => boolean;
}

export const useWishlistStore = create<WishlistState>()(
  persist(
    (set, get) => ({
      items: [],

      addItemToWishlist: (newItem) =>
        set((state) => {
          const existingItem = state.items.find((item) => item.id === newItem.id);
          if (existingItem) return state;
          return { items: [...state.items, newItem] };
        }),

      removeItemFromWishlist: (id) =>
        set((state) => ({
          items: state.items.filter((item) => item.id !== id),
        })),

      removeAllItemsFromWishlist: () => set({ items: [] }),

      setItems: (items) => set({ items }),

      isInWishlist: (id) => get().items.some((item) => item.id === id),
    }),
    {
      name: "xerin_wishlist_store",
    }
  )
);
