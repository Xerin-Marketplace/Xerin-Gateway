"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  Eye,
  PackageCheck,
  RefreshCw,
  Search,
  ShoppingBag,
  Truck,
  UserRound,
  X,
} from "lucide-react";
import { ordersApi } from "@/lib/api/endpoints/commerce";
import type { Order } from "@/types/api/commerce";
import { formatCurrency } from "@/lib/formatCurrency";

const STATUS_OPTIONS = [
  "all",
  "pending",
  "awaiting_payment",
  "paid",
  "processing",
  "shipped",
  "delivered",
  "cancelled",
  "refunded",
];

const PAYMENT_OPTIONS = [
  "all",
  "pending",
  "authorized",
  "paid",
  "failed",
  "refunded",
];

const pretty = (value?: string | null) =>
  (value || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

const orderRef = (order: Order) =>
  order.order_number || `ORD-${order.id.slice(0, 8).toUpperCase()}`;

const customerName = (order: Order) => {
  const full = [
    order.user?.first_name,
    order.user?.last_name,
  ]
    .filter(Boolean)
    .join(" ")
    .trim();

  return full || order.user?.email || order.user_id.slice(0, 8).toUpperCase();
};

const statusClass = (status: string) => {
  const value = status.toLowerCase();
  if (["delivered", "completed", "paid"].includes(value)) {
    return "bg-emerald-50 text-emerald-700 border-emerald-200";
  }
  if (["cancelled", "rejected", "failed", "refunded"].includes(value)) {
    return "bg-red-50 text-red-700 border-red-200";
  }
  if (["processing", "packed", "shipped", "out_for_delivery"].includes(value)) {
    return "bg-blue-50 text-blue-700 border-blue-200";
  }
  return "bg-amber-50 text-amber-700 border-amber-200";
};

export default function OrderList({
  status,
  title = "All Orders",
  subtitle = "View every order generated in the marketplace and manage its fulfilment lifecycle.",
}: {
  view?: string;
  status?: string;
  title?: string;
  subtitle?: string;
}) {
  const [rows, setRows] = useState<Order[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState(status || "all");
  const [paymentFilter, setPaymentFilter] = useState("all");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");
  const [selected, setSelected] = useState<Order | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    setStatusFilter(status || "all");
    setPage(1);
  }, [status]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
      setPage(1);
    }, 350);

    return () => window.clearTimeout(timer);
  }, [query]);

  const load = async () => {
    setLoading(true);
    setError("");

    try {
      const data = await ordersApi.adminList({
        page,
        page_size: pageSize,
        status: statusFilter === "all" ? undefined : statusFilter,
        search: debouncedQuery || undefined,
        payment_status:
          paymentFilter === "all" ? undefined : paymentFilter,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      });

      setRows(data.results);
      setTotal(data.total);
    } catch (cause) {
      setRows([]);
      setTotal(0);
      setError(
        cause instanceof Error ? cause.message : "Unable to load orders.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [
    page,
    pageSize,
    statusFilter,
    paymentFilter,
    debouncedQuery,
    dateFrom,
    dateTo,
  ]);

  const visibleRows = useMemo(() => {
    // This fallback keeps search useful even if the current backend build
    // does not yet consume the optional search query parameter.
    if (!debouncedQuery) return rows;

    const q = debouncedQuery.toLowerCase();

    return rows.filter((order) =>
      [
        order.id,
        order.order_number,
        order.user_id,
        order.user?.first_name,
        order.user?.last_name,
        order.user?.email,
        order.user?.phone,
        order.status,
        order.payment_status,
        order.tracking_number,
        ...order.items.map((item) => item.product_name),
      ]
        .filter(Boolean)
        .join(" ")
        .toLowerCase()
        .includes(q),
    );
  }, [debouncedQuery, rows]);

  const pageStats = useMemo(() => {
    const revenue = rows.reduce(
      (sum, order) => sum + Number(order.total || 0),
      0,
    );

    return {
      orders: rows.length,
      processing: rows.filter((order) =>
        ["processing", "shipped"].includes(order.status),
      ).length,
      delivered: rows.filter((order) =>
        ["delivered", "completed"].includes(order.status),
      ).length,
      revenue,
    };
  }, [rows]);

  const updateStatus = async (order: Order, nextStatus: string) => {
    if (!nextStatus || nextStatus === order.status) return;

    setBusy(true);
    try {
      await ordersApi.updateStatus(order.id, {
        status: nextStatus,
        notes: `Status changed by admin to ${nextStatus}`,
      });
      toast.success("Order status updated.");
      setSelected(null);
      await load();
    } catch (cause) {
      toast.error(
        cause instanceof Error ? cause.message : "Status update failed.",
      );
    } finally {
      setBusy(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[.16em] text-[#f47524]">
              Order management
            </p>
            <h2 className="mt-1 text-2xl font-bold text-[#111827]">{title}</h2>
            <p className="mt-1 max-w-3xl text-sm leading-6 text-[#64748b]">
              {subtitle}
            </p>
          </div>

          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-[#d8e0e9] bg-white px-4 text-sm font-semibold text-[#475569]"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric
          icon={ShoppingBag}
          label="Orders on this page"
          value={String(pageStats.orders)}
          detail={`${total} total system orders`}
        />
        <Metric
          icon={Truck}
          label="In fulfilment"
          value={String(pageStats.processing)}
          detail="Processing or shipped"
        />
        <Metric
          icon={PackageCheck}
          label="Delivered"
          value={String(pageStats.delivered)}
          detail="Completed on this page"
        />
        <Metric
          icon={CircleDollarSign}
          label="Page order value"
          value={formatCurrency(
            pageStats.revenue,
            rows[0]?.currency || "TZS",
          )}
          detail="Value of loaded orders"
        />
      </section>

      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <div className="grid gap-3 lg:grid-cols-[minmax(260px,1.7fr)_repeat(4,minmax(140px,1fr))]">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search order, customer, product or tracking..."
              className="h-11 w-full rounded-xl border-2 border-[#d8e0e9] bg-white pl-10 pr-4 text-sm outline-none focus:border-[#f47524]"
            />
          </div>

          <select
            value={statusFilter}
            onChange={(event) => {
              setStatusFilter(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm outline-none"
          >
            {STATUS_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "All statuses" : pretty(option)}
              </option>
            ))}
          </select>

          <select
            value={paymentFilter}
            onChange={(event) => {
              setPaymentFilter(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm outline-none"
          >
            {PAYMENT_OPTIONS.map((option) => (
              <option key={option} value={option}>
                {option === "all" ? "All payments" : pretty(option)}
              </option>
            ))}
          </select>

          <input
            type="date"
            value={dateFrom}
            onChange={(event) => {
              setDateFrom(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm outline-none"
            title="Date from"
          />

          <input
            type="date"
            value={dateTo}
            onChange={(event) => {
              setDateTo(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm outline-none"
            title="Date to"
          />
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-[#e2e8f0] bg-white shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-gray-500">
            <RefreshCw className="mx-auto animate-spin" size={22} />
            <p className="mt-3 text-sm">Loading system orders...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <p className="font-semibold text-red-600">{error}</p>
            <button
              onClick={() => void load()}
              className="mt-3 text-sm font-semibold text-[#f47524]"
            >
              Retry
            </button>
          </div>
        ) : !visibleRows.length ? (
          <div className="p-12 text-center">
            <ShoppingBag className="mx-auto text-slate-300" size={34} />
            <p className="mt-3 font-semibold text-[#111827]">
              No matching orders found
            </p>
            <p className="mt-1 text-sm text-gray-500">
              Adjust the filters or wait for new customer orders.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1100px] text-left text-sm">
              <thead className="bg-[#f8fafc] text-xs uppercase text-[#64748b]">
                <tr>
                  {[
                    "Order",
                    "Customer",
                    "Items",
                    "Total",
                    "Payment",
                    "Status",
                    "Created",
                    "Actions",
                  ].map((heading) => (
                    <th key={heading} className="px-5 py-3">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody className="divide-y divide-[#edf0f4]">
                {visibleRows.map((order) => (
                  <tr key={order.id} className="hover:bg-orange-50/20">
                    <td className="px-5 py-4">
                      <p className="font-bold text-[#111827]">
                        {orderRef(order)}
                      </p>
                      <p className="mt-0.5 font-mono text-[10px] text-gray-400">
                        {order.id}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2.5">
                        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500">
                          <UserRound size={14} />
                        </span>
                        <div>
                          <p className="font-semibold text-[#111827]">
                            {customerName(order)}
                          </p>
                          {order.user?.email && (
                            <p className="text-xs text-gray-500">
                              {order.user.email}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="px-5 py-4">
                      <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
                        {order.items.length} item
                        {order.items.length === 1 ? "" : "s"}
                      </span>
                    </td>

                    <td className="px-5 py-4 font-bold text-[#111827]">
                      {formatCurrency(order.total, order.currency)}
                    </td>

                    <td className="px-5 py-4">
                      <span className="text-xs font-semibold capitalize text-[#475569]">
                        {pretty(order.payment_status || "unknown")}
                      </span>
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${statusClass(
                          order.status,
                        )}`}
                      >
                        {pretty(order.status)}
                      </span>
                    </td>

                    <td className="px-5 py-4 text-xs text-[#64748b]">
                      <div className="flex items-center gap-1.5">
                        <CalendarDays size={13} />
                        {order.created_at
                          ? new Date(order.created_at).toLocaleString()
                          : "—"}
                      </div>
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2">
                        <button
                          type="button"
                          onClick={() => setSelected(order)}
                          className="inline-flex items-center gap-1.5 rounded-lg border border-[#d8e0e9] px-3 py-2 text-xs font-semibold text-[#334155]"
                        >
                          <Eye size={13} />
                          Quick View
                        </button>
                        <Link
                          href={`/admin/orders/${order.id}`}
                          className="rounded-lg bg-[#111827] px-3 py-2 text-xs font-semibold text-white"
                        >
                          Details
                        </Link>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && (
          <div className="flex flex-col gap-3 border-t border-[#edf0f4] px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-[#64748b]">
              Showing{" "}
              <b className="text-[#111827]">
                {from}-{to}
              </b>{" "}
              of <b className="text-[#111827]">{total}</b> orders
            </p>

            <div className="flex flex-wrap items-center gap-2">
              <select
                value={pageSize}
                onChange={(event) => {
                  setPageSize(Number(event.target.value));
                  setPage(1);
                }}
                className="h-10 rounded-xl border border-[#d8e0e9] bg-white px-3 text-sm"
              >
                {[10, 20, 50, 100].map((size) => (
                  <option key={size} value={size}>
                    {size} / page
                  </option>
                ))}
              </select>

              <button
                type="button"
                disabled={page <= 1 || loading}
                onClick={() => setPage((value) => value - 1)}
                className="inline-flex h-10 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-40"
              >
                <ChevronLeft size={14} />
                Previous
              </button>

              <span className="min-w-24 text-center text-xs font-semibold text-[#475569]">
                Page {page} of {totalPages}
              </span>

              <button
                type="button"
                disabled={page >= totalPages || loading}
                onClick={() => setPage((value) => value + 1)}
                className="inline-flex h-10 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-40"
              >
                Next
                <ChevronRight size={14} />
              </button>
            </div>
          </div>
        )}
      </section>

      {selected && (
        <div
          className="fixed inset-0 z-[100] flex justify-end bg-black/50 backdrop-blur-[2px]"
          onMouseDown={() => !busy && setSelected(null)}
        >
          <aside
            className="flex h-full w-full max-w-2xl flex-col bg-[#f8fafc] shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b bg-white px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f47524]">
                  Order quick view
                </p>
                <h3 className="mt-1 text-xl font-bold text-[#111827]">
                  {orderRef(selected)}
                </h3>
              </div>
              <button
                type="button"
                onClick={() => setSelected(null)}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100"
              >
                <X size={17} />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto p-6">
              <section className="grid gap-3 sm:grid-cols-2">
                <Info label="Customer" value={customerName(selected)} />
                <Info
                  label="Payment status"
                  value={pretty(selected.payment_status)}
                />
                <Info
                  label="Order total"
                  value={formatCurrency(selected.total, selected.currency)}
                />
                <Info label="Delivery method" value={selected.delivery_method || "—"} />
                <Info label="Courier" value={selected.courier_name || "—"} />
                <Info
                  label="Tracking number"
                  value={selected.tracking_number || "—"}
                />
              </section>

              <section className="overflow-hidden rounded-2xl border bg-white">
                <div className="border-b px-5 py-4">
                  <h4 className="font-bold text-[#111827]">Order items</h4>
                </div>
                <div className="divide-y">
                  {selected.items.map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between gap-4 px-5 py-4"
                    >
                      <div>
                        <p className="font-semibold text-[#111827]">
                          {item.product_name}
                        </p>
                        <p className="text-xs text-gray-500">
                          Qty {item.quantity}
                          {item.variant_name ? ` · ${item.variant_name}` : ""}
                        </p>
                      </div>
                      <p className="font-semibold">
                        {formatCurrency(item.total_price, selected.currency)}
                      </p>
                    </div>
                  ))}
                </div>
              </section>

              {selected.notes && (
                <section className="rounded-2xl border bg-white p-5">
                  <p className="text-xs font-bold uppercase tracking-wider text-gray-400">
                    Customer notes
                  </p>
                  <p className="mt-2 text-sm leading-6 text-[#475569]">
                    {selected.notes}
                  </p>
                </section>
              )}

              <section className="rounded-2xl border bg-white p-5">
                <label className="block text-sm font-semibold text-[#334155]">
                  Update order status
                </label>
                <p className="mt-1 text-xs text-gray-500">
                  Use the status that reflects the current fulfilment stage.
                </p>
                <select
                  defaultValue={selected.status}
                  disabled={busy}
                  onChange={(event) =>
                    void updateStatus(selected, event.target.value)
                  }
                  className="mt-3 h-11 w-full rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm outline-none focus:border-[#f47524]"
                >
                  {STATUS_OPTIONS.filter((item) => item !== "all").map(
                    (item) => (
                      <option key={item} value={item}>
                        {pretty(item)}
                      </option>
                    ),
                  )}
                </select>
              </section>
            </div>

            <div className="border-t bg-white p-5">
              <Link
                href={`/admin/orders/${selected.id}`}
                className="block w-full rounded-xl bg-[#111827] px-4 py-3 text-center text-sm font-semibold text-white"
              >
                Open Complete Order Details
              </Link>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function Metric({
  icon: Icon,
  label,
  value,
  detail,
}: {
  icon: typeof ShoppingBag;
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <article className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-[#f47524]">
        <Icon size={17} />
      </span>
      <p className="mt-4 text-2xl font-bold text-[#111827]">{value}</p>
      <p className="mt-1 text-sm font-semibold text-[#475569]">{label}</p>
      <p className="mt-1 text-xs text-gray-400">{detail}</p>
    </article>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-white p-4">
      <p className="text-[11px] font-bold uppercase tracking-wider text-gray-400">
        {label}
      </p>
      <p className="mt-1 break-words text-sm font-semibold text-[#111827]">
        {value}
      </p>
    </div>
  );
}
