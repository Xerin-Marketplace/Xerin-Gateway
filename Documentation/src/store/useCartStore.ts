import { create } from "zustand";
import { persist } from "zustand/middleware";

export type CartItem = {
  id: number | string;
  productId?: string;
  variantId?: string | null;
  title: string;
  price: number;
  discountedPrice: number;
  quantity: number;
  imgs?: {
    thumbnails: string[];
    previews: string[];
  };
};

interface CartState {
  items: CartItem[];
  addItemToCart: (item: CartItem) => void;
  removeItemFromCart: (id: number | string) => void;
  updateCartItemQuantity: (id: number | string, quantity: number) => void;
  removeAllItemsFromCart: () => void;
  setItems: (items: CartItem[]) => void;
}

export const useCartStore = create<CartState>()(
  persist(
    (set) => ({
      items: [],

      addItemToCart: (newItem) =>
        set((state) => {
          const existingItem = state.items.find((item) => item.id === newItem.id);
          if (existingItem) {
            return {
              items: state.items.map((item) =>
                item.id === newItem.id
                  ? { ...item, quantity: item.quantity + newItem.quantity }
                  : item
              ),
            };
          }
          return { items: [...state.items, newItem] };
        }),

      removeItemFromCart: (id) =>
        set((state) => ({
          items: state.items.filter((item) => String(item.id) !== String(id)),
        })),

      updateCartItemQuantity: (id, quantity) =>
        set((state) => ({
          items: state.items.map((item) =>
            String(item.id) === String(id) ? { ...item, quantity } : item
          ),
        })),

      removeAllItemsFromCart: () => set({ items: [] }),
      setItems: (items) => set({ items }),
    }),
    {
      name: "xerin_cart_store",
      partialize: (state) => ({ items: state.items }),
    }
  )
);

// Helper selectors
export const selectCartItems = (state: CartState) => state.items;
export const selectTotalPrice = (state: CartState) =>
  state.items.reduce((total, item) => total + item.discountedPrice * item.quantity, 0);
