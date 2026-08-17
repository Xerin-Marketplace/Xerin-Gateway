"use client";

import { useEffect, useMemo, useState } from "react";
import {
  ChevronLeft,
  ChevronRight,
  Eye,
  Flag,
  MessageSquareText,
  RefreshCw,
  Search,
  Star,
  UserRound,
  X,
} from "lucide-react";
import toast from "react-hot-toast";
import {
  customersService,
  type CustomerReview,
} from "@/lib/api/endpoints/customers";
import { ApiError } from "@/lib/api/client";

const getErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
};

const STATUS_BADGES: Record<string, string> = {
  pending: "border-amber-200 bg-amber-50 text-amber-700",
  approved: "border-emerald-200 bg-emerald-50 text-emerald-700",
  rejected: "border-red-200 bg-red-50 text-red-700",
  hidden: "border-slate-200 bg-slate-100 text-slate-600",
  flagged: "border-red-200 bg-red-50 text-red-700",
};

const pretty = (value: string) =>
  value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function AdminCustomerReviews() {
  const [reviews, setReviews] = useState<CustomerReview[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [status, setStatus] = useState("");
  const [rating, setRating] = useState("");
  const [reportedOnly, setReportedOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [selected, setSelected] = useState<CustomerReview | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setDebouncedQuery(query.trim());
      setPage(1);
    }, 350);
    return () => window.clearTimeout(timer);
  }, [query]);

  const fetchData = async () => {
    setLoading(true);
    setError("");

    try {
      const data = await customersService.listCustomerReviews({
        page,
        page_size: pageSize,
        search: debouncedQuery || undefined,
        status: status || undefined,
        rating: rating ? Number(rating) : undefined,
        reported: reportedOnly ? true : undefined,
      });

      setReviews(data.results);
      setTotal(data.total);
      setTotalPages(data.total_pages);
    } catch (cause) {
      if (cause instanceof ApiError && cause.status === 401) return;
      const message = getErrorMessage(cause);
      setError(message);
      toast.error(message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, pageSize, debouncedQuery, status, rating, reportedOnly]);

  const openReview = async (review: CustomerReview) => {
    setSelected(review);
    setDetailLoading(true);

    try {
      const detail = await customersService.getCustomerReview(review.id);
      setSelected(detail);
    } catch {
      // Backend Task 2 will provide detail endpoint. The summary row is still
      // useful now, so keep the drawer open with what we already have.
    } finally {
      setDetailLoading(false);
    }
  };

  const stats = useMemo(
    () => ({
      loaded: reviews.length,
      pending: reviews.filter((review) => review.status === "pending").length,
      flagged: reviews.filter(
        (review) => review.status === "flagged" || review.reported,
      ).length,
      average: reviews.length
        ? (
            reviews.reduce((sum, review) => sum + review.rating, 0) /
            reviews.length
          ).toFixed(1)
        : "0.0",
    }),
    [reviews],
  );

  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f47524]">
          Customer voice
        </p>
        <h2 className="mt-1 text-2xl font-bold text-[#111827]">
          Customer Reviews
        </h2>
        <p className="mt-1 max-w-3xl text-sm leading-6 text-[#64748b]">
          Review customer feedback across marketplace products, identify
          reported content and inspect the customer, seller and product context
          before moderation.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric label="Total matching reviews" value={total} icon={MessageSquareText} />
        <Metric label="Pending on page" value={stats.pending} icon={RefreshCw} />
        <Metric label="Reported on page" value={stats.flagged} icon={Flag} />
        <Metric label="Average rating" value={`${stats.average}/5`} icon={Star} />
      </section>

      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <div className="grid gap-3 lg:grid-cols-[minmax(260px,1.7fr)_repeat(3,minmax(145px,1fr))]">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search customer, product, seller or review..."
              className="h-11 w-full rounded-xl border-2 border-[#d8e0e9] pl-10 pr-4 text-sm outline-none focus:border-[#f47524]"
            />
          </div>

          <select
            value={status}
            onChange={(event) => {
              setStatus(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm"
          >
            <option value="">All statuses</option>
            {["pending", "approved", "hidden", "flagged", "rejected"].map(
              (value) => (
                <option key={value} value={value}>
                  {pretty(value)}
                </option>
              ),
            )}
          </select>

          <select
            value={rating}
            onChange={(event) => {
              setRating(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm"
          >
            <option value="">All ratings</option>
            {[5, 4, 3, 2, 1].map((value) => (
              <option key={value} value={value}>
                {value} star{value === 1 ? "" : "s"}
              </option>
            ))}
          </select>

          <label className="flex h-11 items-center gap-2 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm font-medium text-[#475569]">
            <input
              type="checkbox"
              checked={reportedOnly}
              onChange={(event) => {
                setReportedOnly(event.target.checked);
                setPage(1);
              }}
            />
            Reported only
          </label>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-[#e2e8f0] bg-white shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-gray-500">
            <RefreshCw className="mx-auto animate-spin" size={22} />
            <p className="mt-3 text-sm">Loading customer reviews...</p>
          </div>
        ) : error ? (
          <div className="p-12 text-center">
            <p className="text-sm font-semibold text-red-600">{error}</p>
            <button
              type="button"
              onClick={() => void fetchData()}
              className="mt-3 text-sm font-semibold text-[#f47524]"
            >
              Retry
            </button>
          </div>
        ) : !reviews.length ? (
          <div className="p-12 text-center text-gray-500">
            No matching reviews found.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1050px] text-left text-sm">
              <thead className="bg-[#f8fafc] text-xs uppercase text-[#64748b]">
                <tr>
                  {[
                    "Customer",
                    "Product / Seller",
                    "Rating",
                    "Review",
                    "Status",
                    "Date",
                    "Action",
                  ].map((heading) => (
                    <th key={heading} className="px-5 py-3">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody className="divide-y divide-[#edf0f4]">
                {reviews.map((review) => (
                  <tr key={review.id} className="hover:bg-orange-50/20">
                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2.5">
                        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500">
                          <UserRound size={14} />
                        </span>
                        <div>
                          <p className="font-semibold text-[#111827]">
                            {review.customer_name || "Customer"}
                          </p>
                          <p className="text-xs text-gray-500">
                            {review.customer_email ||
                              review.user_id.slice(0, 10)}
                          </p>
                        </div>
                      </div>
                    </td>

                    <td className="px-5 py-4">
                      <p className="font-semibold text-[#111827]">
                        {review.product_name ||
                          review.product?.name ||
                          `Product ${review.product_id.slice(0, 8)}`}
                      </p>
                      <p className="mt-0.5 text-xs text-gray-500">
                        Seller: {review.seller_name || "Not provided"}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex items-center gap-1 font-semibold">
                        <Star size={14} className="text-amber-500" />
                        {review.rating}/5
                      </div>
                    </td>

                    <td className="max-w-sm px-5 py-4 text-[#64748b]">
                      <p className="line-clamp-2">
                        {review.comment || "No written comment."}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
                          STATUS_BADGES[review.status] ||
                          "border-slate-200 bg-slate-100 text-slate-600"
                        }`}
                      >
                        {pretty(review.status)}
                      </span>
                    </td>

                    <td className="px-5 py-4 text-xs text-gray-500">
                      {new Date(review.created_at).toLocaleString()}
                    </td>

                    <td className="px-5 py-4">
                      <button
                        type="button"
                        onClick={() => void openReview(review)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-[#111827] px-3 py-2 text-xs font-semibold text-white"
                      >
                        <Eye size={13} />
                        Review
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && !error && (
          <Pagination
            page={page}
            pageSize={pageSize}
            total={total}
            totalPages={totalPages}
            from={from}
            to={to}
            onPage={setPage}
            onPageSize={(size) => {
              setPageSize(size);
              setPage(1);
            }}
          />
        )}
      </section>

      {selected && (
        <div
          className="fixed inset-0 z-[110] flex justify-end bg-black/50 backdrop-blur-[2px]"
          onMouseDown={() => setSelected(null)}
        >
          <aside
            className="h-full w-full max-w-2xl overflow-y-auto bg-[#f8fafc] shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="sticky top-0 z-10 flex items-start justify-between border-b bg-white px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f47524]">
                  Review inspection
                </p>
                <h3 className="mt-1 text-xl font-bold text-[#111827]">
                  Customer Review
                </h3>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100"
              >
                <X size={17} />
              </button>
            </div>

            <div className="space-y-5 p-6">
              {detailLoading && (
                <p className="text-sm text-gray-500">
                  Loading full review context...
                </p>
              )}

              <section className="grid gap-3 sm:grid-cols-2">
                <Info label="Customer" value={selected.customer_name || selected.user_id} />
                <Info
                  label="Product"
                  value={
                    selected.product_name ||
                    selected.product?.name ||
                    selected.product_id
                  }
                />
                <Info label="Seller" value={selected.seller_name || "—"} />
                <Info label="Rating" value={`${selected.rating}/5`} />
                <Info label="Status" value={pretty(selected.status)} />
                <Info
                  label="Reports"
                  value={String(selected.report_count ?? (selected.reported ? 1 : 0))}
                />
              </section>

              <section className="rounded-2xl border bg-white p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Customer comment
                </p>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-[#475569]">
                  {selected.comment || "No written comment was submitted."}
                </p>
              </section>

              <section className="rounded-2xl border bg-white p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Admin reply
                </p>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-[#475569]">
                  {selected.admin_reply ||
                    "No administrative response has been recorded yet."}
                </p>
              </section>

              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
                Moderation actions and admin replies are prepared in the
                frontend API contract. We will connect the actual approve,
                hide, reject and reply operations when we complete Backend
                Task 2.
              </div>
            </div>
          </aside>
        </div>
      )}
    </div>
  );
}

function Metric({
  label,
  value,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  icon: typeof Star;
}) {
  return (
    <article className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
      <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-orange-50 text-[#f47524]">
        <Icon size={17} />
      </span>
      <p className="mt-4 text-2xl font-bold text-[#111827]">{value}</p>
      <p className="mt-1 text-xs text-gray-500">{label}</p>
    </article>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border bg-white p-4">
      <p className="text-[10px] font-bold uppercase tracking-wider text-gray-400">
        {label}
      </p>
      <p className="mt-1 break-words text-sm font-semibold text-[#111827]">
        {value}
      </p>
    </div>
  );
}

function Pagination({
  page,
  pageSize,
  total,
  totalPages,
  from,
  to,
  onPage,
  onPageSize,
}: {
  page: number;
  pageSize: number;
  total: number;
  totalPages: number;
  from: number;
  to: number;
  onPage: (page: number) => void;
  onPageSize: (size: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3 border-t px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
      <p className="text-sm text-gray-500">
        Showing <b className="text-[#111827]">{from}-{to}</b> of{" "}
        <b className="text-[#111827]">{total}</b>
      </p>
      <div className="flex items-center gap-2">
        <select
          value={pageSize}
          onChange={(event) => onPageSize(Number(event.target.value))}
          className="h-10 rounded-xl border bg-white px-3 text-sm"
        >
          {[10, 20, 50, 100].map((size) => (
            <option key={size} value={size}>
              {size} / page
            </option>
          ))}
        </select>
        <button
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="inline-flex h-10 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-40"
        >
          <ChevronLeft size={14} /> Previous
        </button>
        <span className="min-w-24 text-center text-xs font-semibold text-gray-500">
          Page {page} of {Math.max(totalPages, 1)}
        </span>
        <button
          disabled={page >= totalPages || totalPages === 0}
          onClick={() => onPage(page + 1)}
          className="inline-flex h-10 items-center gap-1 rounded-xl border px-3 text-sm font-semibold disabled:opacity-40"
        >
          Next <ChevronRight size={14} />
        </button>
      </div>
    </div>
  );
}
