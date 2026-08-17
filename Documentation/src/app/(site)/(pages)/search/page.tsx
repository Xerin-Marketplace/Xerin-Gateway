"use client";

import { FormEvent, useEffect, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import Breadcrumb from "@/components/Common/Breadcrumb";
import { discoveryApi } from "@/lib/api/endpoints/discovery";
import { getBrands, getCategories } from "@/lib/api/endpoints/products";
import { formatCurrency } from "@/lib/formatCurrency";
import type {
  SearchProductItem,
  SearchSort,
  TrendingSearchItem,
} from "@/types/api/discovery";
import type { Brand, Category } from "@/types/api/product";

const PAGE_SIZE = 20;

export default function SearchPage() {
  const params = useSearchParams();
  const router = useRouter();

  const query = params.get("q")?.trim() ?? "";
  const categoryId = params.get("category_id") || "";
  const brandId = params.get("brand_id") || "";
  const sort = (params.get("sort") || "relevance") as SearchSort;
  const page = Math.max(1, Number(params.get("page") || 1));
  const minPrice = params.get("min_price") || "";
  const maxPrice = params.get("max_price") || "";

  const [input, setInput] = useState(query);
  const [rows, setRows] = useState<SearchProductItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [categories, setCategories] = useState<Category[]>([]);
  const [brands, setBrands] = useState<Brand[]>([]);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [trending, setTrending] = useState<TrendingSearchItem[]>([]);

  const updateParams = (updates: Record<string, string | null>) => {
    const next = new URLSearchParams(params.toString());
    Object.entries(updates).forEach(([key, value]) => {
      if (!value) next.delete(key);
      else next.set(key, value);
    });
    router.push(`/search?${next.toString()}`);
  };

  useEffect(() => {
    void Promise.all([
      getCategories().catch(() => []),
      getBrands().catch(() => []),
      discoveryApi.trending(8).catch(() => []),
    ]).then(([categoryRows, brandRows, trendingRows]) => {
      setCategories(categoryRows);
      setBrands(brandRows);
      setTrending(trendingRows);
    });
  }, []);

  useEffect(() => {
    setInput(query);
  }, [query]);

  useEffect(() => {
    let active = true;
    setLoading(true);

    void discoveryApi
      .searchProducts({
        q: query || undefined,
        category_id: categoryId || undefined,
        brand_id: brandId || undefined,
        min_price: minPrice ? Number(minPrice) : undefined,
        max_price: maxPrice ? Number(maxPrice) : undefined,
        sort,
        page,
        page_size: PAGE_SIZE,
      })
      .then((data) => {
        if (!active) return;
        setRows(data.results);
        setTotal(data.total);
      })
      .catch(() => {
        if (!active) return;
        setRows([]);
        setTotal(0);
      })
      .finally(() => active && setLoading(false));

    return () => {
      active = false;
    };
  }, [query, categoryId, brandId, minPrice, maxPrice, sort, page]);

  useEffect(() => {
    const value = input.trim();
    if (value.length < 2 || value === query) {
      setSuggestions([]);
      return;
    }
    const timer = window.setTimeout(() => {
      void discoveryApi
        .suggestions(value, 8)
        .then((data) => setSuggestions(data.suggestions))
        .catch(() => setSuggestions([]));
    }, 250);
    return () => window.clearTimeout(timer);
  }, [input, query]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const showingFrom = total ? (page - 1) * PAGE_SIZE + 1 : 0;
  const showingTo = Math.min(page * PAGE_SIZE, total);

  const submitSearch = (event: FormEvent) => {
    event.preventDefault();
    updateParams({ q: input.trim() || null, page: null });
    setSuggestions([]);
  };

  return (
    <>
      <Breadcrumb title="Search" pages={["Search"]} />
      <section className="bg-gray-2 py-12 dark:bg-darkTheme-bg">
        <div className="mx-auto max-w-[1280px] px-4 sm:px-8">
          <div className="rounded-2xl border border-gray-3 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
            <p className="text-xs font-bold uppercase tracking-[.14em] text-orange">
              Customer Phase 2
            </p>
            <h1 className="mt-1 text-2xl font-bold text-dark dark:text-white">
              Product Discovery
            </h1>
            <p className="mt-1 text-sm text-dark-4">
              Search only active, approved marketplace products. Prices shown are
              customer-facing marketplace prices.
            </p>

            <form onSubmit={submitSearch} className="relative mt-5">
              <div className="flex gap-2">
                <input
                  value={input}
                  onChange={(event) => setInput(event.target.value)}
                  placeholder="Search product name, description or SKU..."
                  className="h-12 min-w-0 flex-1 rounded-xl border border-gray-3 px-4 text-sm outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white"
                />
                <button className="rounded-xl bg-orange px-6 text-sm font-semibold text-white">
                  Search
                </button>
              </div>

              {suggestions.length > 0 && (
                <div className="absolute z-30 mt-2 w-full overflow-hidden rounded-xl border border-gray-3 bg-white shadow-xl dark:border-white/10 dark:bg-darkTheme-card">
                  {suggestions.map((value) => (
                    <button
                      key={value}
                      type="button"
                      onClick={() => {
                        setInput(value);
                        updateParams({ q: value, page: null });
                        setSuggestions([]);
                      }}
                      className="block w-full border-b border-gray-2 px-4 py-3 text-left text-sm hover:bg-orange/5 last:border-b-0 dark:border-white/10"
                    >
                      {value}
                    </button>
                  ))}
                </div>
              )}
            </form>

            {!query && trending.length > 0 && (
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <span className="text-xs font-semibold text-dark-4">
                  Trending:
                </span>
                {trending.map((item) => (
                  <button
                    key={item.term}
                    onClick={() => updateParams({ q: item.term, page: null })}
                    className="rounded-full bg-gray-1 px-3 py-1.5 text-xs font-medium hover:bg-orange/10 hover:text-orange dark:bg-white/5"
                  >
                    {item.term}
                  </button>
                ))}
              </div>
            )}
          </div>

          <div className="mt-5 grid gap-5 lg:grid-cols-[280px_1fr]">
            <aside className="h-fit rounded-2xl border border-gray-3 bg-white p-5 dark:border-white/10 dark:bg-darkTheme-card">
              <h2 className="font-bold dark:text-white">Filters</h2>

              <Filter label="Category">
                <select
                  value={categoryId}
                  onChange={(e) =>
                    updateParams({ category_id: e.target.value || null, page: null })
                  }
                  className={filterInput}
                >
                  <option value="">All categories</option>
                  {categories.map((item) => (
                    <option key={String(item.id)} value={String(item.id)}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Filter>

              <Filter label="Brand">
                <select
                  value={brandId}
                  onChange={(e) =>
                    updateParams({ brand_id: e.target.value || null, page: null })
                  }
                  className={filterInput}
                >
                  <option value="">All brands</option>
                  {brands.map((item) => (
                    <option key={String(item.id)} value={String(item.id)}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </Filter>

              <div className="mt-4 grid grid-cols-2 gap-2">
                <Filter label="Min price">
                  <input
                    type="number"
                    min={0}
                    defaultValue={minPrice}
                    onBlur={(e) =>
                      updateParams({ min_price: e.target.value || null, page: null })
                    }
                    className={filterInput}
                  />
                </Filter>
                <Filter label="Max price">
                  <input
                    type="number"
                    min={0}
                    defaultValue={maxPrice}
                    onBlur={(e) =>
                      updateParams({ max_price: e.target.value || null, page: null })
                    }
                    className={filterInput}
                  />
                </Filter>
              </div>

              <Filter label="Sort">
                <select
                  value={sort}
                  onChange={(e) =>
                    updateParams({ sort: e.target.value, page: null })
                  }
                  className={filterInput}
                >
                  <option value="relevance">Relevance</option>
                  <option value="newest">Newest</option>
                  <option value="popular">Popular</option>
                  <option value="price_asc">Price: low to high</option>
                  <option value="price_desc">Price: high to low</option>
                </select>
              </Filter>

              {(categoryId || brandId || minPrice || maxPrice || sort !== "relevance") && (
                <button
                  onClick={() =>
                    router.push(query ? `/search?q=${encodeURIComponent(query)}` : "/search")
                  }
                  className="mt-5 w-full rounded-xl border border-gray-3 py-2.5 text-sm font-semibold"
                >
                  Clear Filters
                </button>
              )}
            </aside>

            <main>
              <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h2 className="font-bold text-dark dark:text-white">
                    {query ? `Results for “${query}”` : "Marketplace products"}
                  </h2>
                  <p className="mt-1 text-xs text-dark-4">
                    {total
                      ? `Showing ${showingFrom}-${showingTo} of ${total}`
                      : "No matching products"}
                  </p>
                </div>
              </div>

              {loading ? (
                <div className="rounded-2xl bg-white p-14 text-center dark:bg-darkTheme-card">
                  Searching products...
                </div>
              ) : rows.length === 0 ? (
                <div className="rounded-2xl bg-white p-14 text-center dark:bg-darkTheme-card">
                  <p className="font-semibold">No products matched your search.</p>
                  <p className="mt-1 text-sm text-dark-4">
                    Try another keyword or remove some filters.
                  </p>
                </div>
              ) : (
                <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-3">
                  {rows.map((item) => (
                    <SearchCard key={item.id} item={item} />
                  ))}
                </div>
              )}

              {totalPages > 1 && (
                <div className="mt-7 flex items-center justify-center gap-3">
                  <button
                    disabled={page <= 1}
                    onClick={() => updateParams({ page: String(page - 1) })}
                    className="rounded-lg border border-gray-3 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"
                  >
                    Previous
                  </button>
                  <span className="text-sm text-dark-4">
                    Page {page} of {totalPages}
                  </span>
                  <button
                    disabled={page >= totalPages}
                    onClick={() => updateParams({ page: String(page + 1) })}
                    className="rounded-lg border border-gray-3 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"
                  >
                    Next
                  </button>
                </div>
              )}
            </main>
          </div>
        </div>
      </section>
    </>
  );
}

function SearchCard({ item }: { item: SearchProductItem }) {
  const regular = Number(item.price || 0);
  const sale =
    item.sale_price == null ? null : Number(item.sale_price);
  const effective = sale && sale > 0 && sale < regular ? sale : regular;

  return (
    <article className="overflow-hidden rounded-2xl border border-gray-3 bg-white shadow-sm transition hover:-translate-y-0.5 hover:shadow-md dark:border-white/10 dark:bg-darkTheme-card">
      <Link
        href={`/products/${item.id}`}
        className="flex h-56 items-center justify-center bg-[#f7f8fa] p-5 dark:bg-white/5"
      >
        <Image
          src={item.primary_image_url || "/images/products/placeholder.svg"}
          alt={item.name}
          width={220}
          height={220}
          className="h-full w-full object-contain"
        />
      </Link>
      <div className="p-4">
        <h3 className="line-clamp-2 font-semibold text-dark dark:text-white">
          <Link href={`/products/${item.id}`}>{item.name}</Link>
        </h3>
        <div className="mt-4 flex items-end justify-between gap-3">
          <div>
            <p className="text-xs text-dark-4">Customer price</p>
            <p className="mt-1 text-lg font-bold">
              {formatCurrency(effective, item.currency)}
            </p>
            {effective < regular && (
              <p className="text-xs text-dark-4 line-through">
                {formatCurrency(regular, item.currency)}
              </p>
            )}
          </div>
          <Link
            href={`/products/${item.id}`}
            className="rounded-lg bg-dark px-4 py-2 text-xs font-semibold text-white hover:bg-orange"
          >
            View
          </Link>
        </div>
      </div>
    </article>
  );
}

function Filter({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <label className="mt-4 block text-xs font-semibold text-dark-4">
      {label}
      {children}
    </label>
  );
}

const filterInput =
  "mt-1.5 h-11 w-full rounded-xl border border-gray-3 bg-white px-3 text-sm text-dark outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white";
