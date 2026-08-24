"use client";
import React, { useEffect, useState } from "react";

import { useCartModalContext } from "@/app/context/CartSidebarModalContext";
import { useCartView } from "@/hooks/useCartActions";
import SingleItem from "./SingleItem";
import Link from "next/link";
import EmptyCart from "./EmptyCart";
import PriceDisplay from "@/components/shared/PriceDisplay";

const CartSidebarModal = () => {
  const { isCartModalOpen, closeCartModal } = useCartModalContext();
  const { items: cartItems, total: totalPrice, isAuthenticated } = useCartView();

  useEffect(() => {
    // closing modal while clicking outside
    function handleClickOutside(event) {
      if (!event.target.closest(".modal-content")) {
        closeCartModal();
      }
    }

    if (isCartModalOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }

    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [isCartModalOpen, closeCartModal]);

  return (
    <div
      aria-hidden={!isCartModalOpen}
      className={`fixed inset-0 z-99999 w-full overflow-hidden bg-dark/70 ease-linear duration-300 ${
        isCartModalOpen ? "visible translate-x-0 opacity-100" : "invisible pointer-events-none translate-x-full opacity-0"
      }`}
    >
      <div className="flex min-h-[100dvh] items-stretch justify-end">
        <div className="modal-content relative flex h-[100dvh] w-full max-w-[500px] flex-col bg-white px-4 shadow-1 dark:bg-darkTheme-card sm:px-7.5 lg:px-11">
          <div className="z-10 flex shrink-0 items-center justify-between border-b border-gray-3 bg-white pb-4 pt-[max(14px,env(safe-area-inset-top))] dark:border-darkTheme-border-color dark:bg-darkTheme-card sm:pb-7 sm:pt-7.5 lg:pt-11">
            <h2 className="font-medium text-dark dark:text-white text-lg sm:text-2xl">
              Cart View
            </h2>
            <button
              onClick={() => closeCartModal()}
              aria-label="button for close modal"
              className="flex items-center justify-center ease-in duration-150 bg-meta text-dark-4 dark:text-darkTheme-secondary-muted hover:text-dark dark:hover:text-white"
            >
              <svg
                className="fill-current"
                width="30"
                height="30"
                viewBox="0 0 30 30"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
              >
                <path
                  d="M12.5379 11.2121C12.1718 10.846 11.5782 10.846 11.212 11.2121C10.8459 11.5782 10.8459 12.1718 11.212 12.5379L13.6741 15L11.2121 17.4621C10.846 17.8282 10.846 18.4218 11.2121 18.7879C11.5782 19.154 12.1718 19.154 12.5379 18.7879L15 16.3258L17.462 18.7879C17.8281 19.154 18.4217 19.154 18.7878 18.7879C19.154 18.4218 19.154 17.8282 18.7878 17.462L16.3258 15L18.7879 12.5379C19.154 12.1718 19.154 11.5782 18.7879 11.2121C18.4218 10.846 17.8282 10.846 17.462 11.2121L15 13.6742L12.5379 11.2121Z"
                  fill=""
                />
                <path
                  fillRule="evenodd"
                  clipRule="evenodd"
                  d="M15 1.5625C7.57867 1.5625 1.5625 7.57867 1.5625 15C1.5625 22.4213 7.57867 28.4375 15 28.4375C22.4213 28.4375 28.4375 22.4213 28.4375 15C28.4375 7.57867 22.4213 1.5625 15 1.5625ZM3.4375 15C3.4375 8.61421 8.61421 3.4375 15 3.4375C21.3858 3.4375 26.5625 8.61421 26.5625 15C26.5625 21.3858 21.3858 26.5625 15 26.5625C8.61421 26.5625 3.4375 21.3858 3.4375 15Z"
                  fill=""
                />
              </svg>
            </button>
          </div>

          <div className="no-scrollbar min-h-0 flex-1 overflow-y-auto py-4 sm:py-7.5">
            <div className="flex flex-col gap-6">
              {/* <!-- cart item --> */}
              {cartItems.length > 0 ? (
                cartItems.map((item, key) => (
                  <SingleItem
                    key={key}
                    item={item}
                  />
                ))
              ) : (
                <EmptyCart />
              )}
            </div>
          </div>

          {cartItems.length > 0 && <div className="shrink-0 border-t border-gray-3 bg-white pb-[calc(var(--xerin-mobile-nav-height)+var(--xerin-safe-bottom)+10px)] pt-4 dark:border-darkTheme-border-color dark:bg-darkTheme-card sm:pb-7.5 sm:pt-5 lg:pb-11">
            <div className="flex items-center justify-between gap-5 mb-6">
              <p className="font-medium text-xl text-dark dark:text-white">Subtotal:</p>

              <p className="font-medium text-xl text-dark dark:text-white"><PriceDisplay amount={totalPrice} sourceCurrency="TZS" /></p>
            </div>

            <div className="grid grid-cols-2 gap-2.5 sm:flex sm:items-center sm:gap-4">
              <Link
                onClick={() => closeCartModal()}
                href="/cart"
                className="flex h-12 w-full items-center justify-center rounded-xl bg-blue px-3 text-sm font-semibold text-white transition hover:bg-blue-dark sm:rounded-md sm:px-6 sm:font-medium"
              >
                View Cart
              </Link>

              <Link
                href={isAuthenticated ? "/checkout" : "/signin?redirect=/checkout"}
                className="flex h-12 w-full items-center justify-center rounded-xl bg-dark px-3 text-sm font-semibold text-white transition hover:bg-opacity-95 sm:rounded-md sm:px-6 sm:font-medium"
              >
                Checkout
              </Link>
            </div>
          </div>}
        </div>
      </div>
    </div>
  );
};

export default CartSidebarModal;
