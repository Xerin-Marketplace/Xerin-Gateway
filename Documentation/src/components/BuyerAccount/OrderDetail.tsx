"use client";

import { useState } from "react";
import { useParams, useRouter } from "next/navigation";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useOrder } from "@/hooks/useCommerce";
import { useAddresses } from "@/hooks/useAddresses";
import { ordersApi } from "@/lib/api/endpoints/commerce";
import { formatCurrency } from "@/lib/formatCurrency";
import { printOrderInvoice } from "@/lib/invoice";
import {
  AlertCircle,
  ArrowLeft,
  Download,
  Loader2,
  Package,
  RotateCcw,
  Truck,
  XCircle,
} from "lucide-react";
import Link from "next/link";
import toast from "react-hot-toast";
import type { Order } from "@/types/api/commerce";

const CANCELLABLE_STATUSES = [
  "pending",
  "awaiting_payment",
  "payment_verification",
  "confirmed",
  "processing",
];

const statusColor = (status: string) => {
  switch (status) {
    case "delivered":
    case "completed":
      return "bg-green-100 text-green-700";
    case "cancelled":
    case "refunded":
    case "failed":
      return "bg-red-100 text-red-700";
    case "shipped":
    case "out_for_delivery":
      return "bg-blue-100 text-blue-700";
    default:
      return "bg-orange-100 text-orange-700";
  }
};

