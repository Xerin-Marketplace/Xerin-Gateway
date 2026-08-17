"use client";

import {
  sellerInventoryApi,
  type SellerInventoryItem,
  type SellerInventorySummary,
} from "@/lib/api/endpoints/seller-inventory";
import { productsApi } from "@/lib/api/endpoints/products";
import type { Product } from "@/types/api/product";
import {
  AlertTriangle,
  Boxes,
  CheckCircle2,
  PackagePlus,
  RefreshCw,
  Search,
  Warehouse,
  XCircle,
} from "lucide-react";
import { useEffect, useState } from "react";
import toast from "react-hot-toast";

const PAGE_SIZE = 20;

export default function SellerInventoryPage() {
  const [rows, setRows] = useState<SellerInventoryItem[]>([]);
  const [products, setProducts] = useState<Product[]>([]);
  const [summary, setSummary] = useState<SellerInventorySummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [stockFilter, setStockFilter] =
    useState<"all" | "low" | "out">("all");
  const [configureProduct, setConfigureProduct] = useState<Product | null>(null);
  const [quantity, setQuantity] = useState("0");
  const [threshold, setThreshold] = useState("5");
  const [location, setLocation] = useState("");
  const [configuring, setConfiguring] = useState(false);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const [inventory, productRows, summaryRow] = await Promise.all([
        sellerInventoryApi.list({
          page,
          page_size: PAGE_SIZE,
          search: query || undefined,
          low_stock: stockFilter === "low" ? true : undefined,
          out_of_stock: stockFilter === "out" ? true : undefined,
        }),
        productsApi.getMyProducts({ skip: 0, limit: 100 }),
        sellerInventoryApi.summary(),
      ]);
      setRows(inventory.results);
      setTotal(inventory.total);
      setProducts(productRows);
      setSummary(summaryRow);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Unable to load seller inventory.",
      );
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [page, query, stockFilter]);

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const configure = async () => {
    if (!configureProduct) return;
    const opening = Number(quantity);
    const low = Number(threshold);

    if (!Number.isInteger(opening) || opening < 0) {
      toast.error("Opening stock must be 0 or more.");
      return;
    }
    if (!Number.isInteger(low) || low < 0) {
      toast.error("Low-stock threshold must be 0 or more.");
      return;
    }

    setConfiguring(true);
    try {
      await sellerInventoryApi.configure({
        product_id: String(configureProduct.id),
        variant_id: null,
        quantity: opening,
        low_stock_threshold: low,
        warehouse_location: location.trim() || null,
      });
      toast.success("Stock configured successfully.");
      setConfigureProduct(null);
      await load();
    } catch (cause) {
      toast.error(
        cause instanceof Error
          ? cause.message
          : "Unable to configure stock.",
      );
    } finally {
      setConfiguring(false);
    }
  };

  return (
    <>
      <div className="mx-auto max-w-[1380px] space-y-5">
        <section className="rounded-2xl border border-[#e7ebf0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
          <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f7941d]">
            Seller stock control
          </p>
          <h1 className="mt-1 text-2xl font-bold">Inventory</h1>
          <p className="mt-2 text-sm leading-6 text-[#64748b]">
            This is the seller's physical stock. Xerin calculates:
            <b> available quantity = quantity − reserved quantity.</b>
          </p>
        </section>

        <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          <Stat label="Stock units" value={summary?.total_stock_units ?? 0} icon={Boxes} />
          <Stat label="Reserved" value={summary?.reserved_units ?? 0} icon={Warehouse} />
          <Stat label="Available" value={summary?.available_units ?? 0} icon={CheckCircle2} />
          <Stat label="Low stock" value={summary?.low_stock_variants ?? 0} icon={AlertTriangle} />
          <Stat label="Out of stock" value={summary?.out_of_stock_variants ?? 0} icon={XCircle} />
        </section>

        <section className="rounded-2xl border border-[#e2e8f0] bg-white shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
          <div className="flex flex-col gap-3 border-b border-[#e2e8f0] p-5 dark:border-white/10 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex min-w-0 flex-1 gap-2">
              <div className="relative min-w-0 flex-1 lg:max-w-xl">
                <Search size={16} className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]" />
                <input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") {
                      setPage(1);
                      setQuery(search.trim());
                    }
                  }}
                  placeholder="Search product, SKU or variant..."
                  className="h-11 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] pl-10 pr-4 text-sm outline-none focus:border-[#f7941d] dark:border-white/10 dark:bg-white/5"
                />
              </div>
              <button
                type="button"
                onClick={() => {
                  setPage(1);
                  setQuery(search.trim());
                }}
                className="rounded-xl bg-[#111827] px-4 text-sm font-semibold text-white"
              >
                Search
              </button>
            </div>

            <select
              value={stockFilter}
              onChange={(e) => {
                setPage(1);
                setStockFilter(e.target.value as "all" | "low" | "out");
              }}
              className="h-11 rounded-xl border border-[#e2e8f0] bg-white px-3 text-sm dark:border-white/10 dark:bg-white/5"
            >
              <option value="all">All stock</option>
              <option value="low">Low stock</option>
              <option value="out">Out of stock</option>
            </select>
          </div>

          {loading ? (
            <div className="p-14 text-center text-[#64748b]">
              <RefreshCw className="mx-auto animate-spin" size={20} />
              <p className="mt-3">Loading inventory...</p>
            </div>
          ) : error ? (
            <div className="p-12 text-center text-red-600">{error}</div>
          ) : rows.length === 0 ? (
            <div className="p-12 text-center">
              <p className="font-semibold">No inventory records found.</p>
              <p className="mt-1 text-sm text-[#64748b]">
                Configure stock for one of your products below.
              </p>
              <div className="mt-4 flex flex-wrap justify-center gap-2">
                {products.slice(0, 10).map((product) => (
                  <button
                    key={String(product.id)}
                    onClick={() => {
                      setConfigureProduct(product);
                      setQuantity("0");
                      setThreshold("5");
                      setLocation("");
                    }}
                    className="inline-flex items-center gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2 text-xs font-semibold text-amber-900"
                  >
                    <PackagePlus size={14} />
                    Configure {product.name}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[980px] text-left text-sm">
                <thead className="bg-slate-50 text-xs uppercase text-[#64748b] dark:bg-white/5">
                  <tr>
                    {["Product", "Physical", "Reserved", "Available", "Threshold", "Location", "Updated"].map((h) => (
                      <th key={h} className="px-4 py-3">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-[#e2e8f0] dark:divide-white/10">
                  {rows.map((row) => (
                    <tr key={row.inventory_id}>
                      <td className="px-4 py-4">
                        <p className="font-semibold">{row.product_name}</p>
                        <p className="mt-1 text-xs text-[#64748b]">{row.product_sku}</p>
                      </td>
                      <td className="px-4 py-4 font-semibold">{row.quantity}</td>
                      <td className="px-4 py-4 text-amber-700">{row.reserved_quantity}</td>
                      <td className="px-4 py-4 font-bold text-emerald-700">{row.available_quantity}</td>
                      <td className="px-4 py-4">{row.low_stock_threshold}</td>
                      <td className="px-4 py-4">{row.warehouse_location || "—"}</td>
                      <td className="px-4 py-4 text-xs text-[#64748b]">
                        {row.updated_at ? new Date(row.updated_at).toLocaleString() : "—"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {totalPages > 1 && (
            <div className="flex items-center justify-end gap-3 border-t p-4">
              <button disabled={page <= 1} onClick={() => setPage(page - 1)} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">
                Previous
              </button>
              <span className="text-xs text-[#64748b]">
                Page {page} of {totalPages} · {total} records
              </span>
              <button disabled={page >= totalPages} onClick={() => setPage(page + 1)} className="rounded-lg border px-3 py-2 text-sm disabled:opacity-40">
                Next
              </button>
            </div>
          )}
        </section>
      </div>

      {configureProduct && (
        <div className="fixed inset-0 z-[120] bg-black/55 p-4">
          <div className="mx-auto mt-20 max-w-xl rounded-2xl bg-white p-6 shadow-2xl dark:bg-[#1f2937]">
            <h2 className="text-xl font-bold">Configure Opening Stock</h2>
            <p className="mt-1 text-sm text-[#64748b]">
              {configureProduct.name} · {configureProduct.sku}
            </p>

            <div className="mt-5 grid gap-4 sm:grid-cols-2">
              <label className="text-sm font-semibold">
                Physical quantity
                <input type="number" min="0" value={quantity} onChange={(e) => setQuantity(e.target.value)} className="mt-1.5 h-11 w-full rounded-xl border px-3 dark:bg-white/5" />
              </label>
              <label className="text-sm font-semibold">
                Low-stock threshold
                <input type="number" min="0" value={threshold} onChange={(e) => setThreshold(e.target.value)} className="mt-1.5 h-11 w-full rounded-xl border px-3 dark:bg-white/5" />
              </label>
              <label className="text-sm font-semibold sm:col-span-2">
                Warehouse / stock location
                <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="e.g. Main Store - Rack A" className="mt-1.5 h-11 w-full rounded-xl border px-3 dark:bg-white/5" />
              </label>
            </div>

            <div className="mt-5 rounded-xl bg-slate-50 p-4 text-sm dark:bg-white/5">
              <div className="flex justify-between"><span>Quantity</span><b>{Number(quantity) || 0}</b></div>
              <div className="mt-2 flex justify-between"><span>Reserved</span><b>0</b></div>
              <div className="mt-2 flex justify-between text-emerald-700"><span>Available</span><b>{Number(quantity) || 0}</b></div>
            </div>

            <div className="mt-6 flex justify-end gap-3">
              <button disabled={configuring} onClick={() => setConfigureProduct(null)} className="rounded-xl border px-4 py-2.5 text-sm font-semibold">
                Cancel
              </button>
              <button disabled={configuring} onClick={() => void configure()} className="rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
                {configuring ? "Saving..." : "Save Stock"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function Stat({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: number;
  icon: typeof Boxes;
}) {
  return (
    <div className="rounded-2xl border border-[#e2e8f0] bg-white p-4 shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
      <Icon size={17} className="text-[#f7941d]" />
      <p className="mt-3 text-xs font-semibold text-[#64748b]">{label}</p>
      <p className="mt-1 text-2xl font-bold">{value.toLocaleString()}</p>
    </div>
  );
}
