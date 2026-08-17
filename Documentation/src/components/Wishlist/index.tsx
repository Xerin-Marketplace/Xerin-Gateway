"use client";

import React, { useState } from "react";
import Breadcrumb from "../Common/Breadcrumb";
import { useWishlistStore } from "@/store/useWishlistStore";
import {
  mapWishlistToUi,
  useClearWishlist,
  useWishlist,
} from "@/hooks/useWishlist";
import SingleItem from "./SingleItem";
import { useAuthStore } from "@/store/useAuthStore";

const PAGE_SIZE = 20;

export const Wishlist = () => {
  const [page, setPage] = useState(1);
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const {
    data: backendWishlist,
    isLoading,
    isFetching,
  } = useWishlist({ page, page_size: PAGE_SIZE });

  const guestWishlistItems = useWishlistStore((state) => state.items);
  const removeAllItemsFromWishlist = useWishlistStore(
    (state) => state.removeAllItemsFromWishlist,
  );
  const clearBackendWishlist = useClearWishlist();

  const wishlistItems = isAuthenticated
    ? mapWishlistToUi(backendWishlist?.results ?? [])
    : guestWishlistItems;

  const total = isAuthenticated
    ? backendWishlist?.total ?? 0
    : guestWishlistItems.length;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <>
      <Breadcrumb title="Wishlist" pages={["Wishlist"]} />
      <section className="overflow-hidden bg-gray-2 py-16 dark:bg-darkTheme-bg">
        <div className="mx-auto w-full max-w-[1170px] px-4 sm:px-8 xl:px-0">
          <div className="mb-7 flex flex-wrap items-end justify-between gap-5">
            <div>
              <p className="text-xs font-bold uppercase tracking-[.14em] text-orange">
                Customer Phase 2
              </p>
              <h2 className="mt-1 text-2xl font-semibold text-dark dark:text-white">
                Your Wishlist
              </h2>
              <p className="mt-1 text-sm text-dark-4">
                {total} saved product{total === 1 ? "" : "s"}. Availability is
                rechecked by the backend before purchase.
              </p>
            </div>

            {wishlistItems.length > 0 && (
              <button
                onClick={() => {
                  if (isAuthenticated) clearBackendWishlist.mutate();
                  else removeAllItemsFromWishlist();
                }}
                disabled={clearBackendWishlist.isPending}
                className="rounded-lg border border-red-200 px-4 py-2 text-sm font-semibold text-red-600 disabled:opacity-50"
              >
                {clearBackendWishlist.isPending
                  ? "Clearing..."
                  : "Clear Wishlist"}
              </button>
            )}
          </div>

          <div className="overflow-hidden rounded-2xl bg-white shadow-sm dark:bg-darkTheme-card">
            {isLoading ? (
              <div className="p-14 text-center text-dark-4">
                Loading wishlist...
              </div>
            ) : (
              <div className="w-full overflow-x-auto">
                <div className="min-w-[1170px]">
                  <div className="flex items-center bg-gray-1 px-10 py-4 text-xs font-bold uppercase tracking-wide text-dark-4 dark:bg-white/5">
                    <div className="min-w-[83px]" />
                    <div className="min-w-[387px]">Product</div>
                    <div className="min-w-[205px]">Customer Price</div>
                    <div className="min-w-[265px]">Availability</div>
                    <div className="min-w-[150px] text-right">Action</div>
                  </div>

                  {wishlistItems.map((item) => (
                    <SingleItem item={item} key={item.id} />
                  ))}

                  {!wishlistItems.length && (
                    <div className="px-10 py-14 text-center text-dark-4">
                      Your wishlist is empty. Browse approved marketplace products
                      and save items you want to compare later.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>

          {isAuthenticated && total > PAGE_SIZE && (
            <div className="mt-6 flex items-center justify-center gap-3">
              <button
                type="button"
                disabled={page <= 1 || isFetching}
                onClick={() => setPage((value) => Math.max(1, value - 1))}
                className="rounded-lg border border-gray-3 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"
              >
                Previous
              </button>
              <span className="text-sm text-dark-4">
                Page {page} of {totalPages}
              </span>
              <button
                type="button"
                disabled={page >= totalPages || isFetching}
                onClick={() => setPage((value) => value + 1)}
                className="rounded-lg border border-gray-3 bg-white px-4 py-2 text-sm font-semibold disabled:opacity-40"
              >
                Next
              </button>
            </div>
          )}
        </div>
      </section>
    </>
  );
};
