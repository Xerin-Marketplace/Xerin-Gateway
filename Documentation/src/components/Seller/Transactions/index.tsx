"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ArrowDownCircle,
  ArrowUpCircle,
  ChevronLeft,
  ChevronRight,
  Clock3,
  CreditCard,
  RefreshCw,
  RotateCcw,
  Search,
  WalletCards,
} from "lucide-react";
import toast from "react-hot-toast";

import { sellerWalletApi } from "@/lib/api/endpoints/seller-wallet";
import type {
  SellerWalletTransaction,
  WalletTransactionType,
} from "@/types/api/seller-wallet";

const errorMessage = (error: unknown) => {
  const candidate = error as {
    response?: { data?: { detail?: string | Array<{ msg?: string }> } };
    message?: string;
  };
  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg || "Request failed.";
  return candidate.message || "Request failed.";
};

const money = (value: number | string, currency = "TZS") =>
  new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const transactionMeta = (type: WalletTransactionType) => {
  switch (type) {
    case "sale_credit":
      return { label: "Sale Credit", direction: "credit", icon: ArrowDownCircle };
    case "funds_release":
      return { label: "Funds Release", direction: "credit", icon: ArrowDownCircle };
    case "payout_hold":
      return { label: "Payout Hold", direction: "hold", icon: Clock3 };
    case "payout_completed":
    case "payout_released":
      return { label: pretty(type), direction: "debit", icon: ArrowUpCircle };
    case "refund_debit":
      return { label: "Refund Debit", direction: "debit", icon: RotateCcw };
    default:
      return { label: pretty(type), direction: "neutral", icon: CreditCard };
  }
};

