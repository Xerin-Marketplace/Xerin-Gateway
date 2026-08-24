"use client";

import Breadcrumb from "@/components/Common/Breadcrumb";
import Discount from "@/components/Cart/Discount";
import {
  useCartView,
  useClearCart,
  useRemoveCartItem,
  useUpdateCartItem,
  useValidateCart,
} from "@/hooks/useCartActions";
import PriceDisplay from "@/components/shared/PriceDisplay";
import Link from "next/link";
import {
  CircleAlert,
  RefreshCw,
  ShieldCheck,
  ShoppingCart,
  Tag,
} from "lucide-react";

export default function Cart() {
  const cart = useCartView();
  const update = useUpdateCartItem();
  const remove = useRemoveCartItem();
  const clear = useClearCart();
  const validate = useValidateCart();

  const busy =
    update.isPending ||
    remove.isPending ||
    clear.isPending ||
    validate.isPending;

  const hasBlockingValidation = cart.validationMessages.some((message) =>
    /no longer available|inventory is not configured|only \d+ item/i.test(
      message,
    ),
  );

  return (
    <>
      <Breadcrumb title="Cart" pages={["Cart"]} />

      <section className="bg-gray-2 py-12 dark:bg-darkTheme-bg sm:py-16">
        <div className="mx-auto max-w-[1240px] px-4 sm:px-8">
          {cart.isLoading ? (
            <div className="rounded-2xl bg-white p-14 text-center dark:bg-darkTheme-card">
              <RefreshCw className="mx-auto animate-spin" size={20} />
              <p className="mt-3">Loading your cart...</p>
            </div>
          ) : cart.error ? (
            <div className="rounded-2xl border border-red-200 bg-red-50 p-10 text-center text-red-700">
              <p>Your cart could not be loaded. Your account cart was not changed.</p>
              <button
                onClick={() => void cart.refetch()}
                className="mt-3 font-semibold underline"
              >
                Retry
              </button>
            </div>
          ) : !cart.items.length ? (
            <div className="rounded-2xl bg-white p-14 text-center dark:bg-darkTheme-card">
              <ShoppingCart size={32} className="mx-auto text-gray-4" />
              <h2 className="mt-3 text-xl font-semibold">Your cart is empty</h2>
              <p className="mt-2 text-dark-4">
                Browse approved seller products and add items to your cart.
              </p>
              <Link
                href="/search"
                className="mt-5 inline-block rounded-xl bg-dark px-6 py-3 font-medium text-white"
              >
                Continue Shopping
              </Link>
            </div>
          ) : (
            <>
              <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
                <div>
                  <p className="text-xs font-bold uppercase tracking-[.14em] text-orange">
                    Customer Phase 3
                  </p>
                  <h1 className="mt-1 text-2xl font-bold text-dark dark:text-white">
                    Cart & Promotions
                  </h1>
                  <p className="mt-1 text-sm text-dark-4">
                    Prices and stock are revalidated by the backend before checkout.
                  </p>
                </div>

                <div className="flex flex-wrap gap-2">
                  {cart.isAuthenticated && (
                    <button
                      disabled={busy}
                      onClick={() => validate.mutate()}
                      className="inline-flex items-center gap-2 rounded-xl border border-gray-3 bg-white px-4 py-2.5 text-sm font-semibold disabled:opacity-50 dark:border-white/10 dark:bg-darkTheme-card"
                    >
                      <RefreshCw
                        size={14}
                        className={validate.isPending ? "animate-spin" : ""}
                      />
                      Refresh Price & Stock
                    </button>
                  )}
                  <button
                    disabled={busy}
                    onClick={() => clear.mutate()}
                    className="rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600 disabled:opacity-50"
                  >
                    {clear.isPending ? "Clearing..." : "Clear Cart"}
                  </button>
                </div>
              </div>

              {!cart.isAuthenticated && (
                <div className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-800">
                  Guest cart — sign in to sync items, use seller promotions and
                  proceed through secure checkout.
                </div>
              )}

              {cart.validationMessages.length > 0 && (
                <div className="mb-5 rounded-2xl border border-amber-200 bg-amber-50 p-4">
                  <div className="flex items-start gap-3">
                    <CircleAlert
                      size={18}
                      className="mt-0.5 shrink-0 text-amber-700"
                    />
                    <div>
                      <p className="text-sm font-bold text-amber-800">
                        Cart needs your attention
                      </p>
                      <ul className="mt-2 space-y-1 text-xs leading-5 text-amber-700">
                        {cart.validationMessages.map((message, index) => (
                          <li key={`${message}-${index}`}>• {message}</li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>
              )}

              <div className="grid gap-6 xl:grid-cols-[1fr_390px]">
                <div className="space-y-6">
                  <div className="overflow-x-auto rounded-2xl bg-white shadow-sm dark:bg-darkTheme-card">
                    <table className="w-full min-w-[850px] text-left">
                      <thead className="bg-gray-1 text-xs font-bold uppercase tracking-wide text-dark-4 dark:bg-white/5">
                        <tr>
                          {["Product", "Customer Price", "Quantity", "Subtotal", ""].map(
                            (heading) => (
                              <th key={heading} className="px-6 py-4">
                                {heading}
                              </th>
                            ),
                          )}
                        </tr>
                      </thead>

                      <tbody className="divide-y dark:divide-white/10">
                        {cart.items.map((item) => (
                          <tr key={item.cartItemId}>
                            <td className="px-6 py-5">
                              <Link
                                className="font-semibold hover:text-orange"
                                href={`/products/${item.productId}`}
                              >
                                {item.title}
                              </Link>
                              <p className="mt-1 text-[11px] text-dark-4">
                                Backend-priced cart item
                              </p>
                            </td>

                            <td className="px-6 py-5 font-semibold">
                              {formatCurrency(
                                item.discountedPrice,
                                cart.currency,
                              )}
                            </td>

                            <td className="px-6 py-5">
                              <div className="inline-flex items-center overflow-hidden rounded-xl border border-gray-3 dark:border-white/10">
                                <button
                                  disabled={busy || item.quantity <= 1}
                                  onClick={() =>
                                    update.mutate({
                                      itemId: item.cartItemId,
                                      quantity: item.quantity - 1,
                                    })
                                  }
                                  className="px-3 py-2 disabled:opacity-40"
                                >
                                  −
                                </button>
                                <span className="border-x border-gray-3 px-4 py-2 dark:border-white/10">
                                  {item.quantity}
                                </span>
                                <button
                                  disabled={busy}
                                  onClick={() =>
                                    update.mutate({
                                      itemId: item.cartItemId,
                                      quantity: item.quantity + 1,
                                    })
                                  }
                                  className="px-3 py-2 disabled:opacity-40"
                                >
                                  +
                                </button>
                              </div>
                            </td>

                            <td className="px-6 py-5 font-bold">
                              {formatCurrency(
                                item.discountedPrice * item.quantity,
                                cart.currency,
                              )}
                            </td>

                            <td className="px-6 py-5 text-right">
                              <button
                                disabled={busy}
                                onClick={() =>
                                  remove.mutate(item.cartItemId)
                                }
                                className="font-semibold text-red-600 disabled:opacity-40"
                              >
                                Remove
                              </button>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>

                  <Discount />
                </div>

                <aside className="h-fit rounded-2xl border border-[#e7ebf0] bg-white p-6 shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
                  <div className="flex items-center gap-3">
                    <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange/10 text-orange">
                      <ShieldCheck size={19} />
                    </span>
                    <div>
                      <h2 className="font-bold text-dark dark:text-white">
                        Order Summary
                      </h2>
                      <p className="mt-0.5 text-xs text-dark-4">
                        Backend-calculated totals
                      </p>
                    </div>
                  </div>

                  <div className="mt-6 space-y-3 text-sm">
                    <Row
                      label="Product subtotal"
                      value={<PriceDisplay amount={cart.subtotal} sourceCurrency="TZS" />}
                    />

                    {cart.promotionDiscountAmount > 0 && (
                      <Row
                        label="Seller promotion"
                        value={`-${formatCurrency(
                          cart.promotionDiscountAmount,
                          cart.currency,
                        )}`}
                        saving
                      />
                    )}

                    {cart.couponDiscountAmount > 0 && (
                      <Row
                        label="Platform coupon"
                        value={`-${formatCurrency(
                          cart.couponDiscountAmount,
                          cart.currency,
                        )}`}
                        saving
                      />
                    )}

                    {cart.promotion?.promotion_type === "free_shipping" && (
                      <div className="flex items-start gap-2 rounded-lg bg-emerald-50 p-3 text-xs leading-5 text-emerald-700">
                        <Tag size={14} className="mt-0.5 shrink-0" />
                        Free-shipping promotion saved. Its delivery benefit will
                        be resolved when a logistics service is selected.
                      </div>
                    )}

                    <div className="border-t border-gray-3 pt-4 dark:border-white/10">
                      <Row
                        label="Cart total"
                        value={<PriceDisplay amount={cart.total} sourceCurrency="TZS" />}
                        strong
                      />
                    </div>
                  </div>

                  <p className="mt-4 text-xs leading-5 text-dark-4">
                    Shipping is intentionally excluded until Customer Phase 4,
                    where the selected local/global logistics service will provide
                    the delivery price.
                  </p>

                  <Link
                    href={
                      !cart.isAuthenticated
                        ? "/signin?redirect=/cart"
                        : hasBlockingValidation
                          ? "#"
                          : "/checkout"
                    }
                    aria-disabled={hasBlockingValidation}
                    className={`mt-6 flex justify-center rounded-xl px-6 py-3 font-semibold text-white ${
                      hasBlockingValidation
                        ? "pointer-events-none bg-gray-4"
                        : "bg-orange hover:bg-orange-dark"
                    }`}
                  >
                    {!cart.isAuthenticated
                      ? "Sign in to Continue"
                      : hasBlockingValidation
                        ? "Fix Cart Before Checkout"
                        : "Continue to Delivery"}
                  </Link>
                </aside>
              </div>
            </>
          )}
        </div>
      </section>
    </>
  );
}

function Row({
  label,
  value,
  saving = false,
  strong = false,
}: {
  label: string;
  value: React.ReactNode;
  saving?: boolean;
  strong?: boolean;
}) {
  return (
    <div className={`flex items-center justify-between gap-4 ${strong ? "text-lg" : ""}`}>
      <span className={strong ? "font-bold" : "text-dark-4"}>{label}</span>
      <span
        className={
          saving
            ? "font-bold text-emerald-700"
            : strong
              ? "font-bold"
              : "font-semibold"
        }
      >
        {value}
      </span>
    </div>
  );
}
