"use client";

import DashboardShell from "@/components/Dashboard/DashboardShell";
import RouteGuard from "@/guards/RouteGuard";

export default function DashboardClient() {
  return (
    <RouteGuard>
      <DashboardShell />
    </RouteGuard>
  );
}
