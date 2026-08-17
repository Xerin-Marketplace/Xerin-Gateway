"use client";

import { useSearchParams } from "next/navigation";
import AdminReports, { type ReportView } from "@/components/Admin/Reports";

const supportedReports = new Set<ReportView>([
  "sales",
  "orders",
  "products",
  "inventory",
  "customers",
  "payments",
]);

export default function AdminAnalytics() {
  const requested = useSearchParams().get("report") as ReportView | null;
  const report = requested && supportedReports.has(requested) ? requested : "sales";
  return <AdminReports view={report} />;
}
