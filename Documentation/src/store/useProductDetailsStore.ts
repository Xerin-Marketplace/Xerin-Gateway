import { create } from "zustand";

interface ProductDetailsState {
  value: any;
  updateproductDetails: (product: any) => void;
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

export const useProductDetailsStore = create<ProductDetailsState>((set) => ({
  value: initialProduct,

  updateproductDetails: (product) =>
    set({
      value: { ...product },
    }),
}));