export default function OrderDetail() {
  const params = useParams();
  const router = useRouter();
  const orderId = String(params.orderId);
  const queryClient = useQueryClient();
  const [cancelReason, setCancelReason] = useState("");
  const [showCancel, setShowCancel] = useState(false);

  const { data: order, isLoading, error } = useOrder(orderId);
  const { addresses } = useAddresses();
  const shippingAddress = addresses.find(
    (a) => String(a.id) === String(order?.shipping_address_id),
  );

  const cancelMutation = useMutation({
    mutationFn: (reason: string) =>
      ordersApi.updateStatus(orderId, { status: "cancelled", notes: reason }),
    onSuccess: () => {
      toast.success("Order cancelled");
      setShowCancel(false);
      void queryClient.invalidateQueries({ queryKey: ["orders", orderId] });
      void queryClient.invalidateQueries({ queryKey: ["orders", "mine"] });
    },
    onError: () => {
      toast.error("Unable to cancel order. It may no longer be cancellable.");
    },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center gap-2 text-[#64748b]">
        <Loader2 size={18} className="animate-spin" />
        Loading order details...
      </div>
    );
  }

  if (error || !order) {
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-center text-sm text-red-700">
        <AlertCircle className="mx-auto mb-2" size={24} />
        We could not load this order.
        <div className="mt-4">
          <Link
            href="/account/orders"
            className="inline-flex items-center gap-2 font-semibold"
          >
            <ArrowLeft size={16} /> Back to orders
          </Link>
        </div>
      </div>
    );
  }

  const canCancel = CANCELLABLE_STATUSES.includes(order.status);
  const isDelivered = order.status === "delivered" || order.status === "completed";

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <Link
          href="/account/orders"
          className="inline-flex items-center gap-2 text-sm font-semibold text-[#64748b] hover:text-[#f7941d]"
        >
          <ArrowLeft size={16} /> Back to orders
        </Link>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() => printOrderInvoice(order, shippingAddress ?? null)}
            className="inline-flex items-center gap-2 rounded-xl border border-[#e2e8f0] bg-white px-4 py-2 text-sm font-semibold hover:border-[#f7941d]"
          >
            <Download size={16} />
            Invoice
          </button>
          {canCancel && (
            <button
              onClick={() => setShowCancel(true)}
              className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700"
            >
              <XCircle size={16} />
              Cancel Order
            </button>
          )}
        </div>
      </div>

      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm text-[#64748b]">Order #{order.id.slice(0, 12).toUpperCase()}</p>
            <h1 className="text-2xl font-bold">
              {order.items.length} item{order.items.length === 1 ? "" : "s"}
            </h1>
            <p className="text-sm text-[#64748b]">
              Placed on {new Date(order.created_at).toLocaleString()}
            </p>
          </div>
          <span
            className={`w-fit rounded-full px-3 py-1 text-sm font-semibold capitalize ${statusColor(order.status)}`}
          >
            {order.status.replaceAll("_", " ")}
          </span>
        </div>
      </section>

      <div className="grid gap-5 xl:grid-cols-3">
        <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm xl:col-span-2">
          <h2 className="mb-4 text-lg font-bold">Items</h2>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[600px] text-left text-sm">
              <thead className="bg-[#f8fafc]">
                <tr>
                  {["Product", "Qty", "Unit Price", "Total"].map((h) => (
                    <th key={h} className="p-3">
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {order.items.map((item) => (
                  <tr
                    key={item.id}
                    className="border-t border-[#e2e8f0]"
                  >
                    <td className="p-3 font-medium">
                      {item.product_name}
                      {item.variant_name && (
                        <p className="text-xs text-[#64748b]">{item.variant_name}</p>
                      )}
                    </td>
                    <td className="p-3">{item.quantity}</td>
                    <td className="p-3">
                      {formatCurrency(item.unit_price, order.currency)}
                    </td>
                    <td className="p-3 font-semibold">
                      {formatCurrency(item.total_price, order.currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-6 space-y-1 text-right text-sm">
            <p className="text-[#64748b]">
              Subtotal: {formatCurrency(order.subtotal, order.currency)}
            </p>
            <p className="text-[#64748b]">
              Shipping: {formatCurrency(order.shipping_amount, order.currency)}
            </p>
            <p className="text-[#64748b]">
              Tax: {formatCurrency(order.tax_amount, order.currency)}
            </p>
            {Number(order.discount_amount) > 0 && (
              <p className="text-[#64748b]">
                Discount: -{formatCurrency(order.discount_amount, order.currency)}
              </p>
            )}
            <p className="text-lg font-bold text-[#f7941d]">
              Total: {formatCurrency(order.total, order.currency)}
            </p>
          </div>
        </section>

        <div className="space-y-5">
          <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-lg font-bold">Delivery</h2>
            <div className="flex items-start gap-3 text-sm">
              <Truck size={18} className="mt-0.5 text-[#f7941d]" />
              <div>
                <p className="font-medium">Shipping address</p>
                {shippingAddress ? (
                  <p className="text-[#64748b]">
                    {shippingAddress.street}, {shippingAddress.city},{" "}
                    {shippingAddress.region}, {shippingAddress.country}
                  </p>
                ) : (
                  <p className="text-[#64748b]">Address on file</p>
                )}
              </div>
            </div>
          </section>

          <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
            <h2 className="mb-3 text-lg font-bold">After-sale</h2>
            <div className="space-y-2 text-sm">
              <button
                disabled={!isDelivered}
                title={
                  isDelivered
                    ? "Return workflow is not available yet"
                    : "Only available after delivery"
                }
                className="flex w-full items-center gap-2 rounded-xl border border-[#e2e8f0] px-3 py-2 text-left text-[#64748b] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <RotateCcw size={16} />
                Request return
                <span className="ml-auto text-xs">Coming soon</span>
              </button>
              <button
                disabled={!isDelivered}
                title={
                  isDelivered
                    ? "Refund workflow is not available yet"
                    : "Only available after delivery"
                }
                className="flex w-full items-center gap-2 rounded-xl border border-[#e2e8f0] px-3 py-2 text-left text-[#64748b] disabled:cursor-not-allowed disabled:opacity-50"
              >
                <Package size={16} />
                Request refund
                <span className="ml-auto text-xs">Coming soon</span>
              </button>
            </div>
          </section>
        </div>
      </div>

      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <h2 className="mb-4 text-lg font-bold">Order Timeline</h2>
        <div className="relative pl-4">
          <div className="absolute left-[9px] top-2 bottom-2 w-0.5 bg-[#e2e8f0]" />
          <div className="space-y-6">
            {order.status_history.length > 0 ? (
              order.status_history.map((entry) => (
                <div key={entry.id} className="relative flex items-start gap-4">
                  <span className="z-10 mt-1.5 h-2.5 w-2.5 rounded-full bg-[#f7941d]" />
                  <div>
                    <p className="font-semibold capitalize">
                      {entry.status.replaceAll("_", " ")}
                    </p>
                    {entry.notes && (
                      <p className="text-sm text-[#64748b]">{entry.notes}</p>
                    )}
                    <p className="text-xs text-[#94a3b8]">
                      {new Date(entry.created_at).toLocaleString()}
                    </p>
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-[#64748b]">No status updates yet.</p>
            )}
          </div>
        </div>
      </section>

      {showCancel && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 px-4">
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-lg">
            <h3 className="text-lg font-bold">Cancel order?</h3>
            <p className="mt-1 text-sm text-[#64748b]">
              This action cannot be undone. Please tell us why you are cancelling.
            </p>
            <textarea
              value={cancelReason}
              onChange={(e) => setCancelReason(e.target.value)}
              placeholder="Reason (optional)"
              className="mt-4 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] p-3 text-sm outline-none focus:border-[#f7941d]"
              rows={3}
            />
            <div className="mt-5 flex justify-end gap-3">
              <button
                onClick={() => setShowCancel(false)}
                className="rounded-xl px-4 py-2 text-sm font-semibold text-[#64748b] hover:bg-[#f8fafc]"
              >
                Keep order
              </button>
              <button
                onClick={() => cancelMutation.mutate(cancelReason)}
                disabled={cancelMutation.isPending}
                className="inline-flex items-center gap-2 rounded-xl bg-red-600 px-4 py-2 text-sm font-semibold text-white hover:bg-red-700 disabled:opacity-50"
              >
                {cancelMutation.isPending && <Loader2 size={16} className="animate-spin" />}
                Cancel order
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
