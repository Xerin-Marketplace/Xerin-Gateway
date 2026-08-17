"use client";

import { useEffect, useState } from "react";
import { RefreshCw, Search, Truck } from "lucide-react";
import { ordersApi } from "@/lib/api/endpoints/commerce";
import type { Order } from "@/types/api/commerce";

export default function OrderTracking() {
  const [rows, setRows] = useState<Order[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const result = await ordersApi.adminList({
        page: 1,
        page_size: 100,
        status: "shipped",
      });
      setRows(result.results);
    } catch (cause) {
      setError(
        cause instanceof Error ? cause.message : "Unable to load tracking data.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const visible = rows.filter((order) =>
    [
      order.order_number,
      order.id,
      order.tracking_number,
      order.courier_name,
      order.user?.email,
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(query.trim().toLowerCase()),
  );

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border bg-white p-5 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f47524]">
          Delivery operations
        </p>
        <h2 className="mt-1 text-2xl font-bold text-[#111827]">
          Order Tracking
        </h2>
        <p className="mt-1 text-sm text-gray-500">
          Review shipped orders and any courier or tracking information returned
          by the backend.
        </p>

        <div className="mt-5 flex gap-2">
          <div className="relative flex-1">
            <Search
              size={15}
              className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search tracking number, courier or order..."
              className="h-11 w-full rounded-xl border-2 border-[#d8e0e9] pl-9 pr-3 text-sm outline-none focus:border-[#f47524]"
            />
          </div>
          <button
            onClick={() => void load()}
            className="inline-flex h-11 items-center gap-2 rounded-xl border px-4 text-sm font-semibold"
          >
            <RefreshCw size={14} />
            Refresh
          </button>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border bg-white shadow-sm">
        {loading ? (
          <p className="p-10 text-center text-gray-500">
            Loading shipped orders...
          </p>
        ) : error ? (
          <p className="p-10 text-center text-red-600">{error}</p>
        ) : !visible.length ? (
          <div className="p-12 text-center">
            <Truck className="mx-auto text-slate-300" size={34} />
            <p className="mt-3 font-semibold">No shipped orders found.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[850px] text-left text-sm">
              <thead className="bg-[#f8fafc]">
                <tr>
                  {[
                    "Order",
                    "Courier",
                    "Tracking Number",
                    "Estimated Delivery",
                    "Status",
                  ].map((heading) => (
                    <th key={heading} className="px-5 py-3">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y">
                {visible.map((order) => (
                  <tr key={order.id}>
                    <td className="px-5 py-4 font-semibold">
                      {order.order_number ||
                        `ORD-${order.id.slice(0, 8).toUpperCase()}`}
                    </td>
                    <td className="px-5 py-4">
                      {order.courier_name || "Not assigned"}
                    </td>
                    <td className="px-5 py-4 font-mono text-xs">
                      {order.tracking_number || "Not available"}
                    </td>
                    <td className="px-5 py-4 text-gray-500">
                      {order.estimated_delivery_date
                        ? new Date(
                            order.estimated_delivery_date,
                          ).toLocaleDateString()
                        : "Not provided"}
                    </td>
                    <td className="px-5 py-4 capitalize">
                      {order.status.replaceAll("_", " ")}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
