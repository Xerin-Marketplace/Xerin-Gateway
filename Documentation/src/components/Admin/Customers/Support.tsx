"use client";

import { useEffect, useMemo, useState } from "react";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Clock3,
  Eye,
  Headphones,
  MessageCircleMore,
  RefreshCw,
  Search,
  ShieldAlert,
  Truck,
  UserRound,
  UsersRound,
  X,
} from "lucide-react";
import toast from "react-hot-toast";
import {
  customersService,
  type SupportTicket,
} from "@/lib/api/endpoints/customers";
import { ApiError } from "@/lib/api/client";

const getErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
};

const STATUS_BADGES: Record<string, string> = {
  open: "border-blue-200 bg-blue-50 text-blue-700",
  pending: "border-amber-200 bg-amber-50 text-amber-700",
  in_progress: "border-indigo-200 bg-indigo-50 text-indigo-700",
  processing: "border-indigo-200 bg-indigo-50 text-indigo-700",
  resolved: "border-emerald-200 bg-emerald-50 text-emerald-700",
  closed: "border-slate-200 bg-slate-100 text-slate-600",
};

const PRIORITY_BADGES: Record<string, string> = {
  low: "border-slate-200 bg-slate-100 text-slate-600",
  medium: "border-amber-200 bg-amber-50 text-amber-700",
  high: "border-orange-200 bg-orange-50 text-orange-700",
  urgent: "border-red-200 bg-red-50 text-red-700",
};

const pretty = (value?: string | null) =>
  (value || "unknown")
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());

