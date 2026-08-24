"use client";

import React, { useState } from "react";
import {
  useApplyCoupon,
  useApplyPromotion,
  useAvailableCartPromotions,
  useCartView,
  useRemoveCoupon,
  useRemovePromotion,
} from "@/hooks/useCartActions";
import PriceDisplay from "@/components/shared/PriceDisplay";

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function Discount() {
  const cart = useCartView();
  const [couponCode, setCouponCode] = useState("");
  const [promotionCode, setPromotionCode] = useState("");

  const applyCoupon = useApplyCoupon();
  const removeCoupon = useRemoveCoupon();
  const applyPromotion = useApplyPromotion();
  const removePromotion = useRemovePromotion();
  const offers = useAvailableCartPromotions(
    cart.isAuthenticated && cart.items.length > 0,
  );

  if (!cart.isAuthenticated) {
    return (
      <div className="w-full rounded-xl border border-amber-200 bg-amber-50 p-5 text-sm text-amber-800">
        Sign in to use seller promotions or platform coupon codes. Your guest cart
        can still be merged after login.
      </div>
    );
  }

  const busy =
    applyCoupon.isPending ||
    removeCoupon.isPending ||
    applyPromotion.isPending ||
    removePromotion.isPending;

  return (
    <div className="w-full space-y-5">
      <section className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
        <p className="text-xs font-bold uppercase tracking-[.14em] text-orange">
          Customer Phase 3
        </p>
        <h3 className="mt-1 text-lg font-bold text-dark dark:text-white">
          Seller Promotions
        </h3>
        <p className="mt-1 text-sm leading-6 text-dark-4">
          Seller-funded discounts apply only to eligible products. Xerin
          marketplace commission remains separate from the seller discount.
        </p>

        {cart.promotion ? (
          <div className="mt-4 rounded-xl border border-emerald-200 bg-emerald-50 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-sm font-bold text-emerald-800">
                  {cart.promotion.name}
                  {cart.promotion.code ? ` · ${cart.promotion.code}` : ""}
                </p>
                <p className="mt-1 text-xs text-emerald-700">
                  {pretty(cart.promotion.promotion_type)}
                  {" · "}
                  Eligible subtotal{" "}
                  <PriceDisplay amount={Number(cart.promotion.eligible_subtotal)} sourceCurrency="TZS" />
                </p>
                <p className="mt-1 text-xs font-semibold text-emerald-800">
                  Seller promotion discount:{" "}
                  <PriceDisplay amount={Number(cart.promotion.discount_amount)} sourceCurrency="TZS" />
                </p>
                {cart.promotion.promotion_type === "free_shipping" && (
                  <p className="mt-1 text-xs text-emerald-700">
                    The shipping benefit will be applied when delivery is selected
                    in the next phase.
                  </p>
                )}
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => removePromotion.mutate()}
                className="text-xs font-bold text-red-600 disabled:opacity-50"
              >
                Remove
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="mt-4 flex flex-col gap-2 sm:flex-row">
              <input
                value={promotionCode}
                onChange={(event) =>
                  setPromotionCode(
                    event.target.value.toUpperCase().replace(/\s+/g, ""),
                  )
                }
                placeholder="Enter seller promo code"
                className="h-11 min-w-0 flex-1 rounded-xl border border-gray-3 bg-gray-1 px-4 text-sm outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
              <button
                type="button"
                disabled={busy || !promotionCode.trim()}
                onClick={() => applyPromotion.mutate(promotionCode.trim())}
                className="rounded-xl bg-orange px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {applyPromotion.isPending ? "Applying..." : "Apply Promotion"}
              </button>
            </div>

            {offers.data && offers.data.length > 0 && (
              <div className="mt-5">
                <p className="text-xs font-bold uppercase tracking-wide text-dark-4">
                  Eligible offers for this cart
                </p>
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  {offers.data.slice(0, 6).map((offer) => (
                    <button
                      type="button"
                      key={offer.promotion_id}
                      disabled={
                        busy ||
                        !offer.code ||
                        (Boolean(cart.couponCode) && !offer.stackable)
                      }
                      onClick={() =>
                        offer.code && applyPromotion.mutate(offer.code)
                      }
                      className="rounded-xl border border-orange/20 bg-orange/5 p-4 text-left transition hover:border-orange disabled:cursor-not-allowed disabled:opacity-50"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-dark dark:text-white">
                            {offer.name}
                          </p>
                          <p className="mt-1 text-xs text-dark-4">
                            {pretty(offer.promotion_type)}
                            {offer.code ? ` · ${offer.code}` : " · Automatic"}
                          </p>
                        </div>
                        <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold uppercase text-orange shadow-sm">
                          Seller funded
                        </span>
                      </div>

                      <p className="mt-3 text-sm font-bold text-emerald-700">
                        {offer.promotion_type === "free_shipping" ? (
                          "Free shipping benefit"
                        ) : (
                          <>Save <PriceDisplay amount={Number(offer.discount_amount)} sourceCurrency="TZS" /></>
                        )}
                      </p>

                      {!offer.stackable && cart.couponCode && (
                        <p className="mt-2 text-[11px] text-amber-700">
                          Remove the current coupon before using this offer.
                        </p>
                      )}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </section>

      <section className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
        <h3 className="font-bold text-dark dark:text-white">
          Platform Coupon
        </h3>
        <p className="mt-1 text-sm text-dark-4">
          Platform/admin coupons are separate from seller-funded promotions.
        </p>

        {cart.couponCode ? (
          <div className="mt-4 flex items-center justify-between gap-4 rounded-xl border border-blue-200 bg-blue-50 p-4">
            <div>
              <p className="text-sm font-bold text-blue-800">
                {cart.couponCode}
              </p>
              <p className="mt-1 text-xs text-blue-700">
                Coupon discount:{" "}
                <PriceDisplay amount={cart.couponDiscountAmount} sourceCurrency="TZS" />
              </p>
            </div>
            <button
              type="button"
              disabled={busy}
              onClick={() => removeCoupon.mutate()}
              className="text-xs font-bold text-red-600 disabled:opacity-50"
            >
              Remove
            </button>
          </div>
        ) : (
          <form
            className="mt-4 flex flex-col gap-2 sm:flex-row"
            onSubmit={(event) => {
              event.preventDefault();
              if (couponCode.trim()) {
                applyCoupon.mutate(couponCode.trim().toUpperCase());
              }
            }}
          >
            <input
              value={couponCode}
              onChange={(event) =>
                setCouponCode(
                  event.target.value.toUpperCase().replace(/\s+/g, ""),
                )
              }
              placeholder="Enter platform coupon code"
              className="h-11 min-w-0 flex-1 rounded-xl border border-gray-3 bg-gray-1 px-4 text-sm outline-none focus:border-orange dark:border-white/10 dark:bg-white/5 dark:text-white"
            />
            <button
              disabled={busy || !couponCode.trim()}
              className="rounded-xl bg-dark px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              {applyCoupon.isPending ? "Applying..." : "Apply Coupon"}
            </button>
          </form>
        )}
      </section>
    </div>
  );
}
