import { create } from "zustand";

interface QuickViewState {
  value: any;
  updateQuickView: (product: any) => void;
  resetQuickView: () => void;
}

const initialProduct = {
  title: "",
  reviews: 0,
  price: 0,
  discountedPrice: 0,
  img: "",
  id: 0,
  images: [],
  imgs: { thumbnails: [], previews: [] },
};

export const useQuickViewStore = create<QuickViewState>((set) => ({
  value: initialProduct,

  updateQuickView: (product) =>
    set({
      value: { ...product },
    }),

  resetQuickView: () =>
    set({
      value: initialProduct,
    }),
}));
