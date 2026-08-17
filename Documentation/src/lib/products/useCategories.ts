"use client";

import { useEffect, useState } from "react";
import { productsApi } from "@/lib/api/endpoints/products";
import { mapApiCategoriesToFilters, type UiCategoryFilter } from "./adapters";

export type UseCategoriesResult = {
  categories: UiCategoryFilter[];
  isLoading: boolean;
  error: string | null;
};

export const useCategories = (): UseCategoriesResult => {
  const [categories, setCategories] = useState<UiCategoryFilter[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isActive = true;

    const loadCategories = async () => {
      setIsLoading(true);
      setError(null);

      try {
        const apiCategories = await productsApi.getCategories();

        if (!isActive) return;

        setCategories(mapApiCategoriesToFilters(apiCategories));
      } catch (err) {
        if (!isActive) return;

        setCategories([]);
        setError(
          err instanceof Error
            ? err.message
            : "Unable to load categories from backend."
        );
      } finally {
        if (isActive) {
          setIsLoading(false);
        }
      }
    };

    loadCategories();

    return () => {
      isActive = false;
    };
  }, []);

  return {
    categories,
    isLoading,
    error,
  };
};
