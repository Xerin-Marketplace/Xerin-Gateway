"use client";

import { useEffect, useState } from "react";
import { productsApi } from "@/lib/api/endpoints/products";
import type { ProductListQuery } from "@/types/api/product";
import type { Product as UiProduct } from "@/types/product";
import { mapApiProductsToUiProducts } from "./adapters";

export type UseProductsResult = {
  products: UiProduct[];
  isLoading: boolean;
  error: string | null;
};

export const useProducts = (query?: ProductListQuery): UseProductsResult => {
  const [products, setProducts] = useState<UiProduct[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadProducts = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const apiProducts = await productsApi.list(query);

        if (!isActive) return;

        setProducts(mapApiProductsToUiProducts(apiProducts));
      } catch (err) {
        if (!isActive) return;

        setProducts([]);
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load products from backend."
        );
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadProducts();

    return () => {
      isActive = false;
    };
  }, [JSON.stringify(query)]);

  return {
    products,
    isLoading,
    error,
  };
};
