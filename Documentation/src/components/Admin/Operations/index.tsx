"use client";

import { useMemo, useState } from "react";

type WorkspaceKey =
  | "payments"
  | "promotions"
  | "communications"
  | "user-management"
  | "reports"
  | "system"
  | "account";

type WorkspaceConfig = {
  eyebrow: string;
  title: string;
  description: string;
  primaryAction: string;
  metrics: Array<{ label: string; value: string; trend: string }>;
  stages: Array<{ title: string; description: string }>;
  columns: string[];
  rows: string[][];
};

const configs: Record<WorkspaceKey, WorkspaceConfig> = {
  payments: {
    eyebrow: "Revenue operations",
    title: "Payments",
    description: "Monitor transactions, investigate failures, and move refunds through a controlled review flow.",
    primaryAction: "Export transactions",
    metrics: [
      { label: "Processed today", value: "TZS 0", trend: "Live settlement total" },
      { label: "Successful", value: "0", trend: "Confirmed payments" },
      { label: "Pending", value: "0", trend: "Awaiting provider callback" },
      { label: "Failed", value: "0", trend: "Needs investigation" },
    ],
    stages: [
      { title: "Payment received", description: "Capture provider, order and payer references." },
      { title: "Verification", description: "Validate callback and reconcile the order total." },
      { title: "Settlement", description: "Confirm funds, commission and seller allocation." },
      { title: "Exception handling", description: "Retry, refund or escalate failed transactions." },
    ],
    columns: ["Reference", "Customer", "Method", "Amount", "Status"],
    rows: [],
  },
  promotions: {
    eyebrow: "Growth operations",
    title: "Promotions",
    description: "Plan coupons, discounts and campaigns with clear eligibility, budgets and activation windows.",
    primaryAction: "Create promotion",
    metrics: [
      { label: "Active campaigns", value: "0", trend: "Currently redeemable" },
      { label: "Scheduled", value: "0", trend: "Starts later" },
      { label: "Redemptions", value: "0", trend: "This month" },
      { label: "Discount cost", value: "TZS 0", trend: "This month" },
    ],
    stages: [
      { title: "Define offer", description: "Choose coupon, automatic discount or campaign." },
      { title: "Set eligibility", description: "Limit products, customers, dates and usage." },
      { title: "Review impact", description: "Confirm margin, budget and stacking rules." },
      { title: "Publish & measure", description: "Activate and monitor redemption performance." },
    ],
    columns: ["Promotion", "Type", "Validity", "Usage", "Status"],
    rows: [],
  },
  communications: {
    eyebrow: "Customer engagement",
    title: "Communications",
    description: "Create targeted email, SMS and in-app messages, then track delivery from one queue.",
    primaryAction: "Compose message",
    metrics: [
      { label: "Sent today", value: "0", trend: "All channels" },
      { label: "Delivered", value: "0", trend: "Provider confirmed" },
      { label: "Queued", value: "0", trend: "Waiting to send" },
      { label: "Failed", value: "0", trend: "Needs retry" },
    ],
    stages: [
      { title: "Select audience", description: "Choose customers, sellers or a saved segment." },
      { title: "Compose", description: "Prepare channel-specific subject and message." },
      { title: "Preview & approve", description: "Check variables, consent and delivery time." },
      { title: "Send & monitor", description: "Track queued, delivered and failed messages." },
    ],
    columns: ["Message", "Audience", "Channel", "Scheduled", "Delivery"],
    rows: [],
  },
  "user-management": {
    eyebrow: "Access governance",
    title: "User Management",
    description: "Administer staff accounts, roles, permissions and active sessions with a traceable approval flow.",
    primaryAction: "Invite admin user",
    metrics: [
      { label: "Admin users", value: "1", trend: "Active staff accounts" },
      { label: "Roles", value: "4", trend: "Configured access groups" },
      { label: "Permissions", value: "45", trend: "Available capabilities" },
      { label: "Active sessions", value: "1", trend: "Signed in now" },
    ],
    stages: [
      { title: "Create account", description: "Capture identity, role and contact details." },
      { title: "Assign access", description: "Apply least-privilege role and permissions." },
      { title: "Activate", description: "Send credentials and require password change." },
      { title: "Review", description: "Audit sessions and revoke stale access." },
    ],
    columns: ["User", "Role", "Permissions", "Last active", "Status"],
    rows: [["Super Admin", "Super admin", "45 permissions", "Current session", "Active"]],
  },
  reports: {
    eyebrow: "Business intelligence",
    title: "Reports & Analytics",
    description: "Turn sales, orders, products, inventory, customers and payments into decision-ready reports.",
    primaryAction: "Generate report",
    metrics: [
      { label: "Gross sales", value: "TZS 0", trend: "Selected period" },
      { label: "Orders", value: "0", trend: "Selected period" },
      { label: "Conversion", value: "0%", trend: "Sessions to orders" },
      { label: "Avg. order value", value: "TZS 0", trend: "Selected period" },
    ],
    stages: [
      { title: "Choose dataset", description: "Sales, orders, products, stock or customers." },
      { title: "Apply dimensions", description: "Set period, seller, category and status filters." },
      { title: "Review insights", description: "Compare totals, trends and exceptions." },
      { title: "Export or schedule", description: "Download now or deliver reports automatically." },
    ],
    columns: ["Report", "Period", "Owner", "Last generated", "Status"],
    rows: [],
  },
  system: {
    eyebrow: "Platform reliability",
    title: "System Management",
    description: "Observe audit events, background jobs and application settings without losing operational context.",
    primaryAction: "Open system check",
    metrics: [
      { label: "API status", value: "Online", trend: "Core service reachable" },
      { label: "Queued jobs", value: "0", trend: "Awaiting workers" },
      { label: "Failed jobs", value: "0", trend: "Last 24 hours" },
      { label: "Critical events", value: "0", trend: "Requires attention" },
    ],
    stages: [
      { title: "Observe", description: "Collect application events and health signals." },
      { title: "Triage", description: "Classify severity, owner and affected service." },
      { title: "Resolve", description: "Retry jobs or update controlled settings." },
      { title: "Audit", description: "Keep the actor, change and result history." },
    ],
    columns: ["Event", "Service", "Actor", "Time", "Severity"],
    rows: [["Admin workspace opened", "Web application", "Super Admin", "Now", "Info"]],
  },
  account: {
    eyebrow: "Personal workspace",
    title: "Account",
    description: "Manage your admin profile, security preferences and authenticated sessions.",
    primaryAction: "Edit profile",
    metrics: [
      { label: "Profile status", value: "Active", trend: "Verified account" },
      { label: "Security", value: "Password", trend: "Primary sign-in method" },
      { label: "Sessions", value: "1", trend: "Current browser" },
      { label: "Role", value: "Admin", trend: "Platform access" },
    ],
    stages: [
      { title: "Review profile", description: "Keep name, phone and email accurate." },
      { title: "Secure access", description: "Change password and review sessions." },
      { title: "Confirm changes", description: "Re-authenticate for sensitive updates." },
      { title: "Monitor activity", description: "Sign out sessions you do not recognize." },
    ],
    columns: ["Session", "Location", "Started", "Last active", "Status"],
    rows: [["Current browser", "Local development", "Today", "Now", "Active"]],
  },
};

