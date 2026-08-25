"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";
import {
  BadgeCheck,
  Download,
  FileText,
  LoaderCircle,
  ReceiptText,
  ShieldCheck,
} from "lucide-react";
import { useOrder } from "@/hooks/useCommerce";
import { ordersApi, paymentsApi } from "@/lib/api/endpoints/commerce";
import { formatCurrency } from "@/lib/formatCurrency";
import type { OrderPaymentState } from "@/types/api/commerce";

export default function PaymentSuccessPage() {
  const params = useParams<{ orderId: string }>();
  const orderId = params.orderId;
  const order = useOrder(orderId);
  const [paymentState, setPaymentState] = useState<OrderPaymentState | null>(null);
  const [loadingState, setLoadingState] = useState(true);
  const [downloading, setDownloading] = useState<"invoice" | "receipt" | null>(null);

  useEffect(() => {
    let active = true;
    paymentsApi.orderState(orderId)
      .then((state) => {
        if (active) setPaymentState(state);
      })
      .catch(() => {
        if (active) toast.error("Unable to verify the latest payment state.");
      })
      .finally(() => {
        if (active) setLoadingState(false);
      });
    return () => { active = false; };
  }, [orderId]);

  const download = async (kind: "invoice" | "receipt") => {
    setDownloading(kind);
    try {
      const blob = kind === "receipt"
        ? await ordersApi.receipt(orderId)
        : await ordersApi.invoice(orderId);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = `Xerin-${kind === "receipt" ? "Receipt" : "Invoice"}-${orderId.slice(0, 8).toUpperCase()}.pdf`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast.error(`Unable to download the ${kind}. Please try again.`);
    } finally {
      setDownloading(null);
    }
  };

  if (order.isLoading || loadingState) {
    return (
      <main className="min-h-screen bg-slate-50 px-4 py-16 dark:bg-darkTheme-bg">
        <div className="mx-auto flex max-w-xl items-center justify-center gap-3 rounded-2xl bg-white p-8 text-slate-600 shadow-sm dark:bg-darkTheme-card dark:text-white/70">
          <LoaderCircle className="animate-spin" size={20} />
          Verifying successful payment…
        </div>
      </main>
    );
  }

  if (!order.data || order.error || paymentState?.payment_status !== "completed") {
    return (
      <main className="min-h-screen bg-slate-50 px-4 py-16 dark:bg-darkTheme-bg">
        <div className="mx-auto max-w-xl rounded-2xl bg-white p-8 text-center shadow-sm dark:bg-darkTheme-card">
          <h1 className="text-xl font-bold text-slate-900 dark:text-white">
            Payment confirmation is unavailable
          </h1>
          <p className="mt-2 text-sm text-slate-500">
            Xerin has not verified a completed payment for this order.
          </p>
          <Link href={`/order-success/${orderId}`} className="mt-5 inline-flex rounded-xl bg-[#f7941d] px-5 py-3 font-bold text-white">
            Return to order status
          </Link>
        </div>
      </main>
    );
  }

  const data = order.data;
  const payment = paymentState.latest_payment;

  return (
    <main className="min-h-screen bg-slate-50 px-3 py-6 dark:bg-darkTheme-bg sm:px-4 sm:py-12">
      <div className="mx-auto max-w-2xl space-y-5">
        <div className="flex items-center justify-between gap-3 px-1">
          <Link href="/">
            <img src="/images/logo/logo.png" alt="Xerin Marketplace" className="h-10 w-auto" />
          </Link>
          <span className="inline-flex items-center gap-1.5 rounded-full bg-white px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-emerald-700 shadow-sm dark:bg-darkTheme-card">
            <ShieldCheck size={13} /> Verified payment
          </span>
        </div>

        <section className="overflow-hidden rounded-3xl border border-emerald-100 bg-white shadow-sm dark:border-emerald-500/20 dark:bg-darkTheme-card">
          <div className="bg-emerald-50 px-5 py-7 text-center dark:bg-emerald-500/10 sm:px-8 sm:py-9">
            <span className="mx-auto grid h-16 w-16 place-items-center rounded-full bg-emerald-600 text-white shadow-lg shadow-emerald-600/20">
              <BadgeCheck size={34} />
            </span>
            <p className="mt-4 text-xs font-bold uppercase tracking-[.16em] text-emerald-700">
              Payment successful
            </p>
            <h1 className="mt-1 text-2xl font-bold text-slate-900 dark:text-white sm:text-3xl">
              Thank you — your payment is confirmed
            </h1>
            <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-slate-600 dark:text-white/60">
              Xerin received verified confirmation from the payment provider. Your order can now proceed through fulfilment.
            </p>
          </div>

          <div className="p-5 sm:p-8">
            <dl className="grid gap-4 sm:grid-cols-2">
              <Info label="Order number" value={data.id} />
              <Info label="Order status" value={paymentState.order_status.replaceAll("_", " ")} capitalize />
              <Info label="Amount paid" value={formatCurrency(payment?.amount || data.total, payment?.currency || data.currency)} />
              <Info label="Payment method" value={(payment?.method || "payment").replaceAll("_", " ")} capitalize />
              <Info label="Payment reference" value={payment?.provider_transaction_id || payment?.id || "-"} />
              <Info
                label="Paid at"
                value={payment?.paid_at ? new Date(payment.paid_at).toLocaleString() : "Confirmed"}
              />
            </dl>

            <div className="mt-6 rounded-2xl border border-slate-200 bg-slate-50 p-4 text-xs leading-5 text-slate-600 dark:border-white/10 dark:bg-white/5 dark:text-white/60">
              <b className="text-slate-900 dark:text-white">Invoice vs receipt:</b> the invoice shows what Xerin charged for the order. The receipt is proof that this payment was successfully completed.
            </div>

            <div className="mt-6 grid gap-3 sm:grid-cols-2">
              <button
                type="button"
                onClick={() => void download("receipt")}
                disabled={downloading !== null}
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl bg-[#f7941d] px-4 font-bold text-white disabled:opacity-60"
              >
                <ReceiptText size={17} />
                {downloading === "receipt" ? "Preparing receipt..." : "Download Receipt"}
              </button>
              <button
                type="button"
                onClick={() => void download("invoice")}
                disabled={downloading !== null}
                className="inline-flex min-h-12 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 font-bold text-slate-800 disabled:opacity-60 dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                <FileText size={17} />
                {downloading === "invoice" ? "Preparing invoice..." : "Download Invoice"}
              </button>
            </div>

            <div className="mt-3 grid gap-3 sm:grid-cols-2">
              <Link href={`/account/orders/${data.id}`} className="inline-flex min-h-12 items-center justify-center rounded-xl border border-slate-200 px-4 font-semibold text-slate-700 dark:border-white/10 dark:text-white">
                View Order
              </Link>
              <Link href="/shop-with-sidebar" className="inline-flex min-h-12 items-center justify-center rounded-xl border border-slate-200 px-4 font-semibold text-slate-700 dark:border-white/10 dark:text-white">
                Continue Shopping
              </Link>
            </div>
          </div>
        </section>
      </div>
    </main>
  );
}

function Info({
  label,
  value,
  capitalize = false,
}: {
  label: string;
  value: string;
  capitalize?: boolean;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-slate-100 p-3 dark:border-white/10">
      <dt className="text-[10px] font-bold uppercase tracking-wide text-slate-400">{label}</dt>
      <dd className={`mt-1 break-words text-sm font-semibold text-slate-900 dark:text-white ${capitalize ? "capitalize" : ""}`}>
        {value}
      </dd>
    </div>
  );
}
