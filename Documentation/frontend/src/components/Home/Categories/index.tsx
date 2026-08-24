"use client";

import React, { FormEvent, useMemo, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { useCategories, useProducts } from "@/hooks/useProducts";
import { mapApiProductToUiProduct } from "@/lib/products/adapters";
import PriceDisplay from "@/components/shared/PriceDisplay";

const PAGE_SIZE = 12;

const Categories = () => {
  const [searchInput, setSearchInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [page, setPage] = useState(1);

  const productQuery = useMemo(
    () => ({
      search: searchQuery || undefined,
      category_id: categoryId || undefined,
      skip: (page - 1) * PAGE_SIZE,
      // Fetch one extra product so we know whether another page exists.
      limit: PAGE_SIZE + 1,
    }),
    [searchQuery, categoryId, page],
  );

  const {
    data: productResults = [],
    isLoading,
    isFetching,
    isError,
    refetch,
  } = useProducts(productQuery);

  const { data: categories = [] } = useCategories();

  const hasNextPage = productResults.length > PAGE_SIZE;
  const products = productResults.slice(0, PAGE_SIZE);

  const categoryNameById = useMemo<Map<string, string>>(
    () => new Map(categories.map((category) => [String(category.id), category.name] as const)),
    [categories],
  );

  const handleSearch = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setPage(1);
    setSearchQuery(searchInput.trim());
  };

  const clearFilters = () => {
    setSearchInput("");
    setSearchQuery("");
    setCategoryId("");
    setPage(1);
  };

  const showingFrom = products.length ? (page - 1) * PAGE_SIZE + 1 : 0;
  const showingTo = products.length ? showingFrom + products.length - 1 : 0;

  return (
    <section className="overflow-hidden bg-gray-1 pb-4 pt-3 dark:bg-darkTheme-bg sm:pb-8 sm:pt-10">
      <div className="mx-auto w-full max-w-[1440px] px-4 sm:px-6 lg:px-8 xl:px-10 2xl:px-6">
        {/* Heading */}
        <div className="mb-3 flex items-end justify-between gap-3 sm:mb-5 lg:items-end">
          <div>
            <span className="mb-1 hidden items-center gap-2 text-sm font-medium text-orange sm:flex sm:text-base">
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <path
                  d="M3 7.5 12 3l9 4.5v9L12 21l-9-4.5v-9Z"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinejoin="round"
                />
                <path
                  d="m3.5 7.75 8.5 4.3 8.5-4.3M12 12.05V21"
                  stroke="currentColor"
                  strokeWidth="1.7"
                  strokeLinejoin="round"
                />
              </svg>
              Marketplace Products
            </span>
            <h2 className="text-lg font-bold text-dark dark:text-white sm:text-2xl xl:text-heading-5">
              Explore products from our sellers
            </h2>
            <p className="mt-1 hidden max-w-2xl text-sm text-dark-4 dark:text-darkTheme-secondary-muted sm:block">
              Browse live products published by sellers. Search by product name, description or SKU,
              or filter the catalog by category.
            </p>
          </div>

          <Link
            href="/shop-with-sidebar"
            className="shrink-0 text-xs font-bold text-orange sm:inline-flex sm:w-fit sm:items-center sm:justify-center sm:rounded-lg sm:border sm:border-gray-3 sm:bg-white sm:px-5 sm:py-2.5 sm:text-sm sm:text-dark sm:transition sm:hover:border-orange sm:hover:text-orange dark:sm:border-darkTheme-border-color dark:sm:bg-darkTheme-card dark:sm:text-white"
          >
            Open full shop
          </Link>
        </div>

        {/* Mobile category rail */}
        <div className="xerin-horizontal-scroll -mx-4 mb-4 flex gap-2 px-4 pb-1 sm:hidden">
          <button
            type="button"
            onClick={() => {
              setCategoryId("");
              setPage(1);
            }}
            className={`shrink-0 rounded-full border px-4 py-2 text-xs font-bold ${
              !categoryId
                ? "border-orange bg-orange text-white"
                : "border-gray-3 bg-white text-dark"
            }`}
          >
            All
          </button>
          {categories.map((category) => (
            <button
              key={String(category.id)}
              type="button"
              onClick={() => {
                setCategoryId(String(category.id));
                setPage(1);
              }}
              className={`shrink-0 rounded-full border px-4 py-2 text-xs font-bold ${
                categoryId === String(category.id)
                  ? "border-orange bg-orange text-white"
                  : "border-gray-3 bg-white text-dark"
              }`}
            >
              {category.name}
            </button>
          ))}
        </div>

        {/* Search and filters */}
        <div className="mb-8 hidden rounded-2xl border border-gray-3 bg-white p-4 shadow-sm dark:border-darkTheme-border-color dark:bg-darkTheme-card sm:block sm:p-5">
          <form
            onSubmit={handleSearch}
            className="grid gap-3 md:grid-cols-[minmax(0,1fr)_260px_auto]"
          >
            <div className="relative">
              <svg
                className="absolute left-4 top-1/2 -translate-y-1/2 text-dark-4"
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                aria-hidden="true"
              >
                <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
                <path d="m20 20-4-4" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
              </svg>
              <input
                type="search"
                value={searchInput}
                onChange={(event) => setSearchInput(event.target.value)}
                placeholder="Search products by name, description or SKU..."
                className="h-12 w-full rounded-xl border border-gray-3 bg-gray-1 pl-11 pr-4 text-sm text-dark outline-none transition focus:border-orange focus:ring-2 focus:ring-orange/10 dark:border-darkTheme-border-color dark:bg-darkTheme-secondary-bg dark:text-white"
              />
            </div>

            <select
              value={categoryId}
              onChange={(event) => {
                setCategoryId(event.target.value);
                setPage(1);
              }}
              className="h-12 rounded-xl border border-gray-3 bg-gray-1 px-4 text-sm text-dark outline-none transition focus:border-orange focus:ring-2 focus:ring-orange/10 dark:border-darkTheme-border-color dark:bg-darkTheme-secondary-bg dark:text-white"
              aria-label="Filter products by category"
            >
              <option value="">All categories</option>
              {categories.map((category) => (
                <option key={String(category.id)} value={String(category.id)}>
                  {category.name}
                </option>
              ))}
            </select>

            <button
              type="submit"
              className="h-12 rounded-xl bg-orange px-6 text-sm font-semibold text-white transition hover:bg-orange-dark disabled:cursor-not-allowed disabled:opacity-60"
              disabled={isFetching}
            >
              {isFetching && !isLoading ? "Searching..." : "Search"}
            </button>
          </form>

          {(searchQuery || categoryId) && (
            <div className="mt-4 flex flex-wrap items-center gap-2 text-sm">
              <span className="text-dark-4">Active filters:</span>
              {searchQuery && (
                <span className="rounded-full bg-orange/10 px-3 py-1 font-medium text-orange">
                  Search: {searchQuery}
                </span>
              )}
              {categoryId && (
                <span className="rounded-full bg-orange/10 px-3 py-1 font-medium text-orange">
                  Category: {categoryNameById.get(categoryId) ?? "Selected category"}
                </span>
              )}
              <button
                type="button"
                onClick={clearFilters}
                className="font-semibold text-dark underline-offset-4 hover:text-orange hover:underline dark:text-white"
              >
                Clear filters
              </button>
            </div>
          )}
        </div>

        {/* Results information */}
        <div className="mb-3 hidden flex-wrap items-center justify-between gap-3 sm:flex sm:mb-5">
          <p className="text-sm text-dark-4 dark:text-darkTheme-secondary-muted">
            {isLoading
              ? "Loading products..."
              : products.length
                ? `Showing products ${showingFrom}-${showingTo}`
                : "No products to show"}
          </p>
          <span className="rounded-full bg-white px-3 py-1.5 text-xs font-semibold text-dark shadow-sm dark:bg-darkTheme-card dark:text-white">
            Page {page}
          </span>
        </div>

        {/* Product states */}
        {isLoading ? (
          <div className="grid grid-cols-2 gap-2.5 sm:gap-5 lg:grid-cols-3 xl:grid-cols-4">
            {Array.from({ length: 8 }).map((_, index) => (
              <div
                key={index}
                className="overflow-hidden rounded-2xl border border-gray-3 bg-white shadow-sm dark:border-darkTheme-border-color dark:bg-darkTheme-card"
              >
                <div className="aspect-square animate-pulse bg-gray-2 dark:bg-darkTheme-secondary-bg sm:h-64 sm:aspect-auto" />
                <div className="space-y-2 p-3 sm:space-y-3 sm:p-5">
                  <div className="h-3 w-1/3 animate-pulse rounded bg-gray-2 dark:bg-darkTheme-secondary-bg" />
                  <div className="h-5 w-4/5 animate-pulse rounded bg-gray-2 dark:bg-darkTheme-secondary-bg" />
                  <div className="h-4 w-full animate-pulse rounded bg-gray-2 dark:bg-darkTheme-secondary-bg" />
                  <div className="h-6 w-2/5 animate-pulse rounded bg-gray-2 dark:bg-darkTheme-secondary-bg" />
                </div>
              </div>
            ))}
          </div>
        ) : isError ? (
          <div className="rounded-2xl border border-red-200 bg-red-50 px-6 py-12 text-center">
            <h3 className="font-semibold text-red-700">Products could not be loaded</h3>
            <p className="mt-2 text-sm text-red-600">
              The marketplace API did not return the product catalog. Please try again.
            </p>
            <button
              type="button"
              onClick={() => void refetch()}
              className="mt-5 rounded-lg bg-red-600 px-5 py-2.5 text-sm font-semibold text-white"
            >
              Retry
            </button>
          </div>
        ) : products.length === 0 ? (
          <div className="rounded-2xl border border-gray-3 bg-white px-6 py-14 text-center shadow-sm dark:border-darkTheme-border-color dark:bg-darkTheme-card">
            <h3 className="text-lg font-semibold text-dark dark:text-white">No products found</h3>
            <p className="mt-2 text-sm text-dark-4 dark:text-darkTheme-secondary-muted">
              Try another search term or clear the selected category.
            </p>
            {(searchQuery || categoryId) && (
              <button
                type="button"
                onClick={clearFilters}
                className="mt-5 rounded-lg bg-orange px-5 py-2.5 text-sm font-semibold text-white"
              >
                Show all products
              </button>
            )}
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-2.5 sm:gap-5 lg:grid-cols-3 xl:grid-cols-4">
            {products.map((product) => {
              const uiProduct = mapApiProductToUiProduct(product);
              const imageUrl = uiProduct.imgs?.previews?.[0] ?? "/images/products/placeholder.svg";
              const regularPrice = Number(product.price || 0);
              const salePrice = product.sale_price ? Number(product.sale_price) : null;
              const hasDiscount = salePrice !== null && salePrice > 0 && salePrice < regularPrice;
              const discountPercentage = hasDiscount
                ? Math.round(((regularPrice - salePrice) / regularPrice) * 100)
                : 0;

              return (
                <article
                  key={String(product.id)}
                  className="group flex h-full min-w-0 flex-col overflow-hidden rounded-xl border border-gray-3 bg-white shadow-sm transition duration-300 hover:shadow-lg dark:border-darkTheme-border-color dark:bg-darkTheme-card sm:rounded-2xl sm:hover:-translate-y-1"
                >
                  <Link
                    href={`/products/${product.id}`}
                    className="relative flex aspect-square items-center justify-center overflow-hidden bg-[#f7f8fa] p-2.5 dark:bg-darkTheme-secondary-bg sm:h-64 sm:aspect-auto sm:p-6"
                  >
                    {hasDiscount && (
                      <span className="absolute left-2 top-2 z-10 rounded bg-[#ef4444] px-1.5 py-0.5 text-[10px] font-bold text-white shadow-sm sm:left-4 sm:top-4 sm:rounded-full sm:px-3 sm:py-1 sm:text-xs">
                        -{discountPercentage}%
                      </span>
                    )}
                    <Image
                      src={imageUrl}
                      alt={product.name}
                      width={260}
                      height={260}
                      className="h-full w-full object-contain transition-transform duration-300 group-hover:scale-105"
                    />
                  </Link>

                  <div className="flex flex-1 flex-col p-2.5 sm:p-5">
                    <div className="mb-1 flex items-center justify-between gap-2 sm:mb-2 sm:gap-3">
                      <span className="truncate text-[10px] font-bold uppercase tracking-wide text-orange sm:text-xs sm:font-medium">
                        {categoryNameById.get(String(product.category_id)) ?? "Marketplace"}
                      </span>
                      {product.is_active && product.status === "approved" ? (
                        <span className="hidden rounded-full bg-green-50 px-2.5 py-1 text-[11px] font-semibold text-green-700 dark:bg-green-500/10 dark:text-green-300 sm:inline-flex">
                          Available
                        </span>
                      ) : null}
                    </div>

                    <h3 className="line-clamp-2 min-h-[38px] text-[13px] font-semibold leading-[19px] text-dark transition group-hover:text-orange dark:text-white sm:min-h-[48px] sm:text-base sm:leading-6">
                      <Link href={`/products/${product.id}`}>{product.name}</Link>
                    </h3>

                    <p className="mt-2 hidden line-clamp-2 min-h-[40px] text-sm leading-5 text-dark-4 dark:text-darkTheme-secondary-muted sm:block">
                      {product.description || "Seller-listed product available in the marketplace."}
                    </p>

                    <div className="mt-3 hidden items-center justify-between gap-3 text-xs text-dark-4 dark:text-darkTheme-secondary-muted sm:flex">
                      <span className="truncate">SKU: {product.sku}</span>
                      {typeof product.review_count === "number" && product.review_count > 0 && (
                        <span>{product.review_count} review{product.review_count === 1 ? "" : "s"}</span>
                      )}
                    </div>

                    <div className="mt-2 flex items-end justify-between gap-2 border-t border-gray-3 pt-2 dark:border-darkTheme-border-color sm:mt-4 sm:gap-3 sm:pt-4">
                      <div>
                        <p className="hidden text-xs text-dark-4 dark:text-darkTheme-secondary-muted sm:block">Price</p>
                        <div className="mt-0.5 flex flex-wrap items-center gap-2">
                          <span className="text-[15px] font-extrabold text-[#ef4444] dark:text-white sm:text-lg sm:text-dark">
                            <PriceDisplay amount={hasDiscount ? salePrice! : regularPrice} sourceCurrency={product.currency} />
                          </span>
                          {hasDiscount && (
                            <span className="text-[10px] text-dark-4 line-through sm:text-xs">
                              <PriceDisplay amount={regularPrice} sourceCurrency={product.currency} />
                            </span>
                          )}
                        </div>
                      </div>

                      <Link
                        href={`/products/${product.id}`}
                        className="hidden items-center justify-center rounded-lg bg-dark px-4 py-2.5 text-xs font-semibold text-white transition hover:bg-orange dark:bg-white dark:text-dark dark:hover:bg-orange dark:hover:text-white sm:inline-flex"
                      >
                        View product
                      </Link>
                    </div>
                  </div>
                </article>
              );
            })}
          </div>
        )}

        {/* Pagination */}
        {!isLoading && !isError && (page > 1 || hasNextPage) && (
          <div className="mt-5 flex items-center justify-center gap-2 sm:mt-6 sm:gap-3">
            <button
              type="button"
              onClick={() => {
                setPage((current) => Math.max(1, current - 1));
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              disabled={page === 1 || isFetching}
              className="inline-flex h-10 items-center justify-center rounded-lg border border-gray-3 bg-white px-4 text-sm font-semibold text-dark transition hover:border-orange hover:text-orange disabled:cursor-not-allowed disabled:opacity-40 dark:border-darkTheme-border-color dark:bg-darkTheme-card dark:text-white"
            >
              Previous
            </button>

            <span className="inline-flex h-10 min-w-10 items-center justify-center rounded-lg bg-orange px-4 text-sm font-semibold text-white">
              {page}
            </span>

            <button
              type="button"
              onClick={() => {
                setPage((current) => current + 1);
                window.scrollTo({ top: 0, behavior: "smooth" });
              }}
              disabled={!hasNextPage || isFetching}
              className="inline-flex h-10 items-center justify-center rounded-lg border border-gray-3 bg-white px-4 text-sm font-semibold text-dark transition hover:border-orange hover:text-orange disabled:cursor-not-allowed disabled:opacity-40 dark:border-darkTheme-border-color dark:bg-darkTheme-card dark:text-white"
            >
              Next
            </button>
          </div>
        )}
      </div>
    </section>
  );
};

export default Categories;
