"use client";

import { useEffect } from "react";
import { useParams, useSearchParams } from "next/navigation";
import ShopDetails from "@/components/ShopDetails";
import { useProduct } from "@/hooks/useProducts";
import { mapApiProductToUiProduct } from "@/lib/products/adapters";
import { discoveryApi } from "@/lib/api/endpoints/discovery";
import { useAuthStore } from "@/store/useAuthStore";
import RelatedProducts from "@/components/ProductDiscovery/RelatedProducts";

export default function ProductDetailsPage() {
  const params = useParams();
  const searchParams = useSearchParams();
  const id = params?.id as string;
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const { data: apiProduct, isLoading, error } = useProduct(id);

  useEffect(() => {
    if (!id || !isAuthenticated) return;

    void discoveryApi.recordView(id, {
      source: searchParams.get("source") || "product_detail",
      search_query: searchParams.get("q"),
    }).catch(() => {
      // Product-view analytics must never block the shopping experience.
    });
  }, [id, isAuthenticated, searchParams]);

  if (isLoading) {
    return (
      <section className="py-20 text-center">
        <p className="text-dark dark:text-white">Loading product...</p>
      </section>
    );
  }

  if (error || !apiProduct) {
    return (
      <section className="py-20 text-center">
        <p className="text-dark dark:text-white">Product not found.</p>
      </section>
    );
  }

  return (
    <>
      <ShopDetails product={mapApiProductToUiProduct(apiProduct)} />
      <RelatedProducts productId={id} />
    </>
  );
}
