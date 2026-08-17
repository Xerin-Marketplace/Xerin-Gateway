"use client";

import { ordersApi } from "@/lib/api/endpoints/commerce";
import { formatCurrency } from "@/lib/formatCurrency";
import type {
  CustomerOrderDetail,
  Shipment,
} from "@/types/api/commerce";
import {
  BadgeCheck,
  CalendarClock,
  CircleDollarSign,
  Clock3,
  MapPin,
  PackageCheck,
  RefreshCw,
  Truck,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const paymentTone = (status?: string | null) => {
  if (status === "completed") return "bg-emerald-50 text-emerald-700";
  if (status === "failed" || status === "cancelled")
    return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
};

const shipmentTone = (status: string) => {
  if (status === "delivered") return "bg-emerald-50 text-emerald-700";
  if (["dispatched", "in_transit", "out_for_delivery"].includes(status))
    return "bg-blue-50 text-blue-700";
  if (["failed", "cancelled"].includes(status))
    return "bg-red-50 text-red-700";
  return "bg-amber-50 text-amber-700";
};

export default function BuyerOrderDetails({ orderId }: { orderId: string }) {
  const [order, setOrder] = useState<CustomerOrderDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      setOrder(await ordersApi.customerDetail(orderId));
    } catch (cause) {
      const err = cause as {
        response?: { data?: { detail?: string } };
        message?: string;
      };
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Unable to load this order.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [orderId]);

  const trackingEvents = useMemo(
    () =>
      (order?.shipments ?? [])
        .flatMap((shipment) =>
          shipment.tracking_events.map((event) => ({
            ...event,
            shipment,
          })),
        )
        .sort(
          (a, b) =>
            new Date(b.created_at).getTime() -
            new Date(a.created_at).getTime(),
        ),
    [order],
  );

  if (loading)
    return (
      <p className="rounded-2xl border bg-white p-10 text-center text-[#64748b] dark:bg-darkTheme-card">
        Loading order and delivery tracking...
      </p>
    );

  if (error)
    return (
      <div className="rounded-2xl border border-red-200 bg-red-50 p-8 text-center text-red-700">
        <p>{error}</p>
        <button
          onClick={() => void load()}
          className="mt-3 font-semibold underline"
        >
          Retry
        </button>
      </div>
    );

  if (!order) return null;

  const address = order.shipping_address;

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f7941d]">
            Customer Phase 7
          </p>
          <h1 className="mt-1 text-2xl font-bold">
            Order {order.id.slice(0, 8).toUpperCase()}
          </h1>
          <p className="mt-1 text-sm text-[#64748b]">
            Created {new Date(order.created_at).toLocaleString()}
          </p>
        </div>
        <button
          onClick={() => void load()}
          className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#e2e8f0] bg-white px-4 py-2.5 text-sm font-semibold dark:border-white/10 dark:bg-darkTheme-card"
        >
          <RefreshCw size={14} />
          Refresh Tracking
        </button>
      </div>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          label="Order Status"
          value={pretty(order.status)}
          icon={PackageCheck}
        />
        <Metric
          label="Payment"
          value={pretty(order.payment_status || "not_started")}
          icon={CircleDollarSign}
        />
        <Metric
          label="Delivery Type"
          value={pretty(order.delivery_mode || "not_set")}
          icon={Truck}
        />
        <Metric
          label="Order Total"
          value={formatCurrency(order.total, order.currency)}
          icon={BadgeCheck}
        />
      </section>

      <section className="grid gap-5 xl:grid-cols-[1fr_380px]">
        <div className="space-y-5">
          <Card title="Order Items">
            <div className="divide-y divide-[#e2e8f0] dark:divide-white/10">
              {order.items.map((item) => (
                <div
                  key={item.id}
                  className="flex flex-col gap-3 py-4 first:pt-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
                >
                  <div>
                    <Link
                      href={`/products/${item.product_id}`}
                      className="font-semibold hover:text-[#f7941d]"
                    >
                      {item.product_name}
                    </Link>
                    <p className="mt-1 text-xs text-[#64748b]">
                      Qty {item.quantity}
                      {item.variant_name ? ` · ${item.variant_name}` : ""}
                    </p>
                  </div>
                  <div className="text-right">
                    <p className="font-semibold">
                      {formatCurrency(
                        item.customer_total ?? item.total_price,
                        order.currency,
                      )}
                    </p>
                    {Number(item.promotion_discount_amount || 0) > 0 && (
                      <p className="text-xs text-emerald-700">
                        Seller promotion -{" "}
                        {formatCurrency(
                          item.promotion_discount_amount || 0,
                          order.currency,
                        )}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </Card>

          <Card title="Seller Fulfilment">
            {order.seller_orders.length ? (
              <div className="grid gap-3 sm:grid-cols-2">
                {order.seller_orders.map((sellerOrder, index) => (
                  <div
                    key={sellerOrder.id}
                    className="rounded-xl border border-[#e2e8f0] p-4 dark:border-white/10"
                  >
                    <p className="text-xs font-bold uppercase tracking-wide text-[#94a3b8]">
                      Seller shipment {index + 1}
                    </p>
                    <p className="mt-2 text-lg font-bold capitalize">
                      {pretty(sellerOrder.status)}
                    </p>
                    <p className="mt-1 text-xs text-[#64748b]">
                      {sellerOrder.item_count} item
                      {sellerOrder.item_count === 1 ? "" : "s"}
                    </p>
                    <p className="mt-2 text-xs text-[#64748b]">
                      Seller portion:{" "}
                      {formatCurrency(
                        sellerOrder.seller_subtotal,
                        order.currency,
                      )}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[#64748b]">
                Seller fulfilment records will appear after the order enters
                processing.
              </p>
            )}
          </Card>

          <Card title="Shipment Tracking">
            {order.shipments.length ? (
              <div className="space-y-4">
                {order.shipments.map((shipment, index) => (
                  <ShipmentCard
                    key={shipment.id}
                    shipment={shipment}
                    index={index}
                  />
                ))}
              </div>
            ) : (
              <div className="rounded-xl border border-dashed border-[#cbd5e1] p-5 text-sm text-[#64748b]">
                Shipment has not been created yet. This normally appears after
                payment confirmation or COD acceptance.
              </div>
            )}
          </Card>

          <Card title="Tracking Timeline">
            {trackingEvents.length ? (
              <div className="space-y-0">
                {trackingEvents.map((event, index) => (
                  <div
                    key={event.id}
                    className="relative flex gap-4 pb-6 last:pb-0"
                  >
                    {index < trackingEvents.length - 1 && (
                      <span className="absolute left-[7px] top-4 h-full w-px bg-[#e2e8f0]" />
                    )}
                    <span className="relative mt-1 h-4 w-4 shrink-0 rounded-full border-4 border-orange-100 bg-[#f7941d]" />
                    <div>
                      <p className="font-semibold">
                        {pretty(event.status)}
                      </p>
                      <p className="mt-1 text-xs text-[#64748b]">
                        {new Date(event.created_at).toLocaleString()}
                        {event.location ? ` · ${event.location}` : ""}
                      </p>
                      {event.notes && (
                        <p className="mt-1 text-sm text-[#64748b]">
                          {event.notes}
                        </p>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-[#64748b]">
                Tracking events will appear here as the logistics provider
                updates the shipment.
              </p>
            )}
          </Card>
        </div>

        <aside className="space-y-5">
          <Card title="Payment Status">
            <div className="space-y-3">
              {order.payments.length ? (
                order.payments.map((payment) => (
                  <div
                    key={payment.id}
                    className="rounded-xl border border-[#e2e8f0] p-4 dark:border-white/10"
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="font-semibold capitalize">
                        {pretty(payment.method)}
                      </p>
                      <span
                        className={`rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${paymentTone(
                          payment.status,
                        )}`}
                      >
                        {pretty(payment.status)}
                      </span>
                    </div>
                    <p className="mt-2 text-lg font-bold">
                      {formatCurrency(payment.amount, payment.currency)}
                    </p>
                    <p className="mt-1 text-xs text-[#64748b]">
                      {payment.provider || "Cash / marketplace"}
                    </p>
                    {payment.provider_transaction_id && (
                      <p className="mt-1 break-all text-[11px] text-[#94a3b8]">
                        Ref: {payment.provider_transaction_id}
                      </p>
                    )}
                    <p className="mt-2 text-xs text-[#64748b]">
                      {payment.paid_at
                        ? `Paid ${new Date(payment.paid_at).toLocaleString()}`
                        : payment.method === "cash_on_delivery"
                          ? "Collection due on delivery"
                          : "Awaiting payment confirmation"}
                    </p>
                  </div>
                ))
              ) : (
                <p className="text-sm text-[#64748b]">
                  No payment record is attached to this order yet.
                </p>
              )}
            </div>
          </Card>

          <Card title="Delivery Address">
            {address ? (
              <div className="flex items-start gap-3">
                <MapPin size={18} className="mt-0.5 shrink-0 text-[#f7941d]" />
                <div className="text-sm leading-6 text-[#64748b]">
                  {address.recipient_name && (
                    <p className="font-semibold text-dark dark:text-white">
                      {address.recipient_name}
                    </p>
                  )}
                  <p>{address.street}</p>
                  <p>
                    {[address.ward, address.district, address.city]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                  <p>
                    {[address.region, address.country]
                      .filter(Boolean)
                      .join(", ")}
                  </p>
                  {address.recipient_phone && (
                    <p>{address.recipient_phone}</p>
                  )}
                </div>
              </div>
            ) : (
              <p className="text-sm text-[#64748b]">
                Delivery address snapshot is unavailable.
              </p>
            )}
          </Card>

          <Card title="Order Summary">
            <Summary
              label="Subtotal"
              value={formatCurrency(order.subtotal, order.currency)}
            />
            {Number(order.promotion_discount_amount || 0) > 0 && (
              <Summary
                label="Seller promotion"
                value={`-${formatCurrency(
                  order.promotion_discount_amount || 0,
                  order.currency,
                )}`}
                saving
              />
            )}
            {Number(order.coupon_discount_amount || 0) > 0 && (
              <Summary
                label="Platform coupon"
                value={`-${formatCurrency(
                  order.coupon_discount_amount || 0,
                  order.currency,
                )}`}
                saving
              />
            )}
            <Summary
              label="Shipping"
              value={formatCurrency(order.shipping_amount, order.currency)}
            />
            <Summary
              label="Tax"
              value={formatCurrency(order.tax_amount, order.currency)}
            />
            <div className="mt-3 border-t border-[#e2e8f0] pt-3 dark:border-white/10">
              <Summary
                label="Total"
                value={formatCurrency(order.total, order.currency)}
                strong
              />
            </div>
          </Card>
        </aside>
      </section>

      <Link
        href="/account/orders"
        className="inline-block font-semibold text-[#f7941d]"
      >
        ← Back to orders
      </Link>
    </div>
  );
}

function ShipmentCard({
  shipment,
  index,
}: {
  shipment: Shipment;
  index: number;
}) {
  return (
    <div className="rounded-xl border border-[#e2e8f0] p-4 dark:border-white/10">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-bold uppercase tracking-wide text-[#94a3b8]">
            Shipment {index + 1}
          </p>
          <p className="mt-1 font-bold">
            {shipment.carrier_name || "Marketplace logistics"}
          </p>
          {shipment.tracking_number && (
            <p className="mt-1 break-all text-sm text-[#64748b]">
              Tracking: <b>{shipment.tracking_number}</b>
            </p>
          )}
        </div>
        <span
          className={`w-fit rounded-full px-2.5 py-1 text-[10px] font-bold uppercase ${shipmentTone(
            shipment.status,
          )}`}
        >
          {pretty(shipment.status)}
        </span>
      </div>

      <div className="mt-4 grid gap-3 text-xs text-[#64748b] sm:grid-cols-3">
        <div>
          <p className="font-semibold text-dark dark:text-white">Items</p>
          <p className="mt-1">
            {shipment.items.reduce((sum, item) => sum + item.quantity, 0)}
          </p>
        </div>
        <div>
          <p className="font-semibold text-dark dark:text-white">Dispatch</p>
          <p className="mt-1">
            {shipment.dispatched_at
              ? new Date(shipment.dispatched_at).toLocaleString()
              : "Pending"}
          </p>
        </div>
        <div>
          <p className="font-semibold text-dark dark:text-white">ETA</p>
          <p className="mt-1">
            {shipment.estimated_delivery_to
              ? new Date(shipment.estimated_delivery_to).toLocaleDateString()
              : "Pending"}
          </p>
        </div>
      </div>
    </div>
  );
}

function Card({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
      <h2 className="mb-4 font-bold">{title}</h2>
      {children}
    </section>
  );
}

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof Truck;
}) {
  return (
    <div className="rounded-2xl border border-[#e2e8f0] bg-white p-4 dark:border-white/10 dark:bg-darkTheme-card">
      <Icon size={17} className="text-[#f7941d]" />
      <p className="mt-3 text-xs font-semibold uppercase tracking-wide text-[#94a3b8]">
        {label}
      </p>
      <p className="mt-1 font-bold capitalize">{value}</p>
    </div>
  );
}

function Summary({
  label,
  value,
  saving = false,
  strong = false,
}: {
  label: string;
  value: string;
  saving?: boolean;
  strong?: boolean;
}) {
  return (
    <div className="flex items-center justify-between gap-3 py-1.5 text-sm">
      <span className={strong ? "font-bold" : "text-[#64748b]"}>{label}</span>
      <span
        className={
          strong
            ? "text-lg font-bold"
            : saving
              ? "font-semibold text-emerald-700"
              : "font-semibold"
        }
      >
        {value}
      </span>
    </div>
  );
}
