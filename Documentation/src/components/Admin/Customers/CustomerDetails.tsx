"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { customersService, type CustomerDetails } from "@/lib/api/endpoints/customers";
import { ApiError } from "@/lib/api/client";
import UnavailableFeature from "@/components/Admin/Common/UnavailableFeature";

const getErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
};

const TABS = [
  { key: "overview", label: "Overview" },
  { key: "orders", label: "Orders" },
  { key: "addresses", label: "Addresses" },
  { key: "payments", label: "Payments" },
  { key: "activity", label: "Activity" },
  { key: "unsupported", label: "Unavailable Data" },
];

const AdminCustomerDetails = ({ customerId }: { customerId: string }) => {
  const [data, setData] = useState<CustomerDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState("overview");

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await customersService.getCustomer(customerId);
      setData(res);
    } catch (error) {
      setError(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, [customerId]);

  if (loading) return <div className="py-8 text-center text-gray-600">Loading customer...</div>;
  if (error) return <div className="rounded-2xl border border-red-200 bg-red-50 p-6 text-sm text-red-800"><p>{error}</p><button type="button" onClick={() => void fetchData()} className="mt-3 rounded-lg bg-red-700 px-3 py-2 font-medium text-white">Retry</button></div>;
  if (!data) return <div className="py-8 text-center text-gray-500">Customer not found.</div>;

  const c = data.customer;
  const fullName = `${c.first_name ?? ""} ${c.last_name ?? ""}`.trim() || "Unknown";
  const initials = fullName
    .split(" ")
    .map((n) => n[0])
    .join("")
    .toUpperCase() || "??";

  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-16 w-16 items-center justify-center rounded-full bg-[#dbeafe] text-xl font-bold text-[#1e40af]">
              {initials}
            </div>
            <div>
              <h2 className="text-xl font-semibold text-[#111827]">{fullName}</h2>
              <p className="text-sm text-gray-500">
                {c.email} · {c.phone ?? "No phone"} · ID: {c.id.slice(0, 12).toUpperCase()}
              </p>
            </div>
          </div>
          <div className="flex gap-2">
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${c.status === "active" ? "bg-[#d1fae5] text-[#065f46]" : "bg-[#f3f4f6] text-[#4b5563]"}`}>
              {c.status.replace("_", " ")}
            </span>
            <span className={`rounded-full px-3 py-1 text-xs font-medium ${c.is_verified ? "bg-[#d1fae5] text-[#065f46]" : "bg-[#fef3c7] text-[#92400e]"}`}>
              {c.is_verified ? "Verified" : "Unverified"}
            </span>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
        <SummaryCard label="Orders" value={data.stats.orders} />
        <SummaryCard label="Completed" value={data.stats.completed_orders} />
        <SummaryCard label="Cancelled" value={data.stats.cancelled_orders} />
        <SummaryCard label="Total Spent" value={data.stats.total_spent.toLocaleString()} />
        <SummaryCard label="Avg Order" value={data.stats.average_order.toLocaleString()} />
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-4 border-b border-gray-200">
          <div className="flex flex-wrap gap-4">
            {TABS.map((t) => (
              <button
                key={t.key}
                type="button"
                onClick={() => setActiveTab(t.key)}
                className={`border-b-2 px-2 py-3 text-sm font-medium ${activeTab === t.key ? "border-[#1e40af] text-[#1e40af]" : "border-transparent text-gray-600 hover:text-[#111827]"}`}
              >
                {t.label}
              </button>
            ))}
          </div>
        </div>

        {activeTab === "overview" && (
          <div className="space-y-4">
            <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
              <div className="rounded-xl border border-gray-200 bg-[#f8fafc] p-4">
                <h3 className="mb-3 text-sm font-semibold text-[#111827]">Profile Information</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-gray-500">Full Name</span><span className="text-[#111827]">{fullName}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Email</span><span className="text-[#111827]">{c.email}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Phone</span><span className="text-[#111827]">{c.phone ?? "-"}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Gender</span><span className="text-[#111827]">{c.gender ?? "-"}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Date of Birth</span><span className="text-[#111827]">{c.date_of_birth ? new Date(c.date_of_birth).toLocaleDateString() : "-"}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Joined</span><span className="text-[#111827]">{new Date(c.created_at).toLocaleString()}</span></div>
                  <div className="flex justify-between"><span className="text-gray-500">Last Login</span><span className="text-[#111827]">{c.last_login_at ? new Date(c.last_login_at).toLocaleString() : "-"}</span></div>
                </div>
              </div>

              <div className="rounded-xl border border-gray-200 bg-[#f8fafc] p-4">
                <h3 className="mb-3 text-sm font-semibold text-[#111827]">Recent Orders</h3>
                {data.orders.slice(0, 5).length === 0 ? (
                  <p className="text-sm text-gray-500">No orders yet.</p>
                ) : (
                  <div className="space-y-2">
                    {data.orders.slice(0, 5).map((o) => (
                      <div key={o.id} className="flex items-center justify-between rounded-lg bg-white p-2 text-sm">
                        <span className="font-medium text-[#111827]">{o.order_number}</span>
                        <span className="text-gray-600">{o.total_amount.toLocaleString()} {o.currency}</span>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </div>

            <div className="rounded-xl border border-gray-200 bg-[#f8fafc] p-4">
              <h3 className="mb-3 text-sm font-semibold text-[#111827]">Customer Timeline</h3>
              <div className="space-y-3">
                <TimelineItem title="Registered" date={c.created_at} />
                {c.is_verified && <TimelineItem title="Verified Email" date={c.created_at} />}
                {data.orders.length > 0 && <TimelineItem title="First Order" date={data.orders[data.orders.length - 1].created_at} />}
                {c.last_login_at && <TimelineItem title="Last Login" date={c.last_login_at} />}
              </div>
            </div>
          </div>
        )}

        {activeTab === "orders" && (
          <SimpleTable
            headers={["Order Number", "Date", "Amount", "Payment", "Status"]}
            rows={data.orders.map((o) => [o.order_number, new Date(o.created_at).toLocaleDateString(), `${o.total_amount.toLocaleString()} ${o.currency}`, o.payment_status, o.status])}
            empty="No orders found."
          />
        )}

        {activeTab === "addresses" && (
          <SimpleTable
            headers={["Label", "Type", "Country", "Region", "City", "Street", "Default"]}
            rows={data.addresses.map((a) => [
              a.label ?? "-",
              a.address_type,
              a.country,
              a.region,
              a.city,
              a.street,
              a.is_default ? "Yes" : "No",
            ])}
            empty="No addresses found."
          />
        )}

        {activeTab === "payments" && (
          <SimpleTable
            headers={["Method", "Reference", "Amount", "Status", "Date"]}
            rows={data.payments.map((p) => [p.method, p.transaction_reference ?? "-", `${p.amount.toLocaleString()} ${p.currency}`, p.status, new Date(p.created_at).toLocaleDateString()])}
            empty="No payments found."
          />
        )}

        {activeTab === "activity" && (
          <SimpleTable
            headers={["Date", "Device", "Browser", "IP Address", "Country"]}
            rows={data.login_history.map((h) => [
              new Date(h.login_at).toLocaleString(),
              h.device ?? "-",
              h.browser ?? "-",
              h.ip_address ?? "-",
              h.country ?? "-",
            ])}
            empty="No login history found."
          />
        )}

        {activeTab === "unsupported" && <UnavailableFeature title="Customer reviews, wishlist, and internal notes are unavailable" description="The backend customer-detail contract does not currently provide persisted records or mutation endpoints for these sections." />}
      </div>

      <div className="mt-4">
        <Link href="/admin/customers" className="text-sm font-medium text-[#1e40af] hover:underline">
          ← Back to All Customers
        </Link>
      </div>
    </div>
  );
};

const SummaryCard = ({ label, value }: { label: string; value: string | number }) => (
  <div className="rounded-2xl border border-gray-200 bg-white p-4 shadow-sm">
    <p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p>
    <p className="mt-2 text-xl font-semibold text-[#111827]">{value}</p>
  </div>
);

const TimelineItem = ({ title, date }: { title: string; date: string }) => (
  <div className="flex items-start gap-3">
    <div className="mt-1.5 h-2 w-2 rounded-full bg-[#1e40af]" />
    <div>
      <p className="text-sm font-medium text-[#111827]">{title}</p>
      <p className="text-xs text-gray-500">{new Date(date).toLocaleString()}</p>
    </div>
  </div>
);

const SimpleTable = ({ headers, rows, empty }: { headers: string[]; rows: (string | number)[][]; empty: string }) => (
  <div className="overflow-x-auto">
    {rows.length === 0 ? (
      <p className="py-8 text-center text-sm text-gray-500">{empty}</p>
    ) : (
      <table className="w-full text-left">
        <thead className="bg-[#f8fafc]">
          <tr>
            {headers.map((h) => (
              <th key={h} className="px-4 py-3 text-sm font-medium text-gray-700">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100">
          {rows.map((row, idx) => (
            <tr key={idx} className="hover:bg-gray-50">
              {row.map((cell, cidx) => (
                <td key={cidx} className="px-4 py-3 text-sm text-gray-600">{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    )}
  </div>
);

export default AdminCustomerDetails;
