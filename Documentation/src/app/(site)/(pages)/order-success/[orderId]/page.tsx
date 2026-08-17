"use client";

import Link from "next/link";
import { useParams, useSearchParams } from "next/navigation";
import { useMemo, useState } from "react";
import toast from "react-hot-toast";
import {
  AlertTriangle,
  CheckCircle2,
  CreditCard,
  RefreshCw,
  Smartphone,
} from "lucide-react";
import { useMyPayments, useOrder } from "@/hooks/useCommerce";
import { paymentsApi } from "@/lib/api/endpoints/commerce";
import { formatCurrency } from "@/lib/formatCurrency";
import type {
  PaymentProviderErrorDetail,
} from "@/types/api/commerce";

type RetryContext = {
  method?: string;
  provider?: string;
  phone_number?: string;
};

const retryStorageKey = (orderId: string) =>
  `xerin:payment-retry:${orderId}`;

const readRetryContext = (orderId: string): RetryContext => {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(
      sessionStorage.getItem(retryStorageKey(orderId)) || "{}",
    ) as RetryContext;
  } catch {
    return {};
  }
};

export default function OrderSuccessPage() {
  const params = useParams<{ orderId: string }>();
  const searchParams = useSearchParams();
  const orderId = params.orderId;
  const order = useOrder(orderId);
  const payments = useMyPayments({
    page: 1,
    page_size: 100,
  });

  const [retrying, setRetrying] = useState(false);
  const [retryContext, setRetryContext] = useState<RetryContext>(() =>
    readRetryContext(orderId),
  );

  const paymentIdFromQuery = searchParams.get("payment_id");
  const payment = useMemo(() => {
    const orderPayments = (payments.data?.results ?? [])
      .filter((item) => item.order_id === orderId)
      .sort(
        (a, b) =>
          new Date(b.created_at).getTime() -
          new Date(a.created_at).getTime(),
      );

    if (paymentIdFromQuery) {
      return (
        orderPayments.find((item) => item.id === paymentIdFromQuery) ??
        orderPayments[0]
      );
    }
    return orderPayments[0];
  }, [payments.data, orderId, paymentIdFromQuery]);

  const queryPaymentState = searchParams.get("payment");
  const retryableFromQuery =
    searchParams.get("retryable") !== "0";

  if (order.isLoading || payments.isLoading) {
    return (
      <section className="py-20 text-center">
        Loading order confirmation…
      </section>
    );
  }

  if (order.error || !order.data) {
    return (
      <section className="py-20 text-center">
        <h1 className="text-2xl font-semibold">
          Order confirmation is unavailable
        </h1>
        <Link
          href="/account/orders"
          className="mt-4 inline-block text-blue"
        >
          View your orders
        </Link>
      </section>
    );
  }

  const data = order.data;
  const paymentFailed =
    queryPaymentState === "failed" ||
    payment?.status === "failed";
  const paymentCompleted = payment?.status === "completed";
  const canRetry =
    data.status === "pending" &&
    Boolean(payment) &&
    ["failed", "cancelled"].includes(payment?.status ?? "") &&
    !paymentCompleted &&
    retryableFromQuery &&
    Boolean(retryContext.method);

  const retryPayment = async () => {
    if (!retryContext.method) {
      toast.error(
        "Payment details are unavailable. Open the order and start payment again.",
      );
      return;
    }

    setRetrying(true);
    try {
      const successUrl = `${window.location.origin}/order-success/${data.id}?payment=success`;
      const failureUrl = `${window.location.origin}/order-success/${data.id}?payment=failed&retryable=1`;

      if (!payment) {
        toast.error("The failed payment attempt could not be found. Refresh the page and try again.");
        return;
      }

      const nextPayment = await paymentsApi.retry(payment.id, {
        provider: retryContext.provider,
        phone_number: retryContext.phone_number,
        success_url:
          retryContext.method === "card" ? successUrl : undefined,
        failure_url:
          retryContext.method === "card" ? failureUrl : undefined,
      });

      const checkoutUrl =
        nextPayment.provider_response?.checkout_url;
      if (
        retryContext.method === "card" &&
        checkoutUrl
      ) {
        window.location.assign(checkoutUrl);
        return;
      }

      toast.success(
        nextPayment.status === "processing"
          ? "Payment request sent. Complete it with your payment provider."
          : "Payment request started.",
      );
      await payments.refetch();
      window.history.replaceState(
        null,
        "",
        `/order-success/${data.id}?payment_id=${nextPayment.id}&payment=${nextPayment.status}`,
      );
    } catch (error: unknown) {
      const candidate = error as {
        response?: {
          data?: {
            detail?: string | PaymentProviderErrorDetail;
          };
        };
        message?: string;
      };
      const detail = candidate.response?.data?.detail;
      toast.error(
        typeof detail === "string"
          ? detail
          : detail?.message ||
              candidate.message ||
              "Payment provider is still unavailable. Please retry later.",
      );
      await payments.refetch();
    } finally {
      setRetrying(false);
    }
  };

  return (
    <section className="bg-gray-2 py-16 dark:bg-darkTheme-bg">
      <div className="mx-auto max-w-2xl space-y-5 px-4">
        <div className="rounded-2xl bg-white p-8 shadow-1 dark:bg-darkTheme-card">
          <p className="font-semibold text-green">
            Order received
          </p>
          <h1 className="mt-2 text-3xl font-semibold text-dark dark:text-white">
            Thank you for your order
          </h1>

          <dl className="mt-8 grid gap-4 sm:grid-cols-2">
            <div>
              <dt className="text-sm text-dark-4">
                Order number
              </dt>
              <dd className="break-all font-medium">
                {data.id}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-dark-4">
                Order status
              </dt>
              <dd className="font-medium capitalize">
                {data.status}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-dark-4">
                Payment status
              </dt>
              <dd className="font-medium capitalize">
                {payment?.status ??
                  (paymentFailed ? "failed to start" : "pending")}
              </dd>
            </div>
            <div>
              <dt className="text-sm text-dark-4">
                Total
              </dt>
              <dd className="font-medium">
                {formatCurrency(data.total, data.currency)}
              </dd>
            </div>
          </dl>
        </div>

        {paymentFailed && !paymentCompleted && (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 text-amber-900">
            <div className="flex items-start gap-3">
              <AlertTriangle
                size={20}
                className="mt-0.5 shrink-0"
              />
              <div className="min-w-0 flex-1">
                <h2 className="font-bold">
                  Your order is safe — payment did not start
                </h2>
                <p className="mt-1 text-sm leading-6">
                  You do not need to rebuild your cart. Xerin
                  already created this order for{" "}
                  <b>
                    {formatCurrency(
                      data.total,
                      data.currency,
                    )}
                  </b>
                  . Retry the payment against the same order.
                </p>

                {retryContext.method && (
                  <div className="mt-4 rounded-xl bg-white/70 p-3 text-sm">
                    <div className="flex items-center gap-2 font-semibold">
                      {retryContext.method === "mobile_money" ? (
                        <Smartphone size={15} />
                      ) : (
                        <CreditCard size={15} />
                      )}
                      {retryContext.method.replaceAll("_", " ")}
                      {retryContext.provider
                        ? ` · ${retryContext.provider}`
                        : ""}
                    </div>
                    {retryContext.phone_number && (
                      <p className="mt-1 text-xs">
                        {retryContext.phone_number}
                      </p>
                    )}
                  </div>
                )}

                <button
                  type="button"
                  disabled={!canRetry || retrying}
                  onClick={() => void retryPayment()}
                  className="mt-4 inline-flex items-center gap-2 rounded-xl bg-[#f7941d] px-4 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <RefreshCw
                    size={14}
                    className={retrying ? "animate-spin" : ""}
                  />
                  {retrying ? "Retrying..." : "Retry Payment"}
                </button>

                {!payment && (
                  <p className="mt-3 text-xs">
                    The failed payment attempt is still loading. Refresh this page before retrying.
                  </p>
                )}

                {!retryContext.method && (
                  <p className="mt-3 text-xs">
                    The original payment details are not stored in this
                    browser session. Open the order details to continue.
                  </p>
                )}
              </div>
            </div>
          </div>
        )}

        {paymentCompleted && (
          <div className="flex items-start gap-3 rounded-2xl border border-emerald-200 bg-emerald-50 p-5 text-emerald-800">
            <CheckCircle2 size={20} className="mt-0.5" />
            <div>
              <p className="font-bold">
                Payment confirmed
              </p>
              <p className="mt-1 text-sm">
                Your order is now moving through fulfilment.
              </p>
            </div>
          </div>
        )}

        <div className="rounded-2xl bg-white p-6 shadow-1 dark:bg-darkTheme-card">
          <p className="text-dark-4">
            Delivery progress and status updates will appear in
            your order details.
          </p>
          <div className="mt-6 flex flex-wrap gap-3">
            <Link
              href={`/account/orders/${data.id}`}
              className="rounded-lg bg-blue px-5 py-3 font-medium text-white"
            >
              View order
            </Link>
            <Link
              href="/shop-with-sidebar"
              className="rounded-lg border border-gray-3 px-5 py-3 font-medium"
            >
              Continue shopping
            </Link>
          </div>
        </div>
      </div>
    </section>
  );
}