export default function SellerTransactions() {
  const [rows, setRows] = useState<SellerWalletTransaction[]>([]);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [meta, setMeta] = useState({ total: 0, total_pages: 0 });
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("all");

  const load = async () => {
    setLoading(true);
    try {
      const result = await sellerWalletApi.transactions({
        page,
        page_size: pageSize,
      });
      setRows(result.results);
      setMeta({ total: result.total, total_pages: result.total_pages });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [page, pageSize]);

  // Backend currently paginates wallet transactions but does not expose
  // search/type parameters. These filters intentionally operate only on the
  // current server-returned page instead of pretending they are server-side.
  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();

    return rows.filter((row) => {
      if (typeFilter !== "all" && row.transaction_type !== typeFilter) {
        return false;
      }

      if (!term) return true;

      return [
        row.reference,
        row.description || "",
        row.order_id || "",
        row.transaction_type,
      ]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [rows, search, typeFilter]);

  const creditTotal = visibleRows
    .filter((row) =>
      ["sale_credit", "funds_release"].includes(row.transaction_type),
    )
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);

  const debitTotal = visibleRows
    .filter((row) =>
      ["payout_completed", "payout_released", "refund_debit"].includes(
        row.transaction_type,
      ),
    )
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
              Seller Phase 7
            </p>
            <h1 className="mt-1 text-2xl font-bold text-slate-900 dark:text-white">
              Wallet Transactions
            </h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500 dark:text-white/60">
              Review seller wallet credits, releases, payout holds, completed
              payouts, refunds and administrative adjustments.
            </p>
          </div>

          <button
            type="button"
            onClick={() => void load()}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 dark:border-white/10 dark:text-white/65"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-3">
          <Summary
            label="Transactions on page"
            value={String(visibleRows.length)}
            icon={WalletCards}
          />
          <Summary
            label="Credits on page"
            value={
              visibleRows[0]
                ? money(creditTotal, visibleRows[0].currency)
                : money(0)
            }
            icon={ArrowDownCircle}
          />
          <Summary
            label="Debits on page"
            value={
              visibleRows[0]
                ? money(debitTotal, visibleRows[0].currency)
                : money(0)
            }
            icon={ArrowUpCircle}
          />
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
        <div className="flex flex-col gap-3 border-b border-slate-100 p-5 lg:flex-row lg:items-center lg:justify-between dark:border-white/10">
          <div>
            <h2 className="font-bold text-slate-900 dark:text-white">
              Transaction Ledger
            </h2>
            <p className="mt-1 text-xs text-slate-400">
              Pagination is backend-controlled. Search and type filtering apply to
              the current page because the backend does not expose those query
              parameters yet.
            </p>
          </div>

          <div className="flex flex-col gap-2 sm:flex-row">
            <label className="relative">
              <Search
                size={15}
                className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400"
              />
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Filter current page..."
                className="h-11 min-w-[260px] rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
              />
            </label>

            <select
              value={typeFilter}
              onChange={(event) => setTypeFilter(event.target.value)}
              className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
            >
              <option value="all">All transaction types</option>
              <option value="sale_credit">Sale Credit</option>
              <option value="funds_release">Funds Release</option>
              <option value="payout_hold">Payout Hold</option>
              <option value="payout_completed">Payout Completed</option>
              <option value="payout_released">Payout Released</option>
              <option value="refund_debit">Refund Debit</option>
              <option value="adjustment">Adjustment</option>
            </select>
          </div>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-slate-500">
            <RefreshCw size={20} className="mx-auto animate-spin" />
            <p className="mt-3">Loading wallet transactions...</p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1000px] text-left text-sm">
                <thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400 dark:bg-white/5">
                  <tr>
                    {[
                      "Type",
                      "Reference",
                      "Order",
                      "Amount",
                      "Eligible",
                      "Released",
                      "Created",
                    ].map((header) => (
                      <th key={header} className="px-5 py-3.5">
                        {header}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-100 dark:divide-white/10">
                  {visibleRows.map((row) => {
                    const meta = transactionMeta(row.transaction_type);
                    const Icon = meta.icon;

                    return (
                      <tr key={row.id}>
                        <td className="px-5 py-4">
                          <div className="flex items-center gap-2">
                            <span
                              className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                                meta.direction === "credit"
                                  ? "bg-emerald-50 text-emerald-600"
                                  : meta.direction === "debit"
                                    ? "bg-red-50 text-red-600"
                                    : meta.direction === "hold"
                                      ? "bg-amber-50 text-amber-600"
                                      : "bg-slate-100 text-slate-500"
                              }`}
                            >
                              <Icon size={15} />
                            </span>
                            <div>
                              <p className="font-semibold text-slate-800 dark:text-white/80">
                                {meta.label}
                              </p>
                              {row.description && (
                                <p className="mt-0.5 max-w-[240px] truncate text-[11px] text-slate-400">
                                  {row.description}
                                </p>
                              )}
                            </div>
                          </div>
                        </td>

                        <td className="px-5 py-4 font-mono text-xs text-slate-500">
                          {row.reference}
                        </td>

                        <td className="px-5 py-4 font-mono text-xs text-slate-500">
                          {row.order_id
                            ? `${row.order_id.slice(0, 8)}…`
                            : "—"}
                        </td>

                        <td className="px-5 py-4">
                          <span
                            className={`font-bold ${
                              meta.direction === "credit"
                                ? "text-emerald-700"
                                : meta.direction === "debit"
                                  ? "text-red-600"
                                  : "text-slate-800 dark:text-white"
                            }`}
                          >
                            {meta.direction === "credit"
                              ? "+"
                              : meta.direction === "debit"
                                ? "-"
                                : ""}
                            {money(row.amount, row.currency)}
                          </span>
                        </td>

                        <td className="px-5 py-4 text-xs text-slate-500">
                          {row.eligible_at
                            ? new Date(row.eligible_at).toLocaleString()
                            : "—"}
                        </td>

                        <td className="px-5 py-4 text-xs text-slate-500">
                          {row.released_at
                            ? new Date(row.released_at).toLocaleString()
                            : "—"}
                        </td>

                        <td className="px-5 py-4 text-xs text-slate-500">
                          {new Date(row.created_at).toLocaleString()}
                        </td>
                      </tr>
                    );
                  })}

                  {!visibleRows.length && (
                    <tr>
                      <td colSpan={7} className="px-5 py-14 text-center">
                        <CreditCard size={28} className="mx-auto text-slate-300" />
                        <p className="mt-3 font-semibold text-slate-600 dark:text-white/70">
                          No wallet transactions found
                        </p>
                        <p className="mt-1 text-sm text-slate-400">
                          Seller wallet transactions will appear here as settlement
                          activity occurs.
                        </p>
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>

            <Pagination
              page={page}
              pageSize={pageSize}
              total={meta.total}
              totalPages={meta.total_pages}
              onPage={setPage}
              onPageSize={(size) => {
                setPageSize(size);
                setPage(1);
              }}
            />
          </>
        )}
      </section>
    </div>
  );
}

function Summary({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string;
  icon: typeof WalletCards;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 dark:border-white/10 dark:bg-white/[0.03]">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-lg font-bold text-slate-900 dark:text-white">
            {value}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-white/50">
            {label}
          </p>
        </div>
        <Icon size={18} className="text-[#f7941d]" />
      </div>
    </div>
  );
}

function Pagination({
  page,
  pageSize,
  total,
  totalPages,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}) {
  const from = total ? (page - 1) * pageSize + 1 : 0;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="flex flex-col gap-3 border-t border-slate-100 px-5 py-4 sm:flex-row sm:items-center sm:justify-between dark:border-white/10">
      <p className="text-sm text-slate-500 dark:text-white/50">
        Showing <b>{from}-{to}</b> of <b>{total}</b>
      </p>

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={pageSize}
          onChange={(event) => onPageSize(Number(event.target.value))}
          className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm dark:border-white/10 dark:bg-white/5 dark:text-white"
        >
          {[10, 20, 50, 100].map((size) => (
            <option key={size} value={size}>
              {size} / page
            </option>
          ))}
        </select>

        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="inline-flex h-10 items-center gap-1 rounded-xl border border-slate-200 px-3 text-sm font-semibold disabled:opacity-40 dark:border-white/10"
        >
          <ChevronLeft size={14} />
          Previous
        </button>

        <span className="min-w-[80px] text-center text-xs text-slate-400">
          Page {page} of {Math.max(totalPages, 1)}
        </span>

        <button
          type="button"
          disabled={!totalPages || page >= totalPages}
          onClick={() => onPage(page + 1)}
          className="inline-flex h-10 items-center gap-1 rounded-xl border border-slate-200 px-3 text-sm font-semibold disabled:opacity-40 dark:border-white/10"
        >
          Next
          <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
