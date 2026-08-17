"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import toast from "react-hot-toast";
import { customersService, type Customer, type CustomerSummary } from "@/lib/api/endpoints/customers";
import { ApiError } from "@/lib/api/client";

const getErrorMessage = (error: unknown) => {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return "Something went wrong.";
};

const formatMoney = (amount: number, currency = "TZS") => {
  return new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(amount);
};

const formatNumber = (value: number) => new Intl.NumberFormat("en-US").format(value);

const STATUS_BADGES: Record<string, string> = {
  active: "bg-[#d1fae5] text-[#065f46]",
  inactive: "bg-[#f3f4f6] text-[#4b5563]",
  suspended: "bg-[#fde2e2] text-[#8f2727]",
  pending_verification: "bg-[#fef3c7] text-[#92400e]",
};

const AdminCustomers = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize] = useState(10);
  const [total, setTotal] = useState(0);
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("");
  const [verificationStatus, setVerificationStatus] = useState("");
  const [hasOrders, setHasOrders] = useState("");
  const [customerType, setCustomerType] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [busyCustomerId, setBusyCustomerId] = useState<string | null>(null);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 400);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    setPage(1);
  }, [debouncedSearch, status, verificationStatus, hasOrders, customerType]);

  const fetchData = async () => {
    setLoading(true);
    try {
      const [summaryData, customersData] = await Promise.all([
        customersService.getSummary(),
        customersService.listCustomers({
          page,
          page_size: pageSize,
          search: debouncedSearch || undefined,
          status: status || undefined,
          verification_status: verificationStatus || undefined,
          has_orders: hasOrders === "yes" ? true : hasOrders === "no" ? false : undefined,
          customer_type: customerType || undefined,
        }),
      ]);
      setSummary(summaryData);
      setCustomers(customersData.results);
      setTotal(customersData.total);
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) return;
      toast.error(getErrorMessage(error));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchData();
  }, [page, debouncedSearch, status, verificationStatus, hasOrders, customerType]);

  const clearFilters = () => {
    setSearch("");
    setStatus("");
    setVerificationStatus("");
    setHasOrders("");
    setCustomerType("");
    setPage(1);
  };

  const initials = (c: Customer) =>
    `${c.first_name?.[0] ?? ""}${c.last_name?.[0] ?? ""}`.toUpperCase() || "??";

  const totalPages = Math.ceil(total / pageSize) || 1;

  const toggleCustomerStatus = async (customer: Customer) => {
    const nextStatus = customer.status === "suspended" ? "active" : "suspended";
    const action = nextStatus === "suspended" ? "suspend" : "reactivate";
    if (!window.confirm(`Are you sure you want to ${action} this customer?`)) return;
    setBusyCustomerId(customer.id);
    try {
      const updated = await customersService.updateCustomerStatus(customer.id, nextStatus);
      setCustomers((items) => items.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
      toast.success(`Customer ${action}d successfully.`);
      const summaryData = await customersService.getSummary();
      setSummary(summaryData);
    } catch (error) {
      toast.error(getErrorMessage(error));
    } finally {
      setBusyCustomerId(null);
    }
  };

  return (
    <div className="space-y-4">
      {summary && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          <SummaryCard label="Total Customers" value={summary.total_customers} />
          <SummaryCard label="Active Customers" value={summary.active_customers} />
          <SummaryCard label="Verified Customers" value={summary.verified_customers} />
          <SummaryCard label="New Today" value={summary.new_today} />
          <SummaryCard label="Customers With Orders" value={summary.customers_with_orders} />
          <SummaryCard label="Blocked Customers" value={summary.blocked_customers} />
          <SummaryCard label="VIP Customers" value={summary.vip_customers} />
          <SummaryCard label="Lifetime Revenue" value={formatMoney(summary.lifetime_revenue)} />
        </div>
      )}

      <div className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex flex-wrap gap-2">
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search name, email, phone"
            className="rounded-xl border border-gray-200 bg-[#f8fafc] px-4 py-2 text-sm text-gray-700"
          />
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded-xl border border-gray-200 bg-[#f8fafc] px-4 py-2 text-sm text-gray-700"
          >
            <option value="">All Status</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="suspended">Blocked</option>
            <option value="pending_verification">Pending Verification</option>
          </select>
          <select
            value={verificationStatus}
            onChange={(e) => setVerificationStatus(e.target.value)}
            className="rounded-xl border border-gray-200 bg-[#f8fafc] px-4 py-2 text-sm text-gray-700"
          >
            <option value="">All Verification</option>
            <option value="verified">Verified</option>
            <option value="unverified">Unverified</option>
          </select>
          <select
            value={hasOrders}
            onChange={(e) => setHasOrders(e.target.value)}
            className="rounded-xl border border-gray-200 bg-[#f8fafc] px-4 py-2 text-sm text-gray-700"
          >
            <option value="">All Customers</option>
            <option value="yes">Has Orders</option>
            <option value="no">No Orders</option>
          </select>
          <select
            value={customerType}
            onChange={(e) => setCustomerType(e.target.value)}
            className="rounded-xl border border-gray-200 bg-[#f8fafc] px-4 py-2 text-sm text-gray-700"
          >
            <option value="">Customer Type</option>
            <option value="new">New</option>
            <option value="returning">Returning</option>
            <option value="inactive">Inactive</option>
            <option value="vip">VIP</option>
            <option value="wholesale">Wholesale</option>
          </select>
          <button
            type="button"
            onClick={clearFilters}
            className="rounded-xl bg-[#f8fafc] px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
          >
            Clear
          </button>
        </div>

        {loading ? (
          <div className="py-8 text-center text-gray-600">Loading customers...</div>
        ) : customers.length === 0 ? (
          <div className="py-12 text-center">
            <p className="text-gray-600 font-medium">No customers match your search.</p>
            <p className="text-sm text-gray-500">Try changing the filters or clear the search.</p>
            <div className="mt-4 flex justify-center gap-2">
              <button
                type="button"
                onClick={clearFilters}
                className="rounded-xl bg-[#f8fafc] px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100"
              >
                Clear Filters
              </button>
              <button
                type="button"
                className="rounded-xl bg-[#1e40af] px-4 py-2 text-sm font-medium text-white hover:bg-[#1e3a8a]"
              >
                Invite Customer
              </button>
            </div>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full text-left">
                <thead className="bg-[#f8fafc]">
                  <tr>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Customer</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Customer ID</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Email</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Phone</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Country</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Status</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Verified</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Joined</th>
                    <th className="px-4 py-3 text-sm font-medium text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {customers.map((c) => (
                    <tr key={c.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-3">
                          <div className="flex h-10 w-10 items-center justify-center rounded-full bg-[#dbeafe] text-sm font-semibold text-[#1e40af]">
                            {initials(c)}
                          </div>
                          <div>
                            <p className="text-sm font-medium text-[#111827]">
                              {c.first_name} {c.last_name}
                            </p>
                          </div>
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{c.id.slice(0, 12).toUpperCase()}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{c.email}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{c.phone ?? "-"}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">-</td>
                      <td className="px-4 py-3 text-sm">
                        <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${STATUS_BADGES[c.status] ?? "bg-gray-100 text-gray-600"}`}>
                          {c.status.replace("_", " ")}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">{c.is_verified ? "Yes" : "No"}</td>
                      <td className="px-4 py-3 text-sm text-gray-600">{new Date(c.created_at).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-sm">
                        <div className="flex flex-wrap gap-1">
                          <Link
                            href={`/admin/customers/${c.id}`}
                            className="rounded-lg bg-[#dbeafe] px-2.5 py-1.5 text-xs font-medium text-[#1e40af] hover:bg-[#bfdbfe]"
                          >
                            View Profile
                          </Link>
                          <button
                            type="button"
                            disabled={busyCustomerId === c.id}
                            onClick={() => void toggleCustomerStatus(c)}
                            className="rounded-lg bg-[#f8fafc] px-2.5 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                          >
                            {busyCustomerId === c.id ? "Updating..." : c.status === "suspended" ? "Reactivate" : "Suspend"}
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex items-center justify-between">
              <p className="text-sm text-gray-500">
                Showing {formatNumber((page - 1) * pageSize + 1)} - {formatNumber(Math.min(page * pageSize, total))} of {formatNumber(total)} customers
              </p>
              <div className="flex gap-2">
                <button
                  type="button"
                  disabled={page === 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  className="rounded-xl bg-[#f8fafc] px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  type="button"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => p + 1)}
                  className="rounded-xl bg-[#f8fafc] px-4 py-2 text-sm font-medium text-gray-700 hover:bg-gray-100 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
};

const SummaryCard = ({ label, value }: { label: string; value: string | number }) => (
  <div className="relative overflow-hidden rounded-2xl border border-cyan-100 bg-gradient-to-br from-white to-cyan-50 p-4 shadow-sm">
    <span className="absolute inset-x-0 top-0 h-1 bg-gradient-to-r from-cyan-500 to-blue-500" />
    <p className="text-xs font-medium uppercase tracking-wider text-gray-500">{label}</p>
    <p className="mt-2 text-xl font-semibold text-[#111827]">{value}</p>
  </div>
);

export default AdminCustomers;
