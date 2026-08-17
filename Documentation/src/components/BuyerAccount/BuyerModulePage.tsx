"use client";
import { formatCurrency } from "@/lib/formatCurrency";
import { ordersApi, paymentsApi } from "@/lib/api/endpoints/commerce";
import { authApi } from "@/lib/api/endpoints/auth";
import { usersApi } from "@/lib/api/endpoints/users";
import type { Address, User } from "@/types/api/user";
import type { Order, Payment } from "@/types/api/commerce";
import {
  AlertCircle,
  Bell,
  CreditCard,
  KeyRound,
  Loader2,
  MapPin,
  Package,
  RefreshCw,
  Shield,
  Star,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import toast from "react-hot-toast";
import AddressBookSection from "@/components/MyAccount/AddressBookSection";
type View =
  | "orders"
  | "payments"
  | "addresses"
  | "reviews"
  | "notifications"
  | "security"
  | "details";
const copy = {
  orders: ["My Orders", "Track purchases and delivery progress.", Package],
  payments: [
    "My Payments",
    "Review buyer payment activity and receipts.",
    CreditCard,
  ],
  addresses: [
    "My Addresses",
    "Manage delivery and billing destinations.",
    MapPin,
  ],
  reviews: ["My Reviews", "Manage product feedback you have submitted.", Star],
  notifications: ["Notifications", "Review account and order updates.", Bell],
  security: [
    "Account Security",
    "Protect your buyer account and active sessions.",
    Shield,
  ],
  details: [
    "Account Details",
    "Update your personal buyer information.",
    UserRound,
  ],
} as const;
export default function BuyerModulePage({ view }: { view: View }) {
  const [loading, setLoading] = useState(true),
    [error, setError] = useState(false),
    [orders, setOrders] = useState<Order[]>([]),
    [payments, setPayments] = useState<Payment[]>([]),
    [profile, setProfile] = useState<User | null>(null);
  const [paymentPage, setPaymentPage] = useState(1);
  const [paymentMeta, setPaymentMeta] = useState({
    total: 0,
    total_pages: 0,
  });
  const [paymentSearch, setPaymentSearch] = useState("");
  const [paymentStatusFilter, setPaymentStatusFilter] = useState("all");
  const [orderPage, setOrderPage] = useState(1);
  const [orderMeta, setOrderMeta] = useState({
    total: 0,
    total_pages: 0,
  });
  const [orderSearch, setOrderSearch] = useState("");
  const [orderStatusFilter, setOrderStatusFilter] = useState("all");
  const [orderPaymentFilter, setOrderPaymentFilter] = useState("all");
  const [passwords, setPasswords] = useState({
    current: "",
    next: "",
    confirm: "",
  });
  const [form, setForm] = useState({
    first_name: "",
    last_name: "",
    phone: "",
  });
  const [title, description, Icon] = copy[view];
  async function load() {
    setLoading(true);
    setError(false);
    try {
      if (view === "orders") {
        const result = await ordersApi.mine({
          page: orderPage,
          page_size: 20,
          search: orderSearch.trim() || undefined,
          status:
            orderStatusFilter === "all"
              ? undefined
              : orderStatusFilter,
          payment_status:
            orderPaymentFilter === "all"
              ? undefined
              : orderPaymentFilter,
        });
        setOrders(result.results);
        setOrderMeta({
          total: result.total,
          total_pages: result.total_pages || 0,
        });
      }
      else if (view === "payments") {
        const result = await paymentsApi.mine({
          page: paymentPage,
          page_size: 20,
          search: paymentSearch.trim() || undefined,
          payment_status:
            paymentStatusFilter === "all"
              ? undefined
              : paymentStatusFilter,
        });
        setPayments(result.results);
        setPaymentMeta({
          total: result.total,
          total_pages: result.total_pages,
        });
      }
      else if (view === "addresses")
        setProfile(await usersApi.getMe());
      else if (view === "details") {
        const p = await usersApi.getMe();
        setProfile(p);
        setForm({
          first_name: p.first_name || "",
          last_name: p.last_name || "",
          phone: p.phone || "",
        });
      } else if (view === "security") {
        // Change-password is available. Session-management endpoints are not
        // exposed by the current backend, so do not fail this page trying to load them.
      }
    } catch {
      setError(true);
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, [
    view,
    paymentPage,
    paymentSearch,
    paymentStatusFilter,
    orderPage,
    orderSearch,
    orderStatusFilter,
    orderPaymentFilter,
  ]);
  async function saveDetails(e: FormEvent) {
    e.preventDefault();
    try {
      const p = await usersApi.updateMe(form);
      setProfile(p);
      toast.success("Account details updated.");
    } catch {
      toast.error("Unable to update account details.");
    }
  }
  async function changePassword(e: FormEvent) {
    e.preventDefault();
    if (passwords.next !== passwords.confirm)
      return toast.error("Passwords do not match.");
    try {
      await authApi.changePassword({
        current_password: passwords.current,
        new_password: passwords.next,
      });
      toast.success("Password changed. Sign in again.");
      window.location.assign("/signin");
    } catch {
      toast.error("Unable to change password.");
    }
  }
  return (
    <div className="space-y-5">
      <div>
        <p className="text-sm font-semibold text-[#f7941d]">Buyer Account</p>
        <h1 className="text-2xl font-bold">{title}</h1>
        <p className="mt-1 text-sm text-[#64748b]">{description}</p>
      </div>
      <section className="rounded-2xl border border-[#e2e8f0] bg-white p-5 shadow-sm dark:border-white/10 dark:bg-darkTheme-card">
        <div className="mb-5 flex items-center gap-3">
          <span className="rounded-xl bg-orange-50 p-2.5 text-[#f7941d] dark:bg-orange-400/10">
            <Icon size={21} />
          </span>
          <h2 className="font-bold">{title}</h2>
        </div>
        {loading ? (
          <State
            icon={Loader2}
            spin
            text={`Loading ${title.toLowerCase()}...`}
          />
        ) : error ? (
          <div className="text-center">
            <State
              icon={AlertCircle}
              text={`We could not load ${title.toLowerCase()}.`}
            />
            <button
              onClick={() => void load()}
              className="mt-3 inline-flex items-center gap-2 text-sm font-semibold text-[#f7941d]"
            >
              <RefreshCw size={16} />
              Retry
            </button>
          </div>
        ) : view === "orders" ? (
          <Orders
            items={orders}
            page={orderPage}
            total={orderMeta.total}
            totalPages={orderMeta.total_pages}
            search={orderSearch}
            statusFilter={orderStatusFilter}
            paymentFilter={orderPaymentFilter}
            onSearch={(value) => {
              setOrderSearch(value);
              setOrderPage(1);
            }}
            onStatusFilter={(value) => {
              setOrderStatusFilter(value);
              setOrderPage(1);
            }}
            onPaymentFilter={(value) => {
              setOrderPaymentFilter(value);
              setOrderPage(1);
            }}
            onPage={setOrderPage}
          />
        ) : view === "payments" ? (
          <Payments
            items={payments}
            page={paymentPage}
            total={paymentMeta.total}
            totalPages={paymentMeta.total_pages}
            search={paymentSearch}
            statusFilter={paymentStatusFilter}
            onSearch={(value) => {
              setPaymentSearch(value);
              setPaymentPage(1);
            }}
            onStatusFilter={(value) => {
              setPaymentStatusFilter(value);
              setPaymentPage(1);
            }}
            onPage={setPaymentPage}
          />
        ) : view === "addresses" ? (
          <AddressBookSection
            isActive
            displayName={`${profile?.first_name || ""} ${profile?.last_name || ""}`.trim() || "Name not provided"}
            emailLabel={profile?.email || "Email unavailable"}
            phoneLabel={profile?.phone || "Phone number not added"}
          />
        ) : view === "details" ? (
          <Details
            profile={profile}
            form={form}
            setForm={setForm}
            submit={saveDetails}
          />
        ) : view === "security" ? (
          <Security
            passwords={passwords}
            setPasswords={setPasswords}
            submit={changePassword}
          />
        ) : (
          <Unavailable view={view} />
        )}
      </section>
    </div>
  );
}
function Payments({
  items,
  page,
  total,
  totalPages,
  search,
  statusFilter,
  onSearch,
  onStatusFilter,
  onPage,
}: {
  items: Payment[];
  page: number;
  total: number;
  totalPages: number;
  search: string;
  statusFilter: string;
  onSearch: (value: string) => void;
  onStatusFilter: (value: string) => void;
  onPage: (value: number) => void;
}) {
  return (
    <div>
      <div className="mb-5 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-semibold">Payment History</p>
          <p className="mt-1 text-xs text-[#64748b]">
            {total} payment record{total === 1 ? "" : "s"}
          </p>
        </div>

        <div className="flex flex-col gap-2 sm:flex-row">
          <input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Search payment or order..."
            className="h-10 rounded-xl border border-[#e2e8f0] px-3 text-sm outline-none dark:border-white/10 dark:bg-white/5"
          />
          <select
            value={statusFilter}
            onChange={(event) => onStatusFilter(event.target.value)}
            className="h-10 rounded-xl border border-[#e2e8f0] bg-white px-3 text-sm dark:border-white/10 dark:bg-white/5"
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="processing">Processing</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
            <option value="cancelled">Cancelled</option>
            <option value="refunded">Refunded</option>
          </select>
        </div>
      </div>

      {!items.length ? (
        <Empty
          title="No payments found"
          text="Payment records will appear here after checkout."
          action="Start Shopping"
          href="/search"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-left text-sm">
            <thead className="bg-[#f8fafc] dark:bg-white/5">
              <tr>
                {[
                  "Reference",
                  "Order",
                  "Amount",
                  "Method",
                  "Provider",
                  "Status",
                  "Paid",
                  "Date",
                ].map((x) => (
                  <th key={x} className="p-3">
                    {x}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((p) => (
                <tr
                  key={p.id}
                  className="border-t border-[#e2e8f0] dark:border-white/10"
                >
                  <td className="p-3 font-semibold">
                    {p.provider_transaction_id || p.id.slice(0, 8)}
                  </td>
                  <td className="p-3">
                    <Link
                      href={`/account/orders/${p.order_id}`}
                      className="font-semibold text-[#f7941d]"
                    >
                      {p.order_id.slice(0, 8)}
                    </Link>
                  </td>
                  <td className="p-3">
                    {formatCurrency(p.amount, p.currency)}
                  </td>
                  <td className="p-3 capitalize">
                    {p.method.replaceAll("_", " ")}
                  </td>
                  <td className="p-3 capitalize">
                    {(p.provider || "—").replaceAll("_", " ")}
                  </td>
                  <td className="p-3">
                    <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold capitalize">
                      {p.status}
                    </span>
                  </td>
                  <td className="p-3">
                    {p.paid_at
                      ? new Date(p.paid_at).toLocaleString()
                      : p.method === "cash_on_delivery"
                        ? "On delivery"
                        : "—"}
                  </td>
                  <td className="p-3">
                    {new Date(p.created_at).toLocaleString()}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
            className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm font-semibold disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs text-[#64748b]">
            Page {page} of {Math.max(totalPages, 1)}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPage(page + 1)}
            className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm font-semibold disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function Orders({
  items,
  page,
  total,
  totalPages,
  search,
  statusFilter,
  paymentFilter,
  onSearch,
  onStatusFilter,
  onPaymentFilter,
  onPage,
}: {
  items: Order[];
  page: number;
  total: number;
  totalPages: number;
  search: string;
  statusFilter: string;
  paymentFilter: string;
  onSearch: (value: string) => void;
  onStatusFilter: (value: string) => void;
  onPaymentFilter: (value: string) => void;
  onPage: (value: number) => void;
}) {
  return (
    <div>
      <div className="mb-5 flex flex-col gap-3 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-sm font-semibold">Order History</p>
          <p className="mt-1 text-xs text-[#64748b]">
            {total} order{total === 1 ? "" : "s"} · Search and filters are
            processed by the backend before pagination.
          </p>
        </div>

        <div className="grid gap-2 sm:grid-cols-3">
          <input
            value={search}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Order, product, tracking..."
            className="h-10 rounded-xl border border-[#e2e8f0] px-3 text-sm outline-none dark:border-white/10 dark:bg-white/5"
          />

          <select
            value={statusFilter}
            onChange={(event) => onStatusFilter(event.target.value)}
            className="h-10 rounded-xl border border-[#e2e8f0] bg-white px-3 text-sm dark:border-white/10 dark:bg-white/5"
          >
            <option value="all">All fulfilment</option>
            <option value="pending">Pending</option>
            <option value="paid">Paid</option>
            <option value="processing">Processing</option>
            <option value="shipped">Shipped</option>
            <option value="delivered">Delivered</option>
            <option value="cancelled">Cancelled</option>
            <option value="refunded">Refunded</option>
          </select>

          <select
            value={paymentFilter}
            onChange={(event) => onPaymentFilter(event.target.value)}
            className="h-10 rounded-xl border border-[#e2e8f0] bg-white px-3 text-sm dark:border-white/10 dark:bg-white/5"
          >
            <option value="all">All payments</option>
            <option value="pending">Payment pending</option>
            <option value="processing">Payment processing</option>
            <option value="completed">Paid</option>
            <option value="failed">Payment failed</option>
            <option value="refunded">Refunded</option>
          </select>
        </div>
      </div>

      {!items.length ? (
        <Empty
          title="No orders found"
          text="Try another search/filter or start shopping."
          action="Start Shopping"
          href="/search"
        />
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] text-left text-sm">
            <thead className="bg-[#f8fafc] dark:bg-white/5">
              <tr>
                {[
                  "Order",
                  "Date",
                  "Total",
                  "Fulfilment",
                  "Items",
                  "Action",
                ].map((x) => (
                  <th key={x} className="p-3">
                    {x}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {items.map((order) => (
                <tr
                  key={order.id}
                  className="border-t border-[#e2e8f0] dark:border-white/10"
                >
                  <td className="p-3 font-semibold">
                    {order.id.slice(0, 8).toUpperCase()}
                  </td>
                  <td className="p-3">
                    {new Date(order.created_at).toLocaleDateString()}
                  </td>
                  <td className="p-3">
                    {formatCurrency(order.total, order.currency)}
                  </td>
                  <td className="p-3 capitalize">
                    {order.status.replaceAll("_", " ")}
                  </td>
                  <td className="p-3">{order.items.length}</td>
                  <td className="p-3">
                    <Link
                      href={`/account/orders/${order.id}`}
                      className="font-semibold text-[#f7941d]"
                    >
                      Track Order
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {totalPages > 1 && (
        <div className="mt-5 flex items-center justify-end gap-3">
          <button
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
            className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm font-semibold disabled:opacity-40"
          >
            Previous
          </button>
          <span className="text-xs text-[#64748b]">
            Page {page} of {Math.max(totalPages, 1)}
          </span>
          <button
            disabled={page >= totalPages}
            onClick={() => onPage(page + 1)}
            className="rounded-lg border border-[#e2e8f0] px-3 py-2 text-sm font-semibold disabled:opacity-40"
          >
            Next
          </button>
        </div>
      )}
    </div>
  );
}

function Addresses({ items }: { items: Address[] }) {
  const [rows, setRows] = useState(items);
  async function remove(a: Address) {
    if (a.is_default && rows.length > 1)
      return toast.error(
        "Select another default address before deleting this one.",
      );
    if (!window.confirm("Delete this saved address?")) return;
    try {
      await usersApi.deleteAddress(a.id);
      setRows((v) => v.filter((x) => x.id !== a.id));
      toast.success("Address deleted.");
    } catch {
      toast.error("Unable to delete address.");
    }
  }
  async function makeDefault(a: Address) {
    try {
      const updated = await usersApi.updateAddress(a.id, {
        country: a.country,
        region: a.region,
        city: a.city,
        street: a.street,
        postal_code: a.postal_code,
        is_default: true,
      });
      setRows((v) => v.map((x) => ({ ...x, is_default: x.id === updated.id })));
      toast.success("Default address updated.");
    } catch {
      toast.error("Unable to update default address.");
    }
  }
  if (!rows.length)
    return (
      <Empty
        title="No saved addresses"
        text="Add a delivery address to make checkout faster."
        action="Add Delivery Address"
        href="/account/details"
      />
    );
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      {rows.map((a) => (
        <article
          key={String(a.id)}
          className="rounded-xl border border-[#e2e8f0] p-4 dark:border-white/10"
        >
          <div className="flex justify-between">
            <b>{a.is_default ? "Default address" : "Saved address"}</b>
            {a.is_default && (
              <span className="rounded-full bg-green-50 px-2 py-1 text-xs text-green-700">
                Default
              </span>
            )}
          </div>
          <p className="mt-2 text-sm text-[#64748b]">
            {a.street}, {a.city}, {a.region}, {a.country}
          </p>
          <div className="mt-4 flex gap-3 text-sm font-semibold text-[#f7941d]">
            {!a.is_default && (
              <button onClick={() => void makeDefault(a)}>Set default</button>
            )}
            <button onClick={() => void remove(a)} className="text-red-600">
              Delete
            </button>
          </div>
        </article>
      ))}
    </div>
  );
}
function Details({
  profile,
  form,
  setForm,
  submit,
}: {
  profile: User | null;
  form: { first_name: string; last_name: string; phone: string };
  setForm: (v: typeof form) => void;
  submit: (e: FormEvent) => void;
}) {
  return (
    <form onSubmit={submit}>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field
          label="First name"
          value={form.first_name}
          set={(v) => setForm({ ...form, first_name: v })}
        />
        <Field
          label="Last name"
          value={form.last_name}
          set={(v) => setForm({ ...form, last_name: v })}
        />
        <Field label="Email" value={profile?.email || ""} disabled />
        <Field
          label="Phone"
          value={form.phone}
          set={(v) => setForm({ ...form, phone: v })}
        />
      </div>
      <p className="mt-4 text-sm text-[#64748b]">
        Email: {profile?.is_verified ? "Verified" : "Not verified"} · Account:{" "}
        {profile?.status || "Unknown"}
      </p>
      <button className="mt-5 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white">
        Save changes
      </button>
    </form>
  );
}
function Security({
  passwords,
  setPasswords,
  submit,
}: {
  passwords: { current: string; next: string; confirm: string };
  setPasswords: (v: typeof passwords) => void;
  submit: (e: FormEvent) => void;
}) {
  const strong =
    passwords.next.length >= 8 &&
    /[A-Za-z]/.test(passwords.next) &&
    /\d/.test(passwords.next);

  return (
    <div className="space-y-6">
      <div className="rounded-xl border border-[#e2e8f0] p-5 dark:border-white/10">
        <div className="flex items-start gap-3">
          <span className="rounded-xl bg-orange-50 p-2.5 text-[#f7941d]">
            <KeyRound size={18} />
          </span>
          <div>
            <h3 className="font-bold">Change password</h3>
            <p className="mt-1 text-sm text-[#64748b]">
              Changing your password invalidates existing refresh sessions. You will need to sign in again.
            </p>
          </div>
        </div>

        <form onSubmit={submit} className="mt-5">
          <div className="grid gap-4">
            <Field type="password" label="Current password" value={passwords.current} set={(v)=>setPasswords({...passwords,current:v})}/>
            <Field type="password" label="New password" value={passwords.next} set={(v)=>setPasswords({...passwords,next:v})}/>
            <Field type="password" label="Confirm new password" value={passwords.confirm} set={(v)=>setPasswords({...passwords,confirm:v})}/>
          </div>
          <div className="mt-3 rounded-xl bg-[#f8fafc] p-3 text-xs text-[#64748b] dark:bg-white/5">
            Use at least 8 characters. A combination of letters and numbers is recommended.
            {passwords.next && <span className={`ml-2 font-bold ${strong ? "text-emerald-600" : "text-amber-600"}`}>{strong ? "Good password format" : "Password can be stronger"}</span>}
          </div>
          <button disabled={!passwords.current || !passwords.next || passwords.next !== passwords.confirm} className="mt-4 rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white disabled:cursor-not-allowed disabled:opacity-50">
            Change password
          </button>
        </form>
      </div>

      <div className="rounded-xl border border-[#e2e8f0] p-5 dark:border-white/10">
        <h3 className="font-bold">Account security status</h3>
        <p className="mt-2 text-sm leading-6 text-[#64748b]">
          Password changes are supported by the backend. Active-session management and two-factor authentication are not currently exposed as customer APIs, so this page does not show non-functional controls for them.
        </p>
      </div>
    </div>
  );
}
function Unavailable({ view }: { view: View }) {
  const labels: Record<string, [string, string]> = {
    payments: [
      "No payments yet",
      "Buyer payment history will appear here when the payment-list API becomes available.",
    ],
    reviews: ["Reviews unavailable", "The backend does not currently expose buyer review history or review mutations."],
    notifications: ["Notifications unavailable", "The backend does not currently expose buyer notifications or unread counts."],
  };
  const [a, b] = labels[view];
  return <Empty title={a} text={b} />;
}
function Empty({
  title,
  text,
  action,
  href,
}: {
  title: string;
  text: string;
  action?: string;
  href?: string;
}) {
  return (
    <div className="py-10 text-center">
      <h3 className="font-bold">{title}</h3>
      <p className="mt-2 text-sm text-[#64748b]">{text}</p>
      {action && href && (
        <Link
          href={href}
          className="mt-5 inline-block rounded-xl bg-[#f7941d] px-5 py-2.5 text-sm font-semibold text-white"
        >
          {action}
        </Link>
      )}
    </div>
  );
}
function State({
  icon: Icon,
  text,
  spin,
}: {
  icon: typeof AlertCircle;
  text: string;
  spin?: boolean;
}) {
  return (
    <p className="flex justify-center gap-2 py-10 text-sm text-[#64748b]">
      <Icon size={18} className={spin ? "animate-spin" : ""} />
      {text}
    </p>
  );
}
function Field({
  label,
  value,
  set,
  disabled,
  type = "text",
}: {
  label: string;
  value: string;
  set?: (v: string) => void;
  disabled?: boolean;
  type?: string;
}) {
  return (
    <label className="text-sm font-semibold">
      {label}
      <input
        type={type}
        value={value}
        disabled={disabled}
        onChange={(e) => set?.(e.target.value)}
        className="mt-2 w-full rounded-xl border border-[#e2e8f0] bg-[#f8fafc] px-4 py-3 font-normal outline-none focus:border-[#f7941d] disabled:opacity-60 dark:border-white/10 dark:bg-white/5"
      />
    </label>
  );
}