export default function AdminCustomerSupport() {
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [query, setQuery] = useState("");
  const [debouncedQuery, setDebouncedQuery] = useState("");
  const [status, setStatus] = useState("");
  const [priority, setPriority] = useState("");
  const [channel, setChannel] = useState("");
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [total, setTotal] = useState(0);
  const [totalPages, setTotalPages] = useState(0);
  const [selected, setSelected] = useState<SupportTicket | null>(null);
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
      const data = await customersService.listSupportTickets({
        page,
        page_size: pageSize,
        search: debouncedQuery || undefined,
        status: status || undefined,
        priority: priority || undefined,
        channel: channel || undefined,
      });

      setTickets(data.results);
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
  }, [page, pageSize, debouncedQuery, status, priority, channel]);

  const openTicket = async (ticket: SupportTicket) => {
    setSelected(ticket);
    setDetailLoading(true);

    try {
      const detail = await customersService.getSupportTicket(ticket.id);
      setSelected(detail);
    } catch {
      // Until backend Task 2 supplies ticket detail/conversation, the list row
      // still opens so the administrator can inspect available information.
    } finally {
      setDetailLoading(false);
    }
  };

  const stats = useMemo(
    () => ({
      open: tickets.filter((ticket) => ticket.status === "open").length,
      ongoing: tickets.filter((ticket) =>
        ["pending", "in_progress", "processing"].includes(ticket.status),
      ).length,
      done: tickets.filter((ticket) =>
        ["resolved", "closed"].includes(ticket.status),
      ).length,
      urgent: tickets.filter((ticket) =>
        ["high", "urgent"].includes(ticket.priority),
      ).length,
    }),
    [tickets],
  );

  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <div className="space-y-5">
      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f47524]">
          Customer care operations
        </p>
        <h2 className="mt-1 text-2xl font-bold text-[#111827]">
          Customer Support Tickets
        </h2>
        <p className="mt-1 max-w-4xl text-sm leading-6 text-[#64748b]">
          Central support workspace for customer issues involving marketplace
          sellers, orders and logistics. Administrators can see what is new,
          ongoing, being processed and completed, while maintaining visibility
          across every party in the case.
        </p>
      </section>

      <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Metric icon={Headphones} label="Open on page" value={stats.open} />
        <Metric icon={Clock3} label="Ongoing / processing" value={stats.ongoing} />
        <Metric icon={CheckCircle2} label="Resolved / done" value={stats.done} />
        <Metric icon={ShieldAlert} label="High priority" value={stats.urgent} />
      </section>

      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm">
        <div className="grid gap-3 lg:grid-cols-[minmax(280px,1.8fr)_repeat(3,minmax(145px,1fr))]">
          <div className="relative">
            <Search
              size={16}
              className="absolute left-3.5 top-1/2 -translate-y-1/2 text-[#94a3b8]"
            />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search ticket, customer, seller, order or logistics..."
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
            <option value="open">Open / New</option>
            <option value="pending">Pending</option>
            <option value="in_progress">In Progress</option>
            <option value="processing">Processing</option>
            <option value="resolved">Resolved</option>
            <option value="closed">Closed / Done</option>
          </select>

          <select
            value={priority}
            onChange={(event) => {
              setPriority(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm"
          >
            <option value="">All priorities</option>
            {["low", "medium", "high", "urgent"].map((value) => (
              <option key={value} value={value}>
                {pretty(value)}
              </option>
            ))}
          </select>

          <select
            value={channel}
            onChange={(event) => {
              setChannel(event.target.value);
              setPage(1);
            }}
            className="h-11 rounded-xl border-2 border-[#d8e0e9] bg-white px-3 text-sm"
          >
            <option value="">All channels</option>
            <option value="customer">Customer</option>
            <option value="seller">Seller</option>
            <option value="logistics">Logistics</option>
            <option value="order">Order issue</option>
          </select>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-[#e2e8f0] bg-white shadow-sm">
        {loading ? (
          <div className="p-12 text-center text-gray-500">
            <RefreshCw className="mx-auto animate-spin" size={22} />
            <p className="mt-3 text-sm">Loading support tickets...</p>
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
        ) : !tickets.length ? (
          <div className="p-12 text-center">
            <MessageCircleMore className="mx-auto text-slate-300" size={34} />
            <p className="mt-3 font-semibold text-[#111827]">
              No matching support tickets
            </p>
            <p className="mt-1 text-sm text-gray-500">
              New customer, seller and logistics conversations will appear
              here.
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[1200px] text-left text-sm">
              <thead className="bg-[#f8fafc] text-xs uppercase text-[#64748b]">
                <tr>
                  {[
                    "Ticket",
                    "Customer",
                    "Issue / Context",
                    "Parties",
                    "Priority",
                    "Status",
                    "Assigned",
                    "Updated",
                    "Action",
                  ].map((heading) => (
                    <th key={heading} className="px-5 py-3">
                      {heading}
                    </th>
                  ))}
                </tr>
              </thead>

              <tbody className="divide-y divide-[#edf0f4]">
                {tickets.map((ticket) => (
                  <tr key={ticket.id} className="hover:bg-orange-50/20">
                    <td className="px-5 py-4">
                      <p className="font-bold text-[#111827]">
                        {ticket.ticket_number}
                      </p>
                      <p className="mt-0.5 text-[10px] text-gray-400">
                        {ticket.id.slice(0, 12)}
                      </p>
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex items-center gap-2.5">
                        <span className="flex h-8 w-8 items-center justify-center rounded-full bg-slate-100 text-slate-500">
                          <UserRound size={14} />
                        </span>
                        <div>
                          <p className="font-semibold text-[#111827]">
                            {ticket.customer_name || "Customer"}
                          </p>
                          <p className="text-xs text-gray-500">
                            {ticket.customer_email ||
                              ticket.user_id.slice(0, 10)}
                          </p>
                        </div>
                      </div>
                    </td>

                    <td className="max-w-sm px-5 py-4">
                      <p className="font-semibold text-[#111827]">
                        {ticket.subject}
                      </p>
                      <p className="mt-1 line-clamp-1 text-xs text-gray-500">
                        {ticket.description || "No description"}
                      </p>
                      {ticket.order_id && (
                        <p className="mt-1 text-[10px] font-semibold text-[#f47524]">
                          Order {ticket.order_id.slice(0, 10)}
                        </p>
                      )}
                    </td>

                    <td className="px-5 py-4">
                      <div className="flex flex-wrap gap-1.5">
                        <Party label="Customer" />
                        {ticket.seller_name && <Party label="Seller" />}
                        {ticket.logistics_provider && (
                          <Party label="Logistics" />
                        )}
                      </div>
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
                          PRIORITY_BADGES[ticket.priority] ||
                          "border-slate-200 bg-slate-100 text-slate-600"
                        }`}
                      >
                        {pretty(ticket.priority)}
                      </span>
                    </td>

                    <td className="px-5 py-4">
                      <span
                        className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
                          STATUS_BADGES[ticket.status] ||
                          "border-slate-200 bg-slate-100 text-slate-600"
                        }`}
                      >
                        {pretty(ticket.status)}
                      </span>
                    </td>

                    <td className="px-5 py-4 text-xs text-gray-500">
                      {ticket.assigned_to_name || "Unassigned"}
                    </td>

                    <td className="px-5 py-4 text-xs text-gray-500">
                      {new Date(
                        ticket.updated_at || ticket.created_at,
                      ).toLocaleString()}
                    </td>

                    <td className="px-5 py-4">
                      <button
                        type="button"
                        onClick={() => void openTicket(ticket)}
                        className="inline-flex items-center gap-1.5 rounded-lg bg-[#111827] px-3 py-2 text-xs font-semibold text-white"
                      >
                        <Eye size={13} />
                        Open Case
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
            className="flex h-full w-full max-w-3xl flex-col bg-[#f8fafc] shadow-2xl"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <div className="flex items-start justify-between border-b bg-white px-6 py-5">
              <div>
                <p className="text-xs font-bold uppercase tracking-[.14em] text-[#f47524]">
                  Support case
                </p>
                <h3 className="mt-1 text-xl font-bold text-[#111827]">
                  {selected.ticket_number}
                </h3>
                <p className="mt-1 text-sm text-gray-500">
                  {selected.subject}
                </p>
              </div>
              <button
                onClick={() => setSelected(null)}
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100"
              >
                <X size={17} />
              </button>
            </div>

            <div className="flex-1 space-y-5 overflow-y-auto p-6">
              {detailLoading && (
                <p className="text-sm text-gray-500">
                  Loading complete ticket conversation...
                </p>
              )}

              <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                <Info
                  label="Customer"
                  value={selected.customer_name || selected.user_id}
                />
                <Info label="Seller" value={selected.seller_name || "—"} />
                <Info
                  label="Logistics"
                  value={selected.logistics_provider || "—"}
                />
                <Info label="Priority" value={pretty(selected.priority)} />
                <Info label="Status" value={pretty(selected.status)} />
                <Info
                  label="Assigned to"
                  value={selected.assigned_to_name || "Unassigned"}
                />
              </section>

              <section className="rounded-2xl border bg-white p-5">
                <p className="text-xs font-bold uppercase tracking-wider text-gray-400">
                  Issue description
                </p>
                <p className="mt-3 whitespace-pre-wrap text-sm leading-7 text-[#475569]">
                  {selected.description || "No description provided."}
                </p>
              </section>

              <section className="rounded-2xl border bg-white p-5">
                <div className="flex items-center justify-between">
                  <div>
                    <p className="font-bold text-[#111827]">
                      Conversation & Case Timeline
                    </p>
                    <p className="mt-1 text-xs text-gray-500">
                      Customer, seller, logistics and administrator messages
                      will be visible in one chronological thread.
                    </p>
                  </div>
                  <UsersRound size={18} className="text-[#f47524]" />
                </div>

                {selected.messages?.length ? (
                  <div className="mt-5 space-y-3">
                    {selected.messages.map((message) => (
                      <div
                        key={message.id}
                        className="rounded-xl border bg-[#f8fafc] p-4"
                      >
                        <div className="flex items-center justify-between gap-3">
                          <p className="text-xs font-bold text-[#111827]">
                            {message.sender_name || "Participant"} ·{" "}
                            {pretty(message.sender_role)}
                          </p>
                          <p className="text-[10px] text-gray-400">
                            {new Date(message.created_at).toLocaleString()}
                          </p>
                        </div>
                        <p className="mt-2 whitespace-pre-wrap text-sm leading-6 text-[#475569]">
                          {message.message}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="mt-5 rounded-xl border border-dashed bg-[#f8fafc] p-5 text-center text-sm text-gray-500">
                    Conversation messages will be populated when Backend Task 2
                    adds the ticket message/thread endpoint.
                  </div>
                )}
              </section>

              <section className="rounded-2xl border bg-white p-5">
                <p className="font-bold text-[#111827]">Related operations</p>
                <div className="mt-4 grid gap-3 sm:grid-cols-3">
                  <Context
                    icon={UserRound}
                    label="Customer"
                    value={selected.customer_name || "Linked"}
                  />
                  <Context
                    icon={MessageCircleMore}
                    label="Seller"
                    value={selected.seller_name || "Not linked"}
                  />
                  <Context
                    icon={Truck}
                    label="Logistics"
                    value={selected.logistics_provider || "Not linked"}
                  />
                </div>
              </section>

              <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-xs leading-5 text-amber-800">
                Ticket assignment, status changes, replies, internal notes and
                case resolution are already represented in the frontend API
                contract. We will make those controls live when we implement
                Backend Task 2.
              </div>
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
}: {
  icon: typeof Headphones;
  label: string;
  value: string | number;
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

function Party({ label }: { label: string }) {
  return (
    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-1 text-[10px] font-semibold text-slate-600">
      {label}
    </span>
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

function Context({
  icon: Icon,
  label,
  value,
}: {
  icon: typeof UserRound;
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-xl bg-[#f8fafc] p-4">
      <Icon size={15} className="text-[#f47524]" />
      <p className="mt-2 text-xs font-bold text-[#111827]">{label}</p>
      <p className="mt-1 text-xs text-gray-500">{value}</p>
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
