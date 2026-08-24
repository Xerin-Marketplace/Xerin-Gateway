"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { discoveryApi } from "@/lib/api/endpoints/discovery";
import PriceDisplay from "@/components/shared/PriceDisplay";
import { useAuthStore } from "@/store/useAuthStore";
import type { SearchProductItem } from "@/types/api/discovery";

export default function RelatedProducts({ productId }: { productId: string }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const [related, setRelated] = useState<SearchProductItem[]>([]);
  const [recommended, setRecommended] = useState<SearchProductItem[]>([]);

  useEffect(() => {
    if (!productId) return;

    void discoveryApi
      .related(productId, 8)
      .then((data) => setRelated(data.results))
      .catch(() => setRelated([]));

    if (isAuthenticated) {
      void discoveryApi
        .recommendations(8)
        .then((data) =>
          setRecommended(
            data.results.filter((item) => item.id !== productId),
          ),
        )
        .catch(() => setRecommended([]));
    }
  }, [productId, isAuthenticated]);

  return (
    <div className="space-y-10 bg-gray-2 py-12 dark:bg-darkTheme-bg">
      {related.length > 0 && (
        <ProductStrip
          title="Related Products"
          description="More approved products from similar categories or brands."
          rows={related}
        />
      )}

      {isAuthenticated && recommended.length > 0 && (
        <ProductStrip
          title="Recommended for You"
          description="Personalized from your marketplace browsing activity."
          rows={recommended}
        />
      )}
    </div>
  );
}

function ProductStrip({
  title,
  description,
  rows,
}: {
  title: string;
  description: string;
  rows: SearchProductItem[];
}) {
  return (
    <section className="mx-auto max-w-[1280px] px-4 sm:px-8">
      <h2 className="text-xl font-bold text-dark dark:text-white">{title}</h2>
      <p className="mt-1 text-sm text-dark-4">{description}</p>
      <div className="mt-5 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {rows.slice(0, 8).map((item) => {
          const regular = Number(item.price || 0);
          const sale =
            item.sale_price == null ? null : Number(item.sale_price);
          const price = sale && sale > 0 && sale < regular ? sale : regular;
          return (
            <Link
              key={item.id}
              href={`/products/${item.id}`}
              className="overflow-hidden rounded-xl border border-gray-3 bg-white p-3 shadow-sm transition hover:-translate-y-0.5 dark:border-white/10 dark:bg-darkTheme-card"
            >
              <div className="flex h-40 items-center justify-center rounded-lg bg-[#f7f8fa] p-3 dark:bg-white/5">
                <Image
                  src={item.primary_image_url || "/images/products/placeholder.svg"}
                  alt={item.name}
                  width={160}
                  height={160}
                  className="h-full w-full object-contain"
                />
              </div>
              <p className="mt-3 line-clamp-2 text-sm font-semibold">{item.name}</p>
              <p className="mt-2 font-bold">
                <PriceDisplay amount={price} sourceCurrency={item.currency} />
              </p>
            </Link>
          );
        })}
      </div>
    </section>
  );
}
