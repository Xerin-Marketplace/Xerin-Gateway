"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import {
  BadgeCheck,
  Banknote,
  ChevronLeft,
  ChevronRight,
  CircleAlert,
  Clock3,
  Landmark,
  RefreshCw,
  Search,
  ShieldCheck,
  Smartphone,
  WalletCards,
  XCircle,
} from "lucide-react";
import toast from "react-hot-toast";

import { sellerWalletApi } from "@/lib/api/endpoints/seller-wallet";
import { sellersApi } from "@/lib/api/endpoints/sellers";
import type { PayoutAccount } from "@/types/api/seller";
import type {
  PayoutStatus,
  SellerPayoutRequest,
  SellerWallet,
} from "@/types/api/seller-wallet";

type StatusFilter =
  | "all"
  | "pending"
  | "approved"
  | "processing"
  | "completed"
  | "rejected"
  | "failed"
  | "cancelled";

const money = (value: number | string | null | undefined, currency = "TZS") =>
  new Intl.NumberFormat("en-TZ", {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(Number(value || 0));

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

const errorMessage = (error: unknown) => {
  const candidate = error as {
    response?: { data?: { detail?: string | Array<{ msg?: string }> } };
    message?: string;
  };

  const detail = candidate.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail[0]?.msg) {
    return detail[0].msg || "Request failed.";
  }

  return candidate.message || "Request failed.";
};

const statusMeta = (status: PayoutStatus) => {
  switch (status) {
    case "completed":
      return {
        label: "Completed",
        className: "border-emerald-200 bg-emerald-50 text-emerald-700",
      };
    case "approved":
      return {
        label: "Approved",
        className: "border-blue-200 bg-blue-50 text-blue-700",
      };
    case "processing":
      return {
        label: "Processing",
        className: "border-violet-200 bg-violet-50 text-violet-700",
      };
    case "rejected":
    case "failed":
      return {
        label: pretty(status),
        className: "border-red-200 bg-red-50 text-red-700",
      };
    case "cancelled":
      return {
        label: "Cancelled",
        className: "border-slate-200 bg-slate-50 text-slate-600",
      };
    default:
      return {
        label: "Pending",
        className: "border-amber-200 bg-amber-50 text-amber-700",
      };
  }
};

const maskAccount = (value: string) => {
  if (!value) return "—";
  if (value.length <= 4) return value;
  return `${"•".repeat(Math.min(value.length - 4, 8))}${value.slice(-4)}`;
};

export default function SellerPayouts() {
  const [wallet, setWallet] = useState<SellerWallet | null>(null);
  const [accounts, setAccounts] = useState<PayoutAccount[]>([]);
  const [rows, setRows] = useState<SellerPayoutRequest[]>([]);

  const [loading, setLoading] = useState(true);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [busyPayout, setBusyPayout] = useState<string | null>(null);

  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [meta, setMeta] = useState({ total: 0, total_pages: 0 });

  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");

  const [accountId, setAccountId] = useState("");
  const [amount, setAmount] = useState("");
  const [note, setNote] = useState("");

  const loadFoundation = async () => {
    setLoading(true);
    try {
      const [walletData, payoutAccounts] = await Promise.all([
        sellerWalletApi.wallet(),
        sellersApi.getPayoutAccounts(),
      ]);

      setWallet(walletData);
      setAccounts(payoutAccounts);

      const verifiedDefault =
        payoutAccounts.find(
          (account) =>
            account.is_default &&
            account.is_active !== false &&
            account.verification_status === "verified",
        ) ||
        payoutAccounts.find(
          (account) =>
            account.is_active !== false &&
            account.verification_status === "verified",
        );

      setAccountId((current) => current || verifiedDefault?.id || "");
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const result = await sellerWalletApi.payouts({
        page,
        page_size: pageSize,
      });
      setRows(result.results);
      setMeta({
        total: result.total,
        total_pages: result.total_pages,
      });
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setHistoryLoading(false);
    }
  };

  useEffect(() => {
    void loadFoundation();
  }, []);

  useEffect(() => {
    void loadHistory();
  }, [page, pageSize]);

  const verifiedAccounts = useMemo(
    () =>
      accounts.filter(
        (account) =>
          account.is_active !== false &&
          account.verification_status === "verified",
      ),
    [accounts],
  );

  const selectedAccount = verifiedAccounts.find(
    (account) => account.id === accountId,
  );

  // Current backend payout history endpoint provides pagination only.
  // Search and status filtering below intentionally apply to the current page.
  const visibleRows = useMemo(() => {
    const term = search.trim().toLowerCase();

    return rows.filter((row) => {
      if (statusFilter !== "all" && row.status !== statusFilter) return false;

      if (!term) return true;

      const account = accounts.find(
        (candidate) => candidate.id === row.payout_account_id,
      );

      return [
        row.id,
        row.provider_reference || "",
        row.seller_note || "",
        row.admin_note || "",
        row.status,
        account?.provider || "",
        account?.account_name || "",
      ]
        .join(" ")
        .toLowerCase()
        .includes(term);
    });
  }, [rows, search, statusFilter, accounts]);

  const pendingAmount = rows
    .filter((row) =>
      ["pending", "approved", "processing"].includes(row.status),
    )
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);

  const completedAmount = rows
    .filter((row) => row.status === "completed")
    .reduce((sum, row) => sum + Number(row.amount || 0), 0);

  const submitPayout = async () => {
    if (!wallet) return;

    const numericAmount = Number(amount);

    if (!selectedAccount) {
      toast.error("Select a verified payout account.");
      return;
    }

    if (!Number.isFinite(numericAmount) || numericAmount <= 0) {
      toast.error("Enter a valid payout amount.");
      return;
    }

    if (numericAmount > Number(wallet.available_balance || 0)) {
      toast.error("Payout amount exceeds your available balance.");
      return;
    }

    setSubmitting(true);
    try {
      await sellerWalletApi.requestPayout({
        payout_account_id: selectedAccount.id,
        amount: numericAmount,
        note: note.trim() || null,
      });

      toast.success("Payout request submitted.");
      setAmount("");
      setNote("");
      setPage(1);

      await Promise.all([loadFoundation(), loadHistory()]);
    } catch (error) {
      // The backend remains authoritative for minimum payout and wallet rules.
      toast.error(errorMessage(error));
    } finally {
      setSubmitting(false);
    }
  };

  const cancelPayout = async (row: SellerPayoutRequest) => {
    if (
      !window.confirm(
        `Cancel payout request for ${money(row.amount, row.currency)}?`,
      )
    ) {
      return;
    }

    setBusyPayout(row.id);
    try {
      await sellerWalletApi.cancelPayout(row.id);
      toast.success("Payout request cancelled.");
      await Promise.all([loadFoundation(), loadHistory()]);
    } catch (error) {
      toast.error(errorMessage(error));
    } finally {
      setBusyPayout(null);
    }
  };

  const currency = wallet?.currency || "TZS";

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#f7941d]">
              Seller Phase 8
            </p>
            <h1 className="mt-1 text-2xl font-bold tracking-[-0.02em] text-slate-900 dark:text-white">
              Payout Requests
            </h1>
            <p className="mt-2 text-sm leading-6 text-slate-500 dark:text-white/60">
              Request settlement of available seller funds to a verified payout
              account and follow each request from pending through completion.
            </p>
          </div>

          <button
            type="button"
            onClick={() => {
              void loadFoundation();
              void loadHistory();
            }}
            className="inline-flex items-center justify-center gap-2 rounded-xl border border-slate-200 px-4 py-2.5 text-sm font-semibold text-slate-600 dark:border-white/10 dark:text-white/65"
          >
            <RefreshCw size={15} />
            Refresh
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <Summary
            label="Available Balance"
            value={money(wallet?.available_balance, currency)}
            icon={WalletCards}
            highlight
          />
          <Summary
            label="Reserved Balance"
            value={money(wallet?.reserved_balance, currency)}
            icon={ShieldCheck}
          />
          <Summary
            label="Pending on this page"
            value={money(pendingAmount, currency)}
            icon={Clock3}
          />
          <Summary
            label="Completed on this page"
            value={money(completedAmount, currency)}
            icon={BadgeCheck}
          />
        </div>
      </section>

      {wallet?.is_frozen && (
        <div className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm leading-6 text-red-700">
          <div className="flex items-start gap-3">
            <CircleAlert size={18} className="mt-0.5 shrink-0" />
            <p>
              Your seller wallet is currently frozen. Payout requests may be
              blocked by the backend until the restriction is removed.
            </p>
          </div>
        </div>
      )}

      <section className="grid gap-5 xl:grid-cols-[420px_1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm dark:border-white/10 dark:bg-[#1f2937] sm:p-6">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-orange-50 text-[#f7941d] dark:bg-orange-400/10">
              <Banknote size={19} />
            </span>
            <div>
              <h2 className="font-bold text-slate-900 dark:text-white">
                Request Payout
              </h2>
              <p className="mt-0.5 text-xs text-slate-400">
                Only active and verified accounts can receive payouts.
              </p>
            </div>
          </div>

          {loading ? (
            <div className="py-10 text-center text-sm text-slate-500">
              <RefreshCw size={18} className="mx-auto animate-spin" />
              <p className="mt-2">Loading payout configuration...</p>
            </div>
          ) : verifiedAccounts.length === 0 ? (
            <div className="mt-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
              <p className="text-sm font-semibold text-amber-800">
                No verified payout account
              </p>
              <p className="mt-1 text-xs leading-5 text-amber-700">
                Add a payout account and wait for authorized Xerin staff to verify
                it before requesting settlement.
              </p>
              <Link
                href="/seller/kyc?tab=payouts"
                className="mt-3 inline-flex rounded-lg bg-white px-3 py-2 text-xs font-semibold text-amber-800 shadow-sm"
              >
                Manage Payout Accounts
              </Link>
            </div>
          ) : (
            <div className="mt-5 space-y-4">
              <Field label="Payout account" required>
                <select
                  value={accountId}
                  onChange={(event) => setAccountId(event.target.value)}
                  className={inputClass}
                >
                  <option value="">Select verified account</option>
                  {verifiedAccounts.map((account) => (
                    <option key={account.id} value={account.id}>
                      {account.provider} · {account.account_name} ·{" "}
                      {maskAccount(account.account_number)}
                    </option>
                  ))}
                </select>
              </Field>

              {selectedAccount && (
                <div className="rounded-xl border border-emerald-200 bg-emerald-50 p-3">
                  <div className="flex items-start gap-3">
                    {selectedAccount.account_type === "mobile_money" ? (
                      <Smartphone
                        size={17}
                        className="mt-0.5 text-emerald-700"
                      />
                    ) : (
                      <Landmark
                        size={17}
                        className="mt-0.5 text-emerald-700"
                      />
                    )}
                    <div>
                      <p className="text-sm font-semibold text-emerald-800">
                        {selectedAccount.provider}
                      </p>
                      <p className="mt-0.5 text-xs text-emerald-700">
                        {selectedAccount.account_name} ·{" "}
                        {maskAccount(selectedAccount.account_number)}
                      </p>
                      <p className="mt-1 text-[11px] font-semibold uppercase tracking-wide text-emerald-700">
                        Verified
                        {selectedAccount.is_default ? " · Default" : ""}
                      </p>
                    </div>
                  </div>
                </div>
              )}

              <Field
                label={`Amount (${currency})`}
                required
                hint={`Available: ${money(wallet?.available_balance, currency)}`}
              >
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={amount}
                  onChange={(event) => setAmount(event.target.value)}
                  className={inputClass}
                  placeholder="Enter payout amount"
                />
              </Field>

              <button
                type="button"
                onClick={() =>
                  setAmount(String(Number(wallet?.available_balance || 0)))
                }
                className="text-xs font-semibold text-[#f7941d]"
              >
                Use full available balance
              </button>

              <Field
                label="Seller note"
                hint="Optional note attached to this payout request."
              >
                <textarea
                  value={note}
                  onChange={(event) => setNote(event.target.value)}
                  className={`${inputClass} min-h-24 py-3`}
                  placeholder="Optional payout note..."
                  maxLength={1000}
                />
              </Field>

              <button
                type="button"
                disabled={
                  submitting ||
                  wallet?.is_frozen ||
                  !accountId ||
                  !amount ||
                  Number(amount) <= 0
                }
                onClick={() => void submitPayout()}
                className="w-full rounded-xl bg-[#f7941d] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#e88312] disabled:cursor-not-allowed disabled:opacity-50"
              >
                {submitting ? "Submitting..." : "Request Payout"}
              </button>

              <div className="rounded-xl border border-blue-200 bg-blue-50 p-3 text-xs leading-5 text-blue-800">
                The backend validates the Finance minimum payout amount, available
                wallet balance, account ownership and verification status when you
                submit the request.
              </div>
            </div>
          )}
        </div>

        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm dark:border-white/10 dark:bg-[#1f2937]">
          <div className="flex flex-col gap-3 border-b border-slate-100 p-5 lg:flex-row lg:items-center lg:justify-between dark:border-white/10">
            <div>
              <h2 className="font-bold text-slate-900 dark:text-white">
                Payout History
              </h2>
              <p className="mt-1 text-xs text-slate-400">
                Pagination is backend-controlled. Search and status filters apply
                to the current page because the current payout endpoint exposes
                page and page_size only.
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
                  className="h-11 min-w-[240px] rounded-xl border border-slate-200 bg-white pl-10 pr-3 text-sm outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
                />
              </label>

              <select
                value={statusFilter}
                onChange={(event) =>
                  setStatusFilter(event.target.value as StatusFilter)
                }
                className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm outline-none dark:border-white/10 dark:bg-white/5 dark:text-white"
              >
                <option value="all">All statuses</option>
                <option value="pending">Pending</option>
                <option value="approved">Approved</option>
                <option value="processing">Processing</option>
                <option value="completed">Completed</option>
                <option value="rejected">Rejected</option>
                <option value="failed">Failed</option>
                <option value="cancelled">Cancelled</option>
              </select>
            </div>
          </div>

          {historyLoading ? (
            <div className="p-12 text-center text-sm text-slate-500">
              <RefreshCw size={20} className="mx-auto animate-spin" />
              <p className="mt-3">Loading payout history...</p>
            </div>
          ) : (
            <>
              <div className="overflow-x-auto">
                <table className="w-full min-w-[1050px] text-left text-sm">
                  <thead className="bg-slate-50 text-[10px] font-bold uppercase tracking-[0.08em] text-slate-400 dark:bg-white/5">
                    <tr>
                      {[
                        "Requested",
                        "Account",
                        "Amount",
                        "Status",
                        "Provider Ref",
                        "Processed",
                        "Completed",
                        "Action",
                      ].map((header) => (
                        <th key={header} className="px-5 py-3.5">
                          {header}
                        </th>
                      ))}
                    </tr>
                  </thead>

                  <tbody className="divide-y divide-slate-100 dark:divide-white/10">
                    {visibleRows.map((row) => {
                      const account = accounts.find(
                        (candidate) =>
                          candidate.id === row.payout_account_id,
                      );
                      const metaStatus = statusMeta(row.status);

                      return (
                        <tr key={row.id}>
                          <td className="px-5 py-4 text-xs text-slate-500">
                            {new Date(row.requested_at).toLocaleString()}
                          </td>

                          <td className="px-5 py-4">
                            {account ? (
                              <>
                                <p className="font-semibold text-slate-800 dark:text-white/80">
                                  {account.provider}
                                </p>
                                <p className="mt-0.5 text-xs text-slate-400">
                                  {maskAccount(account.account_number)}
                                </p>
                              </>
                            ) : (
                              <span className="font-mono text-xs text-slate-400">
                                {row.payout_account_id.slice(0, 8)}…
                              </span>
                            )}
                          </td>

                          <td className="px-5 py-4 font-bold text-slate-900 dark:text-white">
                            {money(row.amount, row.currency)}
                          </td>

                          <td className="px-5 py-4">
                            <span
                              className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide ${metaStatus.className}`}
                            >
                              {metaStatus.label}
                            </span>
                            {row.admin_note && (
                              <p className="mt-1 max-w-[220px] text-[11px] leading-4 text-slate-400">
                                {row.admin_note}
                              </p>
                            )}
                          </td>

                          <td className="px-5 py-4 font-mono text-xs text-slate-500">
                            {row.provider_reference || "—"}
                          </td>

                          <td className="px-5 py-4 text-xs text-slate-500">
                            {row.processed_at
                              ? new Date(row.processed_at).toLocaleString()
                              : "—"}
                          </td>

                          <td className="px-5 py-4 text-xs text-slate-500">
                            {row.completed_at
                              ? new Date(row.completed_at).toLocaleString()
                              : "—"}
                          </td>

                          <td className="px-5 py-4">
                            {row.status === "pending" ? (
                              <button
                                type="button"
                                disabled={busyPayout === row.id}
                                onClick={() => void cancelPayout(row)}
                                className="inline-flex items-center gap-1.5 rounded-lg border border-red-200 px-3 py-2 text-xs font-semibold text-red-600 disabled:opacity-50"
                              >
                                <XCircle size={13} />
                                Cancel
                              </button>
                            ) : (
                              <span className="text-xs text-slate-400">
                                —
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}

                    {!visibleRows.length && (
                      <tr>
                        <td colSpan={8} className="px-5 py-14 text-center">
                          <Banknote
                            size={28}
                            className="mx-auto text-slate-300"
                          />
                          <p className="mt-3 font-semibold text-slate-600 dark:text-white/70">
                            No payout requests found
                          </p>
                          <p className="mt-1 text-sm text-slate-400">
                            Eligible seller payout requests will appear here.
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
                onPageSize={(value) => {
                  setPageSize(value);
                  setPage(1);
                }}
              />
            </>
          )}
        </section>
      </section>
    </div>
  );
}

function Summary({
  label,
  value,
  icon: Icon,
  highlight = false,
}: {
  label: string;
  value: string;
  icon: typeof WalletCards;
  highlight?: boolean;
}) {
  return (
    <div
      className={`rounded-xl border p-4 ${
        highlight
          ? "border-orange-200 bg-orange-50"
          : "border-slate-200 bg-slate-50 dark:border-white/10 dark:bg-white/[0.03]"
      }`}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-lg font-bold text-slate-900 dark:text-white">
            {value}
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-white/50">
            {label}
          </p>
        </div>
        <Icon
          size={18}
          className={highlight ? "text-[#f7941d]" : "text-slate-400"}
        />
      </div>
    </div>
  );
}

function Field({
  label,
  required = false,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold text-slate-600 dark:text-white/65">
        {label} {required && <span className="text-red-500">*</span>}
      </span>
      {children}
      {hint && (
        <span className="mt-1 block text-[11px] leading-4 text-slate-400">
          {hint}
        </span>
      )}
    </label>
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

const inputClass =
  "w-full rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800 outline-none transition focus:border-orange-300 focus:ring-4 focus:ring-orange-50 dark:border-white/10 dark:bg-white/5 dark:text-white";