export default function AdminOperationsWorkspace({ workspace }: { workspace: WorkspaceKey }) {
  const config = configs[workspace];
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState("all");
  const filteredRows = useMemo(
    () => config.rows.filter((row) => `${row.join(" ")}`.toLowerCase().includes(query.toLowerCase())),
    [config.rows, query]
  );

  return (
    <div className="space-y-5">
      <section className="overflow-hidden rounded-2xl bg-gradient-to-br from-[#111827] via-[#263244] to-[#f47524] p-6 text-white shadow-lg sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-white/60">{config.eyebrow}</p>
            <h2 className="mt-2 text-3xl font-semibold">{config.title}</h2>
            <p className="mt-3 text-sm leading-6 text-white/75 sm:text-base">{config.description}</p>
          </div>
          <button type="button" className="rounded-xl bg-white px-4 py-2.5 text-sm font-semibold text-[#111827] shadow-sm hover:bg-orange-50">
            {config.primaryAction}
          </button>
        </div>
      </section>

      <section className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {config.metrics.map((metric) => (
          <article key={metric.label} className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{metric.label}</p>
            <p className="mt-2 text-2xl font-semibold text-[#111827]">{metric.value}</p>
            <p className="mt-1 text-xs text-gray-400">{metric.trend}</p>
          </article>
        ))}
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-5">
          <h3 className="text-lg font-semibold text-[#111827]">Business flow</h3>
          <p className="mt-1 text-sm text-gray-500">A consistent path from intake to a measurable result.</p>
        </div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {config.stages.map((stage, index) => (
            <div key={stage.title} className="relative rounded-xl border border-gray-200 bg-[#f8fafc] p-4">
              <span className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-[#f47524] text-xs font-semibold text-white">{index + 1}</span>
              <h4 className="mt-3 font-semibold text-[#111827]">{stage.title}</h4>
              <p className="mt-1 text-sm leading-5 text-gray-500">{stage.description}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="rounded-2xl border border-gray-200 bg-white shadow-sm">
        <div className="flex flex-col gap-3 border-b border-gray-100 p-5 md:flex-row md:items-center md:justify-between">
          <div>
            <h3 className="text-lg font-semibold text-[#111827]">Operational queue</h3>
            <p className="text-sm text-gray-500">Search, review and action records from this workspace.</p>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row">
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${config.title.toLowerCase()}...`} className="rounded-xl border border-gray-200 bg-[#f8fafc] px-4 py-2.5 text-sm outline-none focus:border-[#f47524]" />
            <select value={status} onChange={(event) => setStatus(event.target.value)} className="rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-gray-600">
              <option value="all">All statuses</option>
              <option value="active">Active</option>
              <option value="pending">Pending</option>
              <option value="failed">Needs attention</option>
            </select>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-left">
            <thead className="bg-[#f8fafc] text-xs uppercase tracking-wide text-gray-500">
              <tr>{config.columns.map((column) => <th key={column} className="px-5 py-3 font-semibold">{column}</th>)}</tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {filteredRows.map((row, rowIndex) => (
                <tr key={`${row[0]}-${rowIndex}`} className="hover:bg-orange-50/40">
                  {row.map((cell, cellIndex) => <td key={`${cell}-${cellIndex}`} className="px-5 py-4 text-sm text-gray-600 first:font-medium first:text-[#111827]">{cell}</td>)}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {filteredRows.length === 0 ? (
          <div className="px-6 py-12 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-orange-50 text-xl">◎</div>
            <h4 className="mt-3 font-semibold text-[#111827]">No records in this queue</h4>
            <p className="mt-1 text-sm text-gray-500">New activity will appear here when the workflow is connected.</p>
          </div>
        ) : null}
      </section>
    </div>
  );
}
